from PySide6.QtGui import QImage, QGuiApplication, QPainter, QFont
from PySide6.QtCore import QBuffer, QIODevice, Qt
import sys
from rapidocr_onnxruntime import RapidOCR

app = QGuiApplication(sys.argv)
img = QImage(300, 100, QImage.Format_RGB32)
img.fill(0xFFFFFF)
painter = QPainter(img)
font = QFont("Arial", 24)
painter.setFont(font)
painter.setPen(Qt.black)
painter.drawText(img.rect(), Qt.AlignCenter, "Hello 世界")
painter.end()

buffer = QBuffer()
buffer.open(QIODevice.WriteOnly)
img.save(buffer, "PNG")
data = bytes(buffer.data())

engine = RapidOCR()
result, elapse = engine(data)
print("Result:", result)
if result:
    texts = [res[1] for res in result]
    print("Extracted:", "\n".join(texts))
