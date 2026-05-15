import sys
from PySide6.QtWidgets import QApplication, QLabel, QWidget
from PySide6.QtCore import Qt

app = QApplication(sys.argv)
w = QWidget()
w.resize(300, 200)
w.setStyleSheet("background-color: white;")

l = QLabel("Hello World This is a test", w)
l.setGeometry(50, 50, 200, 50)
l.setTextInteractionFlags(Qt.TextSelectableByMouse)
l.setStyleSheet("QLabel { background-color: rgba(0, 120, 215, 60); color: transparent; selection-background-color: rgba(0, 120, 215, 150); selection-color: transparent; }")

w.show()
sys.exit(app.exec())