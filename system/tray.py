from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QInputDialog
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Qt, QObject, Signal

class TrayIcon(QObject):
    quit_requested = Signal()
    toggle_requested = Signal()
    toggle_panels_requested = Signal()
    settings_requested = Signal()
    about_requested = Signal()
    toggle_hide_ball_when_screenshot_requested = Signal()
    change_clipboard_max_items_requested = Signal(int)
    toggle_clipboard_tracking_requested = Signal()
    change_recent_max_items_requested = Signal(int)
    toggle_recent_tracking_requested = Signal()
    change_clipboard_record_text_requested = Signal(bool)
    change_clipboard_record_image_requested = Signal(bool)
    change_browser_path_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tray = QSystemTrayIcon(self)
        self.hide_ball_when_screenshot = True
        self.clipboard_tracking_enabled = True
        self.clipboard_record_text = True
        self.clipboard_record_image = True
        
        self.tray.setIcon(self._create_dummy_icon())
        self.tray.setToolTip("\u60ac\u6d6e\u52a9\u624b")

        # Context Menu
        self.menu = QMenu()

        # 1. View / Control
        self.action_toggle = QAction("\u663e\u793a/\u9690\u85cf\u60ac\u6d6e\u7403", self) # 显示/隐藏悬浮球
        self.action_toggle.triggered.connect(self.toggle_requested.emit)
        self.menu.addAction(self.action_toggle)

        self.action_toggle_panels = QAction("显示/隐藏所有面板", self)
        self.action_toggle_panels.triggered.connect(self.toggle_panels_requested.emit)
        self.menu.addAction(self.action_toggle_panels)
        self.menu.addSeparator()

        # 2. Clipboard
        self.action_clipboard_tracking = QAction("\u76d1听剪贴板变化", self) # 监听剪贴板变化
        self.action_clipboard_tracking.setCheckable(True)
        self.action_clipboard_tracking.setChecked(self.clipboard_tracking_enabled)
        self.action_clipboard_tracking.triggered.connect(self._on_toggle_clipboard_tracking)
        self.menu.addAction(self.action_clipboard_tracking)

        self.action_clipboard_limit = QAction("\u526a\u8d34\u677f历史容量...", self) # 剪贴板历史容量...
        self.action_clipboard_limit.triggered.connect(self._on_change_clipboard_limit)
        self.menu.addAction(self.action_clipboard_limit)
        self.menu.addSeparator()

        # 2.5 Recent Files
        self.action_recent_tracking = QAction("监听最近使用变化", self)
        self.action_recent_tracking.setCheckable(True)
        self.action_recent_tracking.setChecked(True)
        self.action_recent_tracking.triggered.connect(self._on_toggle_recent_tracking)
        self.menu.addAction(self.action_recent_tracking)

        self.action_recent_limit = QAction("最近使用最大条数...", self)
        self.action_recent_limit.triggered.connect(self._on_change_recent_limit)
        self.menu.addAction(self.action_recent_limit)
        self.menu.addSeparator()

        # 3. Screenshot / Record
        self.action_hide_ball = QAction("\u622a屏时\u81ea动隐藏", self) # 截屏时自动隐藏
        self.action_hide_ball.setCheckable(True)
        self.action_hide_ball.setChecked(self.hide_ball_when_screenshot)
        self.action_hide_ball.triggered.connect(self._on_toggle_hide_ball)
        self.menu.addAction(self.action_hide_ball)
        self.menu.addSeparator()

        # 4. Settings
        self.action_settings = QAction("\u8bbe\u7f6e...", self) # 设置...
        self.action_settings.triggered.connect(self.settings_requested.emit)
        self.menu.addAction(self.action_settings)
        self.menu.addSeparator()

        # 5. System
        self.action_about = QAction("\u5173\u4e8e\u684c\u9762\u4eba\u5076", self) # 关于桌面人偶
        self.action_about.triggered.connect(self.about_requested.emit)
        self.menu.addAction(self.action_about)
        
        self.action_quit = QAction("\u9000\u51fa\u684c\u9762\u4eba\u5076", self) # 退出桌面人偶
        self.action_quit.triggered.connect(self.quit_requested.emit)
        self.menu.addAction(self.action_quit)

        self.tray.activated.connect(self._on_activated)
    def _on_activated(self, reason):
        # QSystemTrayIcon.Trigger \u901a\u5e38\u8868\u793a\u5de6\u952e\u5355\u51fb
        if reason == QSystemTrayIcon.Trigger:
            from PySide6.QtGui import QCursor
            self.menu.exec(QCursor.pos())




    def _on_toggle_hide_ball(self, checked):
        self.hide_ball_when_screenshot = checked
        self.toggle_hide_ball_when_screenshot_requested.emit()

    def set_hide_ball_when_screenshot(self, checked):
        self.hide_ball_when_screenshot = checked
        self.action_hide_ball.setChecked(checked)

    def _on_change_clipboard_limit(self):
        # We need the current limit value. Fallback to 20 if not set as instance var
        current = getattr(self, 'clipboard_max_items', 20)
        value, ok = QInputDialog.getInt(None, "\u8bbe\u7f6e\u526a\u8d34\u677f\u6700\u5927\u6761\u6570", "\u8bf7\u8f93\u5165\u6700\u591a\u4fdd\u5b58\u6761\u6570\uff1a", current, 1, 999, 1)
        if ok:
            self.change_clipboard_max_items_requested.emit(value)

    def _on_toggle_clipboard_tracking(self, checked):
        self.clipboard_tracking_enabled = checked
        self.toggle_clipboard_tracking_requested.emit()

    def set_clipboard_max_items(self, value):
        self.clipboard_max_items = value

    def set_clipboard_tracking_enabled(self, checked):
        self.clipboard_tracking_enabled = checked
        self.action_clipboard_tracking.setChecked(checked)

    def _on_change_recent_limit(self):
        current = getattr(self, 'recent_max_items', 30)
        value, ok = QInputDialog.getInt(None, "设置最近使用最大条数", "请输入最多保存条数：", current, 1, 999, 1)
        if ok:
            self.change_recent_max_items_requested.emit(value)

    def _on_toggle_recent_tracking(self, checked):
        self.recent_tracking_enabled = checked
        self.toggle_recent_tracking_requested.emit()

    def set_recent_max_items(self, value):
        self.recent_max_items = value

    def set_recent_tracking_enabled(self, checked):
        self.recent_tracking_enabled = checked
        self.action_recent_tracking.setChecked(checked)

    def show(self):
        self.tray.show()

    def hide(self):
        self.tray.hide()

    def _create_dummy_icon(self):
        from PySide6.QtGui import QPixmap, QPainter, QColor, QIcon
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setBrush(QColor(50, 150, 250))
        painter.drawEllipse(0, 0, 32, 32)
        painter.end()
        return QIcon(pixmap)
