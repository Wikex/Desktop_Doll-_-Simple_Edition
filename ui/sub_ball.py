import math
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QColor, QFont

class SubBall(QWidget):
    clicked = Signal()
    right_clicked = Signal()
    position_changed = Signal(int, int)

    def __init__(self, main_ball, text="📋", radius=80, angle=math.pi * 1.25, tooltip="Clipboard", bg_color=None, icon=None, skin_config=None):
        super().__init__()
        self.main_ball = main_ball
        self.skin_config = skin_config or {}
        self.radius = radius # Target distance from main ball center
        self.angle = angle   # Current angle in radians
        self.default_angle = angle
        self.default_radius = radius
        self.text = text
        self.tooltip = tooltip
        self.bg_color = bg_color if bg_color else QColor(255, 165, 0, 230)
        self.icon = icon
        
        self.init_ui()
        self._is_dragging = False
        self._has_moved = False
        self._drag_start_pos = QPoint()
        
    def init_ui(self):
        self.setWindowTitle("\u684c\u9762\u4eba\u5076")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        size = self.skin_config.get("sub_ball", {}).get("size", [34, 34])
        self.setFixedSize(int(size[0]), int(size[1]))
        
        # 增加鼠标悬停提示
        self.setToolTip(self.tooltip)
        # 设置提示的样式
        self.setStyleSheet("QToolTip { color: #000; background-color: #ffffe0; border: 1px solid #ccc; font-weight: bold; }")
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        border = self._color(self.skin_config.get("sub_ball", {}).get("border_color"), QColor(255, 255, 255, 80))
        painter.setBrush(self.bg_color)
        painter.setPen(border)
        painter.drawEllipse(1, 1, self.width() - 2, self.height() - 2)
        
        # Draw icon/text
        painter.setPen(Qt.white)
        font = QFont()
        font.setPointSize(int(self.skin_config.get("sub_ball", {}).get("font_size", 10)))
        font.setBold(True)
        painter.setFont(font)
        if hasattr(self, 'icon') and self.icon and not self.icon.isNull():
            icon_size = int(self.skin_config.get("sub_ball", {}).get("icon_size", 20))
            pixmap = self.icon.pixmap(icon_size, icon_size)
            if not pixmap.isNull():
                painter.drawPixmap((self.width() - icon_size) // 2, (self.height() - icon_size) // 2, pixmap)
            else:
                painter.drawText(self.rect(), Qt.AlignCenter, self.text)
        else:
            painter.drawText(self.rect(), Qt.AlignCenter, self.text)

    def reset_position(self):
        self.angle = self.default_angle
        self.radius = self.default_radius
        self.update_position_from_main()

    def update_position_from_main(self):
        # Calculate center of main ball
        mx = self.main_ball.x() + self.main_ball.width() / 2
        my = self.main_ball.y() + self.main_ball.height() / 2
        
        # Calculate my center based on angle and radius
        cx = mx + self.radius * math.cos(self.angle)
        cy = my + self.radius * math.sin(self.angle)
        
        # Set top-left position
        self.move(int(cx - self.width() / 2), int(cy - self.height() / 2))
        self.position_changed.emit(self.x(), self.y())

    def enterEvent(self, event):
        from PySide6.QtWidgets import QToolTip
        QToolTip.showText(self.mapToGlobal(QPoint(self.width() // 2, self.height())), self.tooltip, self)
        super().enterEvent(event)

    def leaveEvent(self, event):
        from PySide6.QtWidgets import QToolTip
        QToolTip.hideText()
        super().leaveEvent(event)

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
            self._has_moved = True
            new_global_pos = event.globalPos() - self._drag_start_pos
            
            # My new center
            scx = new_global_pos.x() + self.width() / 2
            scy = new_global_pos.y() + self.height() / 2
            
            # Main ball center
            mx = self.main_ball.x() + self.main_ball.width() / 2
            my = self.main_ball.y() + self.main_ball.height() / 2
            
            # Calculate new angle and radius
            dx = scx - mx
            dy = scy - my
            dist = math.hypot(dx, dy)
            
            # Clamp distance (keep it around the main ball)
            # Main ball is 60x60, Sub ball is 36x36
            # 最小半径 = 30 + 18 + 5 = 53 (紧挨着+5像素间隙)
            min_radius = self.main_ball.width() / 2 + self.width() / 2 + 5 
            # 最大半径 = 缩小为 120，防止脱离太远
            max_radius = int(self.skin_config.get("layout", {}).get("max_drag_radius", 145))
            clamped_dist = max(min_radius, min(dist, max_radius))
            
            if dist != 0:
                self.angle = math.atan2(dy, dx)
                self.radius = clamped_dist
                
                if hasattr(self, 'siblings'):
                    min_dist_between = self.width() + 5
                    self._resolve_overlap(mx, my, min_dist_between)
                
            self.update_position_from_main()
            event.accept()

    def _resolve_overlap(self, mx, my, min_dist, visited=None):
        if visited is None:
            visited = set()
        visited.add(self)
        
        for sib in self.siblings:
            if not sib.isVisible() or sib in visited:
                continue
            
            my_cx = mx + self.radius * math.cos(self.angle)
            my_cy = my + self.radius * math.sin(self.angle)
            
            sib_cx = mx + sib.radius * math.cos(sib.angle)
            sib_cy = my + sib.radius * math.sin(sib.angle)
            
            actual_dist = math.hypot(sib_cx - my_cx, sib_cy - my_cy)
            if actual_dist < min_dist:
                angle_diff = sib.angle - self.angle
                # Normalize between -pi and pi
                angle_diff = (angle_diff + math.pi) % (2 * math.pi) - math.pi
                if angle_diff == 0:
                    angle_diff = 0.01
                
                push_dir = 1 if angle_diff >= 0 else -1
                
                # Approximate the angle shift needed based on arc length = r * theta
                # min_dist is the chord, angle_needed ~ min_dist / radius
                angle_needed = (min_dist / max(sib.radius, 1)) * 1.1 # 增加10%余量防止精度问题
                
                sib.angle = self.angle + push_dir * angle_needed
                sib.update_position_from_main()
                sib._resolve_overlap(mx, my, min_dist, visited)

    def _color(self, value, fallback):
        if isinstance(value, (list, tuple)) and len(value) >= 3:
            alpha = value[3] if len(value) > 3 else 255
            return QColor(value[0], value[1], value[2], alpha)
        return fallback

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._is_dragging = False
            if not self._has_moved:
                self.clicked.emit()
            event.accept()
