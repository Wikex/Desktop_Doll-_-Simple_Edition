MIN_RECORD_SIZE = 10


def is_record_rect_valid(rect):
    return bool(rect and rect.width() >= MIN_RECORD_SIZE and rect.height() >= MIN_RECORD_SIZE)


def record_rect_error_message():
    return f"请选择至少 {MIN_RECORD_SIZE} x {MIN_RECORD_SIZE} 像素的录屏区域。"
