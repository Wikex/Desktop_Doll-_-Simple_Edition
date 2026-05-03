import os
import time
import mss
import cv2
import numpy as np
from datetime import datetime
from PySide6.QtCore import QThread, Signal, QRect
import win32api
import win32con

class ScreenRecorderThread(QThread):
    finished_recording = Signal(str)
    error_occurred = Signal(str)
    
    def __init__(self, rect: QRect, save_dir: str):
        super().__init__()
        self.rect = rect
        self.save_dir = save_dir
        self._running = False
        
    def stop(self):
        self._running = False
        
    def run(self):
        self._running = True
        try:
            if not os.path.exists(self.save_dir):
                os.makedirs(self.save_dir, exist_ok=True)
                
            filename = datetime.now().strftime("录屏_%Y%m%d_%H%M%S.mp4")
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
                
            monitor = {
                "left": left,
                "top": top,
                "width": width,
                "height": height
            }
            
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            fps = 20.0
            out = cv2.VideoWriter(filepath, fourcc, fps, (width, height))
            
            if not out.isOpened():
                self.error_occurred.emit("无法初始化视频写入器")
                return
                
            sct = mss.mss()
            frame_time = 1.0 / fps
            
            while self._running:
                start_time = time.time()
                
                sct_img = sct.grab(monitor)
                img = np.array(sct_img)
                # Convert BGRA to BGR
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                out.write(img)
                
                elapsed = time.time() - start_time
                sleep_time = frame_time - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
            out.release()
            self.finished_recording.emit(filepath)
            
        except Exception as e:
            self.error_occurred.emit(str(e))
