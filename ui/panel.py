import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                                QApplication, QLabel, QListWidgetItem, QPushButton, 
                                QAbstractItemView, QMessageBox, QDialog, QPlainTextEdit, QScrollArea)
from PySide6.QtCore import Qt, Signal, QTimer, QPoint
from PySide6.QtGui import QMouseEvent, QPixmap, QImage
import base64



class PinnedImageDialog(QWidget):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("\u684c\u9762\u4eba\u5076") # 桌面人偶
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.original_pixmap = pixmap
        self.scale_factor = 1.0
        
        self._is_dragging = False
        self._drag_start_pos = None

        self.setFixedSize(pixmap.size())
        
        # Add a subtle shadow or just rely on OS. Since it's translucent, a slight border might help if there are transparent parts, but raw image is fine.
        # Add tooltip to tell users how to close
        self.setToolTip("\u6eda\u8f6e\u7f29\u653e\uff0c\u53cc\u51fb\u5173\u95ed") # 滚轮缩放，双击关闭

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        scaled_width = int(self.original_pixmap.width() * self.scale_factor)
        scaled_height = int(self.original_pixmap.height() * self.scale_factor)
        
        painter.drawPixmap(0, 0, scaled_width, scaled_height, self.original_pixmap)

    def wheelEvent(self, event):
        angle = event.angleDelta().y()
        
        # Calculate cursor position relative to the image before scaling
        cursor_x = event.position().x()
        cursor_y = event.position().y()
        
        old_scale = self.scale_factor
        
        if angle > 0:
            self.scale_factor *= 1.15
        else:
            self.scale_factor *= 0.85
            
        self.scale_factor = max(0.1, min(self.scale_factor, 15.0))
        
        if self.scale_factor != old_scale:
            scaled_width = int(self.original_pixmap.width() * self.scale_factor)
            scaled_height = int(self.original_pixmap.height() * self.scale_factor)
            
            self.setFixedSize(scaled_width, scaled_height)
            
            # Adjust window position so zoom focuses on mouse cursor
            # new_x = old_window_x - (cursor_x * (new_scale/old_scale) - cursor_x)
            new_x = self.x() - int(cursor_x * (self.scale_factor / old_scale) - cursor_x)
            new_y = self.y() - int(cursor_y * (self.scale_factor / old_scale) - cursor_y)
            self.move(new_x, new_y)
            
            self.update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self._drag_start_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.RightButton:
            self.close()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_dragging and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_start_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._is_dragging = False
            event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        self.close()
        
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

class DetailsDialog(QDialog):
    def __init__(self, item_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("剪贴板内容详情")
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowStaysOnTopHint)
        self.resize(500, 400)
        layout = QVBoxLayout(self)
        
        text = item_data.get("value", "") if isinstance(item_data, dict) else str(item_data)
        text_edit = QPlainTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(text)
        text_edit.setStyleSheet("font-size: 14px; color: #1e293b; background-color: #f8fafc; border: none;")
        layout.addWidget(text_edit)

class ClipboardItemWidget(QWidget):
    deleted = Signal(object)
    viewed = Signal(object)
    
    def __init__(self, text, full_item, parent=None):
        super().__init__(parent)
        self.full_item = full_item
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.btn_view = QPushButton("🔍") # View details
        self.btn_view.setFixedSize(24, 24)
        self.btn_view.setStyleSheet("""
            QPushButton { border-radius: 12px; background-color: #4CAF50; color: white; font-weight: bold; font-size: 12px; }
            QPushButton:hover { background-color: #45a049; }
        """)
        self.btn_view.setCursor(Qt.PointingHandCursor)
        self.btn_view.clicked.connect(self._on_view_clicked)
        layout.addWidget(self.btn_view)
        
        self.btn_delete = QPushButton("✖")
        self.btn_delete.setFixedSize(24, 24)
        self.btn_delete.setStyleSheet("""
            QPushButton { border-radius: 12px; background-color: #ff4c4c; color: white; font-weight: bold; font-size: 12px; }
            QPushButton:hover { background-color: #ff0000; }
        """)
        self.btn_delete.setCursor(Qt.PointingHandCursor)
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        layout.addWidget(self.btn_delete)
        
        if isinstance(full_item, dict) and full_item.get("type") == "image":
            val = full_item.get("value", "")
            image = QImage()
            import os
            if full_item.get("is_path", False) or (os.path.exists(val) and val.endswith('.png')):
                try:
                    with open(val, "rb") as f:
                        image.loadFromData(f.read(), "PNG")
                except Exception:
                    pass
            else:
                try:
                    data = base64.b64decode(val)
                    image.loadFromData(data, "PNG")
                except:
                    pass
            pixmap = QPixmap.fromImage(image)
            # 缩放至最大高度 60 像素，保持比例
            pixmap = pixmap.scaledToHeight(60, Qt.SmoothTransformation)
            self.label = QLabel()
            self.label.setPixmap(pixmap)
            self.label.setStyleSheet("background: transparent;")
            layout.addWidget(self.label, 1)
        else:
            self.label = QLabel(text)
            self.label.setStyleSheet("color: #000000; font-size: 13px; background: transparent;")
            layout.addWidget(self.label, 1)
        
    def _on_delete_clicked(self):
        self.deleted.emit(self.full_item)
        
    def _on_view_clicked(self):
        self.viewed.emit(self.full_item)

class ClipboardListWidget(QListWidget):
    order_changed = Signal(list)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        
    def dropEvent(self, event):
        super().dropEvent(event)
        new_order = [self.item(i).data(Qt.UserRole) for i in range(self.count())]
        self.order_changed.emit(new_order)

class Panel(QWidget):
    item_clicked = Signal(object)
    item_deleted = Signal(object)
    viewed = Signal(object)
    history_cleared = Signal()
    history_reordered = Signal(list)
    toggle_tracking_clicked = Signal()
    toggle_text_tracking_clicked = Signal()
    toggle_image_tracking_clicked = Signal()

    def __init__(self):
        super().__init__()
        self._is_dragging = False
        self._drag_start_pos = None
        self._relative_offset = None
        self._main_ball = None
        self._current_history = []
        self.init_ui()

    def set_main_ball(self, ball):
        self._main_ball = ball

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self._drag_start_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._is_dragging and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_start_pos)
            if self._main_ball:
                self._relative_offset = (self.x() - self._main_ball.x(), self.y() - self._main_ball.y())
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_dragging = False
            event.accept()

    def init_ui(self):
        self.setWindowTitle("\u684c\u9762\u4eba\u5076")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.setFixedSize(320, 420)
        self.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc; border-radius: 10px; color: #000000;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        title_layout = QHBoxLayout()
        
        # Tracking Toggle Buttons (Text/Image)
        self.btn_track_text = QPushButton("文")
        self.btn_track_text.setFixedSize(28, 28)
        self.btn_track_text.setCheckable(True)
        self.btn_track_text.setCursor(Qt.PointingHandCursor)
        self.btn_track_text.setStyleSheet("QPushButton { border: 1px solid #bbb; border-radius: 5px; background-color: #e0e0e0; font-weight: bold; font-size: 14px; color: #333; } QPushButton:checked { background-color: #4CAF50; color: white; border-color: #45a049; }")
        self.btn_track_text.clicked.connect(self.toggle_text_tracking_clicked.emit)
        
        self.btn_track_image = QPushButton("图")
        self.btn_track_image.setFixedSize(28, 28)
        self.btn_track_image.setCheckable(True)
        self.btn_track_image.setCursor(Qt.PointingHandCursor)
        self.btn_track_image.setStyleSheet("QPushButton { border: 1px solid #bbb; border-radius: 5px; background-color: #e0e0e0; font-weight: bold; font-size: 14px; color: #333; } QPushButton:checked { background-color: #2196F3; color: white; border-color: #1E88E5; }")
        self.btn_track_image.clicked.connect(self.toggle_image_tracking_clicked.emit)
        
        title = QLabel("剪贴板历史")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #333;")
        
        btn_close = QPushButton("×")
        btn_close.setFixedSize(24, 24)
        btn_close.setStyleSheet("QPushButton { background-color: transparent; border: none; color: #777; font-weight: bold; font-size: 18px; } QPushButton:hover { color: #ff0000; }")
        btn_close.clicked.connect(self.hide)
        
        title_layout.addWidget(self.btn_track_text)
        title_layout.addWidget(self.btn_track_image)
        title_layout.addStretch()
        title_layout.addWidget(title)
        title_layout.addStretch()
        title_layout.addWidget(btn_close)
        layout.addLayout(title_layout)
        self.list_widget = ClipboardListWidget()
        self.list_widget.setStyleSheet("QListWidget { border: 1px solid #ddd; background-color: white; color: #000000; }")
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.order_changed.connect(self.history_reordered.emit)
        
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_filter_text = QPushButton("\u6587")
        self.btn_filter_text.setCheckable(True)
        self.btn_filter_text.setChecked(True)
        self.btn_filter_text.setToolTip("显示文本")
        self.btn_filter_text.setStyleSheet("QPushButton { background-color: #e0e0e0; color: #333; border-radius: 5px; padding: 8px; font-weight: bold; } QPushButton:checked { background-color: #4CAF50; color: white; }")
        self.btn_filter_text.clicked.connect(self._apply_filter)
        
        self.btn_filter_image = QPushButton("\u56fe")
        self.btn_filter_image.setCheckable(True)
        self.btn_filter_image.setChecked(True)
        self.btn_filter_image.setToolTip("显示图片")
        self.btn_filter_image.setStyleSheet("QPushButton { background-color: #e0e0e0; color: #333; border-radius: 5px; padding: 8px; font-weight: bold; } QPushButton:checked { background-color: #2196F3; color: white; }")
        self.btn_filter_image.clicked.connect(self._apply_filter)

        self.btn_toggle_tracking = QPushButton("正在记录")
        self.btn_toggle_tracking.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; border-radius: 5px; padding: 8px; font-weight: bold; } QPushButton:hover { background-color: #45a049; }")
        self.btn_toggle_tracking.clicked.connect(self.toggle_tracking_clicked.emit)
        
        self.btn_clear_all = QPushButton("清空")
        self.btn_clear_all.setStyleSheet("QPushButton { background-color: #ff4c4c; color: white; border-radius: 5px; padding: 8px; font-weight: bold; } QPushButton:hover { background-color: #ff0000; }")
        self.btn_clear_all.clicked.connect(self._on_clear_all_clicked)
        
        bottom_layout.addWidget(self.btn_filter_text)
        bottom_layout.addWidget(self.btn_filter_image)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_toggle_tracking)
        bottom_layout.addWidget(self.btn_clear_all)
        
        layout.addWidget(self.list_widget)
        layout.addLayout(bottom_layout)

    def set_content_tracking_states(self, text_enabled, image_enabled):
        self.btn_track_text.setChecked(text_enabled)
        self.btn_track_image.setChecked(image_enabled)

    def set_tracking_enabled(self, enabled):
        if enabled:
            self.btn_toggle_tracking.setText("暂停记录")
            self.btn_toggle_tracking.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; border-radius: 5px; padding: 8px; font-weight: bold; } QPushButton:hover { background-color: #45a049; }")
        else:
            self.btn_toggle_tracking.setText("继续记录")
            self.btn_toggle_tracking.setStyleSheet("QPushButton { background-color: #888888; color: white; border-radius: 5px; padding: 8px; font-weight: bold; } QPushButton:hover { background-color: #777777; }")

    def _on_clear_all_clicked(self):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("确认")
        msg_box.setText("确定要清空所有剪贴板历史记录吗？")
        msg_box.setStyleSheet("QMessageBox { background-color: #ffffff; color: #000000; } QLabel { color: #000000; } QPushButton { color: #000000; }")
        btn_yes = msg_box.addButton("是", QMessageBox.YesRole)
        msg_box.addButton("否", QMessageBox.NoRole)
        msg_box.exec()
        if msg_box.clickedButton() == btn_yes:
            self.history_cleared.emit()

    def update_history(self, history_list):
        self._current_history = history_list
        self._apply_filter()

    def _apply_filter(self):
        show_text = self.btn_filter_text.isChecked()
        show_image = self.btn_filter_image.isChecked()
        
        self.list_widget.clear()
        for item_data in self._current_history:
            is_image = isinstance(item_data, dict) and item_data.get("type") == "image"
            
            if is_image and not show_image:
                continue
            if not is_image and not show_text:
                continue
                
            if is_image:
                preview = "[图片]"
            else:
                text = item_data.get("value", "") if isinstance(item_data, dict) else str(item_data)
                preview = text.replace('\\n', ' ')
                if len(preview) > 50: preview = preview[:50] + "..."
                
            list_item = QListWidgetItem()
            list_item.setData(Qt.UserRole, item_data)
            self.list_widget.addItem(list_item)
            widget = ClipboardItemWidget(preview, item_data)
            widget.deleted.connect(self.item_deleted.emit)
            widget.viewed.connect(self._on_item_viewed)
            list_item.setSizeHint(widget.sizeHint())
            self.list_widget.setItemWidget(list_item, widget)

    def _on_item_clicked(self, item):
        full_item = item.data(Qt.UserRole)
        QTimer.singleShot(10, lambda: self.item_clicked.emit(full_item))

    def update_position(self, ball_x, ball_y):
        if self._relative_offset is None:
            self._relative_offset = (-310, -200)
        
        new_x = ball_x + self._relative_offset[0]
        new_y = ball_y + self._relative_offset[1]
        
        screen_geo = QApplication.primaryScreen().availableGeometry()
        new_x = max(screen_geo.left(), min(new_x, screen_geo.right() - self.width()))
        new_y = max(screen_geo.top(), min(new_y, screen_geo.bottom() - self.height()))
        self.move(new_x, new_y)

    def _on_item_viewed(self, item_data):
        if isinstance(item_data, dict) and item_data.get("type") == "image":
            val = item_data.get("value", "")
            image = QImage()
            import os
            if item_data.get("is_path", False) or (os.path.exists(val) and val.endswith('.png')):
                try:
                    with open(val, "rb") as f:
                        image.loadFromData(f.read(), "PNG")
                except Exception:
                    pass
            else:
                import base64
                try:
                    data = base64.b64decode(val)
                    image.loadFromData(data, "PNG")
                except:
                    pass
            
            if image.isNull():
                self.item_deleted.emit(item_data)
                return
                
            pixmap = QPixmap.fromImage(image)
            
            if not hasattr(self, '_pinned_images'):
                self._pinned_images = []
            
            # Clean up closed ones
            self._pinned_images = [p for p in self._pinned_images if p.isVisible()]
            
            pinned = PinnedImageDialog(pixmap)
            
            # Center it on screen
            from PySide6.QtGui import QGuiApplication
            screen_geo = QGuiApplication.primaryScreen().availableGeometry()
            pinned.move(screen_geo.center() - pinned.rect().center())
            pinned.show()
            
            self._pinned_images.append(pinned)
        else:
            self._details_dialog = DetailsDialog(item_data, self)
            self._details_dialog.show()

    def toggle_visibility(self, x, y):
        if self.isVisible():
            self.hide()
        else:
            self.update_position(x, y)
            self.show()
            self.raise_()
