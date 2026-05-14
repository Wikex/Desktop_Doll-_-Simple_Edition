import io

from PySide6.QtCore import QBuffer, QIODevice


class OcrUnavailableError(RuntimeError):
    pass


def recognize_qimage(qimage, languages="chi_sim+eng"):
    """Recognize text from a QImage using optional pytesseract backend."""
    try:
        import pytesseract
        from PIL import Image
    except Exception as exc:
        raise OcrUnavailableError("OCR 组件不可用：请安装 Tesseract 和 pytesseract。") from exc

    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    qimage.save(buffer, "PNG")
    data = bytes(buffer.data())
    image = Image.open(io.BytesIO(data))
    text = pytesseract.image_to_string(image, lang=languages)
    return text.strip()
