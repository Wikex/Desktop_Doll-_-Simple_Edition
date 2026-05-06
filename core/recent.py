import os
import json
import time
from PySide6.QtCore import QObject, Signal, QTimer
from core.windows_recent import list_recent_lnk_files, resolve_lnk_target, is_directory_target, ensure_windows_recent_tracking_enabled
from utils.path_helper import get_base_dir

HISTORY_FILE = os.path.join(get_base_dir(), "recent_history.json")

class RecentManager(QObject):
    items_changed = Signal(list)

    def __init__(self, max_items=30, parent=None):
        super().__init__(parent)
        self.max_items = max_items
        self.tracking_enabled = True
        self.excluded_extensions = set()
        
        ensure_windows_recent_tracking_enabled()
        
        self.history = self._load_history()
        
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.tick_scan)
        self.poll_timer.start(2000) # Poll every 2 seconds
        
        self._last_scan_mtime = {} # path -> mtime

    def set_tracking_enabled(self, enabled):
        was_enabled = self.tracking_enabled
        self.tracking_enabled = enabled
        if enabled and not was_enabled:
            self.tick_scan(silent=True)

    def set_excluded_extensions(self, exts):
        if isinstance(exts, list):
            self.excluded_extensions = {self._normalize_ext(e): True for e in exts if e.strip()}
        else:
            self.excluded_extensions = {self._normalize_ext(k): v for k, v in exts.items() if k.strip()}
        self._purge_excluded()

    def _normalize_ext(self, ext):
        ext = ext.strip().lower()
        if ext and not ext.startswith('.'):
            ext = '.' + ext
        return ext

    def _purge_excluded(self):
        changed = False
        new_history = []
        for item in self.history:
            if not self.excluded_extensions.get(item.get("ext"), False):
                new_history.append(item)
            else:
                changed = True
        if changed:
            self.history = new_history
            self._save_history()
            self.items_changed.emit(self.history)

    def _load_history(self):
        if not os.path.exists(HISTORY_FILE):
            return []
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_history(self):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    def tick_scan(self, silent=False):
        if not self.tracking_enabled and not silent:
            return
            
        changed = False
        
        try:
            lnk_paths = list_recent_lnk_files()
        except Exception:
            lnk_paths = []

        # Take the top N recent shortcuts to process
        for lnk in lnk_paths[:50]:
            try:
                mtime = os.path.getmtime(lnk)
            except Exception:
                continue
                
            if self._last_scan_mtime.get(lnk) == mtime:
                continue
            self._last_scan_mtime[lnk] = mtime
            
            if silent:
                continue
            
            target = resolve_lnk_target(lnk)
            if not target or not os.path.exists(target):
                continue
                
            if is_directory_target(target):
                continue
                
            _, ext = os.path.splitext(target)
            ext = self._normalize_ext(ext)
            
            if self.excluded_extensions.get(ext, False):
                continue
                
            # Add to history
            name = os.path.basename(target)
            
            # Deduplicate
            existing_idx = -1
            for i, item in enumerate(self.history):
                if item.get("path") == target:
                    existing_idx = i
                    break
                    
            new_item = {
                "path": target,
                "name": name,
                "ext": ext,
                "is_app": ext == ".exe",
                "last_seen": time.time()
            }
            
            if existing_idx >= 0:
                self.history.pop(existing_idx)
            
            self.history.insert(0, new_item)
            changed = True
            
        if changed:
            if len(self.history) > self.max_items:
                self.history = self.history[:self.max_items]
            self._save_history()
            self.items_changed.emit(self.history)

    def clean_missing_files(self):
        changed = False
        new_history = []
        for item in self.history:
            if os.path.exists(item.get("path", "")):
                new_history.append(item)
            else:
                changed = True
                
        if changed:
            self.history = new_history
            self._save_history()
            self.items_changed.emit(self.history)

    def clear_history(self):
        if self.history:
            self.history.clear()
            self._save_history()
            self.items_changed.emit(self.history)

    def set_history(self, new_history):
        self.history = new_history
        self._save_history()
        self.items_changed.emit(self.history)

    def get_items(self):
        self.clean_missing_files()
        return self.history

    def open_item(self, item):
        path = item.get("path") if isinstance(item, dict) else str(item)
        if os.path.exists(path):
            try:
                os.startfile(path)
            except Exception as e:
                print(f"Failed to open {path}: {e}")

    def open_item_location(self, item):
        path = item.get("path") if isinstance(item, dict) else str(item)
        if os.path.exists(path):
            import subprocess
            try:
                subprocess.run(['explorer', '/select,', os.path.normpath(path)])
            except Exception as e:
                print(f"Failed to open location for {path}: {e}")
