import os
import sys
import time
from PySide6.QtWidgets import QApplication, QFileDialog
from core.windows_recent import list_recent_lnk_files, resolve_lnk_target
import win32com.client

app = QApplication(sys.argv)

print("Please select a file to test...")
path, _ = QFileDialog.getOpenFileName(None, "Select File", "", "All Files (*.*)")

if not path:
    print("No file selected.")
    sys.exit(0)

print(f"Selected: {path}")

time.sleep(2) # Wait for Windows to create the lnk

shell = win32com.client.Dispatch("WScript.Shell")
found = False
for lnk in list_recent_lnk_files():
    target = resolve_lnk_target(lnk, shell)
    if target and os.path.normpath(target) == os.path.normpath(path):
        found = True
        print(f"FOUND IN RECENT: {lnk}")
        break

if not found:
    print("NOT found in recent.")
