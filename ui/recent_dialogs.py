from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QListWidget, QListWidgetItem, QCheckBox)
from PySide6.QtCore import Qt

class ExcludedExtensionsDialog(QDialog):
    def __init__(self, excluded_extensions, parent=None):
        super().__init__(parent)
        self.setWindowTitle("排除记录")
        self.setFixedSize(300, 400)
        self.setStyleSheet("QDialog { background: white; } QLabel { color: #334155; font-size: 14px; }")
        
        self.excluded = set(excluded_extensions)
        
        layout = QVBoxLayout(self)
        
        desc = QLabel("以下后缀名的文件将不会被记录\n(例如: .tmp, .dat)")
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
        
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("border: 1px solid #cbd5e1; border-radius: 4px;")
        layout.addWidget(self.list_widget)
        
        btn_remove = QPushButton("删除选中项")
        btn_remove.setStyleSheet("padding: 6px; background: #ef4444; color: white; border-radius: 4px; font-weight: bold;")
        btn_remove.clicked.connect(self._remove_selected)
        layout.addWidget(btn_remove)
        
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

    def _normalize_ext(self, ext):
        ext = ext.strip().lower()
        if ext and not ext.startswith('.'):
            ext = '.' + ext
        return ext

    def _add_ext(self):
        ext = self._normalize_ext(self.input_ext.text())
        if ext and ext not in self.excluded:
            self.excluded.add(ext)
            self._refresh_list()
        self.input_ext.clear()

    def _remove_selected(self):
        for item in self.list_widget.selectedItems():
            ext = item.text()
            if ext in self.excluded:
                self.excluded.remove(ext)
        self._refresh_list()

    def _refresh_list(self):
        self.list_widget.clear()
        for ext in sorted(list(self.excluded)):
            self.list_widget.addItem(ext)

    def get_excluded_extensions(self):
        return list(self.excluded)


class ExtensionFilterDialog(QDialog):
    def __init__(self, unique_extensions, visible_extensions_dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("查看")
        self.setFixedSize(300, 400)
        self.setStyleSheet("QDialog { background: white; } QLabel { color: #334155; font-size: 14px; }")
        
        self.result_dict = dict(visible_extensions_dict)
        
        layout = QVBoxLayout(self)
        
        desc = QLabel("取消勾选以在面板中隐藏该类型")
        layout.addWidget(desc)
        
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

    def accept(self):
        for ext, chk in self.checkboxes:
            self.result_dict[ext] = chk.isChecked()
        super().accept()

    def get_visibility_dict(self):
        return self.result_dict
