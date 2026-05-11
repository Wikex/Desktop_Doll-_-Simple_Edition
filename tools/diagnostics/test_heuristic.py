from PySide6.QtWidgets import QApplication
from core.clipboard import ClipboardManager
import sys

app = QApplication(sys.argv)
mgr = ClipboardManager()

class MockMime:
    def formats(self):
        return ["text/plain"]
    def hasHtml(self): return False

def mock_native_formats():
    return ["Ole Private Data", "DataObject", "CF_ENHMETAFILE"]

mime = MockMime()
# Simulate
print("Would ignore?", mgr._is_format_painter(mime))
