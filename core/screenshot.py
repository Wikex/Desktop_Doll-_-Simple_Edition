import ctypes
from ctypes import wintypes
from PySide6.QtCore import QRect
import uiautomation as auto

# 设置 UIAutomation 超时，防止悬浮时卡顿
auto.uiautomation.SetGlobalSearchTimeout(0.1)

# C-level Windows API Bindings via ctypes for maximum performance
user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi

# 预定义 C 参数类型以提升 ctypes 调用速度
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumChildWindows.argtypes = [wintypes.HWND, WNDENUMPROC, wintypes.LPARAM]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]

DWMWA_EXTENDED_FRAME_BOUNDS = 9
SM_CXSCREEN = 0
SM_CYSCREEN = 1

def get_accurate_window_rect(hwnd):
    """使用 C 底层 DWM 获取精确的窗口边界（去掉阴影）"""
    rect = wintypes.RECT()
    try:
        # 尝试获取 DWM 扩展框架边界
        result = dwmapi.DwmGetWindowAttribute(
            hwnd, 
            DWMWA_EXTENDED_FRAME_BOUNDS, 
            ctypes.byref(rect), 
            ctypes.sizeof(rect)
        )
        if result == 0:
            return QRect(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    except Exception:
        pass
    
    # 回退到标准 C API
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return QRect(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)

def is_window_valid(hwnd):
    """底层判断窗口是否可见且有效"""
    if not user32.IsWindowVisible(hwnd):
        return False
    
    # 排除托盘、桌面等特殊窗口
    cls_buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, cls_buf, 256)
    cls_name = cls_buf.value
    
    if cls_name in ("Progman", "Shell_TrayWnd"):
        return False
        
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    if rect.right - rect.left <= 5 or rect.bottom - rect.top <= 5:
        return False
    return True

def get_all_visible_rects():
    """使用 C-FFI 获取当前屏幕所有有效窗口和可见子控件的矩形"""
    rects = []
    
    @WNDENUMPROC
    def callback(hwnd, _):
        if is_window_valid(hwnd):
            child_rects = []
            
            @WNDENUMPROC
            def child_callback(chwnd, _):
                if is_window_valid(chwnd):
                    child_rects.append(get_accurate_window_rect(chwnd))
                return True
                
            try:
                user32.EnumChildWindows(hwnd, child_callback, 0)
            except Exception:
                pass
                
            rects.extend(child_rects)
            rects.append(get_accurate_window_rect(hwnd))
            
        return True

    user32.EnumWindows(callback, 0)
    
    # 屏幕范围作为保底
    screen_w = user32.GetSystemMetrics(SM_CXSCREEN)
    screen_h = user32.GetSystemMetrics(SM_CYSCREEN)
    rects.append(QRect(0, 0, screen_w, screen_h))
    
    # 去重并排序
    unique_rects = []
    seen = set()
    for r in rects:
        t = (r.x(), r.y(), r.width(), r.height())
        if t not in seen:
            unique_rects.append(r)
            seen.add(t)
            
    return unique_rects

def get_uia_rect_at(x, y):
    """使用 UIAutomation 获取无句柄控件的精确边界"""
    try:
        control = auto.ControlFromPoint(x, y)
        if control:
            rect = control.BoundingRectangle
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w > 0 and h > 0:
                return QRect(rect.left, rect.top, w, h)
    except Exception:
        pass
    return None
