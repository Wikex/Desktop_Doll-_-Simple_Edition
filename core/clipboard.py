import json
import os
import base64
import time
import keyboard
from PySide6.QtCore import QObject, Signal, QTimer, QBuffer, QIODevice
from PySide6.QtGui import QClipboard, QImage, QPixmap
from PySide6.QtWidgets import QApplication

from utils.path_helper import get_base_dir
from utils.logger import log_exception
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
        
        # Debounce timer for saving history to disk (reduces IO stuttering)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(2000) # Save 2 seconds after last change
        self._save_timer.timeout.connect(self._do_save_history)
        
        # Debounce timer for image clipboard changes
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(200)  # 200ms debounce
        self._debounce_timer.timeout.connect(self._process_clipboard)
        
        # Flag to prevent reading what we just wrote programmatically
        self.ignore_next = False
        self.last_text = None
        self.last_text_at = 0.0
        self.text_dedupe_window = 2.5

    def _load_history(self):
        if not os.path.exists(HISTORY_FILE):
            return []
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
                return self._dedupe_history(self._normalize_history(raw))
        except Exception as e:
            log_exception(f"Failed to load clipboard history: {e}")
            return []

    def _normalize_text_key(self, text):
        import unicodedata
        import re
        text = text or ""
        # 剥离行首的常见序号和列表符号 (如 "1. ", "(一)", "- ", "* ")
        pattern = r'(?m)^\s*(?:[\(（]?(?:[\d]+|[a-zA-Z]|[一二三四五六七八九十百千万]+)[.\)）\]、](?!\d)\s*|[•·*+\-]\s*)'
        text = re.sub(pattern, '', text)
        
        text = unicodedata.normalize("NFKC", text)
        return "".join(ch for ch in text if unicodedata.category(ch)[0] not in {"Z", "C"})

    def _dedupe_history(self, history):
        deduped = []
        seen_text = set()
        seen_image = set()
        for item in history:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text":
                key = self._normalize_text_key(item.get("value", ""))
                if key in seen_text:
                    continue
                seen_text.add(key)
                deduped.append(item)
            elif item.get("type") == "image":
                key = item.get("value", "")
                if key in seen_image:
                    continue
                seen_image.add(key)
                deduped.append(item)
        return deduped

    def _normalize_history(self, raw_history):
        if not isinstance(raw_history, list):
            return []

        normalized = []
        fallback_time = time.time()
        for index, item in enumerate(raw_history):
            if isinstance(item, dict) and item.get("type") in {"text", "image"}:
                normalized.append(self._normalize_item_metadata(item, fallback_time - index))
            elif isinstance(item, str):
                normalized.append(self._normalize_item_metadata(
                    {"type": "text", "value": item},
                    fallback_time - index
                ))
        return normalized

    def _normalize_item_metadata(self, item, fallback_created_at=None):
        normalized = dict(item)
        normalized["pinned"] = bool(normalized.get("pinned", False))
        created_at = normalized.get("created_at", fallback_created_at)
        try:
            normalized["created_at"] = float(created_at)
        except (TypeError, ValueError):
            normalized["created_at"] = time.time()
        return normalized

    def _save_history(self):
        self._save_timer.start()

    def _do_save_history(self):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=4)
        except Exception as e:
            log_exception(f"Failed to save clipboard history: {e}")

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

    def _is_format_painter(self, mime_data):
        formats = mime_data.formats()
        # MS Office Explicit Format Painter
        if any("formatpainter" in f.lower() or "objformat" in f.lower() for f in formats):
            return True
            
        # WPS Office / MS Office implicit Format Painter heuristic
        # Normal Office copy has ~15-20 formats including RTF and HTML.
        # Format Painter ONLY has plain text and 'Ole Private Data', lacking RTF.
        if "text/plain" in formats and not mime_data.hasHtml() and not any("rtf" in f.lower() or "rich text" in f.lower() for f in formats):
            try:
                import win32clipboard
                import win32process
                import psutil
                
                win32clipboard.OpenClipboard()
                owner_hwnd = win32clipboard.GetClipboardOwner()
                
                native_formats = []
                f = win32clipboard.EnumClipboardFormats(0)
                while f:
                    try:
                        native_formats.append(win32clipboard.GetClipboardFormatName(f))
                    except Exception:
                        pass
                    # Also keep track of integer formats
                    native_formats.append(str(f))
                    f = win32clipboard.EnumClipboardFormats(f)
                win32clipboard.CloseClipboard()
                
                # If EMF (14) or WMF (3) is present, it's an image/equation, NOT a format painter!
                if "14" in native_formats or "3" in native_formats:
                    return False
                
                if owner_hwnd:
                    _, pid = win32process.GetWindowThreadProcessId(owner_hwnd)
                    process_name = psutil.Process(pid).name().lower()
                    if process_name in ["wps.exe", "et.exe", "wpp.exe", "winword.exe", "excel.exe", "powerpnt.exe"]:
                        # Ole Private Data is present in Format Painter, but not in simple text box copies
                        # PPT text boxes have Ole Private Data, but they also have DOZENS of formats (PNG, EMF, etc).
                        # WPS Format Painter typically has exactly 6 formats: ['DataObject', '13', '1', 'Ole Private Data', '16', '7']
                        if "Ole Private Data" in native_formats and len(native_formats) <= 6 and "Rich Text Format" not in native_formats:
                            return True
            except Exception as e:
                log_exception(f"Failed to inspect clipboard owner: {e}")
                try:
                    import win32clipboard
                    win32clipboard.CloseClipboard()
                except Exception as close_error:
                    log_exception(f"Failed to close clipboard: {close_error}")
                    
        return False

    def _image_from_mime_urls(self, mime_data):
        image_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".ico", ".tif", ".tiff"}
        for url in mime_data.urls():
            if not url.isLocalFile():
                continue

            path = url.toLocalFile()
            _, ext = os.path.splitext(path)
            if ext.lower() not in image_exts or not os.path.exists(path):
                continue

            image = QImage(path)
            if not image.isNull():
                return image
        return None

    def _image_from_html(self, html):
        if not html:
            return None

        import re
        from html import unescape
        from urllib.parse import unquote, urlparse

        src_values = re.findall(r"""<img\b[^>]*\bsrc\s*=\s*["']?([^"'\s>]+)""", html, re.IGNORECASE)
        for raw_src in src_values:
            src = unescape(raw_src).strip()

            if src.lower().startswith("data:image/"):
                match = re.match(r"data:image/[^;]+;base64,(.+)", src, re.IGNORECASE | re.DOTALL)
                if not match:
                    continue
                try:
                    data = base64.b64decode(match.group(1), validate=False)
                except Exception as e:
                    log_exception(f"Failed to decode clipboard HTML image: {e}")
                    continue

                image = QImage()
                if image.loadFromData(data) and not image.isNull():
                    return image
                continue

            parsed = urlparse(src)
            if parsed.scheme and parsed.scheme.lower() != "file":
                continue

            path = unquote(parsed.path if parsed.scheme else src)
            if os.name == "nt" and path.startswith("/") and len(path) > 2 and path[2] == ":":
                path = path[1:]
            path = os.path.normpath(path)
            if not os.path.exists(path):
                continue

            image = QImage(path)
            if not image.isNull():
                return image
        return None

    def _process_clipboard(self):
        mime_data = self._clipboard.mimeData()
        
        # Ignore format painter from Office/WPS to prevent junk data from being recorded
        if self._is_format_painter(mime_data):
            return
            
        # Standard image check
        image = None
        checked_html_image = False
        if mime_data.hasImage() and self.record_image:
            image = self._clipboard.image()
        elif mime_data.hasUrls() and self.record_image:
            # WeChat and some Chromium/Electron apps copy images as local temp-file
            # URLs instead of a direct image payload. Treat local image URLs as
            # image clipboard data, but keep ignoring ordinary file-copy URLs.
            image = self._image_from_mime_urls(mime_data)
        elif mime_data.hasHtml() and self.record_image:
            checked_html_image = True
            image = self._image_from_html(mime_data.html())

        if image is None and not checked_html_image and mime_data.hasHtml() and self.record_image:
            image = self._image_from_html(mime_data.html())

        if mime_data.hasUrls() and image is None:
            # Windows Explorer file copy often exposes file URLs and may also
            # include the file path as text. Ignore these payloads entirely so
            # copied files do not pollute the clipboard history.
            return

        if image is not None and not image.isNull() and self.record_image:
            import hashlib
            img_data = image.bits().tobytes()
            img_hash = hashlib.md5(img_data).hexdigest()
            if getattr(self, "last_image_hash", None) == img_hash:
                return
            self.last_image_hash = img_hash
            self.add_image_item(image)
        elif mime_data.hasText() and self.record_text:
            text = mime_data.text().strip().replace('\r\n', '\n').replace('\r', '\n')
            html = mime_data.html() if mime_data.hasHtml() else None
            if text:
                normalized_text = self._normalize_text_key(text)
                now = time.monotonic()
                if getattr(self, "last_normalized_text", None) == normalized_text and (now - self.last_text_at) < self.text_dedupe_window:
                    return
                self.last_normalized_text = normalized_text
                self.last_text_at = now
                self.add_text_item(text, html)

    def _make_text_item(self, text, html=None):
        item = {"type": "text", "value": text, "pinned": False, "created_at": time.time()}
        if html:
            item["html"] = html
        return item

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

        return {
            "type": "image",
            "value": filepath,
            "is_path": True,
            "pinned": False,
            "created_at": time.time()
        }

    def _manage_image_cache(self):
        if not getattr(self, "picture_save_path", "") or not os.path.exists(self.picture_save_path):
            return

        referenced = set()
        for item in self.history:
            if item.get("type") == "image" and item.get("is_path", False):
                referenced.add(os.path.abspath(item.get("value", "")))

        files = []
        for f in os.listdir(self.picture_save_path):
            p = os.path.join(self.picture_save_path, f)
            if os.path.isfile(p):
                files.append((p, os.path.getmtime(p)))
                
        limit = getattr(self, "max_images", 20)
        if len(files) > limit:
            files.sort(key=lambda x: x[1]) # oldest first
            removable = [item for item in files if os.path.abspath(item[0]) not in referenced]
            for p, _ in removable[:len(files) - limit]:
                try:
                    os.remove(p)
                except Exception as e:
                    log_exception(f"Failed to remove cached clipboard image: {e}")

    def _item_key(self, item):
        if item.get("type") == "image":
            return ("image", item.get("value", ""))
        
        val = item.get("value", "")
        return ("text", self._normalize_text_key(val))

    def _pin_count(self):
        return sum(1 for item in self.history if item.get("pinned", False))

    def _order_pinned_then_recent(self):
        pinned = [item for item in self.history if item.get("pinned", False)]
        ordinary = [item for item in self.history if not item.get("pinned", False)]
        ordinary.sort(key=lambda item: float(item.get("created_at", 0.0)), reverse=True)
        self.history = pinned + ordinary

    def _trim_history(self):
        pinned = [item for item in self.history if item.get("pinned", False)]
        ordinary = [item for item in self.history if not item.get("pinned", False)]
        ordinary_limit = max(0, self.max_items - len(pinned))
        self.history = pinned + ordinary[:ordinary_limit]

    def trim_history(self):
        before = list(self.history)
        self._trim_history()
        if self.history != before:
            self._save_history()
            self.history_changed.emit(self.history)

    def add_text_item(self, text, html=None):
        key = ("text", self._normalize_text_key(text))

        for item in self.history:
            if self._item_key(item) == key and item.get("pinned", False):
                item["value"] = text
                if html:
                    item["html"] = html
                elif "html" in item:
                    item.pop("html", None)
                self._save_history()
                self.history_changed.emit(self.history)
                return

        self.history = [item for item in self.history if self._item_key(item) != key]
        self.history.insert(self._pin_count(), self._make_text_item(text, html))
        self._trim_history()
            
        self._save_history()
        self.history_changed.emit(self.history)

    def add_image_item(self, image):
        item = self._make_image_item(image)
        key = self._item_key(item)
        for existing in self.history:
            if self._item_key(existing) == key and existing.get("pinned", False):
                self._save_history()
                self.history_changed.emit(self.history)
                return

        self.history = [existing for existing in self.history if self._item_key(existing) != key]
        self.history.insert(self._pin_count(), item)
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
        self._manage_image_cache()
        
        self._save_history()
        self.history_changed.emit(self.history)

    def remove_item(self, item_to_remove):
        if isinstance(item_to_remove, str):
            item_to_remove = self._make_text_item(item_to_remove)
            
        key = self._item_key(item_to_remove)
        for item in list(self.history):
            if self._item_key(item) == key:
                self.history.remove(item)
                break
                
        self._save_history()
        self.history_changed.emit(self.history)

    def toggle_pin(self, item_to_toggle):
        if isinstance(item_to_toggle, str):
            item_to_toggle = self._make_text_item(item_to_toggle)

        key = self._item_key(item_to_toggle)
        for index, item in enumerate(list(self.history)):
            if self._item_key(item) != key:
                continue

            item = self.history.pop(index)
            item["pinned"] = not item.get("pinned", False)
            if item["pinned"]:
                self.history.insert(self._pin_count(), item)
            else:
                self.history.append(item)
                self._order_pinned_then_recent()
            self._trim_history()
            self._save_history()
            self.history_changed.emit(self.history)
            break

    def clear_history(self, clear_type="all"):
        if clear_type == "all":
            self.history = [item for item in self.history if item.get("pinned", False)]
        elif clear_type == "text":
            self.history = [
                item for item in self.history
                if item.get("pinned", False) or item.get("type") != "text"
            ]
        elif clear_type == "image":
            self.history = [
                item for item in self.history
                if item.get("pinned", False) or item.get("type") != "image"
            ]
            
        self._save_history()
        self.history_changed.emit(self.history)

    def set_history(self, new_history):
        normalized = self._dedupe_history(self._normalize_history(new_history))
        pinned = [item for item in normalized if item.get("pinned", False)]
        ordinary = [item for item in normalized if not item.get("pinned", False)]
        self.history = pinned + ordinary
        self._trim_history()
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

    def _foreground_process_name(self):
        try:
            import win32gui
            import win32process
            import psutil

            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return ""
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            return psutil.Process(pid).name().lower()
        except Exception as e:
            log_exception(f"Failed to inspect foreground process for paste delay: {e}")
            return ""

    def _auto_paste_delay_ms(self):
        process_name = self._foreground_process_name()
        if process_name in {"vmware.exe", "vmplayer.exe", "vmware-vmx.exe"}:
            return 700
        return 50

    def _send_paste_hotkey(self):
        try:
            keyboard.send("ctrl+v")
        except Exception as e:
            log_exception(f"Failed to send paste hotkey: {e}")

    def _schedule_auto_paste(self):
        QTimer.singleShot(self._auto_paste_delay_ms(), self._send_paste_hotkey)

    def copy_to_clipboard(self, item, as_plain_text=False):
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
                except Exception as e:
                    log_exception(f"Failed to decode clipboard image item: {e}")
            if not image.isNull():
                import hashlib
                img_data = image.bits().tobytes()
                self.last_image_hash = hashlib.md5(img_data).hexdigest()
                
                self._clipboard.setImage(image)
                self._schedule_auto_paste()
            else:
                self.remove_item(item)
        else:
            text = item.get("value", "") if isinstance(item, dict) else str(item)
            html = item.get("html", None) if isinstance(item, dict) else None
            
            self.last_normalized_text = self._normalize_text_key(text)
            self.last_text_at = time.monotonic()
            
            from PySide6.QtCore import QMimeData
            mime = QMimeData()
            mime.setText(text)
            if html and not as_plain_text:
                mime.setHtml(html)
            self._clipboard.setMimeData(mime)
            self._schedule_auto_paste()



