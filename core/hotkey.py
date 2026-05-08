import keyboard
from PySide6.QtCore import QObject, Signal, QTimer
from PIL import ImageGrab
from core.screenshot import get_all_visible_rects

class HotkeyManager(QObject):
    action_triggered = Signal(str, object, object)

    def __init__(self, hotkeys=None, parent=None):
        super().__init__(parent)
        self.hotkeys = hotkeys or {} # e.g. {"clipboard": "ctrl+shift+v", "screenshot": "win+shift+s"}
        self._registered_hotkeys = {}
        self.paused = False # map name to actual hotkey string registered
        
        for name, key in self.hotkeys.items():
            self.register_hotkey(name, key)
            
        # Watchdog: Windows sometimes drops low-level hooks if the system stutters.
        # This timer silently re-registers them every 60 seconds to ensure they never permanently die.
        self.watchdog_timer = QTimer(self)
        self.watchdog_timer.timeout.connect(self._reconnect_hooks)
        self.watchdog_timer.start(60000)

    def _reconnect_hooks(self):
        if self.paused:
            return
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        self._registered_hotkeys.clear()
        for name, key in self.hotkeys.items():
            if key:
                self.register_hotkey(name, key)

    def register_hotkey(self, name, key):
        if not key:
            return False
            
        try:
            # register with keyboard
            def cb(n=name):
                if getattr(self, 'paused', False):
                    return
                # Do NOT block the low-level keyboard hook with heavy OS calls! 
                # (ImageGrab and EnumWindows take > 100ms and cause Windows to drop the WH_KEYBOARD_LL hook)
                # Just emit the signal and let the main thread handle the heavy lifting.
                self.action_triggered.emit(n, None, None)
                
            keyboard.add_hotkey(key, cb, suppress=False)
            self._registered_hotkeys[name] = key
            self.hotkeys[name] = key
            return True
        except Exception as e:
            print(f"Failed to register hotkey {key} for {name}: {e}")
            return False

    def update_hotkey(self, name, new_key):
        # unregister old
        old_key = self._registered_hotkeys.get(name)
        if old_key:
            try:
                keyboard.remove_hotkey(old_key)
            except Exception:
                pass
            del self._registered_hotkeys[name]
        
        # register new
        if new_key:
            return self.register_hotkey(name, new_key)
        else:
            self.hotkeys[name] = ""
            return True

    def unregister_hotkey(self, name):
        old_key = self._registered_hotkeys.get(name)
        if old_key:
            try:
                keyboard.remove_hotkey(old_key)
            except Exception:
                pass
            self._registered_hotkeys.pop(name, None)
        self.hotkeys[name] = ""
        return True
