import sys
import os
import ctypes
import subprocess
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

from actions.clipboard_actions import first_url, open_image_location
from actions.record_actions import is_record_rect_valid, record_rect_error_message
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
from ui.screenshot_editor import ScreenshotEditor
from ui.recording_border import RecordingBorder
from core.screen_recorder import ScreenRecorderThread
from core.notebook import NotebookManager
from utils.config import load_options, save_option
from utils.logger import log_exception, log_message
from core.recent import RecentManager
from core.skin_manager import SkinManager
from ui.recent_panel import RecentPanel
import sys
import math
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor

class FloatingAssistant:
    def __init__(self):
        self.app = QApplication(sys.argv)
        
        # Set Application Name for Task Manager / Windows Grouping
        self.app.setApplicationName("\u684c\u9762\u4eba\u5076") # ????
        self.app.setApplicationDisplayName("\u684c\u9762\u4eba\u5076") # ????
        
        # 强制设置全局的 QMessageBox 样式，防止在某些系统的深色模式下出现白底白字的问题
        self.app.setStyleSheet("""
            QMessageBox { background-color: #ffffff; }
            QMessageBox QLabel { color: #000000; font-size: 13px; }
            QMessageBox QPushButton { color: #000000; background-color: #f8fafc; border: 1px solid #cbd5e1; padding: 6px 16px; border-radius: 4px; }
            QMessageBox QPushButton:hover { background-color: #e2e8f0; }
        """)
        
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

        self.options = load_options()
        self.skin_mgr = SkinManager()
        self.skin_config = self.skin_mgr.get_skin_config()

        # Initialize UI
        self.ball = FloatingBall(skin_config=self.skin_config)
        self.tray = TrayIcon()
        self.clipboard_mgr = ClipboardManager(max_items=self.options.get("clipboard_max_items", 20))
        self.hotkey_mgr = HotkeyManager(self.app, load_hotkeys())

        # Sub Balls
        self.sub_balls = []
        
        self.clipboard_ball = SubBall(self.ball, text="📋", radius=80, angle=0, tooltip="\u526a\u8d34\u677f\u5386\u53f2", bg_color=self._sub_ball_color("clipboard", QColor(255, 165, 0, 230)), skin_config=self.skin_config)
        self.sub_balls.append(self.clipboard_ball)

        self.notebook_ball = SubBall(self.ball, text="📝", radius=80, angle=0, tooltip="\u8bb0\u4e8b\u672c", bg_color=self._sub_ball_color("notebook", QColor(50, 150, 250, 230)), skin_config=self.skin_config)
        self.sub_balls.append(self.notebook_ball)

        self.smart_screenshot_ball = SubBall(self.ball, text="🎯", radius=80, angle=0, tooltip="\u667a\u80fd\u622a\u56fe", bg_color=self._sub_ball_color("smart_screenshot", QColor(255, 69, 0, 230)), skin_config=self.skin_config)
        self.sub_balls.append(self.smart_screenshot_ball)

        self.advanced_screenshot_ball = SubBall(self.ball, text="✏️", radius=80, angle=0, tooltip="进阶截图", bg_color=self._sub_ball_color("advanced_screenshot", QColor(124, 58, 237, 230)), skin_config=self.skin_config)
        self.sub_balls.append(self.advanced_screenshot_ball)

        self.record_ball = SubBall(self.ball, text="🎥", radius=80, angle=0, tooltip="\u5f55\u5c4f", bg_color=self._sub_ball_color("record", QColor(255, 0, 0, 230)), skin_config=self.skin_config)
        self.sub_balls.append(self.record_ball)

        self.recent_ball = SubBall(self.ball, text="🕘", radius=80, angle=0, tooltip="最近使用", bg_color=self._sub_ball_color("recent", QColor(0, 150, 136, 230)), skin_config=self.skin_config)
        self.sub_balls.append(self.recent_ball)

        # --- Load custom apps ---
        custom_apps = self.options.get("custom_apps", [])
        from PySide6.QtWidgets import QFileIconProvider
        from PySide6.QtCore import QFileInfo
        for app in custom_apps:
            if not app.get('enabled', True):
                continue
            icon = QFileIconProvider().icon(QFileInfo(app["path"]))
            ball = SubBall(self.ball, text="", radius=80, angle=0, tooltip=app["name"], bg_color=self._sub_ball_color("custom", QColor(100, 100, 100, 230)), icon=icon, skin_config=self.skin_config)
            ball.custom_app_path = app["path"]
            ball.clicked.connect(lambda p=app["path"]: os.startfile(p) if hasattr(os, "startfile") else None)
            self.sub_balls.append(ball)
            
        # Assign angles and radii (concentric layout)
        self._update_balls_layout()
            
        self.notebook_mgr = NotebookManager()
        self.notebook_panel = NotebookPanel()
        self.recent_mgr = RecentManager()
        self.recent_panel = RecentPanel(skin_config=self.skin_config)
        self.panel = Panel(skin_config=self.skin_config)
        self.is_recording = False
        self.recorder_thread = None
        self.recording_border = None
        self.screenshot_editors = []
        self._screenshot_hidden_state = None
        self.video_save_path = self.options.get("video_save_path", "")
        import os
        if self.video_save_path and not os.path.exists(self.video_save_path):
            self.video_save_path = ""
            
        if not self.video_save_path:
            self.video_save_path = os.path.join(get_base_dir(), "video")
            self.options["video_save_path"] = self.video_save_path
            save_option("video_save_path", self.video_save_path)
            
        if not os.path.exists(self.video_save_path):
            try:
                os.makedirs(self.video_save_path)
            except Exception as e:
                log_exception(f"Failed to create video directory: {e}")
        
        self.notebook_panel.set_main_ball(self.ball)
        self.recent_panel.set_main_ball(self.ball)
        self.notebook_panel.set_content(self.notebook_mgr.content)
        
        self.settings_dialog = None

        # Connections - Main Ball
        self.ball.clicked.connect(self.toggle_sub_balls)
        self.ball.right_clicked.connect(self.show_ball_menu)
        self.ball.position_changed.connect(self.on_ball_moved)
        self.ball.edge_hidden_changed.connect(self.on_ball_edge_hidden_changed)
        
        # Connections - Sub Ball
        self.clipboard_ball.clicked.connect(self.on_clipboard_ball_clicked)
        self.clipboard_ball.position_changed.connect(self.on_clipboard_ball_moved)
        self.record_ball.clicked.connect(self.on_record_ball_clicked)
        self.smart_screenshot_ball.clicked.connect(self.on_smart_screenshot_clicked)
        self.advanced_screenshot_ball.clicked.connect(self.on_advanced_screenshot_clicked)
        self.notebook_ball.clicked.connect(self.on_notebook_ball_clicked)
        self.notebook_ball.position_changed.connect(self.on_notebook_ball_moved)
        self.recent_ball.clicked.connect(self.on_recent_ball_clicked)
        self.recent_ball.position_changed.connect(self.on_recent_ball_moved)
        self.record_ball.right_clicked.connect(self.open_video_folder)
        self.clipboard_ball.right_clicked.connect(self.open_picture_folder)

        # Connections - System
        self.tray.quit_requested.connect(self.quit_app)
        self.tray.restart_requested.connect(self.restart_app)
        self.tray.about_requested.connect(self.show_about)
        self.tray.toggle_requested.connect(self.toggle_main_ball)
        self.tray.locate_requested.connect(self.show_ball_locator)
        self.tray.toggle_panels_requested.connect(self.toggle_panels)
        self.tray.settings_requested.connect(self.prompt_settings)
        self.tray.toggle_hide_ball_when_screenshot_requested.connect(self.toggle_hide_ball_when_screenshot)
        self.tray.change_clipboard_max_items_requested.connect(self.set_clipboard_max_items)
        self.tray.toggle_clipboard_tracking_requested.connect(self.toggle_clipboard_tracking)
        self.tray.change_recent_max_items_requested.connect(self.set_recent_max_items)
        self.tray.toggle_recent_tracking_requested.connect(self.toggle_recent_tracking)
        self.panel.toggle_text_tracking_clicked.connect(self.toggle_record_text)
        self.panel.toggle_image_tracking_clicked.connect(self.toggle_record_image)
        
        # Connections - Clipboard
        self.clipboard_mgr.history_changed.connect(self.panel.update_history)
        self.panel.item_clicked.connect(lambda item: self.clipboard_mgr.copy_to_clipboard(item, as_plain_text=False))
        self.panel.item_right_clicked.connect(self._on_clipboard_item_right_clicked)
        self.panel.item_ctrl_left_clicked.connect(self._on_clipboard_item_ctrl_left_clicked)
        self.panel.item_deleted.connect(self.clipboard_mgr.remove_item)
        self.panel.item_pin_toggled.connect(self.clipboard_mgr.toggle_pin)
        self.panel.history_cleared.connect(self.clipboard_mgr.clear_history)
        self.panel.history_reordered.connect(self.clipboard_mgr.set_history)
        self.panel.toggle_tracking_clicked.connect(self.toggle_clipboard_tracking)
        
        # Connections - Recent
        self.recent_mgr.items_changed.connect(self.recent_panel.update_items)
        self.recent_panel.item_clicked.connect(self.recent_mgr.open_item)
        self.recent_panel.item_right_clicked.connect(self.recent_mgr.open_item_location)
        self.recent_panel.item_deleted.connect(self.recent_mgr.remove_item)
        self.recent_panel.item_pin_toggled.connect(self.recent_mgr.toggle_pin)
        self.recent_panel.toggle_tracking_clicked.connect(self.toggle_recent_tracking)
        self.recent_panel.excluded_extensions_changed.connect(self._on_recent_excluded_extensions_changed)
        self.recent_panel.visibility_dict_changed.connect(self._on_recent_visibility_dict_changed)
        self.recent_panel.history_cleared.connect(self.recent_mgr.clear_history)
        self.recent_panel.history_reordered.connect(self.recent_mgr.set_history)
        
        self.notebook_panel.content_changed.connect(self.notebook_mgr.update_content)
        self.hotkey_mgr.action_triggered.connect(self.on_action_triggered)
        
        # Initialize panel with loaded history
        self.panel.update_history(self.clipboard_mgr.get_history())

        self.recent_mgr.max_items = self.options.get("recent_max_items", 30)
        self.recent_mgr.set_excluded_extensions(self.options.get("recent_excluded_extensions", []))
        self._update_recent_excluded_paths()
        self.recent_mgr.set_tracking_enabled(self.options.get("recent_tracking_enabled", True))
        self.recent_panel.set_tracking_enabled(self.options.get("recent_tracking_enabled", True))
        self.recent_panel.set_excluded_extensions(self.options.get("recent_excluded_extensions", []))
        self.recent_panel.set_visibility_dict(self.options.get("recent_extension_visibility", {}))
        self.recent_panel.update_items(self.recent_mgr.get_items())

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
        import os
        if pic_path and not os.path.exists(pic_path):
            pic_path = ""
            
        if not pic_path:
            pic_path = os.path.join(get_base_dir(), "picture")
            self.options["picture_save_path"] = pic_path
            save_option("picture_save_path", pic_path)
            
        if not os.path.exists(pic_path):
            try:
                os.makedirs(pic_path)
            except Exception as e:
                log_exception(f"Failed to create picture directory: {e}")
                
        self.clipboard_mgr.picture_save_path = pic_path
        
        self.clipboard_mgr.tracking_enabled = self.options.get("clipboard_tracking_enabled", True)
        self.panel.set_tracking_enabled(self.options.get("clipboard_tracking_enabled", True))

    def _update_recent_excluded_paths(self):
        custom_apps = self.options.get("custom_apps", [])
        paths = [app["path"] for app in custom_apps if app.get("path")]
        self.recent_mgr.set_excluded_paths(paths)

    def _update_balls_layout(self):
        # Concentric circles layout algorithm
        total_balls = len(self.sub_balls)
        import math
        layout_cfg = self.skin_config.get("layout", {})
        current_circle_radius = int(layout_cfg.get("first_ring_radius", 55))
        ball_gap = max(1, int(layout_cfg.get("ball_gap", 45)))
        ring_spacing = max(1, int(layout_cfg.get("ring_spacing", 45)))
        balls_placed = 0
        
        while balls_placed < total_balls:
            # Calculate max balls that can fit in the current circle
            max_in_circle = max(1, int(2 * math.pi * current_circle_radius / ball_gap))
            balls_in_this_circle = min(max_in_circle, total_balls - balls_placed)
            
            for i in range(balls_in_this_circle):
                b = self.sub_balls[balls_placed + i]
                b.default_radius = current_circle_radius
                b.radius = b.default_radius
                b.default_angle = math.pi * 2 * (i / balls_in_this_circle)
                b.angle = b.default_angle
                b.siblings = [sib for sib in self.sub_balls if sib != b]
                
            balls_placed += balls_in_this_circle
            current_circle_radius += ring_spacing

    def _sub_ball_color(self, name, fallback):
        value = self.skin_config.get("sub_ball", {}).get("colors", {}).get(name)
        if isinstance(value, (list, tuple)) and len(value) >= 3:
            alpha = value[3] if len(value) > 3 else 255
            return QColor(value[0], value[1], value[2], alpha)
        return fallback

    def _screenshot_debug_overlay(self):
        return bool(self.skin_config.get("performance", {}).get("screenshot_debug_overlay", False))

    def toggle_sub_balls(self):
        if self.ball.is_edge_hidden():
            self.ball.reveal_from_edge()
            return

        # When main ball is clicked, show/hide the surrounding sub balls
        any_visible = any(sb.isVisible() for sb in self.sub_balls)
        if any_visible:
            # Hide all sub balls
            for sb in self.sub_balls:
                sb.hide()
        else:
            # Show all sub balls based on options
            if self.options.get("enable_clipboard_ball", True):
                self.clipboard_ball.update_position_from_main()
                self.clipboard_ball.show()
            if self.options.get("enable_notebook_ball", True):
                self.notebook_ball.update_position_from_main()
                self.notebook_ball.show()
            if self.options.get("enable_smart_screenshot_ball", True):
                self.smart_screenshot_ball.update_position_from_main()
                self.smart_screenshot_ball.show()
            if self.options.get("enable_advanced_screenshot_ball", True):
                self.advanced_screenshot_ball.update_position_from_main()
                self.advanced_screenshot_ball.show()
            if self.options.get("enable_record_ball", True):
                self.record_ball.update_position_from_main()
                self.record_ball.show()
            if self.options.get("enable_recent_ball", True):
                self.recent_ball.update_position_from_main()
                self.recent_ball.show()
            
            for sb in self.sub_balls:
                if hasattr(sb, 'custom_app_path'):
                    sb.update_position_from_main()
                    sb.show()

    def on_ball_moved(self, x, y):
        if self.ball.is_edge_hidden():
            return

        # Update positions of all visible sub-balls to maintain their orbit/distance
        for sb in self.sub_balls:
            if sb.isVisible():
                sb.update_position_from_main()

    def on_ball_edge_hidden_changed(self, hidden):
        if hidden:
            for sb in self.sub_balls:
                sb.hide()

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
        pass

    def _on_clipboard_item_right_clicked(self, item):
        if isinstance(item, dict) and item.get("type") == "image":
            import os
            val = item.get("value", "")
            if item.get("is_path", False) or (os.path.exists(val) and val.endswith('.png')):
                open_image_location(val)
        else:
            self.clipboard_mgr.copy_to_clipboard(item, as_plain_text=True)

    def _on_clipboard_item_ctrl_left_clicked(self, item):
        if not isinstance(item, dict) or item.get("type") != "image":
            text = item.get("value", "") if isinstance(item, dict) else str(item)
            url = first_url(text)
            if url:
                self._open_url(url)

    def on_notebook_ball_clicked(self):
        ball_pos = self.notebook_ball.geometry()
        self.notebook_panel.toggle_visibility(ball_pos.x(), ball_pos.y())

    def on_notebook_ball_moved(self, x, y):
        pass

    def on_recent_ball_clicked(self):
        self.recent_mgr.tick_scan()
        ball_pos = self.recent_ball.geometry()
        self.recent_panel.toggle_visibility(ball_pos.x(), ball_pos.y())

    def on_recent_ball_moved(self, x, y):
        pass

    def _open_url(self, url):
        import os
        import subprocess
        import webbrowser

        browser_path = str(self.options.get("browser_path", "") or "").strip()
        if browser_path:
            try:
                if os.path.exists(browser_path):
                    subprocess.Popen([browser_path, url])
                    return
                elif browser_path.lower() in {"msedge", "chrome", "firefox"}:
                    if os.name == "nt":
                        os.system(f'start {browser_path} "{url}"')
                    else:
                        subprocess.Popen([browser_path, url])
                    return
            except Exception as e:
                log_exception(f"Failed to open browser '{browser_path}': {e}")

        try:
            webbrowser.open(url)
        except Exception as e:
            log_exception(f"Fallback webbrowser.open failed for '{url}': {e}")
            if hasattr(os, "startfile"):
                try:
                    os.startfile(url)
                except Exception as e2:
                    log_exception(f"Fallback os.startfile failed for '{url}': {e2}")

    def on_record_ball_clicked(self):
        if self.is_recording:
            # Stop recording
            self.stop_recording()
        else:
            # Start selection
            if hasattr(self, 'screenshot_mask') and self.screenshot_mask is not None:
                return
            self._hide_balls_for_screenshot()
            active_win = QApplication.activeModalWidget() or QApplication.activeWindow()
            self.screenshot_mask = ScreenshotMask(parent=active_win, mode="record", show_debug_overlay=self._screenshot_debug_overlay())
            self.screenshot_mask.rect_selected.connect(self._on_record_rect_selected)
            self.screenshot_mask.finished.connect(self._on_screenshot_finished)
            self.screenshot_mask.exec()
            
    def _on_record_rect_selected(self, rect):
        self._restore_balls_after_screenshot()
        if not is_record_rect_valid(rect):
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(None, "录屏区域过小", record_rect_error_message())
            return

        # Show border with countdown
        self.recording_border = RecordingBorder(rect)
        self.recording_border.countdown_finished.connect(lambda: self.start_actual_recording(rect))
        self.recording_border.show()
        
    def start_actual_recording(self, rect):
        if not is_record_rect_valid(rect):
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(None, "录屏区域过小", record_rect_error_message())
            return

        self.is_recording = True
        self.record_ball.bg_color = self._sub_ball_color("record_active", QColor(50, 200, 50, 230))
        self.record_ball.update()
        fmt = self.options.get("video_save_format", "mp4")
        self.recorder_thread = ScreenRecorderThread(rect, self.video_save_path, save_format=fmt)
        self.recorder_thread.finished_recording.connect(self._on_recording_saved)
        self.recorder_thread.error_occurred.connect(self._on_recording_error)
        self.recorder_thread.start()
        
    def stop_recording(self):
        if self.recorder_thread and self.recorder_thread.isRunning():
            self.recorder_thread.stop()
            if not self.recorder_thread.wait(3000):
                log_message("Timed out while waiting for recorder thread to stop")
            return
        self._reset_recording_ui()

    def _reset_recording_ui(self):
        self.is_recording = False
        self.record_ball.bg_color = self._sub_ball_color("record", QColor(255, 0, 0, 230))
        self.record_ball.update()
        if self.recording_border:
            self.recording_border.hide()
            self.recording_border = None

    def open_video_folder(self):
        import os
        if self.video_save_path and os.path.exists(self.video_save_path):
            os.startfile(self.video_save_path)

    def open_picture_folder(self):
        import os
        pic_path = self.options.get("picture_save_path", "")
        if pic_path and os.path.exists(pic_path):
            os.startfile(pic_path)
            
    def _on_recording_saved(self, path):
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtCore import QTimer
        self._reset_recording_ui()
        self.recorder_thread = None
        # Show success toast or message, no blocking
        msg = QMessageBox(self.ball)
        msg.setWindowTitle("\u5f55\u5c4f\u5b8c\u6210") # 录屏完成
        msg.setText(f"\u89c6\u9891\u5df2\u4fdd\u5b58\u81f3:\n{path}")
        msg.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        msg.show()
        QTimer.singleShot(3000, msg.close)
        
    def _on_recording_error(self, err):
        self._reset_recording_ui()
        self.recorder_thread = None
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(None, "\u5f55\u5c4f\u9519\u8bef", err) # 录屏错误

    def on_smart_screenshot_clicked(self, background_image=None, pre_captured_rects=None):
        self._start_screenshot_mask("screenshot", background_image=background_image, pre_captured_rects=pre_captured_rects)

    def on_advanced_screenshot_clicked(self):
        self._start_screenshot_mask("edit")

    def _start_screenshot_mask(self, mode="screenshot", background_image=None, pre_captured_rects=None):
        if getattr(self, 'screenshot_mask', None) is not None:
            return 
        if getattr(self, '_smart_screenshot_pending', False):
            return

        self._smart_screenshot_pending = True

        popup = QApplication.activePopupWidget()
        if popup:
            popup.close()

        def start_mask():
            if getattr(self, 'screenshot_mask', None) is not None:
                self._smart_screenshot_pending = False
                return

            self._hide_balls_for_screenshot()
            QTimer.singleShot(80, build_mask)

        def build_mask():
            if getattr(self, 'screenshot_mask', None) is not None:
                self._smart_screenshot_pending = False
                self._restore_balls_after_screenshot()
                return

            all_rects_global = None
            virtual_left = 0
            virtual_top = 0
            try:
                import win32api
                import win32con
                nonlocal background_image
                if background_image is None:
                    background_image = ImageGrab.grab(all_screens=True)
                if pre_captured_rects is not None:
                    all_rects_global = pre_captured_rects
                else:
                    all_rects_global = get_all_visible_rects()
                virtual_left = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
                virtual_top = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
            except Exception as e:
                log_exception(f"Failed to prepare smart screenshot mask: {e}")
                background_image = None
                all_rects_global = None

            active_win = QApplication.activeModalWidget() or QApplication.activeWindow()
            self.screenshot_mask = ScreenshotMask(
                parent=active_win,
                mode=mode,
                background_image=background_image,
                all_rects_global=all_rects_global,
                virtual_screen_left=virtual_left,
                virtual_screen_top=virtual_top,
                show_debug_overlay=self._screenshot_debug_overlay(),
            )
            if mode == "edit":
                self.screenshot_mask.image_selected.connect(self._open_screenshot_editor)
            self.screenshot_mask.finished.connect(self._on_screenshot_finished)
            self.screenshot_mask.exec()

        QTimer.singleShot(0, start_mask)

    def _open_screenshot_editor(self, payload):
        if isinstance(payload, dict):
            pixmap = payload.get("pixmap")
            target_rect = payload.get("rect")
        else:
            pixmap = payload
            target_rect = None
        if pixmap is None or pixmap.isNull():
            return
        save_dir = self.options.get("picture_save_path", "") or os.path.join(get_base_dir(), "picture")
        editor = ScreenshotEditor(pixmap, save_dir=save_dir, target_rect=target_rect)
        editor.destroyed.connect(self._cleanup_screenshot_editors)
        self.screenshot_editors.append(editor)
        editor.show()
        editor.raise_()

    def _cleanup_screenshot_editors(self):
        alive = []
        for editor in self.screenshot_editors:
            try:
                if editor.isVisible():
                    alive.append(editor)
            except RuntimeError:
                pass
        self.screenshot_editors = alive
        
    def _on_screenshot_finished(self):
        self._smart_screenshot_pending = False
        self._restore_balls_after_screenshot()
        if hasattr(self, 'screenshot_mask'):
            self.screenshot_mask = None

    def _hide_balls_for_screenshot(self):
        if not self.options.get("hide_ball_when_screenshot", True):
            return
        self._screenshot_hidden_state = {
            "main_visible": self.ball.isVisible(),
            "visible_sub_balls": [sb for sb in self.sub_balls if sb.isVisible()],
        }
        self.ball.hide()
        for sb in self.sub_balls:
            sb.hide()
        self.app.processEvents()

    def _restore_balls_after_screenshot(self):
        if not self.options.get("hide_ball_when_screenshot", True):
            return
        state = self._screenshot_hidden_state or {}
        if state.get("main_visible", True):
            self.ball.show()

        for sb in state.get("visible_sub_balls", []):
            if sb in self.sub_balls:
                sb.reset_position()
                sb.show()
        self._screenshot_hidden_state = None

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
        self.clipboard_mgr.trim_history()

    def set_recent_max_items(self, value):
        self.options["recent_max_items"] = int(value)
        save_option("recent_max_items", self.options["recent_max_items"])
        self.recent_mgr.max_items = self.options["recent_max_items"]
        self.tray.set_recent_max_items(self.options["recent_max_items"])
        self.recent_mgr.trim_history()

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
        
    def toggle_recent_tracking(self):
        current = self.options.get("recent_tracking_enabled", True)
        new_val = not current
        self.options["recent_tracking_enabled"] = new_val
        save_option("recent_tracking_enabled", new_val)
        self.recent_mgr.set_tracking_enabled(new_val)
        self.recent_panel.set_tracking_enabled(new_val)

    def _on_recent_excluded_extensions_changed(self, exts):
        self.options["recent_excluded_extensions"] = exts
        save_option("recent_excluded_extensions", exts)
        self.recent_mgr.set_excluded_extensions(exts)

    def _on_recent_visibility_dict_changed(self, visibility_dict):
        self.options["recent_extension_visibility"] = visibility_dict
        save_option("recent_extension_visibility", visibility_dict)

    def toggle_main_ball(self):
        if self.ball.isVisible():
            self.ball.hide()
            for sb in self.sub_balls:
                sb.hide()
        else:
            self.ball.reveal_from_edge()
            self.ball.show()

    def show_ball_locator(self):
        self.ball.show_locator_hint()

    def toggle_panels(self):
        panels = [self.panel, self.notebook_panel, self.recent_panel]
        any_visible = any(p.isVisible() for p in panels)
        if any_visible:
            self._visible_panels = [p for p in panels if p.isVisible()]
            for p in panels:
                p.hide()
        else:
            if hasattr(self, '_visible_panels') and self._visible_panels:
                for p in self._visible_panels:
                    p.show()
                self._visible_panels = []

    def prompt_settings(self):
        from ui.settings import SettingsDialog
        
        if self.settings_dialog is not None and self.settings_dialog.isVisible():
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()
            return
            
        self.settings_dialog = SettingsDialog(self.options, self.hotkey_mgr, self.clipboard_mgr, self.recent_mgr)
        self.settings_dialog.settings_saved.connect(self.apply_settings)
        self.settings_dialog.show()
        
    def apply_settings(self, new_options):
        self.options = new_options
        self.tray.set_hide_ball_when_screenshot(self.options.get("hide_ball_when_screenshot", True))
        self.tray.set_clipboard_tracking_enabled(self.options.get("clipboard_tracking_enabled", True))
        self.tray.set_clipboard_max_items(self.options.get("clipboard_max_items", 20))
        self.tray.set_recent_max_items(self.options.get("recent_max_items", 30))
        # Apply clipboard
        self.clipboard_mgr.max_items = self.options.get("clipboard_max_items", 20)
        self.clipboard_mgr.tracking_enabled = self.options.get("clipboard_tracking_enabled", True)
        self.panel.set_tracking_enabled(self.clipboard_mgr.tracking_enabled)
        # Apply recent files
        self.recent_mgr.max_items = self.options.get("recent_max_items", 30)
        self.recent_mgr.set_tracking_enabled(self.options.get("recent_tracking_enabled", True))
        self.recent_panel.set_tracking_enabled(self.options.get("recent_tracking_enabled", True))
        self.recent_mgr.set_excluded_extensions(self.options.get("recent_excluded_extensions", []))
        self._update_recent_excluded_paths()
        self.recent_panel.set_excluded_extensions(self.options.get("recent_excluded_extensions", []))
        self.recent_panel.set_visibility_dict(self.options.get("recent_extension_visibility", {}))
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
        self.clipboard_mgr.trim_history()
        self.recent_mgr.trim_history()
        
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
            ball = SubBall(self.ball, text="", radius=80, angle=0, tooltip=app["name"], bg_color=self._sub_ball_color("custom", QColor(100, 100, 100, 230)), icon=icon, skin_config=self.skin_config)
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

            if self.options.get("enable_advanced_screenshot_ball", True):
                self.advanced_screenshot_ball.reset_position()
                self.advanced_screenshot_ball.show()
            else:
                self.advanced_screenshot_ball.hide()
                
            if self.options.get("enable_record_ball", True):
                self.record_ball.reset_position()
                self.record_ball.show()
            else:
                self.record_ball.hide()

            if self.options.get("enable_recent_ball", True):
                self.recent_ball.reset_position()
                self.recent_ball.show()
            else:
                self.recent_ball.hide()
                self.recent_panel.hide()

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
        elif action_name == "smart_screenshot":
            self.on_smart_screenshot_clicked(background_image=payload_img, pre_captured_rects=payload_rects)
        elif action_name == "advanced_screenshot":
            self.on_advanced_screenshot_clicked()
        elif action_name == "notebook":
            self.on_notebook_ball_clicked()
        elif action_name == "toggle_ball":
            self.toggle_main_ball()
        elif action_name == "locate_ball":
            self.show_ball_locator()
        elif action_name == "toggle_panels":
            self.toggle_panels()
        elif action_name == "record":
            self.on_record_ball_clicked()
        elif action_name == "recent":
            from PySide6.QtGui import QCursor
            self.recent_mgr.tick_scan()
            cursor_pos = QCursor.pos()
            self.recent_panel.toggle_visibility(cursor_pos.x(), cursor_pos.y())

    
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

    def restart_app(self):
        env = os.environ.copy()
        env["DESKTOP_DOLL_RESTART_WAIT_PID"] = str(os.getpid())
        try:
            if getattr(sys, "frozen", False):
                command = [sys.executable]
            else:
                script = os.path.abspath(sys.argv[0])
                command = [sys.executable, script, *sys.argv[1:]]

            creation_flags = 0
            if os.name == "nt":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            subprocess.Popen(
                command,
                cwd=get_base_dir(),
                env=env,
                close_fds=True,
                creationflags=creation_flags,
            )
            self.quit_app()
        except Exception as exc:
            log_exception(f"Restart failed: {exc}")
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self.ball, "重新启动失败", str(exc))

    def run(self):
        return self.app.exec()

