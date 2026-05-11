import win32clipboard
try:
    win32clipboard.OpenClipboard()
    text = win32clipboard.GetClipboardData(13)
    win32clipboard.CloseClipboard()
    print("Text:", repr(text))
except Exception as e:
    print("Error:", e)
