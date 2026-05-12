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
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
DWMWA_CLOAKED = 14
MIN_TARGET_WIDTH = 8
MIN_TARGET_HEIGHT = 8

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

def get_virtual_screen_rect():
    """返回所有屏幕合并后的物理坐标范围。"""
    left = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    top = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    width = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    height = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    if width <= 0 or height <= 0:
        width = user32.GetSystemMetrics(SM_CXSCREEN)
        height = user32.GetSystemMetrics(SM_CYSCREEN)
    return QRect(left, top, width, height)

def rect_area(rect):
    return max(0, rect.width()) * max(0, rect.height())

def _is_window_cloaked(hwnd):
    cloaked = ctypes.c_int(0)
    try:
        result = dwmapi.DwmGetWindowAttribute(
            hwnd,
            DWMWA_CLOAKED,
            ctypes.byref(cloaked),
            ctypes.sizeof(cloaked),
        )
        return result == 0 and cloaked.value != 0
    except Exception:
        return False

def _clip_to_virtual_screen(rect, virtual_rect):
    if not rect or rect.width() <= 0 or rect.height() <= 0:
        return None
    if not rect.intersects(virtual_rect):
        return None
    clipped = rect.intersected(virtual_rect)
    if clipped.width() < MIN_TARGET_WIDTH or clipped.height() < MIN_TARGET_HEIGHT:
        return None
    return clipped

def _unique_sorted_rects(rects):
    unique_rects = []
    seen = set()
    virtual_rect = get_virtual_screen_rect()
    for rect in rects:
        clipped = _clip_to_virtual_screen(rect, virtual_rect)
        if not clipped:
            continue
        key = (clipped.x(), clipped.y(), clipped.width(), clipped.height())
        if key in seen:
            continue
        unique_rects.append(clipped)
        seen.add(key)

    unique_rects.sort(key=lambda r: (rect_area(r), r.width() + r.height()))
    return unique_rects

def is_window_valid(hwnd):
    """底层判断窗口是否可见且有效"""
    if not user32.IsWindowVisible(hwnd):
        return False
    if _is_window_cloaked(hwnd):
        return False
    
    # 排除托盘、桌面等特殊窗口
    cls_buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, cls_buf, 256)
    cls_name = cls_buf.value
    
    if cls_name in ("Progman", "WorkerW", "Shell_TrayWnd", "SysShadow", "MsgrIMEWindowClass"):
        return False
        
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    if rect.right - rect.left < MIN_TARGET_WIDTH or rect.bottom - rect.top < MIN_TARGET_HEIGHT:
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
    
    rects.append(get_virtual_screen_rect())
    
    return _unique_sorted_rects(rects)

def _rect_from_uia_control(control):
    rect = control.BoundingRectangle
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    if w > 0 and h > 0:
        return QRect(rect.left, rect.top, w, h)
    return None

def get_uia_rects_at(x, y):
    """使用 UIAutomation 获取点位控件及其父级控件边界，返回小到大排序的候选矩形。"""
    rects = []
    try:
        control = auto.ControlFromPoint(x, y)
        seen_controls = set()
        for _ in range(8):
            if not control:
                break

            control_key = id(control)
            if control_key in seen_controls:
                break
            seen_controls.add(control_key)

            rect = _rect_from_uia_control(control)
            if rect:
                rects.append(rect)

            parent_getter = getattr(control, "GetParentControl", None)
            if not callable(parent_getter):
                break
            control = parent_getter()
    except Exception:
        pass
    return _unique_sorted_rects(rects)

def get_uia_rect_at(x, y):
    """使用 UIAutomation 获取无句柄控件的精确边界"""
    rects = get_uia_rects_at(x, y)
    if rects:
        return rects[0]
    return None
