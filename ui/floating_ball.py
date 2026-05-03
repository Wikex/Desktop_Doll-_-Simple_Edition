import sys
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QColor

class FloatingBall(QWidget):
    # Signal emitted when the ball is clicked
    clicked = Signal()
    right_clicked = Signal()
    position_changed = Signal(int, int)

    def __init__(self):
        super().__init__()
        self.init_ui()
        
        # Variables for dragging
        self._is_dragging = False
        self._drag_start_pos = QPoint()
        self._has_moved = False

    def init_ui(self):
        self.setWindowTitle("\u684c\u9762\u4eba\u5076")
        # Frameless, topmost, tool (not in taskbar)
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint | 
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Fixed size
        self.setFixedSize(60, 60)
        
        # Initial position: bottom right (offset a bit)
        # We will position it when showing to avoid multiple screen issues
        
    def paintEvent(self, event):
        from PySide6.QtGui import QRadialGradient
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Create a modern 3D-like radial gradient
        gradient = QRadialGradient(self.width() / 3, self.height() / 3, self.width())
        gradient.setColorAt(0, QColor(100, 180, 255, 230))
        gradient.setColorAt(1, QColor(20, 100, 220, 210))
        
        painter.setBrush(gradient)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, self.width(), self.height())

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self._has_moved = False
            self._drag_start_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.RightButton:
            self.right_clicked.emit()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_dragging and event.buttons() & Qt.LeftButton:
            # Move the window
            self.move(event.globalPos() - self._drag_start_pos)
            self._has_moved = True
            self.position_changed.emit(self.x(), self.y())
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._is_dragging = False
            if not self._has_moved:
                self.clicked.emit()
            event.accept()

    def move_to_bottom_right(self):
        screen_geo = QApplication.primaryScreen().availableGeometry()
        x = screen_geo.width() - self.width() - 50
        y = screen_geo.height() - self.height() - 50
        self.move(x, y)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ball = FloatingBall()
    ball.move_to_bottom_right()
    ball.show()
    sys.exit(app.exec())
