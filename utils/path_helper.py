import os
import sys

def get_base_dir():
    if getattr(sys, 'frozen', False):
        # We are running in a bundle (PyInstaller)
        return os.path.dirname(sys.executable)
    else:
        # We are running in a normal Python environment
        # Because this file is in utils/, the base dir is its parent
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIG_FILE = os.path.join(get_base_dir(), "config.json")
