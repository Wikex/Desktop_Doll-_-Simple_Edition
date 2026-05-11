import os
import re
import subprocess

from utils.logger import log_exception


URL_PATTERN = re.compile(r"(https?://[^\s]+)")


def first_url(text):
    match = URL_PATTERN.search(text or "")
    return match.group(1) if match else ""


def open_image_location(path):
    if not path or not os.path.exists(path):
        return

    try:
        subprocess.run(["explorer", "/select,", os.path.normpath(path)])
    except Exception as e:
        log_exception(f"Failed to open image folder: {e}")
