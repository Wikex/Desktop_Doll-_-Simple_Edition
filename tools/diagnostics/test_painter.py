import win32clipboard

def find_format_painter():
    formats = []
    try:
        win32clipboard.OpenClipboard()
        f = win32clipboard.EnumClipboardFormats(0)
        while f:
            try:
                name = win32clipboard.GetClipboardFormatName(f)
                formats.append(name.lower())
            except:
                pass
            f = win32clipboard.EnumClipboardFormats(f)
    except:
        pass
    finally:
        win32clipboard.CloseClipboard()
    
    for name in formats:
        if "format" in name and "painter" in name:
            return name
        if "brush" in name:
            return name
    return formats
print(find_format_painter())
