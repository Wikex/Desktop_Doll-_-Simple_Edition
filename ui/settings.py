import sys
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QWidget, QTabWidget,
                               QApplication, QMessageBox, QCheckBox, QSpinBox, QFileDialog, QComboBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QIcon, QCloseEvent
from utils.config import save_hotkeys, save_option, DEFAULT_OPTIONS, DEFAULT_HOTKEYS

class HotkeyLineEdit(QLineEdit):
    focus_in = Signal()
    focus_out = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMinimumHeight(34)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px;
                font-size: 14px;
                color: #1e293b;
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
            }
            QLineEdit:hover {
                border-color: #94a3b8;
                background-color: #ffffff;
            }
            QLineEdit:focus {
                border: 2px solid #3b82f6;
                background-color: #ffffff;
            }
        """)
        
    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        modifiers = event.modifiers()
        if key == Qt.Key_unknown: return

        mods = []
        if modifiers & Qt.ControlModifier: mods.append("ctrl")
        if modifiers & Qt.AltModifier: mods.append("alt")
        if modifiers & Qt.ShiftModifier: mods.append("shift")
        if modifiers & Qt.MetaModifier: mods.append("windows")

        key_str = ""
        if Qt.Key_A <= key <= Qt.Key_Z: key_str = chr(key).lower()
        elif Qt.Key_0 <= key <= Qt.Key_9: key_str = chr(key)
        elif key == Qt.Key_F1: key_str = "f1"
        elif key == Qt.Key_F2: key_str = "f2"
        elif key == Qt.Key_F3: key_str = "f3"
        elif key == Qt.Key_F4: key_str = "f4"
        elif key == Qt.Key_F5: key_str = "f5"
        elif key == Qt.Key_F6: key_str = "f6"
        elif key == Qt.Key_F7: key_str = "f7"
        elif key == Qt.Key_F8: key_str = "f8"
        elif key == Qt.Key_F9: key_str = "f9"
        elif key == Qt.Key_F10: key_str = "f10"
        elif key == Qt.Key_F11: key_str = "f11"
        elif key == Qt.Key_F12: key_str = "f12"
        elif key == Qt.Key_Space: key_str = "space"
        elif key == Qt.Key_Escape: key_str = "esc"
        elif key == Qt.Key_Return or key == Qt.Key_Enter: key_str = "enter"
        elif key == Qt.Key_Tab: key_str = "tab"
        elif key == Qt.Key_Backspace or key == Qt.Key_Delete: 
            self.setText("")
            return
            
        if not key_str and not mods: return
        if key_str: mods.append(key_str)
            
        hotkey_text = "+".join(mods)
        if key_str:
            self.setText(hotkey_text)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.focus_in.emit()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.focus_out.emit()

class HotkeyRow(QWidget):
    text_changed = Signal(str, str)
    focus_in = Signal()
    focus_out = Signal()
    
    def __init__(self, name, label_text, current_hotkey=""):
        super().__init__()
        self.name = name
        self.setProperty("hotkeyRow", True)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 6, 0, 6)
        self.layout.setSpacing(10)
        
        self.label = QLabel(label_text)
        self.label.setMinimumWidth(150)
        self.label.setStyleSheet("font-size: 14px; color: #111827; font-weight: bold;")
        
        self.input = HotkeyLineEdit()
        self.input.setText(current_hotkey)
        self.input.setPlaceholderText("按下快捷键")
        self.input.setAlignment(Qt.AlignCenter)
        self.input.textChanged.connect(self._on_text_changed)
        self.input.focus_in.connect(self.focus_in)
        self.input.focus_out.connect(self.focus_out)
        
        self.btn_clear = QPushButton("×")
        self.btn_clear.setFixedSize(24, 24)
        self.btn_clear.setStyleSheet("border-radius: 12px; background-color: #9ca3af; color: white; font-weight: bold; font-size: 14px;")
        self.btn_clear.clicked.connect(self.clear_input)
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        
        self.lbl_valid = QLabel("✓")
        self.lbl_valid.setFixedSize(24, 24)
        self.lbl_valid.setAlignment(Qt.AlignCenter)
        
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.input, 1)
        self.layout.addWidget(self.btn_clear)
        self.layout.addWidget(self.lbl_valid)
        self._update_validity(current_hotkey)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.setStyleSheet("QWidget[hotkeyRow=\"true\"] { background: #eff6ff; border: 1px solid #93c5fd; border-radius: 8px; }")

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.setStyleSheet("")
        self.input.style().unpolish(self.input)
        self.input.style().polish(self.input)
        
    def _on_text_changed(self, text):
        self._update_validity(text)
        self.text_changed.emit(self.name, text)

    def _update_validity(self, text):
        if text.strip():
            self.lbl_valid.setStyleSheet("border-radius: 12px; background-color: #22c55e; color: white; font-weight: bold; font-size: 14px;")
        else:
            self.lbl_valid.setStyleSheet("border-radius: 12px; background-color: #cbd5e1; color: white; font-weight: bold; font-size: 14px;")

    def clear_input(self):
        self.input.setText("")
        
    def set_hotkey(self, hk):
        # Disconnect temporarily to avoid double emitting during programmatic change
        self.input.blockSignals(True)
        self.input.setText(hk)
        self._update_validity(hk)
        self.input.blockSignals(False)

class SettingsDialog(QDialog):
    settings_saved = Signal(dict) # Emits updated options

    def __init__(self, options, hotkey_mgr, clipboard_mgr=None, recent_mgr=None, parent=None):
        super().__init__(parent)
        self.options = options
        self.hotkey_mgr = hotkey_mgr
        self.clipboard_mgr = clipboard_mgr
        self.recent_mgr = recent_mgr
        self.setWindowTitle("桌面人偶设置")
        self.setFixedSize(580, 480)
        self.setStyleSheet("""
            QDialog {
                background-color: #f1f5f9;
                color: #0f172a;
            }
            QWidget {
                color: #0f172a;
            }
            QMessageBox {
                background-color: #ffffff;
                color: #0f172a;
            }
            QLabel {
                color: #334155;
                font-size: 14px;
            }
            QCheckBox {
                font-size: 14px;
                color: #334155;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #cbd5e1;
                background-color: #ffffff;
            }
            QCheckBox::indicator:hover {
                border-color: #94a3b8;
            }
            QCheckBox::indicator:checked {
                background-color: #3b82f6;
                border-color: #3b82f6;
            }
            QTabWidget::pane {
                border: 1px solid #e2e8f0;
                background-color: #ffffff;
                border-radius: 6px;
            }
            QTabBar::tab {
                background: #f1f5f9;
                color: #64748b;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                border: 1px solid transparent;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:hover {
                color: #334155;
                background: #e2e8f0;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #0f172a;
                border: 1px solid #e2e8f0;
                border-bottom: 1px solid #ffffff;
            }
        """)
        
        self.original_hotkeys = dict(self.hotkey_mgr.hotkeys)
        self.current_hotkeys = dict(self.original_hotkeys)
        
        import copy
        self.original_options = copy.deepcopy(self.options)
        self.current_options = copy.deepcopy(self.options)
        
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        self.tabs = QTabWidget()
        
        # Helper for Restore Default Buttons
        def create_restore_btn(callback):
            btn = QPushButton("\u6062\u590d\u9ed8\u8ba4\u8bbe\u7f6e") # 恢复默认设置
            btn.setStyleSheet("padding: 6px 16px; font-size: 13px; border: 1px solid #cbd5e1; background-color: #f8fafc; color: #475569; border-radius: 6px; font-weight: bold;")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(callback)
            
            layout = QHBoxLayout()
            layout.addStretch()
            layout.addWidget(btn)
            return layout
        
        # --- Tab 1: General ---
        self.tab_general = QWidget()
        gen_layout = QVBoxLayout(self.tab_general)
        gen_layout.setSpacing(15)
        
        self.chk_hide_ball = QCheckBox("\u622a\u5c4f\u65f6\u81ea\u52a8\u9690\u85cf\u60ac\u6d6e\u7403") # 截屏时自动隐藏悬浮球
        self.chk_hide_ball.setChecked(self.current_options.get("hide_ball_when_screenshot", True))
        self.chk_hide_ball.stateChanged.connect(self._on_general_changed)
        gen_layout.addWidget(self.chk_hide_ball)
        
        gen_layout.addStretch()
        gen_layout.addLayout(create_restore_btn(self._restore_general_defaults))
        self.tabs.addTab(self.tab_general, "\u5e38\u89c4\u8bbe\u7f6e") # 常规设置
        
        # --- Tab 2: Clipboard ---
        self.tab_clipboard = QWidget()
        clip_layout = QVBoxLayout(self.tab_clipboard)
        clip_layout.setSpacing(15)
        
        self.chk_clip_tracking = QCheckBox("\u76d1\u542c\u526a\u8d34\u677f\u53d8\u5316") # 监听剪贴板变化
        self.chk_clip_tracking.setChecked(self.current_options.get("clipboard_tracking_enabled", True))
        self.chk_clip_tracking.stateChanged.connect(self._on_clipboard_changed)
        clip_layout.addWidget(self.chk_clip_tracking)
        
        limit_layout = QHBoxLayout()
        limit_label = QLabel("\u526a\u8d34\u677f\u5386\u53f2\u6700\u5927\u6761\u6570:") # 剪贴板历史最大条数:
        self.spin_limit = QSpinBox()
        self.spin_limit.setRange(1, 999)
        self.spin_limit.setValue(self.current_options.get("clipboard_max_items", 20))
        self.spin_limit.editingFinished.connect(self._on_clipboard_limit_editing_finished)
        self.spin_limit.setStyleSheet("padding: 4px 8px; font-size: 14px; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 6px; background-color: #ffffff;")
        limit_layout.addWidget(limit_label)
        limit_layout.addWidget(self.spin_limit)
        limit_layout.addStretch()
        clip_layout.addLayout(limit_layout)
        
        pic_layout = QHBoxLayout()
        pic_label = QLabel("\u56fe\u7247\u7f13\u5b58\u76ee\u5f55:") # 图片缓存目录:
        self.pic_path_input = QLineEdit(self.current_options.get("picture_save_path", ""))
        self.pic_path_input.setReadOnly(True)
        self.pic_path_input.setStyleSheet("padding: 6px 10px; border: 1px solid #cbd5e1; border-radius: 6px; background-color: #f8fafc; color: #64748b;")
        btn_browse_pic = QPushButton("\u6d4f\u89c8...") # 浏览...
        btn_browse_pic.setStyleSheet("padding: 6px 14px; background-color: #e2e8f0; color: #334155; border: 1px solid #cbd5e1; border-radius: 6px; font-weight: bold;")
        btn_browse_pic.clicked.connect(self._browse_pic_path)
        pic_layout.addWidget(pic_label)
        pic_layout.addWidget(self.pic_path_input)
        pic_layout.addWidget(btn_browse_pic)
        clip_layout.addLayout(pic_layout)
        
        pic_limit_layout = QHBoxLayout()
        pic_limit_label = QLabel("\u56fe\u7247\u7f13\u5b58\u6700\u5927\u5f20\u6570:") # 图片缓存最大张数:
        self.spin_pic_limit = QSpinBox()
        self.spin_pic_limit.setRange(1, 999)
        self.spin_pic_limit.setValue(self.current_options.get("clipboard_max_images", 20))
        self.spin_pic_limit.valueChanged.connect(self._on_clipboard_changed)
        self.spin_pic_limit.setStyleSheet("padding: 4px 8px; font-size: 14px; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 6px; background-color: #ffffff;")
        pic_limit_layout.addWidget(pic_limit_label)
        pic_limit_layout.addWidget(self.spin_pic_limit)
        pic_limit_layout.addStretch()
        clip_layout.addLayout(pic_limit_layout)
        clip_layout.addStretch()
        clip_layout.addLayout(create_restore_btn(self._restore_clipboard_defaults))
        self.tabs.addTab(self.tab_clipboard, "\u526a\u8d34\u677f\u8bbe\u7f6e") # 剪贴板设置
        
        # --- Tab 3: Video ---
        self.tab_video = QWidget()
        video_tab_layout = QVBoxLayout(self.tab_video)
        video_tab_layout.setSpacing(15)
        
        video_layout = QHBoxLayout()
        video_label = QLabel("\u5f55\u5c4f\u4fdd\u5b58\u76ee\u5f55:") # 录屏保存目录:
        self.video_path_input = QLineEdit(self.current_options.get("video_save_path", ""))
        self.video_path_input.setReadOnly(True)
        self.video_path_input.setStyleSheet("padding: 6px 10px; border: 1px solid #cbd5e1; border-radius: 6px; background-color: #f8fafc; color: #64748b;")
        btn_browse_video = QPushButton("\u6d4f\u89c8...") # 浏览...
        btn_browse_video.setStyleSheet("padding: 6px 14px; background-color: #e2e8f0; color: #334155; border: 1px solid #cbd5e1; border-radius: 6px; font-weight: bold;")
        btn_browse_video.clicked.connect(self._browse_video_path)
        video_layout.addWidget(video_label)
        video_layout.addWidget(self.video_path_input)
        video_layout.addWidget(btn_browse_video)
        video_tab_layout.addLayout(video_layout)
        
        format_layout = QHBoxLayout()
        format_label = QLabel("保存格式:")
        self.combo_video_format = QComboBox()
        self.combo_video_format.addItems(["mp4", "webm"])
        current_fmt = self.current_options.get("video_save_format", "mp4").lower()
        if current_fmt in ["mp4", "webm"]:
            self.combo_video_format.setCurrentText(current_fmt)
        else:
            self.combo_video_format.setCurrentText("mp4")
        self.combo_video_format.setStyleSheet("padding: 4px 8px; border: 1px solid #cbd5e1; border-radius: 6px; background-color: #ffffff; color: #0f172a;")
        self.combo_video_format.currentTextChanged.connect(self._on_video_format_changed)
        
        format_layout.addWidget(format_label)
        format_layout.addWidget(self.combo_video_format)
        format_layout.addStretch()
        video_tab_layout.addLayout(format_layout)
        
        video_tab_layout.addStretch()
        video_tab_layout.addLayout(create_restore_btn(self._restore_video_defaults))
        self.tabs.addTab(self.tab_video, "\u89c6\u9891\u8bbe\u7f6e") # 视频设置
        
        # --- Tab 4: Recent Files ---
        self.tab_recent = QWidget()
        recent_layout = QVBoxLayout(self.tab_recent)
        recent_layout.setSpacing(15)
        
        self.chk_recent_tracking = QCheckBox("监听最近使用变化")
        self.chk_recent_tracking.setChecked(self.current_options.get("recent_tracking_enabled", True))
        self.chk_recent_tracking.stateChanged.connect(self._on_recent_changed)
        recent_layout.addWidget(self.chk_recent_tracking)
        
        recent_limit_layout = QHBoxLayout()
        recent_limit_label = QLabel("最近使用最大条数:")
        self.spin_recent_limit = QSpinBox()
        self.spin_recent_limit.setRange(1, 999)
        self.spin_recent_limit.setValue(self.current_options.get("recent_max_items", 30))
        self.spin_recent_limit.editingFinished.connect(self._on_recent_limit_editing_finished)
        self.spin_recent_limit.setStyleSheet("padding: 4px 8px; font-size: 14px; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 6px; background-color: #ffffff;")
        recent_limit_layout.addWidget(recent_limit_label)
        recent_limit_layout.addWidget(self.spin_recent_limit)
        recent_limit_layout.addStretch()
        recent_layout.addLayout(recent_limit_layout)
        
        recent_btn_layout = QHBoxLayout()
        btn_manage_excluded = QPushButton("管理禁止记录...")
        btn_manage_excluded.setStyleSheet("padding: 6px 14px; background-color: #ef4444; color: white; border-radius: 6px; font-weight: bold;")
        btn_manage_excluded.clicked.connect(self._open_recent_excluded_dialog)
        
        recent_btn_layout.addWidget(btn_manage_excluded)
        recent_btn_layout.addStretch()
        recent_layout.addLayout(recent_btn_layout)
        
        recent_layout.addStretch()
        recent_layout.addLayout(create_restore_btn(self._restore_recent_defaults))
        self.tabs.addTab(self.tab_recent, "最近使用设置")
        
        # --- Tab 5: Hotkeys ---
        self.tab_hotkeys = QWidget()
        hk_layout = QVBoxLayout(self.tab_hotkeys)
        hk_layout.setSpacing(5)
        
        self.screenshot_row = HotkeyRow("screenshot", "\u7cfb\u7edf\u622a\u5c4f:", self.current_hotkeys.get("screenshot", "")) # 系统截屏:
        self.smart_screenshot_row = HotkeyRow("smart_screenshot", "\u667a\u80fd\u622a\u5c4f:", self.current_hotkeys.get("smart_screenshot", "")) # 智能截屏:
        self.record_row = HotkeyRow("record", "\u667a\u80fd\u5f55\u5c4f:", self.current_hotkeys.get("record", "")) # 智能录屏:
        self.search_row = HotkeyRow("search", "\u5feb\u6377\u641c\u7d22:", self.current_hotkeys.get("search", "")) # 快捷搜索:
        self.notebook_row = HotkeyRow("notebook", "\u663e\u793a/\u9690\u85cf\u8bb0\u4e8b\u672c:", self.current_hotkeys.get("notebook", "")) # 显示/隐藏记事本:
        self.clipboard_row = HotkeyRow("clipboard", "\u663e\u793a/\u9690\u85cf\u526a\u8d34\u677f:", self.current_hotkeys.get("clipboard", "")) # 显示/隐藏剪贴板:
        self.recent_row = HotkeyRow("recent", "显示/隐藏最近使用:", self.current_hotkeys.get("recent", ""))
        self.toggle_ball_row = HotkeyRow("toggle_ball", "\u663e\u793a/\u9690\u85cf\u60ac\u6d6e\u7403:", self.current_hotkeys.get("toggle_ball", "")) # 显示/隐藏悬浮球:
        
        for row in [self.screenshot_row, self.smart_screenshot_row, self.record_row, self.search_row, 
                    self.notebook_row, self.clipboard_row, self.recent_row, self.toggle_ball_row]:
            row.text_changed.connect(self.on_hotkey_changed)
            row.focus_in.connect(lambda: setattr(self.hotkey_mgr, 'paused', True))
            row.focus_out.connect(lambda: setattr(self.hotkey_mgr, 'paused', False))
            hk_layout.addWidget(row)
            
        hk_layout.addStretch()
        hk_layout.addLayout(create_restore_btn(self._restore_hotkey_defaults))
        self.tabs.addTab(self.tab_hotkeys, "\u5feb\u6377\u952e\u8bbe\u7f6e") # 快捷键设置
        
        # --- Tab 4: Features ---
        self.tab_features = QWidget()
        feat_main_layout = QHBoxLayout(self.tab_features)
        feat_main_layout.setSpacing(15)

        # Left Panel (System Features)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        lbl_sys = QLabel("\u7cfb\u7edf\u529f\u80fd") # 系统功能
        lbl_sys.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        self.sys_search = QLineEdit()
        self.sys_search.setPlaceholderText("\u641c\u7d22\u7cfb\u7edf\u529f\u80fd...") # 搜索系统功能...
        self.sys_search.setStyleSheet("padding: 6px; border: 1px solid #cbd5e1; border-radius: 4px; background: white;")
        self.sys_search.textChanged.connect(self._filter_sys_features)
        
        from PySide6.QtWidgets import QScrollArea
        sys_scroll = QScrollArea()
        sys_scroll.setWidgetResizable(True)
        sys_scroll.setStyleSheet("QScrollArea { border: 1px solid #e2e8f0; border-radius: 6px; background: white; }")
        
        self.sys_content = QWidget()
        self.sys_content.setStyleSheet("background: white;")
        self.sys_content_layout = QVBoxLayout(self.sys_content)
        self.sys_content_layout.setAlignment(Qt.AlignTop)
        
        self.features_map = [
            ("enable_clipboard_ball", "\u526a\u8d34\u677f\u5386\u53f2 (📋)"),
            ("enable_screenshot_ball", "\u7cfb\u7edf\u622a\u56fe (✂️)"),
            ("enable_notebook_ball", "\u8bb0\u4e8b\u672c (📝)"),
            ("enable_smart_screenshot_ball", "\u667a\u80fd\u622a\u56fe (🎯)"),
            ("enable_record_ball", "\u667a\u80fd\u5f55\u5c4f (🎥)"),
            ("enable_search_ball", "\u5feb\u6377\u641c\u7d22 (🔍)"),
            ("enable_recent_ball", "最近使用 (🕘)")
        ]
        
        self.feat_checkboxes = {}
        self.sys_feature_widgets = []
        for key, name in self.features_map:
            chk = QCheckBox(f"{name}") 
            chk.setChecked(self.current_options.get(key, True))
            chk.stateChanged.connect(self._on_feature_changed)
            self.sys_content_layout.addWidget(chk)
            self.feat_checkboxes[key] = chk
            self.sys_feature_widgets.append((name, chk))
            
        sys_scroll.setWidget(self.sys_content)
        
        left_layout.addWidget(lbl_sys)
        left_layout.addWidget(self.sys_search)
        left_layout.addWidget(sys_scroll)
        left_layout.addLayout(create_restore_btn(self._restore_feature_defaults))

        # Right Panel (Custom Features)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        lbl_custom = QLabel("\u81ea\u5b9a\u4e49\u8f6f\u4ef6\u5feb\u6377\u542f\u52a8") # 自定义软件快捷启动
        lbl_custom.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        self.custom_search = QLineEdit()
        self.custom_search.setPlaceholderText("\u641c\u7d22\u81ea\u5b9a\u4e49\u8f6f\u4ef6...") # 搜索自定义软件...
        self.custom_search.setStyleSheet("padding: 6px; border: 1px solid #cbd5e1; border-radius: 4px; background: white;")
        self.custom_search.textChanged.connect(self._filter_custom_features)
        
        custom_scroll = QScrollArea()
        custom_scroll.setWidgetResizable(True)
        custom_scroll.setStyleSheet("QScrollArea { border: 1px solid #e2e8f0; border-radius: 6px; background: white; }")
        
        self.custom_content = QWidget()
        self.custom_content.setStyleSheet("background: white;")
        self.custom_content_layout = QVBoxLayout(self.custom_content)
        self.custom_content_layout.setAlignment(Qt.AlignTop)
        self.custom_feature_widgets = []
        
        self._update_custom_apps_list()
        
        custom_scroll.setWidget(self.custom_content)
        
        btn_add_app = QPushButton("\u6dfb\u52a0\u65b0\u529f\u80fd") # 添加新功能
        btn_add_app.setStyleSheet("padding: 6px 14px; background-color: #3b82f6; color: white; border-radius: 6px; font-weight: bold;")
        btn_add_app.clicked.connect(self._add_custom_app_dialog)
        
        right_layout.addWidget(lbl_custom)
        right_layout.addWidget(self.custom_search)
        right_layout.addWidget(custom_scroll)
        right_layout.addWidget(btn_add_app)
        
        feat_main_layout.addWidget(left_panel)
        feat_main_layout.addWidget(right_panel)

        self.tabs.addTab(self.tab_features, "\u529f\u80fd\u7ba1\u7406") # 功能管理
        
        main_layout.addWidget(self.tabs)

    def _filter_sys_features(self, text):
        for name, widget in self.sys_feature_widgets:
            widget.setVisible(text.lower() in name.lower())

    def _filter_custom_features(self, text):
        for name, widget in self.custom_feature_widgets:
            widget.setVisible(text.lower() in name.lower())

    def _update_custom_apps_list(self):
        # Clear layout
        while self.custom_content_layout.count():
            item = self.custom_content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.custom_feature_widgets.clear()
        
        custom_apps = self.current_options.get("custom_apps", [])
        for i, app in enumerate(custom_apps):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(5, 5, 5, 5)
            
            chk = QCheckBox(app['name'])
            chk.setChecked(app.get('enabled', True))
            chk.setStyleSheet("font-size: 14px; color: #334155;")
            chk.setToolTip(app['path'])
            chk.stateChanged.connect(lambda state, idx=i: self._on_custom_app_toggled(idx, state))
            
            btn_del = QPushButton("×")
            btn_del.setFixedSize(20, 20)
            btn_del.setStyleSheet("QPushButton { border-radius: 10px; background-color: #f87171; color: white; font-weight: bold; } QPushButton:hover { background-color: #ef4444; }")
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.clicked.connect(lambda checked=False, idx=i: self._remove_custom_app_by_index(idx))
            
            row_layout.addWidget(chk)
            row_layout.addStretch()
            row_layout.addWidget(btn_del)
            
            self.custom_content_layout.addWidget(row)
            self.custom_feature_widgets.append((app['name'], row))

    def _on_custom_app_toggled(self, idx, state):
        from PySide6.QtCore import Qt
        custom_apps = self.current_options.get("custom_apps", [])
        if 0 <= idx < len(custom_apps):
            custom_apps[idx]['enabled'] = (state == Qt.Checked.value) or (state == Qt.Checked) or (state == 2)
            self.current_options["custom_apps"] = custom_apps
            self._auto_save_options()

    def _add_custom_app_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("\u6dfb\u52a0\u81ea\u5b9a\u4e49\u8f6f\u4ef6") # 添加自定义软件
        dialog.setFixedSize(400, 180)
        dialog.setStyleSheet("QDialog { background: white; } QLabel { color: #334155; font-size: 14px; }")
        
        layout = QVBoxLayout(dialog)
        
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("\u7a0b\u5e8f\u540d\u79f0:")) # 程序名称:
        input_name = QLineEdit()
        input_name.setStyleSheet("padding: 6px; border: 1px solid #cbd5e1; border-radius: 4px; background-color: #f8fafc; color: #0f172a;")
        name_layout.addWidget(input_name)
        layout.addLayout(name_layout)
        
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("\u7a0b\u5e8f\u8def\u5f84:")) # 程序路径:
        input_path = QLineEdit()
        input_path.setStyleSheet("padding: 6px; border: 1px solid #cbd5e1; border-radius: 4px; background-color: #f8fafc; color: #0f172a;")
        btn_browse = QPushButton("\u6d4f\u89c8...") # 浏览...
        btn_browse.setStyleSheet("padding: 6px 12px; background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 4px; color: #0f172a;")
        
        def do_browse():
            path, _ = QFileDialog.getOpenFileName(dialog, "\u9009\u62e9.exe", "", "Executable Files (*.exe)")
            if path:
                input_path.setText(path)
                from PySide6.QtCore import QFileInfo
                if not input_name.text():
                    input_name.setText(QFileInfo(path).baseName())
        btn_browse.clicked.connect(do_browse)
        
        path_layout.addWidget(input_path)
        path_layout.addWidget(btn_browse)
        layout.addLayout(path_layout)
        
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("\u786e\u5b9a") # 确定
        btn_ok.setStyleSheet("padding: 8px 20px; background: #3b82f6; color: white; border-radius: 4px; font-weight: bold;")
        btn_cancel = QPushButton("\u53d6\u6d88") # 取消
        btn_cancel.setStyleSheet("padding: 8px 20px; background: #e2e8f0; color: #334155; border-radius: 4px; font-weight: bold;")
        
        btn_ok.clicked.connect(dialog.accept)
        btn_cancel.clicked.connect(dialog.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)
        
        if dialog.exec() == QDialog.Accepted:
            name = input_name.text().strip()
            path = input_path.text().strip()
            if name and path:
                custom_apps = self.current_options.get("custom_apps", [])
                custom_apps.append({"name": name, "path": path})
                self.current_options["custom_apps"] = custom_apps
                self._update_custom_apps_list()
                self._auto_save_options()

    def _remove_custom_app_by_index(self, idx):
        custom_apps = self.current_options.get("custom_apps", [])
        if 0 <= idx < len(custom_apps):
            custom_apps.pop(idx)
            self.current_options["custom_apps"] = custom_apps
            self._update_custom_apps_list()
            self._auto_save_options()

    def _auto_save_options(self):
        for k, v in self.current_options.items():
            save_option(k, v)
        self.settings_saved.emit(self.current_options)

    def _on_general_changed(self):
        self.current_options["hide_ball_when_screenshot"] = self.chk_hide_ball.isChecked()
        self._auto_save_options()

    
    def _browse_pic_path(self):
        import os
        import shutil
        old_path = self.current_options.get("picture_save_path", "")
        if not old_path:
            from utils.path_helper import get_base_dir
            old_path = os.path.join(get_base_dir(), "picture")
            
        path = QFileDialog.getExistingDirectory(self, "\u9009\u62e9\u56fe\u7247\u4fdd\u5b58\u6587\u4ef6\u5939", self.pic_path_input.text())
        if path:
            if os.path.normpath(path) != os.path.normpath(old_path):
                if os.path.exists(old_path) and os.path.isdir(old_path) and os.listdir(old_path):
                    reply = QMessageBox.question(self, "\u6e05\u7406\u65e7\u76ee\u5f55", f"\u662f\u5426\u5220\u9664\u65e7\u76ee\u5f55\u4e0b\u7684\u6240\u6709\u6587\u4ef6\uff1f\n({old_path})", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    if reply == QMessageBox.Yes:
                        for filename in os.listdir(old_path):
                            filepath = os.path.join(old_path, filename)
                            try:
                                if os.path.isfile(filepath):
                                    os.remove(filepath)
                                elif os.path.isdir(filepath):
                                    shutil.rmtree(filepath)
                            except Exception:
                                pass
            self.pic_path_input.setText(path)
            self.current_options["picture_save_path"] = path
            self._auto_save_options()

    def _browse_video_path(self):
        import os
        import shutil
        old_path = self.current_options.get("video_save_path", "")
        if not old_path:
            from utils.path_helper import get_base_dir
            old_path = os.path.join(get_base_dir(), "video")
            
        path = QFileDialog.getExistingDirectory(self, "\u9009\u62e9\u5f55\u5c4f\u4fdd\u5b58\u6587\u4ef6\u5939", self.video_path_input.text())
        if path:
            if os.path.normpath(path) != os.path.normpath(old_path):
                if os.path.exists(old_path) and os.path.isdir(old_path) and os.listdir(old_path):
                    reply = QMessageBox.question(self, "\u6e05\u7406\u65e7\u76ee\u5f55", f"\u662f\u5426\u5220\u9664\u65e7\u76ee\u5f55\u4e0b\u7684\u6240\u6709\u6587\u4ef6\uff1f\n({old_path})", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    if reply == QMessageBox.Yes:
                        for filename in os.listdir(old_path):
                            filepath = os.path.join(old_path, filename)
                            try:
                                if os.path.isfile(filepath):
                                    os.remove(filepath)
                                elif os.path.isdir(filepath):
                                    shutil.rmtree(filepath)
                            except Exception:
                                pass
            self.video_path_input.setText(path)
            self.current_options["video_save_path"] = path
            self._auto_save_options()

    def _restore_general_defaults(self):
        self.chk_hide_ball.blockSignals(True)
        self.chk_hide_ball.setChecked(DEFAULT_OPTIONS.get("hide_ball_when_screenshot", True))
        self.chk_hide_ball.blockSignals(False)
        
        self.current_options["hide_ball_when_screenshot"] = DEFAULT_OPTIONS.get("hide_ball_when_screenshot", True)
        self._auto_save_options()

    def _restore_video_defaults(self):
        import os
        from utils.path_helper import get_base_dir
        
        default_video_path = os.path.join(get_base_dir(), "video")
        self.video_path_input.setText(default_video_path)
        self.current_options["video_save_path"] = default_video_path
        self.combo_video_format.setCurrentText("mp4")
        self.current_options["video_save_format"] = "mp4"
        self._auto_save_options()

    def _on_video_format_changed(self, text):
        self.current_options["video_save_format"] = text
        self._auto_save_options()

    def _on_clipboard_limit_editing_finished(self):
        new_val = self.spin_limit.value()
        old_val = self.current_options.get("clipboard_max_items", 20)
        
        if new_val == old_val:
            return
            
        if getattr(self, 'clipboard_mgr', None) is not None:
            current_history_len = len(self.clipboard_mgr.get_history())
            if new_val < current_history_len:
                reply = QMessageBox.question(self, "确认修改", 
                    "修改后的最大条数小于当前剪贴板历史条数，是否修改？\n修改后将删除最早的内容。",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No:
                    self.spin_limit.blockSignals(True)
                    self.spin_limit.setValue(old_val)
                    self.spin_limit.blockSignals(False)
                    return
                    
        self.current_options["clipboard_max_items"] = new_val
        self._auto_save_options()

    def _on_clipboard_changed(self):
        self.current_options["clipboard_tracking_enabled"] = self.chk_clip_tracking.isChecked()
        self.current_options["clipboard_max_images"] = self.spin_pic_limit.value()
        self._auto_save_options()

    def _restore_clipboard_defaults(self):
        import os
        from utils.path_helper import get_base_dir
        
        self.chk_clip_tracking.blockSignals(True)
        self.spin_limit.blockSignals(True)
        self.spin_pic_limit.blockSignals(True)
        
        val_tracking = DEFAULT_OPTIONS.get("clipboard_tracking_enabled", True)
        val_max = DEFAULT_OPTIONS.get("clipboard_max_items", 20)
        val_pic_max = DEFAULT_OPTIONS.get("clipboard_max_images", 20)
        default_pic_path = os.path.join(get_base_dir(), "picture")
        
        self.chk_clip_tracking.setChecked(val_tracking)
        self.spin_limit.setValue(val_max)
        self.spin_pic_limit.setValue(val_pic_max)
        self.pic_path_input.setText(default_pic_path)
        
        self.chk_clip_tracking.blockSignals(False)
        self.spin_limit.blockSignals(False)
        self.spin_pic_limit.blockSignals(False)
        
        self.current_options["clipboard_tracking_enabled"] = val_tracking
        self.current_options["clipboard_max_items"] = val_max
        self.current_options["clipboard_max_images"] = val_pic_max
        self.current_options["picture_save_path"] = default_pic_path
        self._auto_save_options()

    def _on_recent_limit_editing_finished(self):
        new_val = self.spin_recent_limit.value()
        old_val = self.current_options.get("recent_max_items", 30)
        
        if new_val == old_val:
            return
            
        if getattr(self, 'recent_mgr', None) is not None:
            current_history_len = len(self.recent_mgr.get_items())
            if new_val < current_history_len:
                reply = QMessageBox.question(self, "确认修改", 
                    "修改后的最大条数小于当前最近使用记录条数，是否修改？\n修改后将删除最早的内容。",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No:
                    self.spin_recent_limit.blockSignals(True)
                    self.spin_recent_limit.setValue(old_val)
                    self.spin_recent_limit.blockSignals(False)
                    return
                    
        self.current_options["recent_max_items"] = new_val
        self._auto_save_options()

    def _on_recent_changed(self):
        self.current_options["recent_tracking_enabled"] = self.chk_recent_tracking.isChecked()
        self.current_options["recent_max_items"] = self.spin_recent_limit.value()
        self._auto_save_options()

    def _open_recent_excluded_dialog(self):
        from ui.recent_dialogs import ExcludedExtensionsDialog
        current_excluded = self.current_options.get("recent_excluded_extensions", {})
        dialog = ExcludedExtensionsDialog(current_excluded, self)
        if dialog.exec() == ExcludedExtensionsDialog.Accepted:
            new_excluded = dialog.get_excluded_extensions()
            self.current_options["recent_excluded_extensions"] = new_excluded
            self._auto_save_options()
            if getattr(self, 'recent_mgr', None):
                self.recent_mgr.set_excluded_extensions(new_excluded)

    def _restore_recent_defaults(self):
        self.chk_recent_tracking.blockSignals(True)
        self.spin_recent_limit.blockSignals(True)
        
        val_tracking = DEFAULT_OPTIONS.get("recent_tracking_enabled", True)
        val_max = DEFAULT_OPTIONS.get("recent_max_items", 30)
        val_excl = DEFAULT_OPTIONS.get("recent_excluded_extensions", {})
        
        self.chk_recent_tracking.setChecked(val_tracking)
        self.spin_recent_limit.setValue(val_max)
        
        self.chk_recent_tracking.blockSignals(False)
        self.spin_recent_limit.blockSignals(False)
        
        self.current_options["recent_tracking_enabled"] = val_tracking
        self.current_options["recent_max_items"] = val_max
        self.current_options["recent_excluded_extensions"] = val_excl
        self._auto_save_options()
        if getattr(self, 'recent_mgr', None):
            self.recent_mgr.set_excluded_extensions(val_excl)

    def _on_feature_changed(self):
        for key, chk in self.feat_checkboxes.items():
            self.current_options[key] = chk.isChecked()
        self._auto_save_options()

    def _restore_feature_defaults(self):
        for key, chk in self.feat_checkboxes.items():
            chk.blockSignals(True)
            chk.setChecked(DEFAULT_OPTIONS.get(key, True))
            self.current_options[key] = DEFAULT_OPTIONS.get(key, True)
            chk.blockSignals(False)
        self._auto_save_options()

    def on_hotkey_changed(self, name, new_text):
        if new_text != self.current_hotkeys.get(name):
            success = self.hotkey_mgr.update_hotkey(name, new_text)
            if success:
                self.current_hotkeys[name] = new_text
                self.original_hotkeys[name] = new_text
                save_hotkeys(self.hotkey_mgr.hotkeys)
            else:
                QMessageBox.warning(self, "\u5feb\u6377\u952e\u51b2\u7a81", f"\u65e0\u6cd5\u6ce8\u518c\u5feb\u6377\u952e: {new_text}\n\u53ef\u80fd\u88ab\u5176\u4ed6\u7a0b\u5e8f\u5360\u7528\u3002")
                # Revert UI
                row_map = {
                    "screenshot": self.screenshot_row,
                    "smart_screenshot": self.smart_screenshot_row,
                    "record": self.record_row,
                    "search": self.search_row,
                    "notebook": self.notebook_row,
                    "clipboard": self.clipboard_row,
                    "recent": self.recent_row,
                    "toggle_ball": self.toggle_ball_row
                }
                row_map[name].set_hotkey(self.current_hotkeys.get(name, ""))

    def _restore_hotkey_defaults(self):
        row_map = {
            "screenshot": self.screenshot_row,
            "smart_screenshot": self.smart_screenshot_row,
            "record": self.record_row,
            "search": self.search_row,
            "notebook": self.notebook_row,
            "clipboard": self.clipboard_row,
            "recent": self.recent_row,
            "toggle_ball": self.toggle_ball_row
        }
        
        failed = []
        for name, default_key in DEFAULT_HOTKEYS.items():
            if name in row_map:
                success = self.hotkey_mgr.update_hotkey(name, default_key)
                if success:
                    row_map[name].set_hotkey(default_key)
                    self.current_hotkeys[name] = default_key
                    self.original_hotkeys[name] = default_key
                else:
                    failed.append(default_key)
                    
        if failed:
            QMessageBox.warning(self, "\u5feb\u6377\u952e\u51b2\u7a81", f"\u90e8\u5206\u9ed8\u8ba4\u5feb\u6377\u952e\u6062\u590d\u5931\u8d25: {', '.join(failed)}")
            
        save_hotkeys(self.hotkey_mgr.hotkeys)
