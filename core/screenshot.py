import win32gui
import win32api
import win32con
import ctypes
from ctypes import wintypes
from PySide6.QtCore import QRect
import uiautomation as auto

# 设置 UIAutomation 超时，防止悬浮时卡顿
auto.uiautomation.SetGlobalSearchTimeout(0.1)

# DWM 相关常量
DWMWA_EXTENDED_FRAME_BOUNDS = 9

def get_accurate_window_rect(hwnd):
    """使用 DWM 获取精确的窗口边界（去掉阴影）"""
    rect = wintypes.RECT()
    try:
        # 尝试获取 DWM 扩展框架边界
        result = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            hwnd, 
            DWMWA_EXTENDED_FRAME_BOUNDS, 
            ctypes.byref(rect), 
            ctypes.sizeof(rect)
        )
        if result == 0:
            return QRect(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    except Exception:
        pass
    
    # 回退到标准 API
    r = win32gui.GetWindowRect(hwnd)
    return QRect(r[0], r[1], r[2] - r[0], r[3] - r[1])

def is_window_valid(hwnd):
    """判断窗口是否可见且有效"""
    if not win32gui.IsWindowVisible(hwnd):
        return False
    
    # 排除托盘、桌面等特殊窗口（可选）
    title = win32gui.GetWindowText(hwnd)
    cls = win32gui.GetClassName(hwnd)
    if cls in ["Progman", "Shell_TrayWnd"]:
        return False
        
    rect = win32gui.GetWindowRect(hwnd)
    if rect[2] - rect[0] <= 5 or rect[3] - rect[1] <= 5:
        return False
    return True

def get_all_visible_rects():
    """获取当前屏幕所有有效窗口和可见子控件的矩形"""
    rects = []
    
    def callback(hwnd, _):
        if is_window_valid(hwnd):
            child_rects = []
            
            def child_callback(chwnd, _):
                if is_window_valid(chwnd):
                    child_rects.append(get_accurate_window_rect(chwnd))
                return True
                
            # 尝试获取子窗口
            try:
                win32gui.EnumChildWindows(hwnd, child_callback, None)
            except Exception:
                pass
                
            # 关键修复：必须将子控件排在父窗口前面！
            # 因为 find_best_rect 会返回包含鼠标的第一个匹配项。
            # 子控件在视觉上始终处于父窗口的“上层”。
            rects.extend(child_rects)
            rects.append(get_accurate_window_rect(hwnd))
            
        return True

    win32gui.EnumWindows(callback, None)
    
    # 屏幕范围作为保底
    screen_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
    screen_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
    rects.append(QRect(0, 0, screen_w, screen_h))
    
    # 去重并排序（从小到大，方便 find_best_rect 匹配）
    unique_rects = []
    seen = set()
    for r in rects:
        t = (r.x(), r.y(), r.width(), r.height())
        if t not in seen:
            unique_rects.append(r)
            seen.add(t)
            
    return unique_rects

def get_uia_rect_at(x, y):
    """使用 UIAutomation 获取无句柄控件的精确边界 (用于现代应用如Electron, WinUI, Chrome等)"""
    try:
        control = auto.ControlFromPoint(x, y)
        if control:
            rect = control.BoundingRectangle
            # (left, top, right, bottom)
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w > 0 and h > 0:
                return QRect(rect.left, rect.top, w, h)
    except Exception:
        pass
    return None
