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

    # Adaptive keepalive: shorter interval when failures are detected
    _KEEPALIVE_NORMAL = 5 * 60 * 1000     # 5 min (normal)
    _KEEPALIVE_FAST   = 45 * 1000          # 45 s  (failure-retry mode)

    def __init__(self, app, hotkeys=None, parent=None):
        super().__init__(parent)
        self.app = app
        self.hotkeys = hotkeys or {}
        self.failed_hotkeys = {}
        self._consecutive_failures = {}  # per-key failure counter (name → count)
        self._registered_ids = {} # map id -> name
        self._registered_names = {} # map name -> id
        self._next_id = 1
        self.paused = False
        self._paused_since = None
        self._last_trigger_time = time.monotonic()
        self._failed_since_last_refresh = False

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
        self._keepalive_timer.setInterval(self._KEEPALIVE_NORMAL)
        self._keepalive_timer.timeout.connect(self._on_keepalive_tick)
        self._keepalive_timer.start()

        # Faster watchdog: if no hotkey fires for 4 minutes despite registrations,
        # suspect Windows deregistered them and refresh early.
        self._watchdog_timer = QTimer(self)
        self._watchdog_timer.setInterval(60_000)   # check every 60 s
        self._watchdog_timer.timeout.connect(self._check_silent_drop)
        self._watchdog_timer.start()

        try:
            self.app.aboutToQuit.connect(self.cleanup)
        except Exception:
            pass

    def _trigger_action(self, name):
        self._last_trigger_time = time.monotonic()
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

    # ── Adaptive keepalive ──────────────────────────────────────────

    def _on_keepalive_tick(self):
        """Periodic full re-registration.  Uses faster interval if any
        hotkey was recently reported as failed.  Persistently occupied keys
        are skipped after MAX_CONSECUTIVE_FAILURES to avoid log spam."""
        MAX_CONSECUTIVE = 5

        self._check_stale_pause()

        active_hotkeys = {
            name: key for name, key in self.hotkeys.items() if key
        }
        if not active_hotkeys:
            return

        # Full re-registration
        for name in list(self._registered_names.keys()):
            self._unregister_native_hotkey(name)

        self._failed_since_last_refresh = False
        for name, key in active_hotkeys.items():
            # Skip keys that have failed persistently — retry once every
            # 10 normal-mode keepalive cycles, hinting at user intervention.
            skips = self._consecutive_failures.get(name, 0)
            if skips >= MAX_CONSECUTIVE:
                if self._keepalive_timer.interval() == self._KEEPALIVE_NORMAL:
                    self._consecutive_failures[name] = MAX_CONSECUTIVE + 1  # allow one retry
                else:
                    continue
            elif skips > MAX_CONSECUTIVE:
                if self._keepalive_timer.interval() == self._KEEPALIVE_NORMAL:
                    self._consecutive_failures[name] = 0  # reset for retry
                else:
                    continue

            ok = self._register_native_hotkey(name, key)
            if not ok:
                self._failed_since_last_refresh = True
                self._consecutive_failures[name] = skips + 1
            else:
                self._consecutive_failures.pop(name, None)

        # Switch back to normal interval if everything succeeded
        self._keepalive_timer.setInterval(
            self._KEEPALIVE_FAST if self._failed_since_last_refresh
            else self._KEEPALIVE_NORMAL
        )

    def _check_silent_drop(self):
        """If hotkeys are registered but none have fired for >4 min,
        Windows may have silently deregistered them (rare).  Force a
        keepalive refresh early."""
        if not self._registered_ids:
            return
        idle = time.monotonic() - self._last_trigger_time
        if idle > 240 and not self._keepalive_timer.isActive():
            # keepalive timer is somehow stopped — restart it
            self._keepalive_timer.start()
        elif idle > 240:
            # Force an early refresh now instead of waiting for the
            # next keepalive tick.
            log_message(
                f"Hotkey watchdog: no event for {idle:.0f}s — forcing refresh"
            )
            self._on_keepalive_tick()

    # ── /Adaptive keepalive ─────────────────────────────────────────

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
        hk_id = self._registered_names.get(name)
        if hk_id is not None:
            try:
                self.user32.UnregisterHotKey(None, hk_id)
            except Exception as e:
                log_message(f"Failed to unregister hotkey id {hk_id} for {name}: {e}")
                return  # keep the mapping intact so it can be retried
            self._registered_ids.pop(hk_id, None)
            self._registered_names.pop(name, None)

    def unregister_hotkey(self, name):
        self._unregister_native_hotkey(name)
        self.hotkeys[name] = ""
        return True

    def refresh_hotkeys(self):
        """Public API — forces a full re-registration immediately."""
        self._on_keepalive_tick()

    def cleanup(self):
        if hasattr(self, "_keepalive_timer"):
            self._keepalive_timer.stop()
        if hasattr(self, "_watchdog_timer"):
            self._watchdog_timer.stop()

        for name in list(self._registered_names.keys()):
            self._unregister_native_hotkey(name)

        try:
            self.app.removeNativeEventFilter(self.filter)
        except Exception:
            pass
