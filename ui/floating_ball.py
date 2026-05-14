import sys
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QPoint, Signal, QTimer
from PySide6.QtGui import QMouseEvent, QPainter, QColor, QPen

class FloatingBall(QWidget):
    # Signal emitted when the ball is clicked
    clicked = Signal()
    right_clicked = Signal()
    position_changed = Signal(int, int)
    edge_hidden_changed = Signal(bool)

    def __init__(self, skin_config=None):
        super().__init__()
        self.skin_config = skin_config or {}
        self.init_ui()
        self._locator_overlay = None
        
        # Variables for dragging
        self._is_dragging = False
        self._drag_start_pos = QPoint()
        self._has_moved = False
        self._edge_hidden = False
        self._edge_side = None

    def init_ui(self):
        self.setWindowTitle("\u684c\u9762\u4eba\u5076")
        # Frameless, topmost, tool (not in taskbar)
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint | 
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        size = self.skin_config.get("main_ball", {}).get("size", [56, 56])
        self.setFixedSize(int(size[0]), int(size[1]))
        
        # Initial position: bottom right (offset a bit)
        # We will position it when showing to avoid multiple screen issues
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        cfg = self.skin_config.get("main_ball", {})
        color = self._color(cfg.get("color"), QColor(37, 99, 235, 230))
        border = self._color(cfg.get("border_color"), QColor(255, 255, 255, 90))

        painter.setBrush(color)
        painter.setPen(border)
        painter.drawEllipse(1, 1, self.width() - 2, self.height() - 2)

    def _color(self, value, fallback):
        if isinstance(value, (list, tuple)) and len(value) >= 3:
            alpha = value[3] if len(value) > 3 else 255
            return QColor(value[0], value[1], value[2], alpha)
        return fallback

    def _edge_hide_cfg(self):
        return self.skin_config.get("main_ball", {}).get("edge_hide", {})

    def is_edge_hidden(self):
        return self._edge_hidden

    def _current_screen_geometry(self):
        if self._edge_hidden and self._edge_side == "left":
            probe = QPoint(self.x() + self.width() - 1, self.y() + self.height() // 2)
        elif self._edge_hidden and self._edge_side == "right":
            probe = QPoint(self.x(), self.y() + self.height() // 2)
        else:
            probe = self.frameGeometry().center()

        screen = QApplication.screenAt(probe) or QApplication.primaryScreen()
        return screen.availableGeometry()

    def _should_edge_hide(self):
        cfg = self._edge_hide_cfg()
        if not cfg.get("enabled", True):
            return None

        screen_geo = self._current_screen_geometry()
        trigger_margin = int(cfg.get("trigger_margin", 16))
        if self.x() <= screen_geo.left() + trigger_margin:
            return "left"
        if self.x() + self.width() >= screen_geo.right() - trigger_margin:
            return "right"
        return None

    def _dock_to_edge(self, side):
        cfg = self._edge_hide_cfg()
        screen_geo = self._current_screen_geometry()
        visible_width = max(4, min(self.width(), int(cfg.get("visible_width", 10))))

        y = max(screen_geo.top(), min(self.y(), screen_geo.bottom() - self.height() + 1))
        if side == "left":
            x = screen_geo.left() - self.width() + visible_width
        else:
            x = screen_geo.right() - visible_width + 1

        self._edge_hidden = True
        self._edge_side = side
        self.move(x, y)
        self.position_changed.emit(self.x(), self.y())
        self.edge_hidden_changed.emit(True)

    def reveal_from_edge(self):
        if not self._edge_hidden:
            return False

        cfg = self._edge_hide_cfg()
        screen_geo = self._current_screen_geometry()
        restore_margin = max(0, int(cfg.get("restore_margin", 8)))

        y = max(screen_geo.top(), min(self.y(), screen_geo.bottom() - self.height() + 1))
        if self._edge_side == "left":
            x = screen_geo.left() + restore_margin
        else:
            x = screen_geo.right() - self.width() - restore_margin + 1

        self._edge_hidden = False
        self._edge_side = None
        self.move(x, y)
        self.position_changed.emit(self.x(), self.y())
        self.edge_hidden_changed.emit(False)
        return True

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
            if self._edge_hidden:
                self.reveal_from_edge()
                self._drag_start_pos = QPoint(self.width() // 2, self.height() // 2)
            # Move the window
            self.move(event.globalPos() - self._drag_start_pos)
            self._has_moved = True
            self.position_changed.emit(self.x(), self.y())
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._is_dragging = False
            if self._edge_hidden:
                self.reveal_from_edge()
            elif self._has_moved:
                side = self._should_edge_hide()
                if side:
                    self._dock_to_edge(side)
            else:
                self.clicked.emit()
            event.accept()

    def move_to_bottom_right(self):
        screen_geo = QApplication.primaryScreen().availableGeometry()
        x = screen_geo.width() - self.width() - 50
        y = screen_geo.height() - self.height() - 50
        self.move(x, y)

    def show_locator_hint(self):
        if self._edge_hidden:
            self.reveal_from_edge()

        self.show()
        self.raise_()
        if self._locator_overlay is not None:
            self._locator_overlay.close()

        overlay = BallLocatorOverlay(self, self.skin_config)
        self._locator_overlay = overlay
        overlay.destroyed.connect(lambda: self._clear_locator_overlay(overlay))
        overlay.start()

    def _clear_locator_overlay(self, overlay):
        if self._locator_overlay is overlay:
            self._locator_overlay = None


class BallLocatorOverlay(QWidget):
    """Lightweight position hint. Can be replaced by a Live2D locator later."""

    def __init__(self, target, skin_config=None):
        super().__init__(None)
        self.target = target
        self.skin_config = skin_config or {}
        cfg = self.skin_config.get("main_ball", {}).get("locator", {})
        self.renderer = cfg.get("renderer", "qt_ripple")
        self.live2d_asset = cfg.get("live2d_asset", "")
        self.overlay_size = int(cfg.get("size", 180))
        self.duration_ms = int(cfg.get("duration_ms", 1600))
        self.interval_ms = int(cfg.get("interval_ms", 33))
        self.frame = 0
        self.max_frames = max(1, self.duration_ms // self.interval_ms)

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFixedSize(self.overlay_size, self.overlay_size)

        self.timer = QTimer(self)
        self.timer.setInterval(self.interval_ms)
        self.timer.timeout.connect(self._tick)

    def start(self):
        self._sync_position()
        self.show()
        self.raise_()
        self.timer.start()

    def _sync_position(self):
        center = self.target.frameGeometry().center()
        self.move(center.x() - self.width() // 2, center.y() - self.height() // 2)

    def _tick(self):
        self.frame += 1
        if not self.target.isVisible() or self.frame >= self.max_frames:
            self.close()
            return
        self._sync_position()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        center = self.rect().center()
        progress = self.frame / self.max_frames
        base_color = QColor(37, 99, 235)
        max_radius = self.width() // 2 - 8

        for i in range(3):
            phase = (progress + i / 3.0) % 1.0
            radius = 24 + int((max_radius - 24) * phase)
            alpha = max(0, int(220 * (1.0 - phase)))
            pen = QPen(QColor(base_color.red(), base_color.green(), base_color.blue(), alpha), 3)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(center, radius, radius)

        badge_w = 64
        badge_h = 24
        badge_x = (self.width() - badge_w) // 2
        badge_y = self.height() - badge_h - 12
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(15, 23, 42, 220))
        painter.drawRoundedRect(badge_x, badge_y, badge_w, badge_h, 5, 5)
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        painter.drawText(badge_x, badge_y, badge_w, badge_h, Qt.AlignCenter, "在这里")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ball = FloatingBall()
    ball.move_to_bottom_right()
    ball.show()
    sys.exit(app.exec())
