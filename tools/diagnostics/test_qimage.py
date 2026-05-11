import ctypes
from ctypes import wintypes
from PySide6.QtGui import QImage, QGuiApplication
import sys

app = QGuiApplication(sys.argv)
width, height = 100, 100
buffer = ctypes.create_string_buffer(width * height * 4)
try:
    img = QImage(buffer, width, height, QImage.Format.Format_RGB32)
    img_copy = img.copy()
    print("QImage creation SUCCESS")
except Exception as e:
    print("QImage creation ERROR:", e)
