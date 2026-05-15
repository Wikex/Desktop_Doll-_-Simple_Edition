from PySide6.QtGui import QImage
from core.ocr import recognize_qimage

img = QImage(100, 100, QImage.Format_ARGB32)
img.fill(0)
try:
    print(recognize_qimage(img))
except Exception as e:
    import traceback
    traceback.print_exc()
