import os
from datetime import datetime

from PySide6.QtCore import Qt, QPoint, QRect, QSize, Signal
from PySide6.QtGui import QColor, QFont, QImage, QKeySequence, QPainter, QPen, QPixmap, QPolygonF, QTextCharFormat, QTextDocument
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
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
    ocrCopyRequested = Signal()
    ocrExitRequested = Signal()

    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.base_pixmap = pixmap
        self.device_ratio = max(1.0, float(pixmap.devicePixelRatio()))
        self.logical_size = QSize(
            max(1, int(round(pixmap.width() / self.device_ratio))),
            max(1, int(round(pixmap.height() / self.device_ratio))),
        )
        self.annotations = []
        self.ocr_mode = False
        self.ocr_entries = []
        self.ocr_selected_indices = set()
        self.ocr_selecting = False
        self.ocr_selection_origin = QPoint()
        self.ocr_selection_rect = QRect()
        self.ocr_selection_mode = "replace"
        self.ocr_selection_base_indices = set()
        self.redo_stack = []
        self.current_annotation = None
        self.current_tool = "pen"
        self.current_color = QColor(239, 68, 68)
        self.current_width = 4
        self.current_text_size = 16
        self.text_editor = None
        self._editing_text_index = None
        self._editing_original_text = None
        self._dragging_text_index = None
        self._dragging_text_offset = QPoint()
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumSize(self.logical_size)
        self.setFixedSize(self.logical_size)

    def set_tool(self, tool):
        self.current_tool = tool

    def set_color(self, color):
        if color.isValid():
            self.current_color = QColor(color)

    def set_width(self, width):
        self.current_width = max(1, int(width))

    def set_text_size(self, size):
        self.current_text_size = max(8, min(72, int(size)))
        if self.text_editor:
            self.text_editor.set_font_size(self.current_text_size)

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
        self.clear_ocr()
        if self.annotations:
            self.redo_stack.extend(reversed(self.annotations))
            self.annotations.clear()
            self.changed.emit()
            self.update()

    def clear_ocr(self):
        self.ocr_mode = False
        self.ocr_entries.clear()
        self.ocr_selected_indices.clear()
        self.ocr_selecting = False
        self.ocr_selection_rect = QRect()
        self.ocr_selection_mode = "replace"
        self.ocr_selection_base_indices.clear()
        self.update()

    def set_ocr_entries(self, entries):
        self._finish_text_editor()
        self.current_annotation = None
        self.ocr_entries = []
        for source_index, entry in enumerate(entries):
            rect = QRect(
                int(round(entry.get("x", 0))),
                int(round(entry.get("y", 0))),
                max(1, int(round(entry.get("w", 0)))),
                max(1, int(round(entry.get("h", 0)))),
            ).intersected(self.rect())
            text = str(entry.get("text", "")).strip()
            if rect.isValid() and not rect.isEmpty() and text:
                self.ocr_entries.extend(self._split_ocr_entry_to_chars(entry, rect, text, source_index))
        self.ocr_selected_indices.clear()
        self.ocr_selection_rect = QRect()
        self.ocr_selecting = False
        self.ocr_selection_mode = "replace"
        self.ocr_selection_base_indices.clear()
        self.ocr_mode = bool(self.ocr_entries)
        self.update()

    def _split_ocr_entry_to_chars(self, entry, rect, text, source_index):
        chars = list(text)
        if not chars:
            return []
        char_entries = []
        left = rect.left()
        width = rect.width()
        for char_index, char in enumerate(chars):
            char_left = left + int(round(width * char_index / len(chars)))
            char_right = left + int(round(width * (char_index + 1) / len(chars))) - 1
            char_rect = QRect(
                char_left,
                rect.top(),
                max(1, char_right - char_left + 1),
                rect.height(),
            ).intersected(self.rect())
            if not char_rect.isValid() or char_rect.isEmpty():
                continue
            normalized = dict(entry)
            normalized["text"] = char
            normalized["rect"] = char_rect
            normalized["x"] = char_rect.x()
            normalized["y"] = char_rect.y()
            normalized["w"] = char_rect.width()
            normalized["h"] = char_rect.height()
            normalized["cy"] = char_rect.center().y()
            normalized["source_index"] = source_index
            normalized["char_index"] = char_index
            char_entries.append(normalized)
        return char_entries

    def selected_ocr_entries(self):
        if not self.ocr_mode:
            return []
        if not self.ocr_selected_indices:
            return list(self.ocr_entries)
        return [
            entry for index, entry in enumerate(self.ocr_entries)
            if index in self.ocr_selected_indices
        ]

    def _update_ocr_selection(self, rect):
        self._apply_ocr_selection(self._ocr_indices_in_rect(rect))

    def _ocr_indices_in_rect(self, rect):
        if rect.width() < 2 or rect.height() < 2:
            return set()
        return {
            index for index, entry in enumerate(self.ocr_entries)
            if rect.contains(entry["rect"].center())
        }

    def _apply_ocr_selection(self, indices):
        if self.ocr_selection_mode == "add":
            self.ocr_selected_indices = set(self.ocr_selection_base_indices) | set(indices)
        elif self.ocr_selection_mode == "remove":
            self.ocr_selected_indices = set(self.ocr_selection_base_indices) - set(indices)
        else:
            self.ocr_selected_indices = set(indices)

    def _ocr_selection_mode_from_modifiers(self, modifiers):
        if modifiers & Qt.AltModifier:
            return "remove"
        if modifiers & Qt.ControlModifier:
            return "add"
        return "replace"

    def _hit_ocr_entry(self, pos):
        for index in range(len(self.ocr_entries) - 1, -1, -1):
            if self.ocr_entries[index]["rect"].contains(pos):
                return index
        return None

    def _draw_ocr_overlay(self, painter):
        if not self.ocr_mode:
            return
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, False)
        normal_fill = QColor(37, 99, 235, 45)
        normal_border = QColor(37, 99, 235, 180)
        selected_fill = QColor(245, 158, 11, 70)
        selected_border = QColor(245, 158, 11, 230)
        for index, entry in enumerate(self.ocr_entries):
            rect = entry["rect"]
            selected = index in self.ocr_selected_indices
            painter.fillRect(rect, selected_fill if selected else normal_fill)
            painter.setPen(QPen(selected_border if selected else normal_border, 1))
            painter.drawRect(rect.adjusted(0, 0, -1, -1))
        if self.ocr_selecting and not self.ocr_selection_rect.isNull():
            painter.setBrush(QColor(37, 99, 235, 35))
            pen = QPen(QColor(37, 99, 235, 230), 1)
            pen.setStyle(Qt.DashLine)
            painter.setPen(pen)
            painter.drawRect(self.ocr_selection_rect.adjusted(0, 0, -1, -1))
        painter.restore()

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
            html = annotation.get("html", "")
            if rect and html:
                document = QTextDocument()
                document.setDocumentMargin(0)
                document.setDefaultFont(font)
                document.setDefaultStyleSheet(f"body {{ color: {annotation.get('color', QColor(239, 68, 68)).name()}; }}")
                document.setHtml(html)
                document.setTextWidth(rect.width())
                painter.save()
                painter.translate(rect.topLeft())
                document.drawContents(painter)
                painter.restore()
            elif rect:
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
        physical_rect = self._logical_to_physical_rect(rect)
        source = rendered.copy(physical_rect)
        source.setDevicePixelRatio(self.device_ratio)
        physical_block = max(1, int(round(block * self.device_ratio)))
        small_w = max(1, physical_rect.width() // physical_block)
        small_h = max(1, physical_rect.height() // physical_block)
        pixelated = source.scaled(small_w, small_h, Qt.IgnoreAspectRatio, Qt.FastTransformation)
        pixelated = pixelated.scaled(physical_rect.size(), Qt.IgnoreAspectRatio, Qt.FastTransformation)
        pixelated.setDevicePixelRatio(self.device_ratio)
        painter.drawPixmap(rect.topLeft(), pixelated)

    def _logical_to_physical_rect(self, rect):
        ratio = self.device_ratio
        return QRect(
            int(round(rect.x() * ratio)),
            int(round(rect.y() * ratio)),
            max(1, int(round(rect.width() * ratio))),
            max(1, int(round(rect.height() * ratio))),
        )

    def render_to_pixmap(self, include_current=True, before_annotation=None):
        output = QPixmap(self.base_pixmap.size())
        output.setDevicePixelRatio(self.device_ratio)
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
        self._draw_ocr_overlay(painter)

    def mousePressEvent(self, event):
        if self.ocr_mode:
            if event.button() == Qt.LeftButton:
                self.ocr_selecting = True
                self.ocr_selection_origin = event.pos()
                self.ocr_selection_rect = QRect(event.pos(), event.pos()).normalized()
                self.ocr_selection_mode = self._ocr_selection_mode_from_modifiers(event.modifiers())
                self.ocr_selection_base_indices = set(self.ocr_selected_indices)
                if self.ocr_selection_mode == "replace":
                    self.ocr_selected_indices.clear()
                self.update()
                event.accept()
            return

        if event.button() != Qt.LeftButton:
            return

        pos = event.pos()
        self._finish_text_editor()
        text_index = self._hit_text_annotation(pos)
        if text_index is not None:
            self._dragging_text_index = text_index
            self._dragging_text_offset = pos - self.annotations[text_index]["rect"].topLeft()
            event.accept()
            return

        if self.current_tool == "text":
            self._start_text_editor(pos)
            return

        self.current_annotation = self._make_annotation(pos)
        self.update()

    def mouseMoveEvent(self, event):
        if self.ocr_mode:
            if self.ocr_selecting and event.buttons() & Qt.LeftButton:
                self.ocr_selection_rect = QRect(self.ocr_selection_origin, event.pos()).normalized().intersected(self.rect())
                self._update_ocr_selection(self.ocr_selection_rect)
                self.update()
                event.accept()
            return

        if self._dragging_text_index is not None and event.buttons() & Qt.LeftButton:
            rect = QRect(self.annotations[self._dragging_text_index]["rect"])
            rect.moveTopLeft(event.pos() - self._dragging_text_offset)
            rect = self._clamp_rect_to_canvas(rect)
            self.annotations[self._dragging_text_index]["rect"] = rect
            self.changed.emit()
            self.update()
            event.accept()
            return

        if not self.current_annotation or not (event.buttons() & Qt.LeftButton):
            return

        if self.current_annotation["type"] == "pen":
            if event.modifiers() & Qt.ShiftModifier:
                self.current_annotation["points"] = [self.current_annotation["points"][0], event.pos()]
            else:
                self.current_annotation["points"].append(event.pos())
        else:
            self.current_annotation["end"] = event.pos()
        self.update()

    def mouseReleaseEvent(self, event):
        if self.ocr_mode:
            if event.button() == Qt.LeftButton and self.ocr_selecting:
                self.ocr_selecting = False
                if self.ocr_selection_rect.width() < 4 and self.ocr_selection_rect.height() < 4:
                    hit_index = self._hit_ocr_entry(event.pos())
                    self._apply_ocr_selection({hit_index} if hit_index is not None else set())
                    self.ocr_selection_rect = QRect()
                else:
                    self._update_ocr_selection(self.ocr_selection_rect)
                self.ocr_selection_base_indices.clear()
                self.update()
                event.accept()
            return

        if event.button() == Qt.LeftButton and self._dragging_text_index is not None:
            self._dragging_text_index = None
            event.accept()
            return

        if event.button() != Qt.LeftButton or not self.current_annotation:
            return

        if self.current_annotation["type"] == "pen" and event.modifiers() & Qt.ShiftModifier:
            self.current_annotation["points"] = [self.current_annotation["points"][0], event.pos()]
        elif self.current_annotation["type"] != "pen":
            self.current_annotation["end"] = event.pos()
        annotation = self.current_annotation
        self.current_annotation = None
        self._append_annotation(annotation)

    def mouseDoubleClickEvent(self, event):
        if self.ocr_mode:
            event.accept()
            return
        if event.button() == Qt.LeftButton:
            text_index = self._hit_text_annotation(event.pos())
            if text_index is not None:
                annotation = self.annotations.pop(text_index)
                self._start_text_editor(annotation["rect"].topLeft(), annotation=annotation, edit_index=text_index)
                self.changed.emit()
                self.update()
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        if self.ocr_mode:
            if event.matches(QKeySequence.Copy):
                self.ocrCopyRequested.emit()
                event.accept()
                return
            if event.key() == Qt.Key_Escape:
                self.ocrExitRequested.emit()
                event.accept()
                return
            event.accept()
            return
        super().keyPressEvent(event)

    def _start_text_editor(self, pos, annotation=None, edit_index=None):
        self._finish_text_editor()
        color = QColor(annotation.get("color", self.current_color)) if annotation else QColor(self.current_color)
        font_size = int(annotation.get("font_size", self.current_text_size)) if annotation else self.current_text_size
        text = annotation.get("text", "") if annotation else ""
        html = annotation.get("html", "") if annotation else ""
        editor = TextAnnotationEditor(color, font_size, self)
        editor.finished.connect(self._commit_text_annotation)
        self._editing_text_index = edit_index
        self._editing_original_text = annotation
        editor_pos = QPoint(pos)
        if annotation and annotation.get("rect"):
            content_rect = QRect(annotation["rect"])
            margin = editor.MARGIN
            editor.resize(content_rect.width() + margin * 2, content_rect.height() + margin * 2)
            editor_pos = content_rect.topLeft() - QPoint(margin, margin)
            editor.set_manual_size(bool(annotation.get("manual_size", False)))
        if text or html:
            editor.set_text(text, html=html)
        x = min(max(0, editor_pos.x()), max(0, self.width() - editor.width()))
        y = min(max(0, editor_pos.y()), max(0, self.height() - editor.height()))
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
        original = self._editing_original_text
        index = self._editing_text_index
        self._editing_original_text = None
        self._editing_text_index = None
        self.text_editor = None
        if annotation.get("__delete__"):
            self.redo_stack.clear()
            self.changed.emit()
            self.update()
            return
        if annotation.get("text"):
            if index is None or index > len(self.annotations):
                self.annotations.append(annotation)
            else:
                self.annotations.insert(index, annotation)
            self.redo_stack.clear()
            self.changed.emit()
            self.update()
        elif original:
            if index is None or index > len(self.annotations):
                self.annotations.append(original)
            else:
                self.annotations.insert(index, original)
            self.changed.emit()
            self.update()

    def _hit_text_annotation(self, pos):
        for index in range(len(self.annotations) - 1, -1, -1):
            annotation = self.annotations[index]
            if annotation.get("type") == "text" and annotation.get("rect") and annotation["rect"].contains(pos):
                return index
        return None

    def _clamp_rect_to_canvas(self, rect):
        clamped = QRect(rect)
        if clamped.left() < 0:
            clamped.moveLeft(0)
        if clamped.top() < 0:
            clamped.moveTop(0)
        if clamped.right() > self.width() - 1:
            clamped.moveRight(self.width() - 1)
        if clamped.bottom() > self.height() - 1:
            clamped.moveBottom(self.height() - 1)
        return clamped


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
        if owner:
            owner.apply_typing_format()
        super().keyPressEvent(event)
        if owner and (event.text() or event.key() in {Qt.Key_Return, Qt.Key_Enter}):
            owner.apply_typing_format()


class TextAnnotationEditor(QWidget):
    finished = Signal(dict)

    MIN_CONTENT_WIDTH = 20
    MIN_SIZE = QSize(MIN_CONTENT_WIDTH + 12, 28)
    MAX_SIZE = QSize(900, 500)
    MARGIN = 6
    HANDLE_SIZE = 8

    def __init__(self, color, font_size, parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        self.font_size = max(8, min(72, int(font_size)))
        self.manual_size = False
        self._resizing = False
        self._resize_handle = ""
        self._resize_start_pos = QPoint()
        self._resize_start_geo = QRect()
        self._autosizing = False
        self.resize(120, 36)
        self.setMinimumSize(self.MIN_SIZE)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.edit = InlineTextEdit(self)
        self.edit.setAcceptRichText(False)
        self.edit.setLineWrapMode(QTextEdit.NoWrap)
        self.edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.edit.document().setDocumentMargin(0)
        self._apply_default_font()
        self.apply_typing_format()
        self.edit.setStyleSheet(
            "QTextEdit {"
            "background: rgba(255, 255, 255, 20);"
            "border: 1px solid rgba(37, 99, 235, 150);"
            f"color: {self.color.name()};"
            "padding: 0;"
            "}"
        )
        self.edit.textChanged.connect(self._autosize_to_content)
        self.edit.document().documentLayout().documentSizeChanged.connect(lambda size: self._autosize_to_content())
        self._sync_edit_geometry()
        self._autosize_to_content()

    def setFocusToText(self):
        self.edit.setFocus()

    def set_text(self, text, html=""):
        if html:
            self.edit.setHtml(html)
        else:
            self.edit.setPlainText(text)
        self.apply_typing_format()
        self._autosize_to_content()

    def set_manual_size(self, enabled):
        self.manual_size = bool(enabled)
        self.edit.setLineWrapMode(QTextEdit.WidgetWidth if self.manual_size else QTextEdit.NoWrap)
        self._autosize_to_content()

    def set_font_size(self, size):
        self.font_size = max(8, min(72, int(size)))
        self.apply_typing_format(apply_to_selection=True)
        self._autosize_to_content()

    def _apply_default_font(self):
        font = QFont(self.edit.font())
        font.setPointSize(self.font_size)
        self.edit.setFont(font)
        self.edit.document().setDefaultFont(font)

    def _typing_char_format(self):
        fmt = QTextCharFormat()
        fmt.setFontPointSize(self.font_size)
        fmt.setForeground(self.color)
        return fmt

    def apply_typing_format(self, apply_to_selection=False):
        self._apply_default_font()
        fmt = self._typing_char_format()
        cursor = self.edit.textCursor()
        if apply_to_selection and cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
            self.edit.setTextCursor(cursor)
        self.edit.setCurrentCharFormat(fmt)

    def finish(self):
        text = self.edit.toPlainText().strip()
        annotation = {
            "type": "text",
            "rect": QRect(self.pos() + QPoint(self.MARGIN, self.MARGIN), self.edit.size()),
            "text": text,
            "html": self.edit.toHtml(),
            "color": QColor(self.color),
            "width": 2,
            "font_size": self.font_size,
            "manual_size": self.manual_size,
        }
        self.finished.emit(annotation)
        self.close()

    def cancel(self):
        self.finished.emit({})
        self.close()

    def _sync_edit_geometry(self):
        margin = self.MARGIN
        self.edit.setGeometry(margin, margin, max(1, self.width() - margin * 2), max(1, self.height() - margin * 2))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_edit_geometry()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_edit_geometry()
        self._autosize_to_content()

    def _autosize_to_content(self):
        if self._autosizing:
            return
        self._autosizing = True
        try:
            self._autosize_to_content_impl()
        finally:
            self._autosizing = False

    def _autosize_to_content_impl(self):
        text = self.edit.toPlainText() or " "
        parent = self.parentWidget()
        document = self.edit.document()

        if self.manual_size:
            content_width = max(1, self.width() - self.MARGIN * 2)
            document.setTextWidth(content_width)
            height = max(self.MIN_SIZE.height(), min(self.MAX_SIZE.height(), int(document.size().height()) + self.MARGIN * 2 + 4))
            if parent:
                height = min(height, max(self.MIN_SIZE.height(), parent.height() - self.y()))
            if self.height() != height:
                self.resize(self.width(), height)
            self._sync_edit_geometry()
            self.update()
            return

        document.setTextWidth(-1)
        desired_text_width = int(document.idealWidth()) + 6
        max_width = self.MAX_SIZE.width()
        if parent:
            max_width = min(max_width, max(self.MIN_SIZE.width(), parent.width() - self.x()))
        content_width = max(self.MIN_SIZE.width() - self.MARGIN * 2, min(max_width - self.MARGIN * 2, desired_text_width))
        document.setTextWidth(content_width)
        width = max(self.MIN_SIZE.width(), min(max_width, content_width + self.MARGIN * 2))
        height = max(self.MIN_SIZE.height(), min(self.MAX_SIZE.height(), int(document.size().height()) + self.MARGIN * 2 + 4))
        if parent:
            height = min(height, max(self.MIN_SIZE.height(), parent.height() - self.y()))
        if self.size() != QSize(width, height):
            self.resize(width, height)
        self._sync_edit_geometry()
        self.update()

    def _handle_points(self):
        mid_x = self.width() // 2
        mid_y = self.height() // 2
        return {
            "top_left": QPoint(1, 1),
            "top": QPoint(mid_x, 1),
            "top_right": QPoint(self.width() - 2, 1),
            "right": QPoint(self.width() - 2, mid_y),
            "bottom_right": QPoint(self.width() - 2, self.height() - 2),
            "bottom": QPoint(mid_x, self.height() - 2),
            "bottom_left": QPoint(1, self.height() - 2),
            "left": QPoint(1, mid_y),
        }

    def _handle_at(self, pos):
        half = self.HANDLE_SIZE
        for name, point in self._handle_points().items():
            rect = QRect(point.x() - half, point.y() - half, half * 2, half * 2)
            if rect.contains(pos):
                return name
        return ""

    def _bounded_geometry(self, geo):
        bounded = QRect(geo)
        bounded.setWidth(max(self.MIN_SIZE.width(), min(self.MAX_SIZE.width(), bounded.width())))
        bounded.setHeight(max(self.MIN_SIZE.height(), min(self.MAX_SIZE.height(), bounded.height())))

        parent = self.parentWidget()
        if parent:
            parent_rect = parent.rect()
            if bounded.left() < parent_rect.left():
                bounded.moveLeft(parent_rect.left())
            if bounded.top() < parent_rect.top():
                bounded.moveTop(parent_rect.top())
            if bounded.right() > parent_rect.right():
                bounded.setRight(parent_rect.right())
            if bounded.bottom() > parent_rect.bottom():
                bounded.setBottom(parent_rect.bottom())
            bounded.setWidth(max(self.MIN_SIZE.width(), bounded.width()))
            bounded.setHeight(max(self.MIN_SIZE.height(), bounded.height()))
        return bounded

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self._show_context_menu(event.globalPos())
            event.accept()
            return
        if event.button() == Qt.LeftButton:
            handle = self._handle_at(event.pos())
            if handle:
                self._resizing = True
                self._resize_handle = handle
                self._resize_start_pos = event.globalPos()
                self._resize_start_geo = QRect(self.geometry())
                self.set_manual_size(True)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            handle = self._handle_at(event.pos())
            if handle:
                self.set_manual_size(False)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            delta = event.globalPos() - self._resize_start_pos
            geo = QRect(self._resize_start_geo)

            if "left" in self._resize_handle:
                geo.setLeft(min(geo.left() + delta.x(), geo.right() - self.MIN_SIZE.width() + 1))
            if "right" in self._resize_handle:
                geo.setRight(max(geo.right() + delta.x(), geo.left() + self.MIN_SIZE.width() - 1))
            if "top" in self._resize_handle:
                geo.setTop(min(geo.top() + delta.y(), geo.bottom() - self.MIN_SIZE.height() + 1))
            if "bottom" in self._resize_handle:
                geo.setBottom(max(geo.bottom() + delta.y(), geo.top() + self.MIN_SIZE.height() - 1))

            self.setGeometry(self._bounded_geometry(geo))
            event.accept()
            return

        handle = self._handle_at(event.pos())
        if handle in {"left", "right"}:
            self.setCursor(Qt.SizeHorCursor)
        elif handle in {"top", "bottom"}:
            self.setCursor(Qt.SizeVerCursor)
        elif handle in {"top_left", "bottom_right"}:
            self.setCursor(Qt.SizeFDiagCursor)
        elif handle in {"top_right", "bottom_left"}:
            self.setCursor(Qt.SizeBDiagCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._resizing:
            self._resizing = False
            self._resize_handle = ""
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(37, 99, 235, 120), 1)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.rect().adjusted(1, 1, -2, -2))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(37, 99, 235, 210))
        for point in self._handle_points().values():
            painter.drawRect(
                point.x() - self.HANDLE_SIZE // 2,
                point.y() - self.HANDLE_SIZE // 2,
                self.HANDLE_SIZE,
                self.HANDLE_SIZE,
            )

    def _show_context_menu(self, global_pos):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #f8fafc; border: 1px solid #2563eb; padding: 4px; } "
            "QMenu::item { color: #111827; padding: 5px 22px 5px 8px; } "
            "QMenu::item:selected { background-color: #dbeafe; }"
        )
        delete_action = menu.addAction("删除文本框")
        chosen = menu.exec(global_pos)
        if chosen == delete_action:
            self.delete()

    def delete(self):
        self.finished.emit({"__delete__": True})
        self.close()


class ToolButton(QToolButton):
    rightClicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.rightClicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class PenSizeMenu(QMenu):
    sizeChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = 4
        self.setStyleSheet(
            "QMenu { background-color: #f8fafc; border: 1px solid #2563eb; padding: 5px; } "
            "QMenu::item { color: #111827; padding: 5px 24px 5px 8px; border-radius: 2px; } "
            "QMenu::item:selected { background-color: #dbeafe; } "
            "QLabel { color: #111827; font-size: 12px; }"
        )
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)
        self.preview = QLabel()
        self.preview.setFixedHeight(22)
        self.preview.setAlignment(Qt.AlignCenter)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.preview)
        layout.addWidget(self.label)
        from PySide6.QtWidgets import QWidgetAction
        header_action = QWidgetAction(self)
        header_action.setDefaultWidget(panel)
        self.addAction(header_action)
        self.addSeparator()
        self.size_actions = {}
        for size in (2, 4, 6, 8, 12, 16, 24):
            action = self.addAction(f"{size}px")
            action.triggered.connect(lambda checked=False, value=size: self.set_size(value))
            self.size_actions[size] = action
        self.set_size(self.value, emit=False)

    def set_size(self, value, emit=True):
        self.value = max(1, min(24, int(value)))
        self.label.setText(f"画笔 {self.value}px  滚轮调整")
        self.preview.setPixmap(self._preview_pixmap())
        for size, action in self.size_actions.items():
            prefix = "✓ " if size == self.value else "  "
            action.setText(f"{prefix}{size}px")
        if emit:
            self.sizeChanged.emit(self.value)

    def _preview_pixmap(self):
        pixmap = QPixmap(80, 22)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(239, 68, 68), self.value)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(8, 11, 72, 11)
        painter.end()
        return pixmap

    def wheelEvent(self, event):
        delta = 1 if event.angleDelta().y() > 0 else -1
        self.set_size(self.value + delta)
        event.accept()


class TextSizeMenu(QMenu):
    sizeChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = 16
        self.setStyleSheet(
            "QMenu { background-color: #f8fafc; border: 1px solid #2563eb; padding: 5px; } "
            "QMenu::item { color: #111827; padding: 5px 24px 5px 8px; border-radius: 2px; } "
            "QMenu::item:selected { background-color: #dbeafe; } "
            "QLabel { color: #111827; font-size: 12px; }"
        )
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 6, 8, 6)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)
        from PySide6.QtWidgets import QWidgetAction
        header_action = QWidgetAction(self)
        header_action.setDefaultWidget(panel)
        self.addAction(header_action)
        self.addSeparator()
        self.size_actions = {}
        for size in (12, 14, 16, 18, 20, 24, 28, 32, 40, 48):
            action = self.addAction(f"{size}px")
            action.triggered.connect(lambda checked=False, value=size: self.set_size(value))
            self.size_actions[size] = action
        self.set_size(self.value, emit=False)

    def set_size(self, value, emit=True):
        self.value = max(8, min(72, int(value)))
        self.label.setText(f"文字 {self.value}px  滚轮调整")
        for size, action in self.size_actions.items():
            prefix = "✓ " if size == self.value else "  "
            action.setText(f"{prefix}{size}px")
        if emit:
            self.sizeChanged.emit(self.value)

    def wheelEvent(self, event):
        delta = 1 if event.angleDelta().y() > 0 else -1
        self.set_size(self.value + delta)
        event.accept()


class ScreenshotEditor(QWidget):
    def __init__(self, pixmap, save_dir="", target_rect=None, parent=None):
        super().__init__(parent)
        pixmap = self._display_pixmap_for_target(pixmap, target_rect)
        self.setWindowTitle("进阶截图")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.save_dir = save_dir or os.path.join(get_base_dir(), "screenshots")
        self.pinned_windows = []
        self._is_dragging = False
        self._drag_start_pos = QPoint()
        self.pen_size_menu = None
        self.text_size_menu = None

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
            if tool == "pen":
                btn.setToolTip("画笔\n按住 Shift 画直线\n右键调整大小")
                btn.rightClicked.connect(self._show_pen_size_menu)
            elif tool == "text":
                btn.setToolTip("文字\n右键调整字号")
                btn.rightClicked.connect(self._show_text_size_menu)
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
        self.canvas.ocrCopyRequested.connect(self._copy_ocr_selection)
        self.canvas.ocrExitRequested.connect(self._exit_ocr_mode)
        layout.addWidget(self.canvas, 0, Qt.AlignLeft | Qt.AlignTop)

        self.status = QLabel("")
        self.status.setStyleSheet("background-color: #0f172a; color: #cbd5e1; padding: 3px 6px; border-radius: 4px;")
        layout.addWidget(self.status, 0, Qt.AlignLeft | Qt.AlignBottom)

        self._select_tool("pen")
        self._refresh_color_button()
        self._refresh_undo_buttons()
        self._fit_to_capture(target_rect)

    def _make_tool_button(self, text, tooltip):
        btn = ToolButton()
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
        ratio_x = pixmap.width() / max(1, target_rect.width())
        ratio_y = pixmap.height() / max(1, target_rect.height())
        ratio = max(1.0, ratio_x, ratio_y)
        display_pixmap = QPixmap(pixmap)
        display_pixmap.setDevicePixelRatio(ratio)
        return display_pixmap

    def _fit_to_capture(self, target_rect):
        self._resize_to_content()
        if target_rect:
            self.place_at_capture(target_rect)

    def _resize_to_content(self):
        self.adjustSize()
        width = max(self.canvas.width(), self.toolbar_widget.sizeHint().width())
        height = self.toolbar_widget.sizeHint().height() + self.canvas.height() + self.status.sizeHint().height()
        self.setFixedSize(width, height)

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
        if tool != "pen":
            self._hide_pen_size_menu()
        if tool != "text":
            self._hide_text_size_menu()

    def _show_pen_size_menu(self):
        self._select_tool("pen")
        if not self.pen_size_menu:
            self.pen_size_menu = PenSizeMenu(self)
            self.pen_size_menu.sizeChanged.connect(self._set_pen_size)
        self.pen_size_menu.set_size(self.canvas.current_width, emit=False)
        btn = self.tool_buttons.get("pen")
        if not btn:
            return
        below = btn.mapToGlobal(QPoint(0, btn.height()))
        above = btn.mapToGlobal(QPoint(0, -self.pen_size_menu.sizeHint().height()))
        screen = QApplication.screenAt(below) or QApplication.primaryScreen()
        screen_geo = screen.availableGeometry()
        pos = below
        if below.y() + self.pen_size_menu.sizeHint().height() > screen_geo.bottom():
            pos = above
        self.pen_size_menu.popup(pos)

    def _hide_pen_size_menu(self):
        if self.pen_size_menu:
            self.pen_size_menu.hide()

    def _set_pen_size(self, value):
        self.canvas.set_width(value)
        self.status.setText(f"画笔大小：{self.canvas.current_width}px")

    def _show_text_size_menu(self):
        self._select_tool("text")
        if not self.text_size_menu:
            self.text_size_menu = TextSizeMenu(self)
            self.text_size_menu.sizeChanged.connect(self._set_text_size)
        self.text_size_menu.set_size(self.canvas.current_text_size, emit=False)
        btn = self.tool_buttons.get("text")
        if not btn:
            return
        below = btn.mapToGlobal(QPoint(0, btn.height()))
        above = btn.mapToGlobal(QPoint(0, -self.text_size_menu.sizeHint().height()))
        screen = QApplication.screenAt(below) or QApplication.primaryScreen()
        screen_geo = screen.availableGeometry()
        pos = below
        if below.y() + self.text_size_menu.sizeHint().height() > screen_geo.bottom():
            pos = above
        self.text_size_menu.popup(pos)

    def _hide_text_size_menu(self):
        if self.text_size_menu:
            self.text_size_menu.hide()

    def _set_text_size(self, value):
        self.canvas.set_text_size(value)
        self.status.setText(f"文字大小：{self.canvas.current_text_size}px")

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
        if self.canvas.ocr_mode:
            self.btn_undo.setEnabled(False)
            self.btn_redo.setEnabled(False)
            return
        self.btn_undo.setEnabled(self.canvas.can_undo())
        self.btn_redo.setEnabled(self.canvas.can_redo())

    def rendered_pixmap(self):
        self.canvas._finish_text_editor()
        return self.canvas.render_to_pixmap()

    def copy_to_clipboard(self):
        QApplication.clipboard().setPixmap(self.rendered_pixmap())
        self.status.setText("已复制到剪贴板")

    def _set_ocr_mode_ui(self, enabled):
        for btn in self.tool_buttons.values():
            btn.setEnabled(not enabled)
        for btn in (
            self.btn_color,
            self.btn_undo,
            self.btn_redo,
            self.btn_clear,
            self.btn_pin,
            self.btn_quick_save,
            self.btn_copy,
            self.btn_save_as,
            self.btn_ocr,
        ):
            btn.setEnabled(not enabled)
        self._hide_pen_size_menu()
        self._hide_text_size_menu()
        if not enabled:
            self._refresh_undo_buttons()

    def _copy_ocr_selection(self):
        text = self._format_ocr_text(self.canvas.selected_ocr_entries())
        if text:
            QApplication.clipboard().setText(text)
            count = len(self.canvas.selected_ocr_entries())
            self.status.setText(f"已复制 OCR 文字：{count} 处")
        else:
            self.status.setText("没有可复制的 OCR 文字")

    def _exit_ocr_mode(self):
        self.canvas.clear_ocr()
        self._set_ocr_mode_ui(False)
        self.status.setText("已退出 OCR 文字复制模式")

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
        if self.canvas.ocr_mode:
            if event.matches(QKeySequence.Copy):
                self._copy_ocr_selection()
                event.accept()
                return
            if event.key() == Qt.Key_Escape:
                self._exit_ocr_mode()
                event.accept()
                return
            event.accept()
            return
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
        
        self.canvas.clear_ocr()
        self._set_ocr_mode_ui(False)
        self.status.setText("正在识别文字...")
        QApplication.processEvents() # Force UI update
        
        try:
            result = recognize_qimage(image)
        except OcrUnavailableError as exc:
            QMessageBox.information(
                self,
                "OCR 不可用",
                f"{exc}\n\n第一版已预留 OCR 入口；安装 OCR 组件后可直接使用。",
            )
            self.status.setText("就绪")
            return
        except Exception as exc:
            log_exception(f"OCR failed: {exc}")
            QMessageBox.warning(self, "OCR 失败", str(exc))
            self.status.setText("就绪")
            return

        if not result:
            QMessageBox.information(self, "识别结果", "没有识别到文字。")
            self.status.setText("就绪")
            return

        entries = []
        ratio = max(1.0, self.canvas.device_ratio)
        for res in result:
            box = res.get("box", []) if isinstance(res, dict) else []
            text = str(res.get("text", "") if isinstance(res, dict) else "").strip()
            if not box or not text:
                continue
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            x, y = min(xs) / ratio, min(ys) / ratio
            w, h = (max(xs) - min(xs)) / ratio, (max(ys) - min(ys)) / ratio
            if w < 2 or h < 2:
                continue
            entries.append({"text": text, "x": x, "y": y, "w": w, "h": h, "cy": y + h / 2})

        text = self._format_ocr_text(entries)
        if text:
            self.canvas.set_ocr_entries(entries)
            if not self.canvas.ocr_mode:
                QMessageBox.information(self, "识别结果", "没有识别到可用文字。")
                self.status.setText("就绪")
                return
            self._set_ocr_mode_ui(True)
            self.canvas.setFocus()
            self.status.setText(f"OCR 模式：拖选文字，Ctrl 追加，Alt 取消，Ctrl+C 复制，Esc 退出（{len(entries)} 处）")
        else:
            QMessageBox.information(self, "识别结果", "没有识别到可用文字。")
            self.status.setText("就绪")

    def _format_ocr_text(self, entries):
        if not entries:
            return ""
        ordered = sorted(entries, key=lambda item: (item["cy"], item["x"]))
        lines = []
        for item in ordered:
            if not lines:
                lines.append([item])
                continue
            current = lines[-1]
            avg_h = sum(part["h"] for part in current) / max(1, len(current))
            if abs(item["cy"] - current[0]["cy"]) <= max(8, avg_h * 0.65):
                current.append(item)
            else:
                lines.append([item])

        output = []
        for line in lines:
            line = sorted(line, key=lambda item: item["x"])
            output.append(self._format_ocr_line(line))
        return "\n".join(line for line in output if line).strip()

    def _format_ocr_line(self, line):
        segments = []
        chars = []
        current_source = None
        last_char_index = None

        def flush_chars():
            nonlocal chars, current_source, last_char_index
            if chars:
                segments.append("".join(chars))
            chars = []
            current_source = None
            last_char_index = None

        for item in line:
            text = item.get("text", "")
            if not text:
                continue
            source_index = item.get("source_index")
            char_index = item.get("char_index")
            if source_index is None or char_index is None:
                flush_chars()
                segments.append(text)
                continue
            if (
                current_source is not None
                and (source_index != current_source or char_index != last_char_index + 1)
            ):
                flush_chars()
            if current_source is None:
                current_source = source_index
            chars.append(text)
            last_char_index = char_index

        flush_chars()
        return " ".join(segment for segment in segments if segment).strip()
