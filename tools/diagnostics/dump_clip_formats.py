import win32clipboard
try:
    win32clipboard.OpenClipboard()
    formats = []
    f = win32clipboard.EnumClipboardFormats(0)
    while f:
        try:
            name = win32clipboard.GetClipboardFormatName(f)
            formats.append(f"{f} ({name})")
        except:
            formats.append(str(f))
        f = win32clipboard.EnumClipboardFormats(f)
    win32clipboard.CloseClipboard()
    print("Formats:", formats)
except Exception as e:
    print("Error:", e)
