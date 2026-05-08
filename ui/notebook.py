import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, 
                                QApplication, QLabel, QPushButton, QMessageBox)
from PySide6.QtCore import Qt, Signal, QTimer, QPoint
from PySide6.QtGui import QClipboard, QMouseEvent, QTextOption

class NotebookPanel(QWidget):
    content_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self._is_dragging = False
        self._drag_start_pos = None
        self._relative_offset = None
        self._main_ball = None
        self.init_ui()

    def set_main_ball(self, ball):
        self._main_ball = ball

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self._drag_start_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_dragging and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_start_pos)
            if self._main_ball:
                self._relative_offset = (self.x() - self._main_ball.x(), self.y() - self._main_ball.y())
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._is_dragging = False
            event.accept()

    def init_ui(self):
        self.setWindowTitle("\u684c\u9762\u4eba\u5076")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(320, 420)
        self.setStyleSheet("background-color: #f6f7fb; border: 1px solid #d8dbe6; border-radius: 12px; color: #000000;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        title_layout = QHBoxLayout()
        title = QLabel("悬浮记事本")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #111827;")
        btn_close = QPushButton("✖")
        btn_close.setFixedSize(20, 20)
        btn_close.setStyleSheet("QPushButton { background-color: transparent; border: none; color: #6b7280; font-weight: bold; font-size: 14px; } QPushButton:hover { color: #ef4444; }")
        btn_close.clicked.connect(self.hide)
        
        title_layout.addStretch()
        title_layout.addWidget(title)
        title_layout.addStretch()
        title_layout.addWidget(btn_close)
        layout.addLayout(title_layout)
        
        self.text_edit = QPlainTextEdit()
        self.text_edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.text_edit.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_edit.setStyleSheet("QTextEdit { border: 1px solid #d1d5db; background-color: white; color: #000000; padding: 10px; border-radius: 8px; font-size: 14px; selection-background-color: #bfdbfe; }")
        self.text_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.text_edit)
        
        btn_layout = QHBoxLayout()
        self.btn_copy = QPushButton("复制全部")
        self.btn_copy.setStyleSheet("QPushButton { background-color: #2563eb; color: white; border-radius: 6px; padding: 8px; font-weight: bold; } QPushButton:hover { background-color: #1d4ed8; }")
        self.btn_copy.clicked.connect(self._on_copy_clicked)
        self.btn_clear = QPushButton("清空")
        self.btn_clear.setStyleSheet("QPushButton { background-color: #ef4444; color: white; border-radius: 6px; padding: 8px; font-weight: bold; } QPushButton:hover { background-color: #dc2626; }")
        self.btn_clear.clicked.connect(self._on_clear_clicked)
        btn_layout.addWidget(self.btn_copy)
        btn_layout.addWidget(self.btn_clear)
        layout.addLayout(btn_layout)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
            event.accept()
            return
        super().keyPressEvent(event)

    def _on_text_changed(self):
        self.content_changed.emit(self.text_edit.toPlainText())

    def _on_copy_clicked(self):
        QApplication.clipboard().setText(self.text_edit.toPlainText())

    def _on_clear_clicked(self):
        msg_box = QMessageBox(self)
        btn_yes = msg_box.addButton("是", QMessageBox.YesRole)
        msg_box.addButton("否", QMessageBox.NoRole)
        msg_box.exec()
        if msg_box.clickedButton() == btn_yes:
            self.text_edit.clear()

    def set_content(self, text):
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(text)
        self.text_edit.blockSignals(False)

    def update_position(self, ball_x, ball_y):
        if self._relative_offset is None:
            # Default to the left of the ball
            self._relative_offset = (-310, -200)
        
        new_x = ball_x + self._relative_offset[0]
        new_y = ball_y + self._relative_offset[1]
        
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
