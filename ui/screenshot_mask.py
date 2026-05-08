from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QRect, QPoint, Signal, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QGuiApplication, QPixmap
from core.screenshot import get_all_visible_rects, get_uia_rect_at
from PIL import ImageGrab
import io
import win32api
import win32con


class ScreenshotMask(QWidget):
    finished = Signal()
    rect_selected = Signal(object)

    def __init__(self, mode="screenshot", background_image=None, all_rects_global=None, virtual_screen_left=None, virtual_screen_top=None):
        self.mode = mode
        super().__init__()
        self.setWindowTitle("\u684c\u9762\u4eba\u5076")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setWindowModality(Qt.ApplicationModal)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)

        self.start_pos_global = None
        self.current_pos_global = None
        self.is_dragging = False
        self.smart_rect_physical = None
        self.smart_rect_global = None
        self.background_image = background_image
        self.all_rects_global = all_rects_global if all_rects_global is not None else get_all_visible_rects()
        self.virtual_screen_left = virtual_screen_left if virtual_screen_left is not None else win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
        self.virtual_screen_top = virtual_screen_top if virtual_screen_top is not None else win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
        self.total_geometry = self._get_total_geometry()
        self.setGeometry(self.total_geometry)

    def showEvent(self, event):
        super().showEvent(event)
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.ActiveWindowFocusReason)

    def _get_total_geometry(self):
        total_rect = QRect()
        for screen in QGuiApplication.screens():
            total_rect = total_rect.united(screen.geometry())
        return total_rect

    def _screen_for_logical_point(self, point):
        screen = QGuiApplication.screenAt(point)
        return screen or QGuiApplication.primaryScreen()

    def _screen_for_physical_point(self, point):
        for screen in QGuiApplication.screens():
            geom = screen.geometry()
            ratio = screen.devicePixelRatio()
            left = int(round(geom.x() * ratio))
            top = int(round(geom.y() * ratio))
            right = int(round((geom.x() + geom.width()) * ratio))
            bottom = int(round((geom.y() + geom.height()) * ratio))
            if left <= point.x() <= right and top <= point.y() <= bottom:
                return screen
        return QGuiApplication.primaryScreen()

    def _logical_point_to_physical(self, point):
        screen = self._screen_for_logical_point(point)
        ratio = screen.devicePixelRatio()
        geom = screen.geometry()
        return QPoint(
            int(round((point.x() - geom.x()) * ratio + geom.x() * ratio)),
            int(round((point.y() - geom.y()) * ratio + geom.y() * ratio)),
        )

    def _physical_rect_to_logical(self, rect):
        center = rect.center()
        screen = self._screen_for_physical_point(center)
        ratio = screen.devicePixelRatio()
        geom = screen.geometry()
        return QRect(
            int(round((rect.x() - geom.x() * ratio) / ratio + geom.x())),
            int(round((rect.y() - geom.y() * ratio) / ratio + geom.y())),
            max(1, int(round(rect.width() / ratio))),
            max(1, int(round(rect.height() / ratio))),
        )

    def _logical_rect_to_physical(self, rect):
        center = rect.center()
        screen = self._screen_for_logical_point(center)
        ratio = screen.devicePixelRatio()
        geom = screen.geometry()
        return QRect(
            int(round((rect.x() - geom.x()) * ratio + geom.x() * ratio)),
            int(round((rect.y() - geom.y()) * ratio + geom.y() * ratio)),
            max(1, int(round(rect.width() * ratio))),
            max(1, int(round(rect.height() * ratio))),
        )

    def find_best_rect(self, global_pos):
        physical_pos = self._logical_point_to_physical(global_pos)
        screen_area = self.total_geometry.width() * self.total_geometry.height()
        
        uia_rect = None
        try:
            rect = get_uia_rect_at(physical_pos.x(), physical_pos.y())
            if rect:
                area = rect.width() * rect.height()
                if 20 < area < screen_area * 0.95:
                    uia_rect = rect
        except Exception:
            pass

        ew_rect = None
        for rect in self.all_rects_global:
            if rect.contains(physical_pos):
                if rect.width() * rect.height() > 20:
                    ew_rect = rect
                    break

        try:
            with open("screenshot_debug.log", "a") as f:
                f.write(f"Mouse: {physical_pos.x()}, {physical_pos.y()} | UIA: {uia_rect} | EW: {ew_rect}\n")
                f.write("All rects available:\n")
                for i, r in enumerate(self.all_rects_global[:10]):
                    f.write(f"  {i}: {r.x()}, {r.y()}, {r.width()}x{r.height()}\n")
        except:
            pass

        if uia_rect and ew_rect:
            self.last_uia_rect = uia_rect
            self.last_ew_rect = ew_rect
            if (ew_rect.width() * ew_rect.height()) < (uia_rect.width() * uia_rect.height()):
                return ew_rect
            return uia_rect
            
        self.last_uia_rect = uia_rect
        self.last_ew_rect = ew_rect
        return uia_rect or ew_rect

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        offset = self.total_geometry.topLeft()

        if self.background_image is not None and not hasattr(self, '_bg_pixmap'):
            try:
                byte_io = io.BytesIO()
                self.background_image.save(byte_io, format='PNG')
                self._bg_pixmap = QPixmap()
                self._bg_pixmap.loadFromData(byte_io.getvalue())
            except Exception:
                self._bg_pixmap = None

        if hasattr(self, '_bg_pixmap') and self._bg_pixmap is not None:
            painter.drawPixmap(self.rect(), self._bg_pixmap)
        else:
            painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        local_rect = None
        local_drag_rect = None

        if self.smart_rect_global and not self.is_dragging:
            local_rect = self.smart_rect_global.translated(-offset)

        if self.is_dragging and self.start_pos_global and self.current_pos_global:
            drag_rect_global = QRect(self.start_pos_global, self.current_pos_global).normalized()
            local_drag_rect = drag_rect_global.translated(-offset)

        from PySide6.QtGui import QRegion
        clip_region = QRegion(self.rect())
        if local_rect:
            clip_region = clip_region.subtracted(QRegion(local_rect))
        if local_drag_rect:
            clip_region = clip_region.subtracted(QRegion(local_drag_rect))

        painter.setClipRegion(clip_region)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))
        
        painter.setClipping(False)

        if local_rect:
            painter.setPen(QPen(QColor(255, 165, 0), 3))
            painter.drawRect(local_rect)

        if local_drag_rect:
            painter.setPen(QPen(QColor(0, 120, 215), 2))
            painter.drawRect(local_drag_rect)

        # Debug info
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        debug_text = f"Pos: {self.current_pos_global.x() if self.current_pos_global else 0}, {self.current_pos_global.y() if self.current_pos_global else 0}"
        if getattr(self, 'last_uia_rect', None):
            debug_text += f" | UIA: {self.last_uia_rect.width()}x{self.last_uia_rect.height()}"
        if getattr(self, 'last_ew_rect', None):
            debug_text += f" | EW: {self.last_ew_rect.width()}x{self.last_ew_rect.height()}"
        
        if self.current_pos_global:
            painter.drawText(self.current_pos_global.x() - offset.x() + 15, self.current_pos_global.y() - offset.y() + 15, debug_text)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_pos_global = event.globalPos()
            self.current_pos_global = event.globalPos()
            self.is_dragging = False
        elif event.button() == Qt.RightButton:
            self.close_mask()

    def mouseMoveEvent(self, event):
        self.current_pos_global = event.globalPos()
        if event.buttons() & Qt.LeftButton:
            if self.start_pos_global and (self.current_pos_global - self.start_pos_global).manhattanLength() > 5:
                self.is_dragging = True

        if not self.is_dragging:
            self.smart_rect_physical = self.find_best_rect(self.current_pos_global)
            self.smart_rect_global = self._physical_rect_to_logical(self.smart_rect_physical) if self.smart_rect_physical else None

        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.is_dragging:
                final_rect_global = QRect(self.start_pos_global, event.globalPos()).normalized()
                self.capture_rect(self._logical_rect_to_physical(final_rect_global))
            else:
                if self.smart_rect_physical:
                    self.capture_rect(self.smart_rect_physical)
                else:
                    self.close_mask()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close_mask()

    def capture_rect(self, qrect_global):
        if qrect_global.width() < 5 or qrect_global.height() < 5:
            if hasattr(self, 'close_mask'):
                self.close_mask()
            else:
                self.hide()
                self.finished.emit()
            return

        self.hide()
        if self.mode == "record":
            self.rect_selected.emit(qrect_global)
            if hasattr(self, 'close_mask'):
                self.close_mask()
            else:
                self.finished.emit()
        else:
            QTimer.singleShot(150, lambda: self._do_capture(qrect_global))

    def _do_capture(self, qrect_global):
        try:
            v_left = self.virtual_screen_left
            v_top = self.virtual_screen_top

            left = qrect_global.x() - v_left
            top = qrect_global.y() - v_top
            right = left + qrect_global.width()
            bottom = top + qrect_global.height()

            if self.background_image is not None:
                img = self.background_image.crop((left, top, right, bottom))
            else:
                img = ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)

            byte_io = io.BytesIO()
            img.save(byte_io, format='PNG')
            pixmap = QPixmap()
            pixmap.loadFromData(byte_io.getvalue())

            QApplication.clipboard().setPixmap(pixmap)
        except Exception as e:
            print(f"Capture failed: {e}")
        finally:
            self.finished.emit()
            self.close()

    def close_mask(self):
        self.finished.emit()
        self.close()
        self.deleteLater()
