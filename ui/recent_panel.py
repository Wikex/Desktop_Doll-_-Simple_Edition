import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                               QApplication, QLabel, QListWidgetItem, QPushButton, 
                               QAbstractItemView)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QIcon
from ui.recent_dialogs import ExcludedExtensionsDialog, ExtensionFilterDialog

class RecentListWidget(QListWidget):
    item_right_clicked = Signal(object)
    order_changed = Signal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def mimeData(self, items):
        mime_data = super().mimeData(items)
        from PySide6.QtCore import QUrl
        urls = []
        for item in items:
            item_data = item.data(Qt.UserRole)
            if isinstance(item_data, dict):
                path = item_data.get("path", "")
                if path and os.path.exists(path):
                    urls.append(QUrl.fromLocalFile(path))
        if urls:
            mime_data.setUrls(urls)
        return mime_data

    def startDrag(self, supportedActions):
        from PySide6.QtGui import QDrag
        from PySide6.QtCore import QPoint
        drag = QDrag(self)
        
        mime_data = self.mimeData(self.selectedItems())
        drag.setMimeData(mime_data)
        
        selected = self.selectedItems()
        if selected:
            rect = self.visualItemRect(selected[0])
            pixmap = self.viewport().grab(rect)
            drag.setPixmap(pixmap)
            drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))
            
        action = drag.exec(supportedActions, Qt.CopyAction)
        
        if action == Qt.MoveAction and drag.target() == self:
            for item in self.selectedItems():
                self.takeItem(self.row(item))

    def dragEnterEvent(self, event):
        if event.source() is self:
            event.setDropAction(Qt.MoveAction)
            super().dragEnterEvent(event)
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.source() is self:
            event.setDropAction(Qt.MoveAction)
            super().dragMoveEvent(event)
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.source() is self:
            event.setDropAction(Qt.MoveAction)
        super().dropEvent(event)
        new_order = [self.item(i).data(Qt.UserRole) for i in range(self.count())]
        self.order_changed.emit(new_order)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        item = self.itemAt(event.pos())
        if item and event.button() == Qt.RightButton:
            self.item_right_clicked.emit(item)

class RecentItemWidget(QWidget):
    deleted = Signal(object)

    def __init__(self, item_data, parent=None):
        super().__init__(parent)
        self.item_data = item_data
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_Hover, True)
        self.setStyleSheet("RecentItemWidget { background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; } RecentItemWidget:hover { border: 1px solid #3b82f6; }")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.btn_delete = QPushButton("✖")
        self.btn_delete.setFixedSize(24, 24)
        self.btn_delete.setStyleSheet("""
            QPushButton { border-radius: 12px; background-color: #ff4c4c; color: white; font-weight: bold; font-size: 12px; }
            QPushButton:hover { background-color: #ff0000; }
        """)
        self.btn_delete.setCursor(Qt.PointingHandCursor)
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        layout.addWidget(self.btn_delete)
        
        from PySide6.QtWidgets import QFileIconProvider
        from PySide6.QtCore import QFileInfo
        
        path = item_data.get("path", "")
        name = item_data.get("name", "")
        
        icon = QFileIconProvider().icon(QFileInfo(path))
        
        icon_label = QLabel()
        icon_label.setPixmap(icon.pixmap(24, 24))
        layout.addWidget(icon_label)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        name_label = QLabel()
        name_label.setStyleSheet("color: #000000; font-size: 13px; font-weight: bold; background: transparent;")
        
        path_label = QLabel()
        path_label.setStyleSheet("color: #666666; font-size: 11px; background: transparent;")
        
        self.hover_timer = QTimer(self)
        self.hover_timer.setSingleShot(True)
        self.hover_timer.setInterval(800)
        self.hover_timer.timeout.connect(self.show_hover_effect)
        
        from PySide6.QtGui import QFontMetrics
        name_fm = QFontMetrics(name_label.font())
        path_fm = QFontMetrics(path_label.font())
        
        # Max width 170 to account for delete button and icon and prevent clipping right border
        elided_name = name_fm.elidedText(name, Qt.ElideRight, 170)
        elided_path = path_fm.elidedText(path, Qt.ElideRight, 170)
        
        name_label.setText(elided_name)
        path_label.setText(elided_path)
        
        text_layout.addWidget(name_label)
        text_layout.addWidget(path_label)
        
        layout.addLayout(text_layout, 1)

    def enterEvent(self, event):
        self.hover_timer.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hover_timer.stop()
        from PySide6.QtWidgets import QToolTip
        QToolTip.hideText()
        super().leaveEvent(event)

    def show_hover_effect(self):
        path = self.item_data.get("path", "")
        if not path:
            return
            
        ext = self.item_data.get("ext", "").lower()
        from PySide6.QtWidgets import QToolTip
        from PySide6.QtGui import QCursor
        
        if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.webp'] and os.path.exists(path):
            from PySide6.QtGui import QImage, QPixmap
            from PySide6.QtCore import QBuffer, QIODevice
            image = QImage(path)
            if not image.isNull():
                image = image.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                pixmap = QPixmap.fromImage(image)
                buffer = QBuffer()
                buffer.open(QIODevice.WriteOnly)
                pixmap.save(buffer, "PNG")
                img_b64 = buffer.data().toBase64().data().decode('utf-8')
                html = f"<img src='data:image/png;base64,{img_b64}'><br>路径: {path}"
                QToolTip.showText(QCursor.pos(), html, self)
                return
                
        QToolTip.showText(QCursor.pos(), f"路径: {path}", self)

    def _on_delete_clicked(self):
        self.deleted.emit(self.item_data)

class RecentPanel(QWidget):
    item_clicked = Signal(object)
    item_right_clicked = Signal(object)
    item_deleted = Signal(object)
    toggle_tracking_clicked = Signal()
    excluded_extensions_changed = Signal(list)
    visibility_dict_changed = Signal(dict)
    history_cleared = Signal()
    history_reordered = Signal(list)

    def __init__(self):
        super().__init__()
        self._is_dragging = False
        self._drag_start_pos = None
        self._relative_offset = None
        self._main_ball = None
        self._current_items = []
        self._excluded_extensions = []
        self._visibility_dict = {}
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
        self.setWindowTitle("最近使用")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.setFixedSize(320, 420)
        self.setStyleSheet("RecentPanel { background-color: #f0f0f0; border: 1px solid #ccc; border-radius: 10px; } QLabel, QPushButton, QCheckBox, QListWidget { color: #000000; }")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        title_layout = QHBoxLayout()
        
        self.btn_excluded = QPushButton("禁止记录")
        self.btn_excluded.setFixedSize(70, 28)
        self.btn_excluded.setCursor(Qt.PointingHandCursor)
        self.btn_excluded.setStyleSheet("QPushButton { background-color: #ef4444; color: white; border-radius: 5px; font-weight: bold; font-size: 13px; } QPushButton:hover { background-color: #dc2626; }")
        self.btn_excluded.clicked.connect(self._on_excluded_clicked)
        
        title = QLabel("最近使用")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #333;")
        
        btn_close = QPushButton("×")
        btn_close.setFixedSize(24, 24)
        btn_close.setStyleSheet("QPushButton { background-color: transparent; border: none; color: #777; font-weight: bold; font-size: 18px; } QPushButton:hover { color: #ff0000; }")
        btn_close.clicked.connect(self.hide)
        
        title_layout.addWidget(self.btn_excluded)
        title_layout.addStretch()
        title_layout.addWidget(title)
        title_layout.addStretch()
        title_layout.addWidget(btn_close)
        layout.addLayout(title_layout)
        
        self.list_widget = RecentListWidget()
        self.list_widget.setStyleSheet("QListWidget { border: 1px solid #ddd; background-color: white; color: #000000; }")
        self.list_widget.itemDoubleClicked.connect(self._on_item_clicked)
        self.list_widget.item_right_clicked.connect(self._on_item_right_clicked)
        self.list_widget.order_changed.connect(self.history_reordered.emit)
        
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_filter = QPushButton("查看")
        self.btn_filter.setStyleSheet("QPushButton { background-color: #3b82f6; color: white; border-radius: 5px; padding: 6px 12px; font-weight: bold; } QPushButton:hover { background-color: #2563eb; }")
        self.btn_filter.clicked.connect(self._on_filter_clicked)
        
        self.btn_toggle_tracking = QPushButton("记录")
        self.btn_toggle_tracking.setFixedSize(60, 28)
        self.btn_toggle_tracking.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_tracking.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; border-radius: 5px; font-weight: bold; font-size: 13px; } QPushButton:hover { background-color: #45a049; }")
        self.btn_toggle_tracking.clicked.connect(self.toggle_tracking_clicked.emit)
        
        self.btn_clear_all = QPushButton("清空")
        self.btn_clear_all.setFixedSize(50, 28)
        self.btn_clear_all.setCursor(Qt.PointingHandCursor)
        self.btn_clear_all.setStyleSheet("QPushButton { background-color: #ff4c4c; color: white; border-radius: 5px; padding: 6px; font-weight: bold; font-size: 13px; } QPushButton:hover { background-color: #ff0000; }")
        self.btn_clear_all.clicked.connect(self._on_clear_clicked)
        
        bottom_layout.addWidget(self.btn_filter)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_toggle_tracking)
        bottom_layout.addWidget(self.btn_clear_all)
        
        layout.addWidget(self.list_widget)
        layout.addLayout(bottom_layout)

    def set_tracking_enabled(self, enabled):
        if enabled:
            self.btn_toggle_tracking.setText("记录中")
            self.btn_toggle_tracking.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; border-radius: 5px; font-weight: bold; font-size: 12px; } QPushButton:hover { background-color: #45a049; }")
        else:
            self.btn_toggle_tracking.setText("已暂停")
            self.btn_toggle_tracking.setStyleSheet("QPushButton { background-color: #888888; color: white; border-radius: 5px; font-weight: bold; font-size: 12px; } QPushButton:hover { background-color: #777777; }")

    def set_excluded_extensions(self, exts):
        self._excluded_extensions = exts

    def set_visibility_dict(self, visibility_dict):
        self._visibility_dict = visibility_dict
        self._apply_filter()

    def _on_excluded_clicked(self):
        dialog = ExcludedExtensionsDialog(self._excluded_extensions, self)
        if dialog.exec() == ExcludedExtensionsDialog.Accepted:
            new_exts = dialog.get_excluded_extensions()
            self._excluded_extensions = new_exts
            self.excluded_extensions_changed.emit(new_exts)

    def _on_filter_clicked(self):
        unique_exts = set(item.get("ext", "") for item in self._current_items)
        dialog = ExtensionFilterDialog(unique_exts, self._visibility_dict, self)
        if dialog.exec() == ExtensionFilterDialog.Accepted:
            new_dict = dialog.get_visibility_dict()
            self._visibility_dict = new_dict
            self.visibility_dict_changed.emit(new_dict)
            self._apply_filter()

    def _on_clear_clicked(self):
        from PySide6.QtWidgets import QMessageBox
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("确认清空")
        msg_box.setText("确定要清空所有的最近使用记录吗？")
        btn_yes = msg_box.addButton("是", QMessageBox.YesRole)
        btn_no = msg_box.addButton("否", QMessageBox.NoRole)
        msg_box.exec()
        if msg_box.clickedButton() == btn_yes:
            self.history_cleared.emit()

    def update_items(self, items):
        self._current_items = items
        self._apply_filter()

    def _apply_filter(self):
        v_scroll = self.list_widget.verticalScrollBar().value()
        
        self.list_widget.setUpdatesEnabled(False)
        self.list_widget.clear()
        
        for item_data in self._current_items:
            ext = item_data.get("ext", "")
            is_visible = self._visibility_dict.get(ext, True)
            if not is_visible:
                continue
                
            list_item = QListWidgetItem()
            list_item.setData(Qt.UserRole, item_data)
            self.list_widget.addItem(list_item)
            
            widget = RecentItemWidget(item_data)
            widget.deleted.connect(self.item_deleted.emit)
            list_item.setSizeHint(widget.sizeHint())
            self.list_widget.setItemWidget(list_item, widget)
            
        self.list_widget.setUpdatesEnabled(True)
        QTimer.singleShot(0, lambda: self.list_widget.verticalScrollBar().setValue(v_scroll))

    def _on_item_clicked(self, item):
        full_item = item.data(Qt.UserRole)
        QTimer.singleShot(10, lambda: self.item_clicked.emit(full_item))

    def _on_item_right_clicked(self, item):
        full_item = item.data(Qt.UserRole)
        QTimer.singleShot(10, lambda: self.item_right_clicked.emit(full_item))

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

    def toggle_visibility(self, x, y):
        if self.isVisible():
            self.hide()
        else:
            self.update_position(x, y)
            self.show()
            self.raise_()
