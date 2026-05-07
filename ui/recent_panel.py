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
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def dropEvent(self, event):
        super().dropEvent(event)
        new_order = [self.item(i).data(Qt.UserRole) for i in range(self.count())]
        self.order_changed.emit(new_order)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        item = self.itemAt(event.pos())
        if item and event.button() == Qt.RightButton:
            self.item_right_clicked.emit(item)

class RecentItemWidget(QWidget):
    def __init__(self, item_data, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("RecentItemWidget { background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; }")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
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
        path_label.setToolTip(path)
        
        from PySide6.QtGui import QFontMetrics
        name_fm = QFontMetrics(name_label.font())
        path_fm = QFontMetrics(path_label.font())
        
        # Max width 230 is safe because there are no action buttons, just the icon (24px) + layout margins
        elided_name = name_fm.elidedText(name, Qt.ElideRight, 230)
        elided_path = path_fm.elidedText(path, Qt.ElideRight, 230)
        
        name_label.setText(elided_name)
        path_label.setText(elided_path)
        
        text_layout.addWidget(name_label)
        text_layout.addWidget(path_label)
        
        layout.addLayout(text_layout, 1)

class RecentPanel(QWidget):
    item_clicked = Signal(object)
    item_right_clicked = Signal(object)
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
        self.setStyleSheet("RecentPanel { background-color: #f0f0f0; border: 1px solid #ccc; border-radius: 10px; } QWidget { color: #000000; }")
        
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
        reply = QMessageBox.question(self, "确认清空", 
            "确定要清空所有的最近使用记录吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.history_cleared.emit()

    def update_items(self, items):
        self._current_items = items
        self._apply_filter()

    def _apply_filter(self):
        v_scroll = self.list_widget.verticalScrollBar().value()
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
            list_item.setSizeHint(widget.sizeHint())
            self.list_widget.setItemWidget(list_item, widget)
            
        QTimer.singleShot(0, lambda: self.list_widget.verticalScrollBar().setValue(v_scroll))

    def _on_item_clicked(self, item):
        full_item = item.data(Qt.UserRole)
        QTimer.singleShot(10, lambda: self.item_clicked.emit(full_item))

    def _on_item_right_clicked(self, item):
        full_item = item.data(Qt.UserRole)
        QTimer.singleShot(10, lambda: self.item_right_clicked.emit(full_item))

    def update_position(self, ball_x, ball_y):
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
