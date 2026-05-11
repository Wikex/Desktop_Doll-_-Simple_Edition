import sys
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
mime = app.clipboard().mimeData()
print("Has text:", mime.hasText())
print("Text content:", repr(mime.text()))
print("Has image:", mime.hasImage())
