from PySide6.QtCore import QBuffer, QIODevice, Qt

class OcrUnavailableError(RuntimeError):
    pass

# Singleton engine to prevent reloading models on every screenshot
_engine = None

def get_engine():
    global _engine
    if _engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            # Lower text_score (0.5→0.3) so standalone digits (which get lower
            # confidence from the recognition model) are not silently dropped.
            # Also lower det box_thresh (0.5→0.4) to accept slightly weaker
            # detection boxes, helping small / isolated characters get through.
            _engine = RapidOCR(text_score=0.3)
            _engine.text_detector.postprocess_op.box_thresh = 0.4
        except Exception as exc:
            raise OcrUnavailableError("OCR 组件加载失败，请确保安装了 rapidocr-onnxruntime。") from exc
    return _engine

def _ocr_scale_factor(qimage):
    max_side = max(qimage.width(), qimage.height())
    if max_side <= 900:
        return 2.5
    if max_side <= 1600:
        return 2.0
    if max_side <= 2400:
        return 1.5
    return 1.0


def _encode_png(qimage, scale_factor):
    image = qimage
    if scale_factor > 1.0:
        image = qimage.scaled(
            int(qimage.width() * scale_factor),
            int(qimage.height() * scale_factor),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def _normalize_box(box, scale_factor):
    if not box:
        return None
    normalized = []
    try:
        for point in box:
            normalized.append([float(point[0]) / scale_factor, float(point[1]) / scale_factor])
    except (TypeError, ValueError, IndexError):
        return None
    return normalized if len(normalized) >= 4 else None


def _normalize_rapidocr_result(raw_result, scale_factor):
    if raw_result is None:
        return []

    # rapidocr-onnxruntime commonly returns (result, elapse). Newer wrappers may
    # return only result. Normalize here so UI code never depends on backend shape.
    result = raw_result[0] if isinstance(raw_result, tuple) and raw_result else raw_result
    if not result:
        return []

    normalized = []
    for item in result:
        if not item or len(item) < 2:
            continue
        box = _normalize_box(item[0], scale_factor)
        text = str(item[1] or "").strip()
        score = 0.0
        if len(item) >= 3:
            try:
                score = float(item[2])
            except (TypeError, ValueError):
                score = 0.0
        if box and text:
            normalized.append({"box": box, "text": text, "score": score})
    return normalized


def recognize_qimage(qimage, languages="chi_sim+eng", scale_factor=None):
    """Recognize text from a QImage using RapidOCR (ONNX).

    Returns a list of dicts: {"box": [[x, y], ...], "text": str, "score": float}.
    Coordinates are always mapped back to the original qimage size.
    """
    engine = get_engine()
    scale = float(scale_factor) if scale_factor else _ocr_scale_factor(qimage)
    data = _encode_png(qimage, scale)
    raw_result = engine(data)
    return _normalize_rapidocr_result(raw_result, scale)
