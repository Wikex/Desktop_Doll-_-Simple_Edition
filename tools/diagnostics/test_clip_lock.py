import sys
import ctypes
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
mime = app.clipboard().mimeData()

user32 = ctypes.windll.user32
if user32.OpenClipboard(0):
    print("OpenClipboard succeeded!")
    user32.CloseClipboard()
else:
    print(f"OpenClipboard FAILED! Error: {ctypes.GetLastError()}")
