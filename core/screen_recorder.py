import os
import time
import mss
import cv2
import numpy as np
from datetime import datetime
from PySide6.QtCore import QThread, Signal, QRect
import win32api
import win32con
from utils.logger import log_exception

class ScreenRecorderThread(QThread):
    finished_recording = Signal(str)
    error_occurred = Signal(str)
    
    def __init__(self, rect: QRect, save_dir: str, save_format: str = "mp4"):
        super().__init__()
        self.rect = rect
        self.save_dir = save_dir
        self.save_format = save_format.lower()
        self._running = False
        
    def stop(self):
        self._running = False
        
    def run(self):
        self._running = True
        out = None
        filepath = ""
        error_message = ""
        completed = False
        try:
            if not os.path.exists(self.save_dir):
                os.makedirs(self.save_dir, exist_ok=True)
                
            ext = self.save_format
            if ext not in ["mp4", "webm"]:
                ext = "mp4"
                
            filename = datetime.now().strftime(f"录屏_%Y%m%d_%H%M%S.{ext}")
            filepath = os.path.join(self.save_dir, filename)
            
            v_left = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
            v_top = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
            
            # self.rect is in global physical coordinates
            left = self.rect.x() - v_left
            top = self.rect.y() - v_top
            width = self.rect.width()
            height = self.rect.height()
            
            # Ensure even dimensions for cv2
            if width % 2 != 0:
                width -= 1
            if height % 2 != 0:
                height -= 1

            if width < 10 or height < 10:
                error_message = "录屏区域过小，请选择至少 10 x 10 像素的区域"
                return
                
            monitor = {
                "left": left,
                "top": top,
                "width": width,
                "height": height
            }
            
            if ext == "webm":
                fourcc = cv2.VideoWriter_fourcc(*'VP80')
                fps = 60.0
                out = cv2.VideoWriter(filepath, fourcc, fps, (width, height))
            else:
                # Try H264 via Media Foundation backend
                fourcc = cv2.VideoWriter_fourcc(*'H264')
                fps = 60.0
                out = cv2.VideoWriter(filepath, cv2.CAP_MSMF, fourcc, fps, (width, height))
                
                # Fallback to standard MP4v if H264 fails to initialize
                if not out.isOpened():
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                    out = cv2.VideoWriter(filepath, fourcc, fps, (width, height))
            
            if not out.isOpened():
                error_message = "无法初始化视频写入器"
                return
                
            sct = mss.mss()
            frame_time = 1.0 / fps
            last_valid_img = None
            
            while self._running:
                start_time = time.time()
                
                try:
                    sct_img = sct.grab(monitor)
                    img = np.array(sct_img)
                    # Convert BGRA to BGR
                    img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                    last_valid_img = img
                except mss.exception.ScreenShotError:
                    # BitBlt fails when an administrator window (like Everything) is in the foreground due to UIPI
                    if last_valid_img is not None:
                        img = last_valid_img
                    else:
                        img = np.zeros((height, width, 3), dtype=np.uint8)
                except Exception as e:
                    log_exception(f"Frame grab failed: {e}")
                    if last_valid_img is not None:
                        img = last_valid_img
                    else:
                        img = np.zeros((height, width, 3), dtype=np.uint8)
                        
                out.write(img)
                
                elapsed = time.time() - start_time
                sleep_time = frame_time - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
            completed = True

        except Exception as e:
            error_message = str(e)
            log_exception(f"Screen recording failed: {e}")
        finally:
            if out is not None:
                out.release()
            if error_message:
                self.error_occurred.emit(error_message)
            elif completed and filepath:
                self.finished_recording.emit(filepath)
