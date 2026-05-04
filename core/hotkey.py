import keyboard
from PySide6.QtCore import QObject, Signal
from PIL import ImageGrab

class HotkeyManager(QObject):
    action_triggered = Signal(str, object)

    def __init__(self, hotkeys=None, parent=None):
        super().__init__(parent)
        self.hotkeys = hotkeys or {} # e.g. {"clipboard": "ctrl+shift+v", "screenshot": "win+shift+s"}
        self._registered_hotkeys = {}
        self.paused = False # map name to actual hotkey string registered
        
        for name, key in self.hotkeys.items():
            self.register_hotkey(name, key)

    def register_hotkey(self, name, key):
        if not key:
            return False
            
        try:
            # register with keyboard
            def cb(n=name):
                if getattr(self, 'paused', False):
                    return
                payload = None
                if n == "smart_screenshot":
                    try:
                        payload = ImageGrab.grab(all_screens=True)
                    except Exception:
                        pass
                self.action_triggered.emit(n, payload)
                
            keyboard.add_hotkey(key, cb)
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
