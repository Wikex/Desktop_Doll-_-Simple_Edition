import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QAbstractNativeEventFilter
import ctypes
from ctypes import wintypes

class WinHotkeyFilter(QAbstractNativeEventFilter):
    def nativeEventFilter(self, eventType, message):
        if eventType == b"windows_generic_MSG" or eventType == b"windows_dispatcher_MSG":
            msg = ctypes.wintypes.MSG.from_address(message.__int__())
            if msg.message == 0x0312: # WM_HOTKEY
                print("Hotkey pressed! ID:", msg.wParam)
                return True, 0
        return False, 0

app = QApplication(sys.argv)
filter = WinHotkeyFilter()
app.installNativeEventFilter(filter)

user32 = ctypes.windll.user32
user32.RegisterHotKey(None, 1, 0x0002 | 0x0004, 0x41) # Ctrl+Shift+A

from PySide6.QtCore import QTimer
def trigger():
    import keyboard
    keyboard.send("ctrl+shift+a")
    print("Simulated key press")
    QTimer.singleShot(500, app.quit)

QTimer.singleShot(1000, trigger)

app.exec()
