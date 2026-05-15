import os
from datetime import datetime

from PySide6.QtCore import Qt, QPoint, QRect, QSize, Signal
from PySide6.QtGui import QColor, QFont, QImage, QKeySequence, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QTextEdit,
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

TOOL_ICONS = {
    "rect": "□",
    "arrow": "↗",
    "pen": "✎",
    "mosaic": "▦",
    "text": "T",
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
        self.text_editor = None
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
        self._finish_text_editor()
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
            font = QFont()
            font.setPointSize(annotation.get("font_size", 16))
            painter.setFont(font)
            rect = annotation.get("rect")
            if rect:
                painter.drawText(rect, Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop, annotation.get("text", ""))
            else:
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
            self._start_text_editor(pos)
            return

        self._finish_text_editor()
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

    def _start_text_editor(self, pos):
        self._finish_text_editor()
        editor = TextAnnotationEditor(QColor(self.current_color), self)
        editor.finished.connect(self._commit_text_annotation)
        x = min(max(0, pos.x()), max(0, self.width() - editor.width()))
        y = min(max(0, pos.y()), max(0, self.height() - editor.height()))
        editor.move(x, y)
        editor.show()
        editor.setFocusToText()
        self.text_editor = editor

    def _finish_text_editor(self):
        if self.text_editor:
            editor = self.text_editor
            self.text_editor = None
            editor.finish()

    def _cancel_text_editor(self):
        if self.text_editor:
            editor = self.text_editor
            self.text_editor = None
            editor.cancel()

    def _commit_text_annotation(self, annotation):
        self.text_editor = None
        if annotation.get("text"):
            self.annotations.append(annotation)
            self.redo_stack.clear()
            self.changed.emit()
            self.update()


class InlineTextEdit(QTextEdit):
    def keyPressEvent(self, event):
        owner = self.parentWidget()
        if event.key() == Qt.Key_Escape and owner:
            owner.cancel()
            event.accept()
            return
        if event.key() in {Qt.Key_Return, Qt.Key_Enter} and event.modifiers() & Qt.ControlModifier and owner:
            owner.finish()
            event.accept()
            return
        super().keyPressEvent(event)


class TextAnnotationEditor(QWidget):
    finished = Signal(dict)

    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        self.setFixedSize(170, 72)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.edit = InlineTextEdit(self)
        self.edit.setGeometry(9, 9, self.width() - 18, self.height() - 18)
        self.edit.setAcceptRichText(False)
        self.edit.setFontPointSize(16)
        self.edit.setStyleSheet(
            "QTextEdit {"
            "background: rgba(255, 255, 255, 18);"
            "border: 1px solid #f8fafc;"
            "color: #111827;"
            "padding: 2px;"
            "}"
        )

    def setFocusToText(self):
        self.edit.setFocus()

    def finish(self):
        text = self.edit.toPlainText().strip()
        annotation = {
            "type": "text",
            "rect": QRect(self.pos() + QPoint(9, 9), self.edit.size()),
            "text": text,
            "color": QColor(self.color),
            "width": 2,
            "font_size": 16,
        }
        self.finished.emit(annotation)
        self.close()

    def cancel(self):
        self.finished.emit({})
        self.close()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(37, 99, 235), 2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.rect().adjusted(8, 8, -8, -8))
        painter.setBrush(QColor(37, 99, 235))
        for point in (
            QPoint(self.width() // 2, 4),
            QPoint(4, self.height() // 2),
            QPoint(self.width() - 4, self.height() // 2),
            QPoint(4, self.height() - 4),
            QPoint(self.width() - 4, self.height() - 4),
        ):
            painter.drawEllipse(point, 5, 5)


class ScreenshotEditor(QWidget):
    def __init__(self, pixmap, save_dir="", target_rect=None, parent=None):
        super().__init__(parent)
        pixmap = self._display_pixmap_for_target(pixmap, target_rect)
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
        self.toolbar_widget.setObjectName("screenshotToolbar")
        self.toolbar_widget.setStyleSheet(
            "#screenshotToolbar { background-color: #f8fafc; border: 1px solid #2563eb; } "
            "QToolButton { background-color: transparent; color: #2f3337; border: 0; border-radius: 2px; padding: 0; font-size: 22px; } "
            "QToolButton:hover { background-color: #e5e7eb; } "
            "QToolButton:checked { background-color: #dbeafe; color: #1d4ed8; } "
            "QToolButton:disabled { color: #a3aab3; } "
            "QFrame { color: #c4c9d0; background-color: #c4c9d0; } "
            "QLabel { color: #4b5563; }"
        )
        toolbar = QHBoxLayout(self.toolbar_widget)
        toolbar.setContentsMargins(8, 6, 8, 6)
        toolbar.setSpacing(5)
        self.tool_buttons = {}
        for tool, label in TOOL_NAMES.items():
            btn = self._make_tool_button(TOOL_ICONS.get(tool, label), label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked=False, t=tool: self._select_tool(t))
            toolbar.addWidget(btn)
            self.tool_buttons[tool] = btn

        self._add_toolbar_separator(toolbar)

        self.btn_color = self._make_tool_button("■", "颜色")
        self.btn_color.setFixedSize(34, 32)
        self.btn_color.clicked.connect(self._choose_color)
        toolbar.addWidget(self.btn_color)

        self._add_toolbar_separator(toolbar)

        self.btn_undo = self._make_tool_button("↶", "撤销 Ctrl+Z")
        self.btn_undo.setToolTip("Ctrl+Z")
        self.btn_undo.clicked.connect(self._undo)
        toolbar.addWidget(self.btn_undo)

        self.btn_redo = self._make_tool_button("↷", "重做 Ctrl+Y")
        self.btn_redo.setToolTip("Ctrl+Y")
        self.btn_redo.clicked.connect(self._redo)
        toolbar.addWidget(self.btn_redo)

        self.btn_clear = self._make_tool_button("×", "清除标注")
        self.btn_clear.clicked.connect(self._clear_annotations)
        toolbar.addWidget(self.btn_clear)

        toolbar.addStretch()

        self.btn_pin = self._make_tool_button("⌖", "定图")
        self.btn_pin.clicked.connect(self.pin_to_desktop)
        toolbar.addWidget(self.btn_pin)

        self.btn_quick_save = self._make_tool_button("▣", "快速保存")
        self.btn_quick_save.clicked.connect(self.quick_save)
        toolbar.addWidget(self.btn_quick_save)

        self.btn_copy = self._make_tool_button("⧉", "复制")
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        toolbar.addWidget(self.btn_copy)

        self.btn_save_as = self._make_tool_button("▤", "另存为")
        self.btn_save_as.clicked.connect(self.save_as)
        toolbar.addWidget(self.btn_save_as)

        self.btn_ocr = self._make_tool_button("文", "识别文字")
        self.btn_ocr.clicked.connect(self.run_ocr)
        toolbar.addWidget(self.btn_ocr)

        self._add_toolbar_separator(toolbar)

        self.btn_close = self._make_tool_button("×", "关闭")
        self.btn_close.clicked.connect(self.close)
        toolbar.addWidget(self.btn_close)

        layout.addWidget(self.toolbar_widget)

        self.canvas = ScreenshotCanvas(pixmap)
        self.canvas.changed.connect(self._refresh_undo_buttons)
        layout.addWidget(self.canvas)

        self.status = QLabel("")
        self.status.setStyleSheet("background-color: #0f172a; color: #cbd5e1; padding: 3px 6px;")
        layout.addWidget(self.status)
        self._select_tool("pen")
        self._refresh_color_button()
        self._refresh_undo_buttons()
        self._fit_to_capture(target_rect)

    def _make_tool_button(self, text, tooltip):
        btn = QToolButton()
        btn.setText(text)
        btn.setToolTip(tooltip)
        btn.setFixedSize(34, 32)
        return btn

    def _add_toolbar_separator(self, toolbar):
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Plain)
        line.setFixedSize(1, 24)
        toolbar.addWidget(line)

    def _refresh_color_button(self):
        color = self.canvas.current_color.name()
        self.btn_color.setStyleSheet(
            "QToolButton {"
            "background-color: #f8fafc;"
            "border: 0;"
            "border-radius: 2px;"
            f"color: {color};"
            "font-size: 22px;"
            "}"
            "QToolButton:hover { background-color: #e5e7eb; }"
        )

    def _display_pixmap_for_target(self, pixmap, target_rect):
        if not target_rect or target_rect.width() <= 0 or target_rect.height() <= 0:
            return pixmap
        if pixmap.width() <= target_rect.width() and pixmap.height() <= target_rect.height():
            return pixmap
        return pixmap.scaled(
            target_rect.size(),
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation,
        )

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

    def _select_tool(self, tool):
        self.canvas.set_tool(tool)
        for name, btn in self.tool_buttons.items():
            btn.setChecked(name == tool)

    def _choose_color(self):
        color = QColorDialog.getColor(self.canvas.current_color, self, "选择标注颜色")
        if color.isValid():
            self.canvas.set_color(color)
            self._refresh_color_button()

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
        self.canvas._finish_text_editor()
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

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Undo):
            self._undo()
            event.accept()
            return
        if event.matches(QKeySequence.Redo):
            self._redo()
            event.accept()
            return
        super().keyPressEvent(event)

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
