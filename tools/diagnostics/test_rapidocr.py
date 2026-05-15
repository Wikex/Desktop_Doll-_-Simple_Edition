from PySide6.QtGui import QImage, QGuiApplication
import sys
import numpy as np
from rapidocr_onnxruntime import RapidOCR

app = QGuiApplication(sys.argv)
img = QImage(100, 100, QImage.Format_RGB32)
img.fill(0xFFFFFF)

def qimage_to_numpy(qimage):
    qimage = qimage.convertToFormat(QImage.Format_RGB32)
    width = qimage.width()
    height = qimage.height()
    ptr = qimage.bits()
    ptr.setsize(height * width * 4)
    arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))
    return arr[..., :3] # drop alpha, BGR format is fine for rapidocr

img_arr = qimage_to_numpy(img)
engine = RapidOCR()
result, elapse = engine(img_arr)
print("Result:", result)
