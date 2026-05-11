import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QAbstractNativeEventFilter, QTimer
import ctypes

class WinHotkeyFilter(QAbstractNativeEventFilter):
    def nativeEventFilter(self, eventType, message):
        if eventType in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            msg = ctypes.wintypes.MSG.from_address(message.__int__())
            if msg.message == 0x0312:
                print("Captured WM_HOTKEY!", msg.wParam)
                return True, 0
        return False, 0

app = QApplication(sys.argv)
f = WinHotkeyFilter()
app.installNativeEventFilter(f)

user32 = ctypes.windll.user32
res = user32.RegisterHotKey(None, 1, 0x0002 | 0x0004, 0x41) # ctrl+shift+a
print("Register returned:", res)

def trigger():
    import keyboard
    keyboard.send("ctrl+shift+a")
    QTimer.singleShot(500, app.quit)

QTimer.singleShot(1000, trigger)
app.exec()
