import os
from datetime import datetime

from PySide6.QtCore import Qt, QPoint, QRect, QSize, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.ocr import OcrUnavailableError, recognize_qimage
from ui.panel import PinnedImageDialog
from utils.logger import log_exception
from utils.path_helper import get_base_dir


TOOL_NAMES = {
    "pen": "画笔",
    "rect": "矩形",
    "arrow": "箭头",
    "text": "文字",
    "mosaic": "马赛克",
}


class ScreenshotCanvas(QWidget):
    changed = Signal()

    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.base_pixmap = pixmap
        self.annotations = []
        self.redo_stack = []
        self.current_annotation = None
        self.current_tool = "pen"
        self.current_color = QColor(239, 68, 68)
        self.current_width = 4
        self.setMouseTracking(True)
        self.setMinimumSize(QSize(pixmap.width(), pixmap.height()))
        self.setFixedSize(pixmap.size())

    def set_tool(self, tool):
        self.current_tool = tool

    def set_color(self, color):
        if color.isValid():
            self.current_color = QColor(color)

    def set_width(self, width):
        self.current_width = max(1, int(width))

    def can_undo(self):
        return bool(self.annotations)

    def can_redo(self):
        return bool(self.redo_stack)

    def undo(self):
        if self.annotations:
            self.redo_stack.append(self.annotations.pop())
            self.changed.emit()
            self.update()

    def redo(self):
        if self.redo_stack:
            self.annotations.append(self.redo_stack.pop())
            self.changed.emit()
            self.update()

    def clear_annotations(self):
        if self.annotations:
            self.redo_stack.extend(reversed(self.annotations))
            self.annotations.clear()
            self.changed.emit()
            self.update()

    def _append_annotation(self, annotation):
        self.annotations.append(annotation)
        self.redo_stack.clear()
        self.changed.emit()
        self.update()

    def _make_annotation(self, start, end=None):
        color = self.current_color
        width = self.current_width
        if self.current_tool == "pen":
            return {"type": "pen", "points": [start], "color": color, "width": width}
        if self.current_tool == "rect":
            return {"type": "rect", "start": start, "end": end or start, "color": color, "width": width}
        if self.current_tool == "arrow":
            return {"type": "arrow", "start": start, "end": end or start, "color": color, "width": width}
        if self.current_tool == "mosaic":
            return {"type": "mosaic", "start": start, "end": end or start, "block": max(8, width * 3)}
        return None

    def _draw_annotation(self, painter, annotation):
        typ = annotation.get("type")
        if typ in {"pen", "rect", "arrow", "text"}:
            pen = QPen(annotation.get("color", QColor(239, 68, 68)), annotation.get("width", 4))
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)

        if typ == "pen":
            points = annotation.get("points", [])
            for index in range(1, len(points)):
                painter.drawLine(points[index - 1], points[index])
        elif typ == "rect":
            rect = QRect(annotation["start"], annotation["end"]).normalized()
            painter.drawRect(rect)
        elif typ == "arrow":
            start = annotation["start"]
            end = annotation["end"]
            painter.drawLine(start, end)
            self._draw_arrow_head(painter, start, end, annotation.get("width", 4))
        elif typ == "text":
            painter.drawText(annotation["pos"], annotation.get("text", ""))
        elif typ == "mosaic":
            self._draw_mosaic(painter, annotation)

    def _draw_arrow_head(self, painter, start, end, width):
        import math

        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = math.hypot(dx, dy)
        if length < 1:
            return
        angle = math.atan2(dy, dx)
        size = max(10, int(width) * 4)
        points = []
        for offset in (math.pi * 0.82, -math.pi * 0.82):
            px = end.x() + size * math.cos(angle + offset)
            py = end.y() + size * math.sin(angle + offset)
            points.append(QPoint(int(px), int(py)))
        painter.setBrush(painter.pen().color())
        painter.drawPolygon(QPolygonF([end, points[0], points[1]]))

    def _draw_mosaic(self, painter, annotation):
        rect = QRect(annotation["start"], annotation["end"]).normalized().intersected(self.rect())
        if rect.width() < 2 or rect.height() < 2:
            return

        block = max(6, int(annotation.get("block", 12)))
        rendered = self.render_to_pixmap(include_current=False, before_annotation=annotation)
        source = rendered.copy(rect)
        small_w = max(1, rect.width() // block)
        small_h = max(1, rect.height() // block)
        pixelated = source.scaled(small_w, small_h, Qt.IgnoreAspectRatio, Qt.FastTransformation)
        pixelated = pixelated.scaled(rect.size(), Qt.IgnoreAspectRatio, Qt.FastTransformation)
        painter.drawPixmap(rect.topLeft(), pixelated)

    def render_to_pixmap(self, include_current=True, before_annotation=None):
        output = QPixmap(self.base_pixmap.size())
        output.fill(Qt.transparent)
        painter = QPainter(output)
        painter.drawPixmap(0, 0, self.base_pixmap)
        for annotation in self.annotations:
            if annotation is before_annotation:
                break
            self._draw_annotation(painter, annotation)
        if include_current and self.current_annotation:
            self._draw_annotation(painter, self.current_annotation)
        painter.end()
        return output

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.base_pixmap)
        for annotation in self.annotations:
            self._draw_annotation(painter, annotation)
        if self.current_annotation:
            self._draw_annotation(painter, self.current_annotation)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return

        pos = event.pos()
        if self.current_tool == "text":
            text, ok = QInputDialog.getText(self, "添加文字", "请输入标注文字：")
            if ok and text:
                self._append_annotation({
                    "type": "text",
                    "pos": pos,
                    "text": text,
                    "color": QColor(self.current_color),
                    "width": self.current_width,
                })
            return

        self.current_annotation = self._make_annotation(pos)
        self.update()

    def mouseMoveEvent(self, event):
        if not self.current_annotation or not (event.buttons() & Qt.LeftButton):
            return

        if self.current_annotation["type"] == "pen":
            self.current_annotation["points"].append(event.pos())
        else:
            self.current_annotation["end"] = event.pos()
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or not self.current_annotation:
            return

        if self.current_annotation["type"] != "pen":
            self.current_annotation["end"] = event.pos()
        annotation = self.current_annotation
        self.current_annotation = None
        self._append_annotation(annotation)


class ScreenshotEditor(QWidget):
    def __init__(self, pixmap, save_dir="", target_rect=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("进阶截图")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.save_dir = save_dir or os.path.join(get_base_dir(), "screenshots")
        self.pinned_windows = []
        self._is_dragging = False
        self._drag_start_pos = QPoint()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.toolbar_widget = QWidget()
        self.toolbar_widget.setStyleSheet(
            "QWidget { background-color: #0f172a; color: white; } "
            "QPushButton, QToolButton, QSpinBox { background-color: #f8fafc; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 6px; } "
            "QToolButton:checked { background-color: #bfdbfe; border-color: #2563eb; } "
            "QLabel { color: white; }"
        )
        toolbar = QHBoxLayout(self.toolbar_widget)
        toolbar.setContentsMargins(6, 4, 6, 4)
        toolbar.setSpacing(6)
        self.tool_buttons = {}
        for tool, label in TOOL_NAMES.items():
            btn = QToolButton()
            btn.setText(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked=False, t=tool: self._select_tool(t))
            toolbar.addWidget(btn)
            self.tool_buttons[tool] = btn

        self.btn_color = QPushButton("颜色")
        self.btn_color.clicked.connect(self._choose_color)
        toolbar.addWidget(self.btn_color)

        toolbar.addWidget(QLabel("粗细"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 24)
        self.width_spin.setValue(4)
        self.width_spin.valueChanged.connect(self.canvas_width_changed)
        toolbar.addWidget(self.width_spin)

        self.btn_undo = QPushButton("撤销")
        self.btn_undo.clicked.connect(self._undo)
        toolbar.addWidget(self.btn_undo)

        self.btn_redo = QPushButton("重做")
        self.btn_redo.clicked.connect(self._redo)
        toolbar.addWidget(self.btn_redo)

        self.btn_clear = QPushButton("清标注")
        self.btn_clear.clicked.connect(self._clear_annotations)
        toolbar.addWidget(self.btn_clear)

        toolbar.addStretch()

        self.btn_copy = QPushButton("复制")
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        toolbar.addWidget(self.btn_copy)

        self.btn_quick_save = QPushButton("快速保存")
        self.btn_quick_save.clicked.connect(self.quick_save)
        toolbar.addWidget(self.btn_quick_save)

        self.btn_save_as = QPushButton("另存为")
        self.btn_save_as.clicked.connect(self.save_as)
        toolbar.addWidget(self.btn_save_as)

        self.btn_pin = QPushButton("定图")
        self.btn_pin.clicked.connect(self.pin_to_desktop)
        toolbar.addWidget(self.btn_pin)

        self.btn_ocr = QPushButton("识别文字")
        self.btn_ocr.clicked.connect(self.run_ocr)
        toolbar.addWidget(self.btn_ocr)

        self.btn_close = QPushButton("×")
        self.btn_close.setFixedWidth(26)
        self.btn_close.clicked.connect(self.close)
        toolbar.addWidget(self.btn_close)

        layout.addWidget(self.toolbar_widget)

        self.canvas = ScreenshotCanvas(pixmap)
        self.canvas.changed.connect(self._refresh_undo_buttons)
        self.width_spin.valueChanged.connect(self.canvas.set_width)
        layout.addWidget(self.canvas)

        self.status = QLabel("")
        self.status.setStyleSheet("background-color: #0f172a; color: #cbd5e1; padding: 3px 6px;")
        layout.addWidget(self.status)
        self._select_tool("pen")
        self._refresh_undo_buttons()
        self._fit_to_capture(target_rect)

    def _fit_to_capture(self, target_rect):
        self.adjustSize()
        width = max(self.canvas.width(), self.toolbar_widget.sizeHint().width())
        height = self.toolbar_widget.sizeHint().height() + self.canvas.height() + self.status.sizeHint().height()
        self.setFixedSize(width, height)
        if target_rect:
            self.place_at_capture(target_rect)

    def place_at_capture(self, target_rect):
        screen = QApplication.screenAt(target_rect.center()) or QApplication.primaryScreen()
        screen_geo = screen.availableGeometry()
        toolbar_h = self.toolbar_widget.sizeHint().height()
        x = target_rect.x()
        y = target_rect.y() - toolbar_h
        x = max(screen_geo.left(), min(x, screen_geo.right() - self.width() + 1))
        y = max(screen_geo.top(), min(y, screen_geo.bottom() - self.height() + 1))
        self.move(x, y)

    def canvas_width_changed(self, value):
        self.canvas.set_width(value)

    def _select_tool(self, tool):
        self.canvas.set_tool(tool)
        for name, btn in self.tool_buttons.items():
            btn.setChecked(name == tool)

    def _choose_color(self):
        color = QColorDialog.getColor(self.canvas.current_color, self, "选择标注颜色")
        if color.isValid():
            self.canvas.set_color(color)

    def _undo(self):
        self.canvas.undo()

    def _redo(self):
        self.canvas.redo()

    def _clear_annotations(self):
        self.canvas.clear_annotations()

    def _refresh_undo_buttons(self):
        self.btn_undo.setEnabled(self.canvas.can_undo())
        self.btn_redo.setEnabled(self.canvas.can_redo())

    def rendered_pixmap(self):
        return self.canvas.render_to_pixmap()

    def copy_to_clipboard(self):
        QApplication.clipboard().setPixmap(self.rendered_pixmap())
        self.status.setText("已复制到剪贴板")

    def _default_save_path(self):
        os.makedirs(self.save_dir, exist_ok=True)
        filename = datetime.now().strftime("Screenshot_%Y%m%d_%H%M%S.png")
        return os.path.join(self.save_dir, filename)

    def quick_save(self):
        path = self._default_save_path()
        if self.rendered_pixmap().save(path, "PNG"):
            self.status.setText(f"已保存：{path}")
        else:
            QMessageBox.warning(self, "保存失败", "无法保存截图。")

    def save_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存截图",
            self._default_save_path(),
            "PNG 图片 (*.png);;JPEG 图片 (*.jpg *.jpeg);;WebP 图片 (*.webp)",
        )
        if not path:
            return
        ext = os.path.splitext(path)[1].lower()
        fmt = "JPG" if ext in {".jpg", ".jpeg"} else "WEBP" if ext == ".webp" else "PNG"
        if self.rendered_pixmap().save(path, fmt):
            self.status.setText(f"已保存：{path}")
        else:
            QMessageBox.warning(self, "保存失败", "无法保存截图。")

    def pin_to_desktop(self):
        pinned = PinnedImageDialog(self.rendered_pixmap(), None)
        pinned.move(self.canvas.mapToGlobal(QPoint(0, 0)))
        pinned.show()
        self.pinned_windows.append(pinned)
        self.pinned_windows = [w for w in self.pinned_windows if w.isVisible()]
        self.status.setText("已定图到桌面")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.pos().y() <= self.toolbar_widget.height():
            self._is_dragging = True
            self._drag_start_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._is_dragging and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_start_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_dragging = False
            event.accept()

    def run_ocr(self):
        image = self.rendered_pixmap().toImage().convertToFormat(QImage.Format_ARGB32)
        try:
            text = recognize_qimage(image)
        except OcrUnavailableError as exc:
            QMessageBox.information(
                self,
                "OCR 不可用",
                f"{exc}\n\n第一版已预留 OCR 入口；安装 OCR 组件后可直接使用。",
            )
            return
        except Exception as exc:
            log_exception(f"OCR failed: {exc}")
            QMessageBox.warning(self, "OCR 失败", str(exc))
            return

        if not text:
            QMessageBox.information(self, "识别结果", "没有识别到文字。")
            return

        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "识别结果", text)
        self.status.setText("OCR 结果已复制到剪贴板")
