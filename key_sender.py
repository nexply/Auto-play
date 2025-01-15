import win32gui
import win32con
import win32api
import ctypes
from ctypes import wintypes
from typing import Optional

# 定义 Windows API 结构体
class KEYBOARD_INPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))
    ]

class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [
            ("ki", KEYBOARD_INPUT),
            ("padding", ctypes.c_byte * 32)
        ]
    _anonymous_ = ("_input",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("_input", _INPUT)
    ]

class KeySender:
    """按键消息发送器"""
    def __init__(self, target_window: str = "燕云十六声"):
        self.target_window = target_window
        self.hwnd = None
        self._find_window()
        
    def _find_window(self) -> bool:
        """查找目标窗口"""
        self.hwnd = win32gui.FindWindow(None, self.target_window)
        return self.hwnd is not None
    
    def _get_vk_code(self, key: str) -> int:
        """获取虚拟键码"""
        key = key.upper()
        return win32api.VkKeyScan(key) & 0xFF
    
    def send_key(self, key: str, press: bool = True) -> bool:
        """发送按键消息
        Args:
            key: 按键字符
            press: True为按下，False为释放
        """
        if not self.hwnd and not self._find_window():
            return False
            
        # 确保窗口在前台
        if win32gui.GetForegroundWindow() != self.hwnd:
            win32gui.SetForegroundWindow(self.hwnd)
        
        # 准备输入结构体
        vk_code = self._get_vk_code(key)
        inputs = INPUT(
            type=1,  # INPUT_KEYBOARD
            ki=KEYBOARD_INPUT(
                wVk=vk_code,
                wScan=0,
                dwFlags=0x0002 if not press else 0x0000,  # KEYEVENTF_KEYUP for release
                time=0,
                dwExtraInfo=ctypes.pointer(wintypes.ULONG(0))
            )
        )
        
        # 发送输入
        nInputs = 1
        cbSize = ctypes.sizeof(INPUT)
        result = ctypes.windll.user32.SendInput(nInputs, ctypes.byref(inputs), cbSize)
        return result == nInputs 