from PySide6.QtCore import QBuffer, QIODevice

class OcrUnavailableError(RuntimeError):
    pass

# Singleton engine to prevent reloading models on every screenshot
_engine = None

def get_engine():
    global _engine
    if _engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _engine = RapidOCR()
        except Exception as exc:
            raise OcrUnavailableError("OCR 组件加载失败，请确保安装了 rapidocr-onnxruntime。") from exc
    return _engine

def recognize_qimage(qimage, languages="chi_sim+eng"):
    """Recognize text from a QImage using RapidOCR (ONNX)."""
    engine = get_engine()

    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    qimage.save(buffer, "PNG")
    data = bytes(buffer.data())
    
    result, elapse = engine(data)
    return result
