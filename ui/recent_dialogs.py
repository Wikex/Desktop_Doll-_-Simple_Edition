from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QListWidget, QListWidgetItem, QCheckBox, QWidget)
from PySide6.QtCore import Qt

class ExcludedExtensionsDialog(QDialog):
    def __init__(self, excluded_extensions, parent=None):
        super().__init__(parent)
        self.setWindowTitle("排除记录 - 桌面人偶")
        # Removing Qt.Window to see if standard QDialog behavior works better with parent
        self.setFixedSize(320, 400)
        self.setStyleSheet("QDialog { background: white; } QLabel { color: #334155; font-size: 14px; }")
        
        # Ensure backward compatibility if it's a list
        if isinstance(excluded_extensions, list):
            self.excluded = {ext: True for ext in excluded_extensions}
        else:
            self.excluded = dict(excluded_extensions)
        
        layout = QVBoxLayout(self)
        
        desc = QLabel("勾选左侧选框表示禁止记录\n(例如: .tmp, .dat)")
        layout.addWidget(desc)
        
        input_layout = QHBoxLayout()
        self.input_ext = QLineEdit()
        self.input_ext.setPlaceholderText("输入后缀，例如 .txt")
        self.input_ext.setStyleSheet("padding: 6px; border: 1px solid #cbd5e1; border-radius: 4px; background-color: #f8fafc; color: #0f172a;")
        
        btn_add = QPushButton("添加")
        btn_add.setStyleSheet("padding: 6px 12px; background: #3b82f6; color: white; border-radius: 4px; font-weight: bold;")
        btn_add.clicked.connect(self._add_ext)
        
        input_layout.addWidget(self.input_ext)
        input_layout.addWidget(btn_add)
        layout.addLayout(input_layout)
        
        # Add Select All button
        btn_select_all = QPushButton("全选 / 取消全选")
        btn_select_all.setStyleSheet("padding: 6px; background: #e2e8f0; color: #334155; border-radius: 4px; font-weight: bold;")
        btn_select_all.clicked.connect(self._toggle_select_all)
        layout.addWidget(btn_select_all)
        
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("border: 1px solid #cbd5e1; border-radius: 4px;")
        layout.addWidget(self.list_widget)
        
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("确定")
        btn_ok.setStyleSheet("padding: 8px 20px; background: #3b82f6; color: white; border-radius: 4px; font-weight: bold;")
        btn_cancel = QPushButton("取消")
        btn_cancel.setStyleSheet("padding: 8px 20px; background: #e2e8f0; color: #334155; border-radius: 4px; font-weight: bold;")
        
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)
        
        self._refresh_list()

    def _toggle_select_all(self):
        all_checked = all(self.excluded.values()) if self.excluded else False
        for ext in self.excluded:
            self.excluded[ext] = not all_checked
        self._refresh_list()

    def _normalize_ext(self, ext):
        ext = ext.strip().lower()
        if ext and not ext.startswith('.'):
            ext = '.' + ext
        return ext

    def _add_ext(self):
        ext = self._normalize_ext(self.input_ext.text())
        if ext and ext not in self.excluded:
            self.excluded[ext] = True
            self._refresh_list()
        self.input_ext.clear()

    def _remove_ext(self, ext):
        if ext in self.excluded:
            del self.excluded[ext]
        self._refresh_list()

    def _on_checkbox_toggled(self, ext, state):
        self.excluded[ext] = state

    def _refresh_list(self):
        self.list_widget.clear()
        for ext in sorted(list(self.excluded.keys())):
            item = QListWidgetItem()
            self.list_widget.addItem(item)
            
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(5, 2, 5, 2)
            
            chk = QCheckBox(ext)
            chk.setChecked(self.excluded[ext])
            chk.toggled.connect(lambda state, e=ext: self._on_checkbox_toggled(e, state))
            
            btn_del = QPushButton("删除")
            btn_del.setStyleSheet("background-color: #ef4444; color: white; border-radius: 4px; padding: 4px 8px; font-weight: bold;")
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.clicked.connect(lambda checked, e=ext: self._remove_ext(e))
            
            row_layout.addWidget(chk)
            row_layout.addStretch()
            row_layout.addWidget(btn_del)
            
            item.setSizeHint(row_widget.sizeHint())
            self.list_widget.setItemWidget(item, row_widget)

    def get_excluded_extensions(self):
        return self.excluded


class ExtensionFilterDialog(QDialog):
    def __init__(self, unique_extensions, visible_extensions_dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("查看")
        # Ensure it inherits the parent's DPI correctly
        self.setFixedSize(300, 400)
        self.setStyleSheet("QDialog { background: white; } QLabel { color: #334155; font-size: 14px; }")
        
        self.result_dict = dict(visible_extensions_dict)
        
        layout = QVBoxLayout(self)
        
        desc = QLabel("取消勾选以在面板中隐藏该类型")
        layout.addWidget(desc)

        btn_select_all = QPushButton("全选 / 取消全选")
        btn_select_all.setStyleSheet("padding: 6px; background: #e2e8f0; color: #334155; border-radius: 4px; font-weight: bold;")
        btn_select_all.clicked.connect(self._toggle_select_all)
        layout.addWidget(btn_select_all)
        
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("border: 1px solid #cbd5e1; border-radius: 4px;")
        
        self.checkboxes = []
        for ext in sorted(list(unique_extensions)):
            item = QListWidgetItem()
            self.list_widget.addItem(item)
            
            chk = QCheckBox(ext if ext else "未知后缀")
            # If not explicitly false in dict, it's visible (default true)
            is_visible = self.result_dict.get(ext, True)
            chk.setChecked(is_visible)
            
            self.checkboxes.append((ext, chk))
            
            item.setSizeHint(chk.sizeHint())
            self.list_widget.setItemWidget(item, chk)
            
        layout.addWidget(self.list_widget)
        
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("确定")
        btn_ok.setStyleSheet("padding: 8px 20px; background: #3b82f6; color: white; border-radius: 4px; font-weight: bold;")
        btn_cancel = QPushButton("取消")
        btn_cancel.setStyleSheet("padding: 8px 20px; background: #e2e8f0; color: #334155; border-radius: 4px; font-weight: bold;")
        
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)

    def _toggle_select_all(self):
        if not self.checkboxes:
            return
        # If all checked, uncheck all. Else check all.
        all_checked = all(chk.isChecked() for ext, chk in self.checkboxes)
        for ext, chk in self.checkboxes:
            chk.setChecked(not all_checked)

    def accept(self):
        for ext, chk in self.checkboxes:
            self.result_dict[ext] = chk.isChecked()
        super().accept()

    def get_visibility_dict(self):
        return self.result_dict
