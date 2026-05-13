import ctypes
import time
from ctypes import wintypes
from PySide6.QtCore import QObject, Signal, QAbstractNativeEventFilter, QTimer
from PIL import ImageGrab
from core.screenshot import get_all_visible_rects
from utils.logger import log_message

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

def parse_hotkey(key_str):
    mods = 0
    vk = 0
    parts = key_str.lower().split('+')
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if p in ('ctrl', 'control'): mods |= MOD_CONTROL
        elif p == 'shift': mods |= MOD_SHIFT
        elif p == 'alt': mods |= MOD_ALT
        elif p in ('win', 'windows'): mods |= MOD_WIN
        else:
            if len(p) == 1 and 'a' <= p <= 'z':
                vk = ord(p.upper())
            elif len(p) == 1 and '0' <= p <= '9':
                vk = ord(p)
            elif p.startswith('f') and p[1:].isdigit():
                vk = 0x6F + int(p[1:])
            elif p == 'space': vk = 0x20
            elif p in ('esc', 'escape'): vk = 0x1B
            elif p in ('enter', 'return'): vk = 0x0D
            elif p == 'tab': vk = 0x09
            elif p == 'up': vk = 0x26
            elif p == 'down': vk = 0x28
            elif p == 'left': vk = 0x25
            elif p == 'right': vk = 0x27
            elif p == '-': vk = 0xBD
            elif p == '=': vk = 0xBB
            elif p == '[': vk = 0xDB
            elif p == ']': vk = 0xDD
            elif p == '\\': vk = 0xDC
            elif p == ';': vk = 0xBA
            elif p == "'": vk = 0xDE
            elif p == ',': vk = 0xBC
            elif p == '.': vk = 0xBE
            elif p == '/': vk = 0xBF
            elif p == '`': vk = 0xC0
    return mods, vk

class NativeHotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager

    def nativeEventFilter(self, eventType, message):
        if eventType == b"windows_generic_MSG" or eventType == b"windows_dispatcher_MSG":
            msg = wintypes.MSG.from_address(message.__int__())
            if msg.message == WM_HOTKEY:
                hotkey_id = msg.wParam
                if hotkey_id in self.manager._registered_ids:
                    name = self.manager._registered_ids[hotkey_id]
                    self.manager._trigger_action(name)
                    return True, 0
        return False, 0

class HotkeyManager(QObject):
    action_triggered = Signal(str, object, object)

    def __init__(self, app, hotkeys=None, parent=None):
        super().__init__(parent)
        self.app = app
        self.hotkeys = hotkeys or {}
        self.failed_hotkeys = {}
        self._registered_ids = {} # map id -> name
        self._registered_names = {} # map name -> id
        self._next_id = 1
        self.paused = False
        self._paused_since = None
        
        self.filter = NativeHotkeyFilter(self)
        self.app.installNativeEventFilter(self.filter)
        
        self.user32 = ctypes.windll.user32
        self.user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        self.user32.RegisterHotKey.restype = wintypes.BOOL
        self.user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user32.UnregisterHotKey.restype = wintypes.BOOL
        
        for name, key in list(self.hotkeys.items()):
            self._register_native_hotkey(name, key)

        self._keepalive_timer = QTimer(self)
        self._keepalive_timer.setInterval(5 * 60 * 1000)
        self._keepalive_timer.timeout.connect(self.refresh_hotkeys)
        self._keepalive_timer.start()

        try:
            self.app.aboutToQuit.connect(self.cleanup)
        except Exception:
            pass

    def _trigger_action(self, name):
        if self.paused:
            return
        self.action_triggered.emit(name, None, None)

    def set_paused(self, paused):
        self.paused = bool(paused)
        self._paused_since = time.monotonic() if self.paused else None

    def _check_stale_pause(self):
        if not self.paused or self._paused_since is None:
            return
        if time.monotonic() - self._paused_since > 120:
            self.set_paused(False)
            log_message("Hotkey pause timed out and was automatically cleared")

    def _register_native_hotkey(self, name, key):
        if not key:
            self.failed_hotkeys.pop(name, None)
            return False

        mods, vk = parse_hotkey(key)
        if vk == 0 and mods == 0:
            self.failed_hotkeys[name] = key
            log_message(f"Invalid hotkey {key} for {name}")
            return False

        self._unregister_native_hotkey(name)

        hk_id = self._next_id
        self._next_id += 1

        success = self.user32.RegisterHotKey(None, hk_id, mods, vk)
        if success:
            self._registered_ids[hk_id] = name
            self._registered_names[name] = hk_id
            self.failed_hotkeys.pop(name, None)
            return True

        self.failed_hotkeys[name] = key
        log_message(f"Failed to register hotkey {key} for {name}")
        return False

    def register_hotkey(self, name, key):
        if self._register_native_hotkey(name, key):
            self.hotkeys[name] = key
            return True
        return False

    def update_hotkey(self, name, new_key):
        old_key = self.hotkeys.get(name, "")
        if new_key == old_key:
            return True

        self.unregister_hotkey(name)
        if not new_key:
            self.hotkeys[name] = ""
            return True

        if self._register_native_hotkey(name, new_key):
            self.hotkeys[name] = new_key
            return True

        if old_key:
            self._register_native_hotkey(name, old_key)
            self.hotkeys[name] = old_key
        else:
            self.hotkeys[name] = ""
        return False

    def _unregister_native_hotkey(self, name):
        hk_id = self._registered_names.pop(name, None)
        if hk_id is not None:
            try:
                self.user32.UnregisterHotKey(None, hk_id)
            except Exception as e:
                log_message(f"Failed to unregister hotkey id {hk_id} for {name}: {e}")
            self._registered_ids.pop(hk_id, None)

    def unregister_hotkey(self, name):
        self._unregister_native_hotkey(name)
        self.hotkeys[name] = ""
        return True

    def refresh_hotkeys(self):
        self._check_stale_pause()

        active_hotkeys = {
            name: key
            for name, key in self.hotkeys.items()
            if key
        }
        if not active_hotkeys:
            return

        for name in list(self._registered_names.keys()):
            self._unregister_native_hotkey(name)

        for name, key in active_hotkeys.items():
            self._register_native_hotkey(name, key)

    def cleanup(self):
        if hasattr(self, "_keepalive_timer"):
            self._keepalive_timer.stop()

        for name in list(self._registered_names.keys()):
            self._unregister_native_hotkey(name)

        try:
            self.app.removeNativeEventFilter(self.filter)
        except Exception:
            pass
