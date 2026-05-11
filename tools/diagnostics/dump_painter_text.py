import win32clipboard
try:
    win32clipboard.OpenClipboard()
    text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()
    print("Text in clipboard:", repr(text))
except Exception as e:
    print("Error:", e)
