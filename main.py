import sys
import os
import ctypes
from utils.path_helper import get_base_dir
from PIL import ImageGrab

# 设置 Windows DPI 感知 (需在创建 QApplication 之前调用)
try: 
    ctypes.windll.shcore.SetProcessDpiAwareness(1) # Process_System_DPI_Aware
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Fix Qt platform plugin error when running from a copied pythonw.exe
import PySide6
plugins_path = os.path.join(os.path.dirname(PySide6.__file__), 'plugins')
os.environ['QT_PLUGIN_PATH'] = plugins_path
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = os.path.join(plugins_path, 'platforms')

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from ui.floating_ball import FloatingBall
from ui.sub_ball import SubBall
from ui.panel import Panel
from system.tray import TrayIcon
from core.clipboard import ClipboardManager
from core.hotkey import HotkeyManager
from core.screenshot import get_all_visible_rects
from utils.config import load_hotkeys
from ui.notebook import NotebookPanel
from ui.screenshot_mask import ScreenshotMask
from ui.recording_border import RecordingBorder
from ui.search_box import SearchBoxPanel
from core.screen_recorder import ScreenRecorderThread
from core.notebook import NotebookManager
from utils.config import load_options, save_option
import sys
import math
import keyboard 
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor

class FloatingAssistant:
    def __init__(self):
        self.app = QApplication(sys.argv)
        
        # Set Application Name for Task Manager / Windows Grouping
        self.app.setApplicationName("\u684c\u9762\u4eba\u5076") # ????
        self.app.setApplicationDisplayName("\u684c\u9762\u4eba\u5076") # ????
        
        try:
            import ctypes
            myappid = 'shuwe.desktop.assistant.1.0' # arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass
        
        # Don't quit when last window is closed (important for tray/background apps)
        self.app.setQuitOnLastWindowClosed(False)

        import os
        from PySide6.QtGui import QIcon
        icon_path = os.path.join(get_base_dir(), "app_icon.ico")
        if os.path.exists(icon_path):
            self.app.setWindowIcon(QIcon(icon_path))

        # Initialize UI
        self.ball = FloatingBall()
        self.tray = TrayIcon()
        self.clipboard_mgr = ClipboardManager(max_items=20)
        self.hotkey_mgr = HotkeyManager(load_hotkeys())
        self.options = load_options()

        # Sub Balls
        self.sub_balls = []
        
        self.clipboard_ball = SubBall(self.ball, text="📋", radius=80, angle=0, tooltip="\u526a\u8d34\u677f\u5386\u53f2", bg_color=QColor(255, 165, 0, 230))
        self.sub_balls.append(self.clipboard_ball)

        self.screenshot_ball = SubBall(self.ball, text="✂️", radius=80, angle=0, tooltip="\u7cfb\u7edf\u622a\u56fe", bg_color=QColor(50, 200, 50, 230))
        self.sub_balls.append(self.screenshot_ball)

        self.notebook_ball = SubBall(self.ball, text="📝", radius=80, angle=0, tooltip="\u8bb0\u4e8b\u672c", bg_color=QColor(50, 150, 250, 230))
        self.sub_balls.append(self.notebook_ball)

        self.smart_screenshot_ball = SubBall(self.ball, text="🎯", radius=80, angle=0, tooltip="\u667a\u80fd\u622a\u56fe", bg_color=QColor(255, 69, 0, 230))
        self.sub_balls.append(self.smart_screenshot_ball)

        self.record_ball = SubBall(self.ball, text="🎥", radius=80, angle=0, tooltip="\u5f55\u5c4f", bg_color=QColor(255, 0, 0, 230))
        self.sub_balls.append(self.record_ball)

        self.search_ball = SubBall(self.ball, text="\U0001f50d", radius=80, angle=0, tooltip="\u641c\u7d22", bg_color=QColor(156, 39, 176, 230))
        self.sub_balls.append(self.search_ball)

        # --- Load custom apps ---
        custom_apps = self.options.get("custom_apps", [])
        from PySide6.QtWidgets import QFileIconProvider
        from PySide6.QtCore import QFileInfo
        for app in custom_apps:
            if not app.get('enabled', True):
                continue
            icon = QFileIconProvider().icon(QFileInfo(app["path"]))
            ball = SubBall(self.ball, text="", radius=80, angle=0, tooltip=app["name"], bg_color=QColor(100, 100, 100, 230), icon=icon)
            ball.custom_app_path = app["path"]
            ball.clicked.connect(lambda p=app["path"]: os.startfile(p) if hasattr(os, "startfile") else None)
            self.sub_balls.append(ball)
            
        # Assign angles and radii (concentric layout)
        self._update_balls_layout()
            
        self.notebook_mgr = NotebookManager()
        self.notebook_panel = NotebookPanel()
        self.panel = Panel()
        self.is_recording = False
        self.video_save_path = self.options.get("video_save_path", "")
        if not self.video_save_path:
            import os
            self.video_save_path = os.path.join(get_base_dir(), "video")
            self.options["video_save_path"] = self.video_save_path
        
        self.notebook_panel.set_main_ball(self.ball)
        self.search_panel = SearchBoxPanel()
        self.search_panel.set_main_ball(self.ball)
        self.search_panel.search_requested.connect(self.perform_web_search)
        self.notebook_panel.set_content(self.notebook_mgr.content)
        
        self.settings_dialog = None

        # Connections - Main Ball
        self.ball.clicked.connect(self.toggle_sub_balls)
        self.ball.right_clicked.connect(self.show_ball_menu)
        self.ball.position_changed.connect(self.on_ball_moved)
        
        # Connections - Sub Ball
        self.clipboard_ball.clicked.connect(self.on_clipboard_ball_clicked)
        self.clipboard_ball.position_changed.connect(self.on_clipboard_ball_moved)
        self.screenshot_ball.clicked.connect(self.on_screenshot_ball_clicked)
        self.record_ball.clicked.connect(self.on_record_ball_clicked)
        self.search_ball.clicked.connect(self.on_search_ball_clicked)
        self.search_ball.position_changed.connect(self.on_search_ball_moved)
        self.smart_screenshot_ball.clicked.connect(self.on_smart_screenshot_clicked)
        self.notebook_ball.clicked.connect(self.on_notebook_ball_clicked)
        self.notebook_ball.position_changed.connect(self.on_notebook_ball_moved)

        # Connections - System
        self.tray.quit_requested.connect(self.quit_app)
        self.tray.about_requested.connect(self.show_about)
        self.tray.toggle_requested.connect(self.toggle_main_ball)
        self.tray.settings_requested.connect(self.prompt_settings)
        self.tray.toggle_hide_ball_when_screenshot_requested.connect(self.toggle_hide_ball_when_screenshot)
        self.tray.change_clipboard_max_items_requested.connect(self.set_clipboard_max_items)
        self.tray.toggle_clipboard_tracking_requested.connect(self.toggle_clipboard_tracking)
        self.tray.change_video_path_requested.connect(self.set_video_save_path)
        self.panel.toggle_text_tracking_clicked.connect(self.toggle_record_text)
        self.panel.toggle_image_tracking_clicked.connect(self.toggle_record_image)
        
        # Connections - Clipboard
        self.clipboard_mgr.history_changed.connect(self.panel.update_history)
        self.panel.item_clicked.connect(self.clipboard_mgr.copy_to_clipboard)
        self.panel.item_deleted.connect(self.clipboard_mgr.remove_item)
        self.panel.history_cleared.connect(self.clipboard_mgr.clear_history)
        self.panel.history_reordered.connect(self.clipboard_mgr.set_history)
        self.panel.toggle_tracking_clicked.connect(self.toggle_clipboard_tracking)
        self.notebook_panel.content_changed.connect(self.notebook_mgr.update_content)
        self.hotkey_mgr.action_triggered.connect(self.on_action_triggered)
        
        # Initialize panel with loaded history
        self.panel.update_history(self.clipboard_mgr.get_history())

        # Initial show
        self.ball.move_to_bottom_right()
        self.ball.show()
        self.tray.show()
        self.tray.set_hide_ball_when_screenshot(self.options.get("hide_ball_when_screenshot", True))
        self.tray.set_clipboard_tracking_enabled(self.options.get("clipboard_tracking_enabled", True))
        self.tray.set_clipboard_max_items(self.options.get("clipboard_max_items", 20))
        self.clipboard_mgr.record_text = self.options.get('record_text', True)
        self.clipboard_mgr.record_image = self.options.get('record_image', True)
        self.panel.set_content_tracking_states(self.clipboard_mgr.record_text, self.clipboard_mgr.record_image)
        self.clipboard_mgr.max_items = self.options.get("clipboard_max_items", 20)
        self.clipboard_mgr.max_images = self.options.get("clipboard_max_images", 20)
        
        # Apply picture path
        pic_path = self.options.get("picture_save_path", "")
        if not pic_path:
            import os
            pic_path = os.path.join(get_base_dir(), "picture")
            self.options["picture_save_path"] = pic_path
        self.clipboard_mgr.picture_save_path = pic_path
        
        self.clipboard_mgr.tracking_enabled = self.options.get("clipboard_tracking_enabled", True)
        self.panel.set_tracking_enabled(self.options.get("clipboard_tracking_enabled", True))

    def _update_balls_layout(self):
        # Concentric circles layout algorithm
        total_balls = len(self.sub_balls)
        import math
        # 初始内圈半径设置紧凑（主球半径30 + 子球半径18 + 间隙）= 55
        current_circle_radius = 55
        balls_placed = 0
        
        while balls_placed < total_balls:
            # Calculate max balls that can fit in the current circle
            # Assuming ball diameter + gap = ~45 pixels
            max_in_circle = max(1, int(2 * math.pi * current_circle_radius / 45))
            balls_in_this_circle = min(max_in_circle, total_balls - balls_placed)
            
            for i in range(balls_in_this_circle):
                b = self.sub_balls[balls_placed + i]
                b.default_radius = current_circle_radius
                b.radius = b.default_radius
                b.default_angle = math.pi * 2 * (i / balls_in_this_circle)
                b.angle = b.default_angle
                b.siblings = [sib for sib in self.sub_balls if sib != b]
                
            balls_placed += balls_in_this_circle
            # 每多一圈向外扩展 45 像素
            current_circle_radius += 45

    def toggle_sub_balls(self):
        # When main ball is clicked, show/hide the surrounding sub balls
        any_visible = any(sb.isVisible() for sb in self.sub_balls)
        if any_visible:
            # Hide all sub balls and panels
            for sb in self.sub_balls:
                sb.hide()
            self.panel.hide()
            self.notebook_panel.hide()
            self.search_panel.hide()
        else:
            # Show all sub balls based on options
            if self.options.get("enable_clipboard_ball", True):
                self.clipboard_ball.update_position_from_main()
                self.clipboard_ball.show()
            if self.options.get("enable_screenshot_ball", True):
                self.screenshot_ball.update_position_from_main()
                self.screenshot_ball.show()
            if self.options.get("enable_notebook_ball", True):
                self.notebook_ball.update_position_from_main()
                self.notebook_ball.show()
            if self.options.get("enable_smart_screenshot_ball", True):
                self.smart_screenshot_ball.update_position_from_main()
                self.smart_screenshot_ball.show()
            if self.options.get("enable_record_ball", True):
                self.record_ball.update_position_from_main()
                self.record_ball.show()
            if self.options.get("enable_search_ball", True):
                self.search_ball.update_position_from_main()
                self.search_ball.show()
            
            for sb in self.sub_balls:
                if hasattr(sb, 'custom_app_path'):
                    sb.update_position_from_main()
                    sb.show()

    def on_ball_moved(self, x, y):
        # Update positions of all visible sub-balls to maintain their orbit/distance
        for sb in self.sub_balls:
            if sb.isVisible():
                sb.update_position_from_main()

    def show_ball_menu(self):
        from PySide6.QtGui import QCursor
        self.tray.menu.exec(QCursor.pos())
                
    def on_clipboard_ball_clicked(self):
        # Clean missing files before showing
        self.clipboard_mgr.clean_missing_files()
        # Toggle clipboard panel near the sub-ball
        ball_pos = self.clipboard_ball.geometry()
        self.panel.toggle_visibility(ball_pos.x(), ball_pos.y())

    def on_clipboard_ball_moved(self, x, y):
        # If panel is visible, keep it positioned relative to the sub-ball
        if self.panel.isVisible():
            self.panel.update_position(x, y)

    def on_notebook_ball_clicked(self):
        ball_pos = self.notebook_ball.geometry()
        self.notebook_panel.toggle_visibility(ball_pos.x(), ball_pos.y())

    def on_notebook_ball_moved(self, x, y):
        if self.notebook_panel.isVisible():
            self.notebook_panel.update_position(x, y)

    def on_screenshot_ball_clicked(self):
        self._trigger_system_screenshot()

    

    def on_search_ball_clicked(self):
        ball_pos = self.search_ball.geometry()
        self.search_panel.toggle_visibility(ball_pos.x(), ball_pos.y())

    def on_search_ball_moved(self, x, y):
        if self.search_panel.isVisible():
            self.search_panel.update_position(x, y)

    def perform_web_search(self, query):
        import urllib.parse
        import webbrowser
        
        # Use Bing as default search engine
        search_url = "https://www.bing.com/search?q=" + urllib.parse.quote(query)
        webbrowser.open(search_url)

    def on_record_ball_clicked(self):
        if self.is_recording:
            # Stop recording
            self.stop_recording()
        else:
            # Start selection
            if hasattr(self, 'screenshot_mask') and self.screenshot_mask is not None:
                return
            self._hide_balls_for_screenshot()
            self.screenshot_mask = ScreenshotMask(mode="record")
            self.screenshot_mask.rect_selected.connect(self._on_record_rect_selected)
            self.screenshot_mask.finished.connect(self._on_screenshot_finished)
            self.screenshot_mask.show()
            
    def _on_record_rect_selected(self, rect):
        self._restore_balls_after_screenshot()
        # Show border with countdown
        self.recording_border = RecordingBorder(rect)
        self.recording_border.countdown_finished.connect(lambda: self.start_actual_recording(rect))
        self.recording_border.show()
        
    def start_actual_recording(self, rect):
        self.is_recording = True
        from PySide6.QtGui import QColor
        self.record_ball.bg_color = QColor(50, 200, 50, 230) # Green indicating recording
        self.record_ball.update()
        self.recorder_thread = ScreenRecorderThread(rect, self.video_save_path)
        self.recorder_thread.finished_recording.connect(self._on_recording_saved)
        self.recorder_thread.error_occurred.connect(self._on_recording_error)
        self.recorder_thread.start()
        
    def stop_recording(self):
        if self.recorder_thread:
            self.recorder_thread.stop()
        self.is_recording = False
        from PySide6.QtGui import QColor
        self.record_ball.bg_color = QColor(255, 0, 0, 230) # Back to Red
        self.record_ball.update()
        if self.recording_border:
            self.recording_border.hide()
            self.recording_border = None
            
    def _on_recording_saved(self, path):
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtCore import QTimer
        # Show success toast or message, no blocking
        msg = QMessageBox(self.ball)
        msg.setWindowTitle("\u5f55\u5c4f\u5b8c\u6210") # 录屏完成
        msg.setText(f"\u89c6\u9891\u5df2\u4fdd\u5b58\u81f3:\n{path}")
        msg.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        msg.show()
        QTimer.singleShot(3000, msg.close)
        
    def _on_recording_error(self, err):
        self.stop_recording()
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(None, "\u5f55\u5c4f\u9519\u8bef", err) # 录屏错误

    def on_smart_screenshot_clicked(self, background_image=None, pre_captured_rects=None):
        if hasattr(self, 'screenshot_mask'):
            return 

        all_rects_global = None
        virtual_left = 0
        virtual_top = 0
        try:
            import win32api
            import win32con
            if background_image is None:
                background_image = ImageGrab.grab(all_screens=True)
            if pre_captured_rects is not None:
                all_rects_global = pre_captured_rects
            else:
                all_rects_global = get_all_visible_rects()
            virtual_left = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
            virtual_top = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
        except Exception:
            background_image = None
            all_rects_global = None

        self._hide_balls_for_screenshot()
        self.screenshot_mask = ScreenshotMask(
            background_image=background_image,
            all_rects_global=all_rects_global,
            virtual_screen_left=virtual_left,
            virtual_screen_top=virtual_top,
        )
        self.screenshot_mask.finished.connect(self._on_screenshot_finished)
        self.screenshot_mask.show()
        
    def _on_screenshot_finished(self):
        self._restore_balls_after_screenshot()
        if hasattr(self, 'screenshot_mask'):
            del self.screenshot_mask

    def _hide_balls_for_screenshot(self):
        if not self.options.get("hide_ball_when_screenshot", True):
            return
        self._were_sub_balls_visible = any(sb.isVisible() for sb in self.sub_balls)
        self.ball.hide()
        for sb in self.sub_balls:
            sb.hide()

    def _restore_balls_after_screenshot(self):
        if not self.options.get("hide_ball_when_screenshot", True):
            return
        self.ball.show()
        if getattr(self, '_were_sub_balls_visible', False):
            if self.options.get("enable_clipboard_ball", True):
                self.clipboard_ball.reset_position()
                self.clipboard_ball.show()
            if self.options.get("enable_screenshot_ball", True):
                self.screenshot_ball.reset_position()
                self.screenshot_ball.show()
            if self.options.get("enable_notebook_ball", True):
                self.notebook_ball.reset_position()
                self.notebook_ball.show()
            if self.options.get("enable_smart_screenshot_ball", True):
                self.smart_screenshot_ball.reset_position()
                self.smart_screenshot_ball.show()
            if self.options.get("enable_record_ball", True):
                self.record_ball.reset_position()
                self.record_ball.show()
            if self.options.get("enable_search_ball", True):
                self.search_ball.reset_position()
                self.search_ball.show()

            for sb in self.sub_balls:
                if hasattr(sb, 'custom_app_path'):
                    sb.reset_position()
                    sb.show()

    def toggle_hide_ball_when_screenshot(self):
        current = self.options.get("hide_ball_when_screenshot", True)
        self.options["hide_ball_when_screenshot"] = not current
        save_option("hide_ball_when_screenshot", self.options["hide_ball_when_screenshot"])
        self.tray.set_hide_ball_when_screenshot(self.options["hide_ball_when_screenshot"])

    def set_clipboard_max_items(self, value):
        self.options["clipboard_max_items"] = int(value)
        save_option("clipboard_max_items", self.options["clipboard_max_items"])
        self.clipboard_mgr.max_items = self.options["clipboard_max_items"]
        self.tray.set_clipboard_max_items(self.options["clipboard_max_items"])
        self.clipboard_mgr.history = self.clipboard_mgr.get_history()[: self.clipboard_mgr.max_items]
        self.clipboard_mgr.history_changed.emit(self.clipboard_mgr.history)

    def set_video_save_path(self, path):
        self.video_save_path = path
        self.options["video_save_path"] = path
        save_option("video_save_path", path)
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(None, "\u63d0\u793a", f"\u5df2\u4fee\u6539\u5f55\u5c4f\u4fdd\u5b58\u8def\u5f84\u4e3a:\n{path}")
        
    def toggle_clipboard_tracking(self):
        current = self.options.get("clipboard_tracking_enabled", True)
        self.options["clipboard_tracking_enabled"] = not current
        save_option("clipboard_tracking_enabled", self.options["clipboard_tracking_enabled"])
        self.clipboard_mgr.tracking_enabled = self.options["clipboard_tracking_enabled"]
        self.panel.set_tracking_enabled(self.options["clipboard_tracking_enabled"])

    def toggle_record_text(self):
        current = self.options.get("record_text", True)
        new_val = not current
        self.options["record_text"] = new_val
        save_option("record_text", new_val)
        self.clipboard_mgr.record_text = new_val
        self.panel.set_content_tracking_states(new_val, self.options.get("record_image", True))

    def toggle_record_image(self):
        current = self.options.get("record_image", True)
        new_val = not current
        self.options["record_image"] = new_val
        save_option("record_image", new_val)
        self.clipboard_mgr.record_image = new_val
        self.panel.set_content_tracking_states(self.options.get("record_text", True), new_val)
        
    def _trigger_system_screenshot(self):
        # 释放所有可能的修饰键（避免组合键冲突，如 win+shift+s 触发失败）
        self._hide_balls_for_screenshot()
        for k in ['ctrl', 'shift', 'alt', 'windows', 'left windows', 'right windows']:
            try:
                keyboard.release(k)
            except ValueError:
                pass
                
        keyboard.send("win+shift+s")
        QTimer.singleShot(1200, self._restore_balls_after_screenshot)

    def toggle_main_ball(self):
        if self.ball.isVisible():
            self.ball.hide()
            for sb in self.sub_balls:
                sb.hide()
            self.panel.hide()
            self.notebook_panel.hide()
            self.search_panel.hide()
        else:
            self.ball.show()

    def prompt_settings(self):
        from ui.settings import SettingsDialog
        
        if self.settings_dialog is not None and self.settings_dialog.isVisible():
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()
            return
            
        self.settings_dialog = SettingsDialog(self.options, self.hotkey_mgr)
        self.settings_dialog.settings_saved.connect(self.apply_settings)
        self.settings_dialog.show()
        
    def apply_settings(self, new_options):
        self.options = new_options
        self.tray.set_hide_ball_when_screenshot(self.options.get("hide_ball_when_screenshot", True))
        self.tray.set_clipboard_tracking_enabled(self.options.get("clipboard_tracking_enabled", True))
        self.tray.set_clipboard_max_items(self.options.get("clipboard_max_items", 20))
        # Apply clipboard
        self.clipboard_mgr.max_items = self.options.get("clipboard_max_items", 20)
        self.clipboard_mgr.tracking_enabled = self.options.get("clipboard_tracking_enabled", True)
        self.panel.set_tracking_enabled(self.clipboard_mgr.tracking_enabled)
        # Apply video path
        self.video_save_path = self.options.get("video_save_path", "")
        
        # Apply picture path
        pic_path = self.options.get("picture_save_path", "")
        if not pic_path:
            import os
            pic_path = os.path.join(get_base_dir(), "picture")
            self.options["picture_save_path"] = pic_path
        self.clipboard_mgr.picture_save_path = pic_path
        self.clipboard_mgr.max_images = self.options.get("clipboard_max_images", 20)
        if not self.video_save_path:
            import os
            self.video_save_path = os.path.join(get_base_dir(), "video")
            self.options["video_save_path"] = self.video_save_path
        # Apply UI refresh if needed
        self.clipboard_mgr.history = self.clipboard_mgr.get_history()[: self.clipboard_mgr.max_items]
        self.clipboard_mgr.history_changed.emit(self.clipboard_mgr.history)
        
        # Delete old custom balls
        old_custom_balls = [sb for sb in self.sub_balls if hasattr(sb, 'custom_app_path')]
        for sb in old_custom_balls:
            if sb.isVisible():
                sb.hide()
            self.sub_balls.remove(sb)
            sb.deleteLater()

        # Create new custom balls
        custom_apps = self.options.get("custom_apps", [])
        from PySide6.QtWidgets import QFileIconProvider
        from PySide6.QtCore import QFileInfo
        import math
        import os
        for app in custom_apps:
            if not app.get('enabled', True):
                continue
            icon = QFileIconProvider().icon(QFileInfo(app["path"]))
            ball = SubBall(self.ball, text="", radius=80, angle=0, tooltip=app["name"], bg_color=QColor(100, 100, 100, 230), icon=icon)
            ball.custom_app_path = app["path"]
            ball.clicked.connect(lambda p=app["path"]: os.startfile(p) if hasattr(os, "startfile") else None)
            self.sub_balls.append(ball)

        # Reassign angles
        self._update_balls_layout()

        # Synchronize sub-balls visibility dynamically if the menu is currently expanded
        # If at least one ball is visible, we consider the menu "expanded"
        any_visible = any(sb.isVisible() for sb in self.sub_balls)
        
        # However, what if ALL balls were just disabled? We might want to track a state `self._menu_expanded`
        # But since we don't have it, we check if they were visible before this update.
        if any_visible:
            if self.options.get("enable_clipboard_ball", True):
                self.clipboard_ball.reset_position()
                self.clipboard_ball.show()
            else:
                self.clipboard_ball.hide()
                self.panel.hide()
                
            if self.options.get("enable_screenshot_ball", True):
                self.screenshot_ball.reset_position()
                self.screenshot_ball.show()
            else:
                self.screenshot_ball.hide()
                
            if self.options.get("enable_notebook_ball", True):
                self.notebook_ball.reset_position()
                self.notebook_ball.show()
            else:
                self.notebook_ball.hide()
                self.notebook_panel.hide()
                
            if self.options.get("enable_smart_screenshot_ball", True):
                self.smart_screenshot_ball.reset_position()
                self.smart_screenshot_ball.show()
            else:
                self.smart_screenshot_ball.hide()
                
            if self.options.get("enable_record_ball", True):
                self.record_ball.reset_position()
                self.record_ball.show()
            else:
                self.record_ball.hide()
                
            if self.options.get("enable_search_ball", True):
                self.search_ball.reset_position()
                self.search_ball.show()
            else:
                self.search_ball.hide()
                self.search_panel.hide()

            for sb in self.sub_balls:
                if hasattr(sb, 'custom_app_path'):
                    sb.reset_position()
                    sb.show()
                
    def on_action_triggered(self, action_name, payload_img=None, payload_rects=None):
        if action_name == "clipboard":
            self.clipboard_mgr.clean_missing_files()
            # Open panel relative to current cursor position
            from PySide6.QtGui import QCursor
            cursor_pos = QCursor.pos()
            self.panel.toggle_visibility(cursor_pos.x(), cursor_pos.y())
        elif action_name == "screenshot":
            self.on_screenshot_ball_clicked()
        elif action_name == "smart_screenshot":
            self.on_smart_screenshot_clicked(background_image=payload_img, pre_captured_rects=payload_rects)
        elif action_name == "notebook":
            self.on_notebook_ball_clicked()
        elif action_name == "toggle_ball":
            self.toggle_main_ball()
        elif action_name == "record":
            self.on_record_ball_clicked()
        elif action_name == "search":
            self.on_search_ball_clicked()

    
    def show_about(self):
        from PySide6.QtWidgets import QMessageBox
        msg = QMessageBox(self.ball)
        msg.setWindowTitle("\u5173\u4e8e") # 关于
        msg.setText("\u4f5c\u8005\uff1aWikex\u4f2a\u5915\n\u8c37\u6b4c\u90ae\u7bb1\uff1ashuweixing295@gmail.com\nQQ\u90ae\u7bb1\uff1a2110575127@qq.com") # 作者信息
        msg.setStyleSheet("QMessageBox { background-color: #ffffff; color: #000000; } QLabel { color: #000000; font-size: 14px; font-weight: bold; } QPushButton { color: #000000; padding: 5px 15px; }")
        msg.exec()

    def quit_app(self):
        self.tray.hide()
        self.app.quit()

    def run(self):
        return self.app.exec()

if __name__ == "__main__":
    import win32api
    import win32event
    import winerror
    mutex_name = "DesktopAssistantUniqueMutex_1_0"
    mutex = win32event.CreateMutex(None, 1, mutex_name)
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, "桌面人偶已经在运行中。", "提示", 0x30)
        sys.exit(0)

    assistant = FloatingAssistant()
    sys.exit(assistant.run())





