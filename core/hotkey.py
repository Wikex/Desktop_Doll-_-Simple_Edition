import ctypes
from ctypes import wintypes
from PySide6.QtCore import QObject, Signal, QAbstractNativeEventFilter
from PIL import ImageGrab
from core.screenshot import get_all_visible_rects

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
        self._registered_ids = {} # map id -> name
        self._next_id = 1
        self.paused = False
        
        self.filter = NativeHotkeyFilter(self)
        self.app.installNativeEventFilter(self.filter)
        
        self.user32 = ctypes.windll.user32
        
        for name, key in self.hotkeys.items():
            self.register_hotkey(name, key)

    def _trigger_action(self, name):
        if self.paused:
            return
        self.action_triggered.emit(name, None, None)

    def register_hotkey(self, name, key):
        if not key:
            return False
            
        mods, vk = parse_hotkey(key)
        if vk == 0 and mods == 0:
            return False
            
        hk_id = self._next_id
        self._next_id += 1
        
        # Unregister if previously registered with this name
        self.unregister_hotkey(name)
        
        success = self.user32.RegisterHotKey(None, hk_id, mods, vk)
        if success:
            self._registered_ids[hk_id] = name
            self.hotkeys[name] = key
            return True
        else:
            print(f"Failed to register hotkey {key} for {name}")
            return False

    def update_hotkey(self, name, new_key):
        self.unregister_hotkey(name)
        if new_key:
            return self.register_hotkey(name, new_key)
        else:
            self.hotkeys[name] = ""
            return True

    def unregister_hotkey(self, name):
        hk_id = None
        for i, n in list(self._registered_ids.items()):
            if n == name:
                hk_id = i
                break
                
        if hk_id is not None:
            self.user32.UnregisterHotKey(None, hk_id)
            del self._registered_ids[hk_id]
            
        self.hotkeys[name] = ""
        return True
