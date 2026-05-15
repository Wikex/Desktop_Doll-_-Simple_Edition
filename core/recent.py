import os
import json
import time
from PySide6.QtCore import QObject, Signal, QTimer, QThread, QFileSystemWatcher
from core.windows_recent import (
    delete_recent_links_for_target,
    get_recent_dir,
    list_recent_lnk_files,
    resolve_lnk_target,
    is_directory_target,
    ensure_windows_recent_tracking_enabled,
)
from utils.path_helper import get_base_dir
from utils.logger import log_exception

HISTORY_FILE = os.path.join(get_base_dir(), "recent_history.json")
SCAN_STATE_FILE = os.path.join(get_base_dir(), "recent_scan_state.json")

class RecentScannerThread(QThread):
    scan_finished = Signal(list, dict) # new_items, updated_mtimes

    def __init__(self, excluded_extensions, last_scan_mtime, parent=None):
        super().__init__(parent)
        self.excluded_extensions = excluded_extensions.copy() if excluded_extensions else {}
        self.last_scan_mtime = last_scan_mtime.copy() if last_scan_mtime else {}

    def _normalize_ext(self, ext):
        ext = ext.strip().lower()
        if ext and not ext.startswith('.'):
            ext = '.' + ext
        return ext

    def run(self):
        shell = None
        pythoncom = None
        try:
            try:
                import pythoncom as pythoncom_module
                import win32com.client

                pythoncom = pythoncom_module
                pythoncom.CoInitialize()
                shell = win32com.client.Dispatch("WScript.Shell")
            except Exception as e:
                log_exception(f"Failed to initialize Recent COM shell: {e}")

            lnk_paths = list_recent_lnk_files()

            new_items = []
            updated_mtimes = self.last_scan_mtime.copy()

            for lnk in lnk_paths[:80]:
                try:
                    mtime = os.path.getmtime(lnk)
                except Exception:
                    continue

                if updated_mtimes.get(lnk) == mtime:
                    continue
                updated_mtimes[lnk] = mtime

                target = resolve_lnk_target(lnk, shell=shell)
                if not target or not os.path.exists(target):
                    continue

                if is_directory_target(target):
                    continue

                _, ext = os.path.splitext(target)
                ext = self._normalize_ext(ext)

                if self.excluded_extensions.get(ext, False):
                    continue

                now = time.time()
                name = os.path.basename(target)
                new_item = {
                    "path": target,
                    "name": name,
                    "ext": ext,
                    "is_app": ext == ".exe",
                    "last_seen": now,
                    "created_at": now,
                    "pinned": False
                }
                new_items.append(new_item)

            self.scan_finished.emit(new_items, updated_mtimes)
        except Exception as e:
            log_exception(f"Failed to scan recent files: {e}")
            self.scan_finished.emit([], self.last_scan_mtime)
        finally:
            if pythoncom:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

class RecentManager(QObject):
    items_changed = Signal(list)

    def __init__(self, max_items=30, parent=None):
        super().__init__(parent)
        self.max_items = max_items
        self.tracking_enabled = True
        self.excluded_extensions = {}
        
        ensure_windows_recent_tracking_enabled()
        
        self.history = self._load_history()
        self._last_scan_mtime = self._load_scan_state() # lnk path -> mtime
        self._rescan_requested = False
        self._drop_current_scan_results = False

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.tick_scan)
        self.poll_timer.start(1000)

        self._scan_debounce_timer = QTimer(self)
        self._scan_debounce_timer.setSingleShot(True)
        self._scan_debounce_timer.setInterval(300)
        self._scan_debounce_timer.timeout.connect(self.tick_scan)

        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._on_recent_dir_changed)
        self._watch_recent_dir()

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(2000)
        self._save_timer.timeout.connect(self._do_save_history)

        QTimer.singleShot(800, self.tick_scan)

    def set_tracking_enabled(self, enabled):
        was_enabled = self.tracking_enabled
        self.tracking_enabled = enabled
        if enabled and not was_enabled:
            self._watch_recent_dir()
            self.tick_scan(silent=True)
        elif not enabled:
            self._clear_recent_watcher()

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
                return self._dedupe_history(self._normalize_history(json.load(f)))
        except Exception as e:
            log_exception(f"Failed to load recent history: {e}")
            return []

    def _load_scan_state(self):
        if not os.path.exists(SCAN_STATE_FILE):
            return {}
        try:
            with open(SCAN_STATE_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, dict):
                return {}
            return {
                str(path): float(mtime)
                for path, mtime in raw.items()
                if isinstance(path, str)
            }
        except Exception as e:
            log_exception(f"Failed to load recent scan state: {e}")
            return {}

    def _normalize_history(self, raw_history):
        if not isinstance(raw_history, list):
            return []

        normalized = []
        fallback_time = time.time()
        for index, item in enumerate(raw_history):
            if not isinstance(item, dict) or not item.get("path"):
                continue
            normalized.append(self._normalize_item_metadata(item, fallback_time - index))
        return normalized

    def _normalize_item_metadata(self, item, fallback_created_at=None):
        normalized = dict(item)
        normalized["pinned"] = bool(normalized.get("pinned", False))
        created_at = normalized.get("created_at", normalized.get("last_seen", fallback_created_at))
        try:
            normalized["created_at"] = float(created_at)
        except (TypeError, ValueError):
            normalized["created_at"] = time.time()
        try:
            normalized["last_seen"] = float(normalized.get("last_seen", normalized["created_at"]))
        except (TypeError, ValueError):
            normalized["last_seen"] = normalized["created_at"]
        return normalized

    def _dedupe_history(self, history):
        deduped = []
        seen_paths = set()
        for item in history:
            key = self._path_key(item.get("path", ""))
            if not key or key in seen_paths:
                continue
            seen_paths.add(key)
            deduped.append(item)
        return deduped

    def _path_key(self, path):
        return os.path.normcase(os.path.abspath(path)) if path else ""

    def _pin_count(self):
        return sum(1 for item in self.history if item.get("pinned", False))

    def _order_pinned_then_recent(self):
        pinned = [item for item in self.history if item.get("pinned", False)]
        ordinary = [item for item in self.history if not item.get("pinned", False)]
        ordinary.sort(key=lambda item: float(item.get("created_at", item.get("last_seen", 0.0))), reverse=True)
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
            self.items_changed.emit(self.history)

    def _save_history(self):
        self._save_timer.start()

    def _save_history_now(self):
        self._save_timer.stop()
        self._do_save_history()

    def _do_save_history(self):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=4)
        except Exception as e:
            log_exception(f"Failed to save recent history: {e}")

    def _save_scan_state(self):
        try:
            with open(SCAN_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._last_scan_mtime, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log_exception(f"Failed to save recent scan state: {e}")

    def _mark_current_recent_links_seen(self):
        try:
            for lnk in list_recent_lnk_files():
                try:
                    self._last_scan_mtime[lnk] = os.path.getmtime(lnk)
                except Exception:
                    continue
            self._save_scan_state()
        except Exception as e:
            log_exception(f"Failed to mark current recent links seen: {e}")

    def _watch_recent_dir(self):
        if not self.tracking_enabled:
            return
        recent_dir = get_recent_dir()
        if not recent_dir or not os.path.isdir(recent_dir):
            return
        if recent_dir not in self._watcher.directories():
            self._watcher.addPath(recent_dir)

    def _clear_recent_watcher(self):
        dirs = self._watcher.directories()
        if dirs:
            self._watcher.removePaths(dirs)

    def _on_recent_dir_changed(self, path):
        self._watch_recent_dir()
        if self.tracking_enabled:
            self._scan_debounce_timer.start()

    def tick_scan(self, silent=False):
        if not self.tracking_enabled and not silent:
            return
            
        if hasattr(self, '_scanner') and self._scanner.isRunning():
            self._rescan_requested = True
            return
            
        self._rescan_requested = False
        self._scanner = RecentScannerThread(self.excluded_extensions, self._last_scan_mtime, self)
        self._scanner.scan_finished.connect(lambda new_items, mtimes: self._on_scan_finished(new_items, mtimes, silent))
        self._scanner.start()

    def _on_scan_finished(self, new_items, updated_mtimes, silent):
        self._last_scan_mtime.update(updated_mtimes)
        self._save_scan_state()

        if self._rescan_requested and self.tracking_enabled:
            self._rescan_requested = False
            QTimer.singleShot(0, self.tick_scan)

        if self._drop_current_scan_results:
            self._drop_current_scan_results = False
            return
        
        if silent:
            return
            
        changed = False
        for new_item in new_items:
            new_item = self._normalize_item_metadata(new_item)
            # Deduplicate
            existing_idx = -1
            for i, item in enumerate(self.history):
                if self._path_key(item.get("path")) == self._path_key(new_item.get("path")):
                    existing_idx = i
                    break
                    
            if existing_idx >= 0:
                existing = self.history[existing_idx]
                if existing.get("pinned", False):
                    created_at = existing.get("created_at", existing.get("last_seen", time.time()))
                    existing.update(new_item)
                    existing["created_at"] = created_at
                    existing["pinned"] = True
                    changed = True
                    continue
                self.history.pop(existing_idx)
            
            self.history.insert(self._pin_count(), new_item)
            changed = True
            
        if changed:
            self._trim_history()
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
        self._scan_debounce_timer.stop()
        if hasattr(self, '_scanner') and self._scanner.isRunning():
            self._drop_current_scan_results = True
        self._mark_current_recent_links_seen()
        if self.history:
            self.history = [item for item in self.history if item.get("pinned", False)]
            self._save_history_now()
            self.items_changed.emit(self.history)

    def remove_item(self, item_to_remove):
        path = item_to_remove.get("path") if isinstance(item_to_remove, dict) else str(item_to_remove)
        key = self._path_key(path)
        for i, item in enumerate(self.history):
            if self._path_key(item.get("path")) == key:
                self.history.pop(i)
                self._scan_debounce_timer.stop()
                if hasattr(self, '_scanner') and self._scanner.isRunning():
                    self._drop_current_scan_results = True
                removed_links = delete_recent_links_for_target(path)
                for lnk_path in removed_links:
                    self._last_scan_mtime.pop(lnk_path, None)
                if removed_links:
                    self._save_scan_state()
                self._save_history_now()
                self.items_changed.emit(self.history)
                break

    def toggle_pin(self, item_to_toggle):
        path = item_to_toggle.get("path") if isinstance(item_to_toggle, dict) else str(item_to_toggle)
        key = self._path_key(path)
        for index, item in enumerate(list(self.history)):
            if self._path_key(item.get("path")) != key:
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
            self.items_changed.emit(self.history)
            break

    def set_history(self, new_history):
        normalized = self._dedupe_history(self._normalize_history(new_history))
        pinned = [item for item in normalized if item.get("pinned", False)]
        ordinary = [item for item in normalized if not item.get("pinned", False)]
        self.history = pinned + ordinary
        self._trim_history()
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
                log_exception(f"Failed to open {path}: {e}")

    def open_item_location(self, item):
        path = item.get("path") if isinstance(item, dict) else str(item)
        if os.path.exists(path):
            import subprocess
            try:
                subprocess.run(['explorer', '/select,', os.path.normpath(path)])
            except Exception as e:
                log_exception(f"Failed to open location for {path}: {e}")
