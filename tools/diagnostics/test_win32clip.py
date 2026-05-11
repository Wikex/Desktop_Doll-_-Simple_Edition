import win32clipboard
try:
    win32clipboard.OpenClipboard()
    formats = []
    f = win32clipboard.EnumClipboardFormats(0)
    while f:
        formats.append(f)
        f = win32clipboard.EnumClipboardFormats(f)
    print("Formats:", formats)
    
    if 14 in formats:
        h = win32clipboard.GetClipboardData(14)
        print("HEMF:", h)
except Exception as e:
    print("Error:", e)
finally:
    win32clipboard.CloseClipboard()
