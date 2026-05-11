import win32clipboard
import ctypes
from ctypes import wintypes
import sys
import traceback

def test_emf():
    print("Testing clipboard...")
    try:
        win32clipboard.OpenClipboard()
    except Exception as e:
        print("Failed to open clipboard:", e)
        return

    try:
        formats = []
        f = win32clipboard.EnumClipboardFormats(0)
        while f:
            formats.append(f)
            f = win32clipboard.EnumClipboardFormats(f)
            
        print("Formats available:", formats)
        
        # Test getting text just to see if we can get anything
        if win32clipboard.CF_UNICODETEXT in formats:
            print("Text available:", repr(win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)[:50]))
            
        if 14 in formats: # CF_ENHMETAFILE
            print("Trying CF_ENHMETAFILE via win32clipboard...")
            try:
                handle = win32clipboard.GetClipboardData(14)
                print("win32clipboard HEMF handle:", handle)
            except Exception as e:
                print("win32clipboard.GetClipboardData(14) error:", e)

            print("Trying CF_ENHMETAFILE via ctypes...")
            user32 = ctypes.windll.user32
            user32.GetClipboardData.restype = wintypes.HANDLE
            user32.GetClipboardData.argtypes = [wintypes.UINT]
            handle_c = user32.GetClipboardData(14)
            print("ctypes HEMF handle:", handle_c)
            
        if 3 in formats: # CF_METAFILEPICT
            print("Trying CF_METAFILEPICT...")
            try:
                handle_3 = win32clipboard.GetClipboardData(3)
                print("CF_METAFILEPICT handle:", handle_3)
            except Exception as e:
                print("CF_METAFILEPICT error:", e)
                
    except Exception as e:
        traceback.print_exc()
    finally:
        win32clipboard.CloseClipboard()

test_emf()
