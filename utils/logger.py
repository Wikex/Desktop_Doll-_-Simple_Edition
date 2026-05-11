import os
import traceback
from datetime import datetime

from utils.path_helper import get_base_dir


LOG_FILE = os.path.join(get_base_dir(), "desktop_doll.log")


def log_message(message):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n")
    except Exception:
        pass


def log_exception(message):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n")
            f.write(traceback.format_exc())
            f.write("\n")
    except Exception:
        pass
