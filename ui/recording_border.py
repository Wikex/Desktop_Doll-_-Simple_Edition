import math
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRect, QTimer, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QGuiApplication, QFont

class RecordingBorder(QWidget):
    countdown_finished = Signal()

    def __init__(self, target_rect_physical: QRect):
        super().__init__()
        self.setWindowTitle("桌面人偶_录屏边框")
        
        # Transparent for mouse events so user can click through the border
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint | 
            Qt.Tool | 
            Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        # Convert physical target rect back to logical rect for drawing
        center = target_rect_physical.center()
        screen = QGuiApplication.primaryScreen()
        for s in QGuiApplication.screens():
            geom = s.geometry()
            ratio = s.devicePixelRatio()
            left = int(round(geom.x() * ratio))
            top = int(round(geom.y() * ratio))
            right = int(round((geom.x() + geom.width()) * ratio))
            bottom = int(round((geom.y() + geom.height()) * ratio))
            if left <= center.x() <= right and top <= center.y() <= bottom:
                screen = s
                break

        ratio = screen.devicePixelRatio()
        geom = screen.geometry()
        
        lx = int(round((target_rect_physical.x() - geom.x() * ratio) / ratio + geom.x()))
        ly = int(round((target_rect_physical.y() - geom.y() * ratio) / ratio + geom.y()))
        lw = max(1, int(round(target_rect_physical.width() / ratio)))
        lh = max(1, int(round(target_rect_physical.height() / ratio)))
        
        self.logical_rect = QRect(lx, ly, lw, lh)
        
        # Expand the window by 4 logical pixels so the 2-pixel border is drawn OUTSIDE the capture area
        # This prevents the border itself from being recorded
        self.setGeometry(self.logical_rect.adjusted(-4, -4, 4, 4))
        
        self.countdown = 3
        self.is_recording = False
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw red border
        pen = QPen(QColor(255, 0, 0, 200), 4) # 4 logical pixels thick
        pen.setJoinStyle(Qt.MiterJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        
        # Draw exactly at the bounds of the widget (since widget is larger than capture area)
        # Inward 2px offset for the 4px pen width so it fully fits inside the widget without clipping
        painter.drawRect(2, 2, self.width() - 4, self.height() - 4)
        
        # Draw countdown or recording indicator
        font = QFont("Arial", 48, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 0, 0, 220))
        
        if not self.is_recording:
            painter.drawText(self.rect(), Qt.AlignCenter, str(self.countdown))
        else:
            # Maybe just draw a tiny REC indicator or keep it empty
            # Let's keep it empty during recording so it doesn't distract or overlap
            pass

    def tick(self):
        if self.countdown > 1:
            self.countdown -= 1
            self.update()
        else:
            self.countdown = 0
            self.is_recording = True
            self.timer.stop()
            self.update()
            self.countdown_finished.emit()
