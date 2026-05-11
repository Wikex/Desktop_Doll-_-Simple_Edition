import sys
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
mime = app.clipboard().mimeData()
print("Qt MIME formats:")
for f in mime.formats():
    print(f" - {f}")
