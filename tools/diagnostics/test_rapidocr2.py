from PySide6.QtGui import QImage, QGuiApplication
from PySide6.QtCore import QBuffer, QIODevice
import sys
import numpy as np
from rapidocr_onnxruntime import RapidOCR

app = QGuiApplication(sys.argv)
img = QImage(100, 100, QImage.Format_RGB32)
img.fill(0xFFFFFF)

buffer = QBuffer()
buffer.open(QIODevice.WriteOnly)
img.save(buffer, "PNG")
data = bytes(buffer.data())

engine = RapidOCR()
result, elapse = engine(data)
print("Result:", result)
