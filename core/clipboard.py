import json
import os
import base64
import keyboard
from PySide6.QtCore import QObject, Signal, QTimer, QBuffer, QIODevice
from PySide6.QtGui import QClipboard, QImage, QPixmap
from PySide6.QtWidgets import QApplication

from utils.path_helper import get_base_dir
HISTORY_FILE = os.path.join(get_base_dir(), "history.json")

class ClipboardManager(QObject):
    # Emits when a new valid text is added to the history
    history_changed = Signal(list)

    def __init__(self, max_items=20, parent=None):
        super().__init__(parent)
        self.max_items = max_items
        self.history = self._load_history()
        self._clipboard = QApplication.clipboard()
        self.tracking_enabled = True
        self.record_text = True
        self.record_image = True
        self.picture_save_path = ""
        self.max_images = 20
        
        # Connect to clipboard data change signal
        self._clipboard.dataChanged.connect(self._on_clipboard_changed)
        
        # Debounce timer for image clipboard changes
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(200)  # 200ms debounce
        self._debounce_timer.timeout.connect(self._process_clipboard)
        
        # Flag to prevent reading what we just wrote programmatically
        self.ignore_next = False

    def _load_history(self):
        if not os.path.exists(HISTORY_FILE):
            return []
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
                return self._normalize_history(raw)
        except Exception as e:
            print(f"Failed to load history: {e}")
            return []

    def _normalize_history(self, raw_history):
        if not isinstance(raw_history, list):
            return []

        normalized = []
        for item in raw_history:
            if isinstance(item, dict) and item.get("type") in {"text", "image"}:
                normalized.append(item)
            elif isinstance(item, str):
                normalized.append({"type": "text", "value": item})
        return normalized

    def _save_history(self):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Failed to save history: {e}")

    def _on_clipboard_changed(self, mode=QClipboard.Clipboard):
        if mode != QClipboard.Clipboard:
            return
            
        if not self.tracking_enabled:
            return
            
        if self.ignore_next:
            self.ignore_next = False
            return
            
        # Restart the debounce timer. If multiple changes arrive rapidly (like a screenshot),
        # only the last one will trigger the processing.
        self._debounce_timer.start()

    def _process_clipboard(self):
        mime_data = self._clipboard.mimeData()
        if mime_data.hasUrls():
            # Windows Explorer file copy often exposes file URLs and may also
            # include the file path as text. Ignore these payloads entirely so
            # copied files do not pollute the clipboard history.
            return
        if mime_data.hasImage() and self.record_image:
            image = self._clipboard.image()
            if not image.isNull():
                import hashlib
                img_data = image.bits().tobytes()
                img_hash = hashlib.md5(img_data).hexdigest()
                if getattr(self, "last_image_hash", None) == img_hash:
                    return
                self.last_image_hash = img_hash
                self.add_image_item(image)
        elif mime_data.hasText() and self.record_text:
            text = mime_data.text().strip()
            if text:
                if getattr(self, "last_text", None) == text:
                    return
                self.last_text = text
                self.add_text_item(text)

    def _make_text_item(self, text):
        return {"type": "text", "value": text}

    def _make_image_item(self, image):
        if not getattr(self, "picture_save_path", ""):
            from utils.path_helper import get_base_dir
            self.picture_save_path = os.path.join(get_base_dir(), "picture")
            
        if not os.path.exists(self.picture_save_path):
            os.makedirs(self.picture_save_path, exist_ok=True)
            
        from datetime import datetime
        filename = datetime.now().strftime("IMG_%Y%m%d_%H%M%S_%f.png")
        filepath = os.path.join(self.picture_save_path, filename)
        
        image.save(filepath, "PNG")
        
        self._manage_image_cache()
        
        return {
            "type": "image",
            "value": filepath,
            "is_path": True
        }

    def _manage_image_cache(self):
        if not getattr(self, "picture_save_path", "") or not os.path.exists(self.picture_save_path):
            return
            
        files = []
        for f in os.listdir(self.picture_save_path):
            p = os.path.join(self.picture_save_path, f)
            if os.path.isfile(p):
                files.append((p, os.path.getmtime(p)))
                
        limit = getattr(self, "max_images", 20)
        if len(files) > limit:
            files.sort(key=lambda x: x[1]) # oldest first
            # delete oldest until we reach limit
            for i in range(len(files) - limit):
                try:
                    os.remove(files[i][0])
                except Exception:
                    pass

    def _item_key(self, item):
        if item.get("type") == "image":
            return ("image", item.get("value", ""))
        return ("text", item.get("value", ""))

    def _trim_history(self):
        if len(self.history) > self.max_items:
            self.history = self.history[:self.max_items]

    def add_text_item(self, text):
        # Remove if it already exists (deduplication)
        key = ("text", text)
        self.history = [item for item in self.history if self._item_key(item) != key]
            
        # Add to top (most recent)
        self.history.insert(0, self._make_text_item(text))
        self._trim_history()
            
        self._save_history()
        self.history_changed.emit(self.history)

    def add_image_item(self, image):
        item = self._make_image_item(image)
        key = self._item_key(item)
        self.history = [existing for existing in self.history if self._item_key(existing) != key]
        self.history.insert(0, item)
        self._trim_history()
        
        # Clean missing files before emitting to prevent showing blank entries
        valid_history = []
        for it in self.history:
            if it.get("type") == "image":
                val = it.get("value", "")
                if it.get("is_path", False) or val.endswith('.png'):
                    if not os.path.exists(val):
                        continue
            valid_history.append(it)
        self.history = valid_history
        
        self._save_history()
        self.history_changed.emit(self.history)

    def remove_item(self, item_to_remove):
        if isinstance(item_to_remove, str):
            item_to_remove = self._make_text_item(item_to_remove)
            
        key = self._item_key(item_to_remove)
        for item in list(self.history):
            if self._item_key(item) == key:
                if item.get("type") == "image":
                    val = item.get("value", "")
                    if os.path.exists(val) and val.endswith(".png"):
                        try:
                            os.remove(val)
                        except Exception:
                            pass
                self.history.remove(item)
                break
                
        self._save_history()
        self.history_changed.emit(self.history)

    def clear_history(self):
        for item in self.history:
            if item.get("type") == "image":
                val = item.get("value", "")
                if os.path.exists(val) and val.endswith(".png"):
                    try:
                        os.remove(val)
                    except Exception:
                        pass
        self.history.clear()
        self._save_history()
        self.history_changed.emit(self.history)

    def set_history(self, new_history):
        self.history = self._normalize_history(new_history)
        self._save_history()
        # Emit so the UI rebuilds cleanly after a drag-drop reorder
        self.history_changed.emit(self.history)

    def get_history(self):
        self.clean_missing_files()
        return self.history

    def clean_missing_files(self):
        changed = False
        valid_history = []
        for item in self.history:
            if item.get("type") == "image":
                val = item.get("value", "")
                if item.get("is_path", False) or val.endswith('.png'):
                    if not os.path.exists(val):
                        changed = True
                        continue
            valid_history.append(item)
            
        if changed:
            self.history = valid_history
            self._save_history()
            self.history_changed.emit(self.history)

    def copy_to_clipboard(self, item):
        """Called when user clicks an item to copy it back"""
        self.ignore_next = True
        if isinstance(item, dict) and item.get("type") == "image":
            val = item.get("value", "")
            image = QImage()
            if item.get("is_path", False) or (os.path.exists(val) and val.endswith('.png')):
                image.load(val)
            else:
                try:
                    data = base64.b64decode(val)
                    image.loadFromData(data, "PNG")
                except:
                    pass
            if not image.isNull():
                self._clipboard.setImage(image)
                QTimer.singleShot(50, lambda: keyboard.send("ctrl+v"))
            else:
                self.remove_item(item)
        else:
            text = item.get("value", "") if isinstance(item, dict) else str(item)
            self._clipboard.setText(text)
            QTimer.singleShot(50, lambda: keyboard.send("ctrl+v"))



