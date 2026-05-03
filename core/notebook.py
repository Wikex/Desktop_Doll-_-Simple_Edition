import json
import os
from PySide6.QtCore import QObject, Signal, QTimer

NOTEBOOK_FILE = "notebook.json"

class NotebookManager(QObject):
    content_loaded = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.content = ""
        
        # 防抖定时器：800ms
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(800)
        self._save_timer.timeout.connect(self._save_to_disk)
        
        self.load_content()

    def load_content(self):
        if os.path.exists(NOTEBOOK_FILE):
            try:
                with open(NOTEBOOK_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.content = data.get("content", "")
            except Exception as e:
                print(f"Failed to load notebook: {e}")
        self.content_loaded.emit(self.content)
        return self.content

    def update_content(self, text):
        self.content = text
        # 每次文本改变，重新开始计时（防抖机制）
        self._save_timer.start()

    def _save_to_disk(self):
        try:
            with open(NOTEBOOK_FILE, "w", encoding="utf-8") as f:
                json.dump({"content": self.content}, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Failed to save notebook: {e}")
