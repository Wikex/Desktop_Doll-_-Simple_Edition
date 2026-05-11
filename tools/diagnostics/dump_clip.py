import win32clipboard
import ctypes

def dump_clipboard():
    try:
        win32clipboard.OpenClipboard()
    except Exception as e:
        print("Could not open clipboard:", e)
        return

    formats = []
    f = win32clipboard.EnumClipboardFormats(0)
    while f:
        formats.append(f)
        f = win32clipboard.EnumClipboardFormats(f)
        
    print("Available Clipboard Formats:")
    for f in formats:
        name = "Unknown"
        if f == 1: name = "CF_TEXT"
        elif f == 2: name = "CF_BITMAP"
        elif f == 3: name = "CF_METAFILEPICT"
        elif f == 8: name = "CF_DIB"
        elif f == 13: name = "CF_UNICODETEXT"
        elif f == 14: name = "CF_ENHMETAFILE"
        else:
            try:
                name = win32clipboard.GetClipboardFormatName(f)
            except:
                name = f"Custom/Unknown ({f})"
        print(f" - {f}: {name}")
        
    win32clipboard.CloseClipboard()

dump_clipboard()
