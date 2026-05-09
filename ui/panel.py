import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                               QApplication, QLabel, QListWidgetItem, QPushButton, 
                               QAbstractItemView, QMessageBox, QDialog, QPlainTextEdit, QScrollArea, QToolTip)
from PySide6.QtCore import Qt, Signal, QTimer, QPoint
from PySide6.QtGui import QMouseEvent, QPixmap, QImage
import base64

class PinnedImageDialog(QWidget):
    def __init__(self, pixmap, item_data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("\u684c\u9762\u4eba\u5076") # 桌面人偶
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.original_pixmap = pixmap
        self.item_data = item_data
        self.scale_factor = 1.0
        
        self._is_dragging = False
        self._drag_start_pos = None

        self.setFixedSize(pixmap.size())

        screen = QApplication.primaryScreen()
        if screen:
            ratio = screen.devicePixelRatio()
            if ratio and ratio > 1.0:
                self.scale_factor = 1.0 / ratio
                self.setFixedSize(
                    max(1, int(pixmap.width() * self.scale_factor)),
                    max(1, int(pixmap.height() * self.scale_factor)),
                )
        
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
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_Hover, True)
        self.setStyleSheet("ClipboardItemWidget { background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; } ClipboardItemWidget:hover { border: 1px solid #3b82f6; }")
        
        self.hover_timer = QTimer(self)
        self.hover_timer.setSingleShot(True)
        self.hover_timer.setInterval(1000)
        self.hover_timer.timeout.connect(self.show_hover_effect)
        self.full_tooltip_text = ""
        
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
            self.full_tooltip_text = f"图片路径: {val}"
            self.label.setPixmap(pixmap)
            self.label.setStyleSheet("background: transparent;")
            
            img_container = QWidget()
            img_container.setStyleSheet("background: transparent;")
            img_layout = QHBoxLayout(img_container)
            img_layout.setContentsMargins(0, 0, 0, 0)
            img_layout.addStretch()
            img_layout.addWidget(self.label)
            img_layout.addStretch()
            
            layout.addWidget(img_container, 1)
        else:
            import re
            from PySide6.QtGui import QFontMetrics
            self.label = QLabel()
            
            # Check if text contains URL to style it differently
            if re.search(r'(https?://[^\s]+)', text):
                self.label.setStyleSheet("color: #2563eb; font-size: 13px; background: transparent; text-decoration: underline;")
                self.full_tooltip_text = text + "\n\n(提示: 按住 Ctrl + 左键 直接打开网址)"
            else:
                self.label.setStyleSheet("color: #000000; font-size: 13px; background: transparent;")
                self.full_tooltip_text = text + "\n\n(提示: 按住 Ctrl + 左键 快捷搜索此内容)"
            
            
            display_text = text.strip().replace('\r\n', '\n').replace('\r', '\n')
            display_text = display_text.replace('\n', '  ')
            
            fm = QFontMetrics(self.label.font())
            max_width = 190
            
            if fm.horizontalAdvance(display_text) <= max_width:
                final_text = display_text
            else:
                line1 = ""
                rem = ""
                for i in range(len(display_text), 0, -1):
                    if fm.horizontalAdvance(display_text[:i]) <= max_width:
                        line1 = display_text[:i]
                        rem = display_text[i:]
                        break
                
                if not line1:
                    line1 = display_text[:1]
                    rem = display_text[1:]
                    
                if fm.horizontalAdvance(rem) <= max_width:
                    final_text = line1 + "\n" + rem
                else:
                    line2 = fm.elidedText(rem, Qt.ElideRight, max_width)
                    final_text = line1 + "\n" + line2
                    
            self.label.setText(final_text)
            layout.addWidget(self.label, 1)
        
    def _on_delete_clicked(self):
        self.deleted.emit(self.full_item)
        
    def _on_view_clicked(self):
        self.viewed.emit(self.full_item)

    def enterEvent(self, event):
        self.hover_timer.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hover_timer.stop()
        QToolTip.hideText()
        super().leaveEvent(event)

    def show_hover_effect(self):
        if not self.full_tooltip_text:
            return
        from PySide6.QtGui import QCursor
        QToolTip.showText(QCursor.pos(), self.full_tooltip_text, self)

class ClipboardListWidget(QListWidget):
    order_changed = Signal(list)
    item_right_clicked = Signal(object)
    item_ctrl_left_clicked = Signal(object)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
    def dropEvent(self, event):
        super().dropEvent(event)
        new_order = [self.item(i).data(Qt.UserRole) for i in range(self.count())]
        self.order_changed.emit(new_order)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        item = self.itemAt(event.pos())
        if item:
            if event.button() == Qt.RightButton:
                self.item_right_clicked.emit(item)
            elif event.button() == Qt.LeftButton and (event.modifiers() & Qt.ControlModifier):
                self.item_ctrl_left_clicked.emit(item)

class Panel(QWidget):
    item_clicked = Signal(object)
    item_right_clicked = Signal(object)
    item_ctrl_left_clicked = Signal(object)
    item_deleted = Signal(object)
    viewed = Signal(object)
    history_cleared = Signal(str)
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
            self._has_been_dragged = True
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
        self.setStyleSheet("Panel { background-color: #f0f0f0; border: 1px solid #ccc; border-radius: 10px; } QLabel, QPushButton, QCheckBox, QListWidget { color: #000000; }")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        title_layout = QHBoxLayout()
        
        # Tracking Toggle Buttons (Text/Image)
        self.btn_track_text = QPushButton("存文")
        self.btn_track_text.setFixedSize(40, 28)
        self.btn_track_text.setCheckable(True)
        self.btn_track_text.setCursor(Qt.PointingHandCursor)
        self.btn_track_text.setToolTip("开启/暂停文字监听")
        self.btn_track_text.setStyleSheet("QPushButton { border: 1px solid #bbb; border-radius: 5px; background-color: #e0e0e0; font-weight: bold; font-size: 14px; color: #333; } QPushButton:checked { background-color: #4CAF50; color: white; border-color: #45a049; }")
        self.btn_track_text.clicked.connect(self.toggle_text_tracking_clicked.emit)
        
        self.btn_track_image = QPushButton("存图")
        self.btn_track_image.setFixedSize(40, 28)
        self.btn_track_image.setCheckable(True)
        self.btn_track_image.setCursor(Qt.PointingHandCursor)
        self.btn_track_image.setToolTip("开启/暂停图片监听")
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
        self.list_widget.item_right_clicked.connect(self._on_item_right_clicked)
        self.list_widget.item_ctrl_left_clicked.connect(self._on_item_ctrl_left_clicked)
        self.list_widget.order_changed.connect(self.history_reordered.emit)
        
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_filter_text = QPushButton("看文")
        self.btn_filter_text.setCheckable(True)
        self.btn_filter_text.setChecked(True)
        self.btn_filter_text.setToolTip("显示/隐藏文本记录")
        self.btn_filter_text.setStyleSheet("QPushButton { background-color: #e0e0e0; color: #333; border-radius: 5px; padding: 8px; font-weight: bold; } QPushButton:checked { background-color: #4CAF50; color: white; }")
        self.btn_filter_text.clicked.connect(self._apply_filter)
        
        self.btn_filter_image = QPushButton("看图")
        self.btn_filter_image.setCheckable(True)
        self.btn_filter_image.setChecked(True)
        self.btn_filter_image.setToolTip("显示/隐藏图片记录")
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
        if not self._current_history:
            return
            
        has_text = False
        has_image = False
        for item in self._current_history:
            if item.get("type") == "image":
                has_image = True
            else:
                has_text = True
            if has_text and has_image:
                break
                
        msg_box = QMessageBox(self)
        
        if has_text and has_image:
            msg_box.setWindowTitle("清空选项")
            msg_box.setText("请选择要清空的剪贴板内容：")
            
            btn_text = msg_box.addButton("仅清空文字", QMessageBox.ActionRole)
            btn_image = msg_box.addButton("仅清空图片", QMessageBox.ActionRole)
            btn_all = msg_box.addButton("文字和图片", QMessageBox.ActionRole)
            btn_cancel = msg_box.addButton("取消", QMessageBox.RejectRole)
            
            msg_box.exec()
            clicked = msg_box.clickedButton()
            
            if clicked == btn_text:
                self.history_cleared.emit("text")
            elif clicked == btn_image:
                self.history_cleared.emit("image")
            elif clicked == btn_all:
                self.history_cleared.emit("all")
        else:
            msg_box.setWindowTitle("确认清空")
            content_type = "图片" if has_image else "文字"
            msg_box.setText(f"确定要清空所有的{content_type}记录吗？")
            btn_yes = msg_box.addButton("是", QMessageBox.YesRole)
            btn_no = msg_box.addButton("否", QMessageBox.NoRole)
            msg_box.exec()
            if msg_box.clickedButton() == btn_yes:
                self.history_cleared.emit("all")

    def update_history(self, history_list):
        self._current_history = history_list
        self._sync_open_image_dialogs()
        self._apply_filter()

    def _sync_open_image_dialogs(self):
        if not hasattr(self, '_pinned_images'):
            return

        current_keys = set()
        for item in self._current_history:
            if isinstance(item, dict):
                current_keys.add((item.get("type"), item.get("value", "")))

        still_open = []
        for dialog in self._pinned_images:
            item_data = getattr(dialog, 'item_data', None)
            item_key = None
            if isinstance(item_data, dict):
                item_key = (item_data.get("type"), item_data.get("value", ""))

            if item_key is not None and item_key not in current_keys:
                dialog.close()
            elif dialog.isVisible():
                still_open.append(dialog)

        self._pinned_images = still_open

    def _apply_filter(self):
        show_text = self.btn_filter_text.isChecked()
        show_image = self.btn_filter_image.isChecked()
        
        v_scroll = self.list_widget.verticalScrollBar().value()
        
        # Stop UI updates during massive DOM manipulation to prevent stutter
        self.list_widget.setUpdatesEnabled(False)
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
                preview = text
                
            list_item = QListWidgetItem()
            list_item.setData(Qt.UserRole, item_data)
            self.list_widget.addItem(list_item)
            widget = ClipboardItemWidget(preview, item_data)
            widget.deleted.connect(self.item_deleted.emit)
            widget.viewed.connect(self._on_item_viewed)
            list_item.setSizeHint(widget.sizeHint())
            self.list_widget.setItemWidget(list_item, widget)
            
        self.list_widget.setUpdatesEnabled(True)
        # Restore scroll position after a short delay to allow layout update
        QTimer.singleShot(0, lambda: self.list_widget.verticalScrollBar().setValue(v_scroll))

    def _on_item_clicked(self, item):
        full_item = item.data(Qt.UserRole)
        QTimer.singleShot(10, lambda: self.item_clicked.emit(full_item))

    def _on_item_right_clicked(self, item):
        full_item = item.data(Qt.UserRole)
        QTimer.singleShot(10, lambda: self.item_right_clicked.emit(full_item))

    def _on_item_ctrl_left_clicked(self, item):
        full_item = item.data(Qt.UserRole)
        QTimer.singleShot(10, lambda: self.item_ctrl_left_clicked.emit(full_item))

    def update_position(self, ball_x, ball_y):
        if getattr(self, '_has_been_dragged', False):
            return
            
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
            
            pinned = PinnedImageDialog(pixmap, item_data)
            
            # Center it on screen
            from PySide6.QtGui import QGuiApplication
            screen_geo = QGuiApplication.primaryScreen().availableGeometry()
            pinned.move(screen_geo.center() - pinned.rect().center())
            pinned.show()
            pinned.item_data = item_data
            
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
