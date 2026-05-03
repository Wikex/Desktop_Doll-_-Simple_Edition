import sys
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent

class SearchBoxPanel(QWidget):
    search_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.init_ui()
        self._main_ball = None
        self._relative_offset = (-100, 60) # Below the main ball

    def set_main_ball(self, ball):
        self._main_ball = ball

    def init_ui(self):
        self.setWindowTitle("\u684c\u9762\u4eba\u5076") # 桌面人偶
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(300, 60)
        
        # Main container to allow border radius with translucent background
        self.container = QWidget(self)
        self.container.setFixedSize(self.width(), self.height())
        self.container.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 240);
                border: 1px solid #ccc;
                border-radius: 30px;
            }
        """)
        
        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(20, 5, 10, 5)
        
        self.input = QLineEdit()
        self.input.setPlaceholderText("\u641c\u7d22...") # 搜索...
        self.input.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
                font-size: 16px;
                color: #333;
            }
        """)
        self.input.returnPressed.connect(self._on_search)
        
        self.btn_search = QPushButton("\uD83D\uDD0D") # 🔍
        self.btn_search.setFixedSize(40, 40)
        self.btn_search.setCursor(Qt.PointingHandCursor)
        self.btn_search.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: #f0f0f0;
                border-radius: 20px;
                font-size: 18px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        self.btn_search.clicked.connect(self._on_search)
        
        layout.addWidget(self.input, 1)
        layout.addWidget(self.btn_search)

    def _on_search(self):
        text = self.input.text().strip()
        if text:
            self.search_requested.emit(text)
            self.input.setText("")
            self.hide()

    def update_position(self, ball_x, ball_y):
        new_x = ball_x + self._relative_offset[0]
        new_y = ball_y + self._relative_offset[1]
        
        from PySide6.QtWidgets import QApplication
        screen_geo = QApplication.primaryScreen().availableGeometry()
        new_x = max(screen_geo.left(), min(new_x, screen_geo.right() - self.width()))
        new_y = max(screen_geo.top(), min(new_y, screen_geo.bottom() - self.height()))
        self.move(new_x, new_y)

    def toggle_visibility(self, x, y):
        if self.isVisible():
            self.hide()
        else:
            self.update_position(x, y)
            self.show()
            self.raise_()
            self.activateWindow()
            self.input.setFocus()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)
