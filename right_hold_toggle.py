from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wintypes
import json
import queue
import signal
import sys
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
import uuid
import webbrowser
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from tkinter import messagebox, ttk

try:
    import pystray
    from PIL import Image, ImageDraw, ImageTk
except Exception:
    pystray = None
    Image = None
    ImageDraw = None
    ImageTk = None


APP_NAME = "D4Helper"
GITHUB_LATEST_RELEASE_API = "https://api.github.com/repos/indiefun/d4-helper/releases/latest"
GITHUB_RELEASES_URL = "https://github.com/indiefun/d4-helper/releases/latest"
APP_MUTEX_NAME = "Global\\D4HelperSingleInstance"
APP_MUTEX_HANDLE: wintypes.HANDLE | None = None
PENDING_RELEASES: set[tuple[str, int]] = set()
PENDING_RELEASES_LOCK = threading.Lock()
DEFAULT_WINDOW_TITLE_CONTAINS = "暗黑破坏神IV"
DEFAULT_PROCESS_NAME = "Diablo IV.exe"
SUPPORT_QQ_GROUP = "958154728"


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_path(relative_path: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", app_dir()))
    return base / relative_path


CONFIG_PATH = app_dir() / "config.json"
DONATE_IMAGE_PATH = resource_path("assets/donate.jpg")
APP_ICON_PATH = resource_path("assets/app-icon.png")
WORM_ROUTE_DIR = resource_path("assets/worm-routes")
VERSION_PATH = app_dir() / "VERSION"
BUNDLED_VERSION_PATH = resource_path("VERSION")


def read_app_version() -> str:
    for path in (VERSION_PATH, BUNDLED_VERSION_PATH):
        try:
            version = path.read_text(encoding="utf-8").strip()
            if version:
                return version.lstrip("v")
        except OSError:
            pass
    return "unknown"


APP_VERSION = read_app_version()
APP_TITLE = f"{APP_NAME} v{APP_VERSION}" if APP_VERSION != "unknown" else APP_NAME


def acquire_single_instance() -> bool:
    global APP_MUTEX_HANDLE
    APP_MUTEX_HANDLE = kernel32.CreateMutexW(None, True, APP_MUTEX_NAME)
    if not APP_MUTEX_HANDLE:
        return True
    return ctypes.get_last_error() != ERROR_ALREADY_EXISTS

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
GA_ROOT = 2
HWND_TOPMOST = wintypes.HWND(-1)
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

VK_XBUTTON1 = 0x05
VK_XBUTTON2 = 0x06
VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_CAPITAL = 0x14
VK_SPACE = 0x20
VK_PRIOR = 0x21
VK_NEXT = 0x22
VK_END = 0x23
VK_HOME = 0x24
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_INSERT = 0x2D
VK_DELETE = 0x2E
VK_F1 = 0x70
VK_F2 = 0x71
VK_F3 = 0x72
VK_F4 = 0x73
VK_F5 = 0x74
VK_F6 = 0x75
VK_F7 = 0x76
VK_F8 = 0x77
VK_F9 = 0x78
VK_F10 = 0x79
VK_F11 = 0x7A
VK_F12 = 0x7B

INPUT_MOUSE = 0
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
KEYEVENTF_KEYUP = 0x0002

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MAX_PATH = 260
ERROR_ALREADY_EXISTS = 183

ACTION_NONE = "none"
ACTION_HOLD = "hold"
ACTION_PRESS_CYCLE = "press_cycle"
ACTION_RECORDED = "recorded"
PLAYBACK_ONCE = "once"
PLAYBACK_LOOP = "loop"

KEYBOARD_KEYS = {
    **{str(index): 0x30 + index for index in range(10)},
    **{chr(code).lower(): code for code in range(0x41, 0x5B)},
    "space": VK_SPACE,
    "tab": VK_TAB,
    "enter": VK_RETURN,
    "backspace": VK_BACK,
    "capslock": VK_CAPITAL,
    "shift": VK_SHIFT,
    "ctrl": VK_CONTROL,
    "alt": VK_MENU,
    "insert": VK_INSERT,
    "delete": VK_DELETE,
    "home": VK_HOME,
    "end": VK_END,
    "pageup": VK_PRIOR,
    "pagedown": VK_NEXT,
    "up": VK_UP,
    "down": VK_DOWN,
    "left_arrow": VK_LEFT,
    "right_arrow": VK_RIGHT,
    "f1": VK_F1,
    "f2": VK_F2,
    "f3": VK_F3,
    "f4": VK_F4,
    "f5": VK_F5,
    "f6": VK_F6,
    "f7": VK_F7,
    "f8": VK_F8,
    "f9": VK_F9,
    "f10": VK_F10,
    "f11": VK_F11,
    "f12": VK_F12,
}
MOUSE_KEYS = {
    "xbutton1": VK_XBUTTON1,
    "xbutton2": VK_XBUTTON2,
    "middle": 0x04,
}
TRIGGER_KEYS = {**MOUSE_KEYS, **KEYBOARD_KEYS}
KEY_LABELS = {
    "xbutton1": "侧键 1",
    "xbutton2": "侧键 2",
    "middle": "鼠标中键",
    **{str(index): str(index) for index in range(10)},
    **{chr(code).lower(): chr(code) for code in range(0x41, 0x5B)},
    "space": "空格",
    "tab": "Tab",
    "enter": "Enter",
    "backspace": "Backspace",
    "capslock": "CapsLock",
    "shift": "Shift",
    "ctrl": "Ctrl",
    "alt": "Alt",
    "insert": "Insert",
    "delete": "Delete",
    "home": "Home",
    "end": "End",
    "pageup": "PageUp",
    "pagedown": "PageDown",
    "up": "方向键上",
    "down": "方向键下",
    "left_arrow": "方向键左",
    "right_arrow": "方向键右",
    **{f"f{index}": f"F{index}" for index in range(1, 13)},
}
TRIGGER_LABELS = {key: KEY_LABELS[key] for key in TRIGGER_KEYS}
OPTIONAL_TRIGGER_KEYS = {
    "none": None,
    **TRIGGER_KEYS,
}
OPTIONAL_TRIGGER_LABELS = {
    "none": "无",
    **TRIGGER_LABELS,
}
ACTION_LABELS = {
    ACTION_NONE: "无",
    ACTION_HOLD: "自动按住",
    ACTION_PRESS_CYCLE: "循环连按",
    ACTION_RECORDED: "录制回放",
}
PLAYBACK_MODE_LABELS = {
    PLAYBACK_ONCE: "执行一次",
    PLAYBACK_LOOP: "循环执行",
}
PRESS_KEYS = {
    "none": None,
    "left": "left",
    "right": "right",
    "middle": "middle",
    **KEYBOARD_KEYS,
}
PRESS_KEY_LABELS = {
    "none": "无",
    "left": "左键",
    "right": "右键",
    "middle": "鼠标中键",
    **{key: KEY_LABELS[key] for key in KEYBOARD_KEYS},
}
COMMON_TRIGGER_KEYS = [
    "xbutton1",
    "xbutton2",
    "middle",
    "f1",
    "f2",
    "f3",
    "f4",
    "f5",
    "f6",
    "f7",
    "f8",
    "f9",
    "f10",
    "f11",
    "f12",
]
COMMON_OPTIONAL_TRIGGER_KEYS = [
    "none",
    *COMMON_TRIGGER_KEYS,
]
COMMON_PRESS_KEYS = [
    "none",
    "left",
    "right",
    "middle",
    "1",
    "2",
    "3",
    "4",
    "space",
    "tab",
    "shift",
    "ctrl",
    "alt",
]
LABEL_TO_KEY_ID = {value.lower(): key for key, value in {**PRESS_KEY_LABELS, **TRIGGER_LABELS}.items()}
KEY_ALIASES = {
    "无": "none",
    "none": "none",
    "space": "space",
    "空格键": "space",
    "鼠标左键": "left",
    "mouse left": "left",
    "left button": "left",
    "鼠标右键": "right",
    "mouse right": "right",
    "right button": "right",
    "鼠标中键": "middle",
    "middle button": "middle",
    "mbutton": "middle",
    "侧键1": "xbutton1",
    "侧键 1": "xbutton1",
    "xbutton1": "xbutton1",
    "mouse4": "xbutton1",
    "侧键2": "xbutton2",
    "侧键 2": "xbutton2",
    "xbutton2": "xbutton2",
    "mouse5": "xbutton2",
    "control": "ctrl",
    "ctrl": "ctrl",
    "escape": "esc",
    "esc": "esc",
    "pgup": "pageup",
    "pgdn": "pagedown",
    "left": "left_arrow",
    "right": "right_arrow",
}
RECORDABLE_KEYS = {
    "left": 0x01,
    "right": 0x02,
    "middle": 0x04,
    **MOUSE_KEYS,
    **KEYBOARD_KEYS,
}
RECORD_CANCEL_KEY = 0x1B
DEFAULT_INTERVAL_MS = 100
MIN_MACRO_INTERVAL_MS = 1
DEFAULT_POLL_INTERVAL_MS = 50
DEFAULT_OVERLAY_OPACITY = 0.60
DEFAULT_RECORD_TRIGGER = "f12"
DEFAULT_RECORD_COUNTDOWN_SEC = 3
DEFAULT_RECORD_MAX_SECONDS = 30
DEFAULT_ROUTE_TRIGGER = "f11"
DEFAULT_OVERLAY_LAYOUT_TRIGGER = "f10"
DEFAULT_ROUTE_OPACITY = 0.90
DEFAULT_ROUTE_X = 1000
DEFAULT_ROUTE_Y = 120
MAX_RECORDED_EVENTS = 500
MAX_FOREGROUND_POLL_MS = 50
FOREGROUND_METADATA_REFRESH_SECONDS = 1.0

ROUTE_SIZE_LABELS = {
    "small": "小",
    "medium": "中",
    "large": "大",
}


@dataclass(frozen=True)
class WormRouteMap:
    id: str
    name: str

    @property
    def image_path(self) -> Path:
        return WORM_ROUTE_DIR / f"route-{self.id}.webp"

    @property
    def thumbnail_path(self) -> Path:
        return WORM_ROUTE_DIR / "thumbnails" / f"thumb-{self.id}.webp"


WORM_ROUTE_MAPS = (
    WormRouteMap("01", "马洛文"),
    WormRouteMap("03", "图尔杜拉"),
    WormRouteMap("14", "黑石警戒塔"),
    WormRouteMap("15", "基兰岱"),
    WormRouteMap("19", "墨涅斯塔"),
    WormRouteMap("21", "基奥瓦沙西"),
    WormRouteMap("25", "废墟祭坛"),
    WormRouteMap("26", "铁狼营地"),
    WormRouteMap("28", "吉库尔"),
    WormRouteMap("32", "维金哈尼"),
    WormRouteMap("33", "扎宾泽特西"),
)
WORM_ROUTE_MAP_BY_ID = {route.id: route for route in WORM_ROUTE_MAPS}


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", INPUT_UNION),
    ]


class FAST_EVENT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("key", ctypes.c_int),
        ("at_ms", ctypes.c_int),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("has_pos", ctypes.c_int),
    ]


user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = wintypes.BOOL
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = wintypes.LONG
user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
user32.SetWindowLongW.restype = wintypes.LONG
user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.SetWindowPos.restype = wintypes.BOOL

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL


def _native_item_code(item: str) -> int:
    if item == "left":
        return 1
    if item == "right":
        return 2
    if item == "middle":
        return 3
    virtual_key = PRESS_KEYS.get(item)
    if isinstance(virtual_key, int):
        return 0x100 + virtual_key
    return 0


class FastInputKernel:
    """Optional native scheduler used for sub-10ms macro timing."""

    def __init__(self) -> None:
        self.dll: ctypes.CDLL | None = None
        self.handle: ctypes.c_void_p | None = None
        self.slots: dict[str, int] = {}
        self.target_active = False
        self.supported = True
        candidates = (
            resource_path("fast_input_kernel.dll"),
            app_dir() / "fast_input_kernel.dll",
            app_dir() / "native" / "fast_input_kernel.dll",
        )
        for path in candidates:
            try:
                if not path.exists():
                    continue
                self.dll = ctypes.WinDLL(str(path))
                break
            except OSError:
                self.dll = None
        if self.dll is None:
            return

        self.dll.rhk_create.restype = ctypes.c_void_p
        self.dll.rhk_destroy.argtypes = [ctypes.c_void_p]
        self.dll.rhk_start.argtypes = [ctypes.c_void_p]
        self.dll.rhk_stop.argtypes = [ctypes.c_void_p]
        self.dll.rhk_clear_config.argtypes = [ctypes.c_void_p]
        self.dll.rhk_set_target_active.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.dll.rhk_set_active.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        self.dll.rhk_is_active.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.dll.rhk_is_active.restype = ctypes.c_int
        self.dll.rhk_configure_macro.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_int,
            ctypes.POINTER(FAST_EVENT),
            ctypes.c_int,
        ]
        self.handle = ctypes.c_void_p(self.dll.rhk_create())
        if not self.handle:
            self.dll = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    @property
    def available(self) -> bool:
        return self.supported and self.dll is not None and bool(self.handle)

    def configure(self, macros: list[MacroConfig]) -> None:
        if self.dll is None or not self.handle:
            return
        if len(macros) > 64:
            self.supported = False
            self.slots = {}
            self.dll.rhk_clear_config(self.handle)
            return
        self.supported = True
        self.slots = {macro.id: index for index, macro in enumerate(macros[:64])}
        self.dll.rhk_clear_config(self.handle)
        for index, macro in enumerate(macros[:64]):
            sequence_values = [
                value for item in macro.sequence
                if (value := _native_item_code(item))
            ]
            hold_values = [
                value for item in hold_items(macro)
                if (value := _native_item_code(item))
            ]
            recording_values = normalize_recording(macro.recording)
            sequence_array = (ctypes.c_int * max(1, len(sequence_values)))(*sequence_values)
            hold_array = (ctypes.c_int * max(1, len(hold_values)))(*hold_values)
            event_values = []
            for event in recording_values:
                item = _native_item_code(press_key_label_to_id(str(event.get("key", ""))))
                event_type = 1 if str(event.get("type", "")) == "key_down" else 2
                if not item:
                    continue
                try:
                    at_ms = max(0, int(event.get("at_ms", 0)))
                except (TypeError, ValueError):
                    at_ms = 0
                try:
                    x = int(event.get("x", 0))
                    y = int(event.get("y", 0))
                except (TypeError, ValueError):
                    x, y = 0, 0
                event_values.append(FAST_EVENT(event_type, item, at_ms, x, y, int("x" in event and "y" in event)))
            event_array = (FAST_EVENT * max(1, len(event_values)))()
            for event_index, event in enumerate(event_values):
                event_array[event_index] = event
            action_id = {
                ACTION_NONE: 0,
                ACTION_HOLD: 1,
                ACTION_PRESS_CYCLE: 2,
                ACTION_RECORDED: 3,
            }.get(macro.action, 0)
            self.dll.rhk_configure_macro(
                self.handle,
                index,
                int(bool(macro.enabled)),
                action_id,
                max(int(macro.interval_ms), MIN_MACRO_INTERVAL_MS),
                int(macro.playback_mode == PLAYBACK_LOOP),
                sequence_array,
                len(sequence_values),
                hold_array,
                len(hold_values),
                event_array,
                len(event_values),
            )

    def start(self) -> None:
        if self.available:
            self.dll.rhk_start(self.handle)

    def stop(self) -> None:
        if self.dll is not None and self.handle:
            self.dll.rhk_stop(self.handle)

    def close(self) -> None:
        if self.dll is not None and self.handle:
            self.dll.rhk_destroy(self.handle)
            self.handle = None
            self.dll = None

    def set_target_active(self, active: bool) -> None:
        if self.available:
            self.target_active = bool(active)
            self.dll.rhk_set_target_active(self.handle, int(self.target_active))

    def set_active(self, macro_id: str, active: bool) -> None:
        if self.available and macro_id in self.slots:
            self.dll.rhk_set_active(self.handle, self.slots[macro_id], int(bool(active)))

    def is_active(self, macro_id: str) -> bool:
        if not self.available or macro_id not in self.slots:
            return False
        return bool(self.dll.rhk_is_active(self.handle, self.slots[macro_id]))

    def reset_active(self) -> None:
        if not self.available:
            return
        self.dll.rhk_set_target_active(self.handle, 0)
        if self.target_active:
            self.dll.rhk_set_target_active(self.handle, 1)


@dataclass
class MacroConfig:
    enabled: bool
    name: str
    trigger: str
    action: str
    sequence: list[str]
    interval_ms: int = DEFAULT_INTERVAL_MS
    id: str = ""
    playback_mode: str = PLAYBACK_ONCE
    recording: list[dict[str, object]] | None = None


@dataclass
class ToggleProfile:
    enabled: bool
    trigger: str
    macro_ids: list[str]
    id: str = ""


@dataclass
class Config:
    window_title_contains: str = DEFAULT_WINDOW_TITLE_CONTAINS
    process_name: str = DEFAULT_PROCESS_NAME
    macros: list[MacroConfig] | None = None
    toggle_profiles: list[ToggleProfile] | None = None
    poll_interval_ms: int = DEFAULT_POLL_INTERVAL_MS
    overlay_enabled: bool = True
    overlay_x: int = 20
    overlay_y: int = 20
    overlay_opacity: float = DEFAULT_OVERLAY_OPACITY
    recording_trigger: str = DEFAULT_RECORD_TRIGGER
    recording_countdown_sec: int = DEFAULT_RECORD_COUNTDOWN_SEC
    recording_max_seconds: int = DEFAULT_RECORD_MAX_SECONDS
    route_enabled: bool = True
    route_trigger: str = DEFAULT_ROUTE_TRIGGER
    overlay_layout_trigger: str = DEFAULT_OVERLAY_LAYOUT_TRIGGER
    route_x: int = DEFAULT_ROUTE_X
    route_y: int = DEFAULT_ROUTE_Y
    route_size: str = "medium"
    route_opacity: float = DEFAULT_ROUTE_OPACITY
    route_last_selected: str = "01"


@dataclass(frozen=True)
class Snapshot:
    target_active: bool
    macro_states: dict[str, bool]
    config: Config
    foreground_title: str
    foreground_process: str
    target_window_rect: tuple[int, int, int, int] | None = None
    recording_status: str = "idle"
    recording_trigger: str = DEFAULT_RECORD_TRIGGER
    recording_countdown_remaining: int = 0
    recording_elapsed_ms: int = 0
    recording_event_count: int = 0


class MacroEngine:
    def __init__(self, config: Config, event_queue: queue.Queue[object] | None = None) -> None:
        self.lock = threading.RLock()
        self.config = normalize_config(config)
        self.config_generation = 0
        self.event_queue = event_queue
        self.running = False
        self.thread: threading.Thread | None = None
        self.right_is_down = False
        self.left_is_down = False
        self.middle_is_down = False
        self.held_keys: set[int] = set()
        self.active_macros: set[str] = set()
        self.last_trigger_down: dict[str, bool] = {}
        self.next_press_at: dict[str, float] = {}
        self.sequence_index: dict[str, int] = {}
        self.playback_state: dict[str, dict[str, object]] = {}
        self.playback_held_items: dict[str, set[str]] = {}
        self.target_active = False
        self.foreground_title = ""
        self.foreground_process = ""
        self.foreground_hwnd = 0
        self.foreground_metadata_at = 0.0
        self.target_window_rect: tuple[int, int, int, int] | None = None
        self.overlay_layout_active = False
        self.recording_status = "idle"
        self.recording_countdown_until = 0.0
        self.recording_started_at = 0.0
        self.recorded_events: list[dict[str, object]] = []
        self.record_last_down: dict[str, bool] = {}
        self.native_kernel = FastInputKernel()
        self.native_started = False

    @property
    def native_enabled(self) -> bool:
        return self.native_started and self.native_kernel.available

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        if self.native_kernel.available:
            self.native_kernel.configure(self.config.macros or [])
            if self.native_kernel.available:
                self.native_kernel.start()
                self.native_started = True
        self.running = True
        self.thread = threading.Thread(target=self._run, name="macro-engine", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.5)
        with self.lock:
            self.active_macros.clear()
        self.release_all_inputs_with_retry()
        self.native_kernel.stop()
        self.native_kernel.close()
        self.native_started = False

    def update_config(self, config: Config) -> None:
        config = normalize_config(config)
        validate_config(config)
        with self.lock:
            self.config = config
            self.config_generation += 1
            self.active_macros.clear()
            self.last_trigger_down = {}
            self.next_press_at = {}
            self.sequence_index = {}
            self.playback_state = {}
            if self.recording_status in {"countdown", "recording"}:
                self._cancel_recording_locked()
            if self.target_active:
                self._seed_trigger_states_locked(config)
            if self.native_kernel.available:
                self.native_kernel.configure(config.macros or [])
            self.release_all_inputs()

    def update_route_selection(self, route_id: str) -> Config:
        with self.lock:
            if route_id in WORM_ROUTE_MAP_BY_ID:
                self.config.route_last_selected = route_id
            return clone_config(self.config)

    def update_overlay_position(self, overlay_name: str, x: int, y: int) -> Config:
        with self.lock:
            if overlay_name == "status":
                self.config.overlay_x = int(x)
                self.config.overlay_y = int(y)
            elif overlay_name == "route":
                self.config.route_x = int(x)
                self.config.route_y = int(y)
            return clone_config(self.config)

    def set_overlay_layout_active(self, active: bool) -> None:
        with self.lock:
            self.overlay_layout_active = bool(active)

    def snapshot(self) -> Snapshot:
        with self.lock:
            return Snapshot(
                target_active=self.target_active,
                macro_states={macro.id: macro.id in self.active_macros for macro in self.config.macros or []},
                config=clone_config(self.config),
                foreground_title=self.foreground_title,
                foreground_process=self.foreground_process,
                target_window_rect=self.target_window_rect,
                recording_status=self.recording_status,
                recording_trigger=self.config.recording_trigger,
                recording_countdown_remaining=max(0, int(self.recording_countdown_until - time.monotonic() + 0.99)) if self.recording_status == "countdown" else 0,
                recording_elapsed_ms=max(0, int((time.monotonic() - self.recording_started_at) * 1000)) if self.recording_status == "recording" else 0,
                recording_event_count=len(self.recorded_events),
            )

    def _run(self) -> None:
        error_message = ""
        try:
            self._run_loop()
        except Exception as exc:
            error_message = str(exc)
        finally:
            self.running = False
            with self.lock:
                self._clear_macro_state_locked()
            released = self.release_all_inputs_with_retry()
        if error_message and self.event_queue is not None:
            self.event_queue.put({"type": "engine_error", "message": error_message, "released": released})

    def _run_loop(self) -> None:
        while self.running:
            with self.lock:
                config = clone_config(self.config)
                config_generation = self.config_generation

            hwnd, title, process = self._read_foreground_window()
            target_active = foreground_matches_values(config, title, process)
            target_rect = get_window_rect(hwnd) if target_active else None

            release_inputs = False
            special_event: str | None = None
            with self.lock:
                if config_generation != self.config_generation:
                    config = clone_config(self.config)
                    target_active = foreground_matches_values(config, title, process)
                was_target_active = self.target_active
                self.target_active = target_active
                self.foreground_title = title
                self.foreground_process = process
                if self.native_enabled:
                    self.native_kernel.set_target_active(target_active)
                if target_active and target_rect is not None:
                    self.target_window_rect = rect_to_tuple(target_rect)

                target_changed = target_active != was_target_active
                stale_tracked_inputs = not self.active_macros and self._has_tracked_inputs()
                if target_changed or (not target_active and self.active_macros) or stale_tracked_inputs:
                    self._clear_macro_state_locked()
                    release_inputs = True
                if not target_active and self.recording_status in {"countdown", "recording"}:
                    self._cancel_recording_locked()
                if target_active and not was_target_active:
                    self._seed_trigger_states_locked(config)

                recording_triggered = self._handle_recording_trigger_locked(config, target_active)

                layout_virtual_key = TRIGGER_KEYS.get(config.overlay_layout_trigger)
                layout_down = is_key_down(layout_virtual_key) if layout_virtual_key is not None else False
                layout_trigger_key = "overlay:layout"
                layout_triggered = (
                    (target_active or self.overlay_layout_active)
                    and layout_down
                    and not self.last_trigger_down.get(layout_trigger_key, False)
                )
                self.last_trigger_down[layout_trigger_key] = layout_down

                route_virtual_key = TRIGGER_KEYS.get(config.route_trigger)
                route_down = is_key_down(route_virtual_key) if route_virtual_key is not None else False
                route_trigger_key = "route:toggle"
                route_triggered = (
                    config.route_enabled
                    and target_active
                    and route_down
                    and not self.last_trigger_down.get(route_trigger_key, False)
                )
                self.last_trigger_down[route_trigger_key] = route_down

                if layout_triggered or route_triggered:
                    if self.recording_status in {"countdown", "recording"}:
                        self._cancel_recording_locked()
                    special_event = "overlay_layout_toggle" if layout_triggered else "route_toggle"

                special_triggered = recording_triggered or layout_triggered or route_triggered
                if special_triggered:
                    self._clear_macro_state_locked()
                    release_inputs = True
                recording_blocks_macros = self.recording_status in {"countdown", "recording"}

                for profile in config.toggle_profiles or []:
                    if not profile.enabled:
                        continue
                    virtual_key = TRIGGER_KEYS.get(profile.trigger)
                    down = is_key_down(virtual_key) if target_active and not recording_blocks_macros and not special_triggered and virtual_key is not None else False
                    trigger_key = f"profile:{profile.id}"
                    if target_active and down and not self.last_trigger_down.get(trigger_key, False):
                        self._toggle_profile(profile, config.macros or [])
                    self.last_trigger_down[trigger_key] = down

                for macro in config.macros or []:
                    if not macro.enabled or macro.action == ACTION_NONE:
                        continue
                    virtual_key = TRIGGER_KEYS.get(macro.trigger)
                    if virtual_key is None:
                        continue
                    down = is_key_down(virtual_key) if target_active and not recording_blocks_macros and not special_triggered else False
                    trigger_key = f"macro:{macro.id}"
                    if target_active and down and not self.last_trigger_down.get(trigger_key, False):
                        self._toggle_macro(macro)
                    self.last_trigger_down[trigger_key] = down

                if self.native_enabled:
                    for macro in config.macros or []:
                        if macro.action == ACTION_RECORDED and macro.id in self.active_macros and not self.native_kernel.is_active(macro.id):
                            self.active_macros.discard(macro.id)

                active_cycle_macros = [
                    macro for macro in (config.macros or [])
                    if target_active and macro.enabled and macro.action == ACTION_PRESS_CYCLE and macro.id in self.active_macros
                ]
                active_recorded_macros = [
                    macro for macro in (config.macros or [])
                    if target_active and macro.enabled and macro.action == ACTION_RECORDED and macro.id in self.active_macros
                ]

            if release_inputs:
                self.release_all_inputs()
            if special_event is not None and self.event_queue is not None:
                self.event_queue.put({"type": special_event})

            now = time.monotonic()
            with self.lock:
                self._advance_recording_locked(config, target_active, now)

            if not self.native_enabled:
                for macro in active_cycle_macros:
                    with self.lock:
                        if not self.target_active or macro.id not in self.active_macros:
                            continue
                        if now < self.next_press_at.get(macro.id, 0.0):
                            continue
                        sequence = [item for item in macro.sequence if item != "none"]
                        if sequence:
                            index = self.sequence_index.get(macro.id, 0) % len(sequence)
                            self._press_cycle_item(sequence[index])
                            self.sequence_index[macro.id] = index + 1
                            self.next_press_at[macro.id] = now + (max(macro.interval_ms, MIN_MACRO_INTERVAL_MS) / 1000)

                for macro in active_recorded_macros:
                    with self.lock:
                        if self.target_active and macro.id in self.active_macros:
                            self._advance_recorded_playback(macro, now)

            recording_active = self.recording_status == "recording"
            poll_ms = min(max(config.poll_interval_ms, 10), MAX_FOREGROUND_POLL_MS)
            active_intervals = [
                max(int(macro.interval_ms), MIN_MACRO_INTERVAL_MS)
                for macro in (*active_cycle_macros, *active_recorded_macros)
            ]
            if active_intervals and not self.native_enabled:
                poll_ms = min(poll_ms, min(active_intervals))
            time.sleep(0.01 if recording_active else poll_ms / 1000)

    def _read_foreground_window(self) -> tuple[int, str, str]:
        hwnd = int(user32.GetForegroundWindow() or 0)
        now = time.monotonic()
        hwnd_changed = hwnd != self.foreground_hwnd
        metadata_expired = now - self.foreground_metadata_at >= FOREGROUND_METADATA_REFRESH_SECONDS
        if hwnd_changed or metadata_expired:
            previous_title = self.foreground_title
            previous_process = self.foreground_process
            self.foreground_hwnd = hwnd
            self.foreground_metadata_at = now
            title = get_window_title(hwnd) if hwnd else ""
            process = get_process_name(hwnd) if hwnd else ""
            if not hwnd_changed:
                title = title or previous_title
                process = process or previous_process
            return hwnd, title, process
        return hwnd, self.foreground_title, self.foreground_process

    def _seed_trigger_states_locked(self, config: Config) -> None:
        self.last_trigger_down["recording:toggle"] = self._trigger_is_down(config.recording_trigger, optional=True)
        self.last_trigger_down["overlay:layout"] = self._trigger_is_down(config.overlay_layout_trigger)
        self.last_trigger_down["route:toggle"] = self._trigger_is_down(config.route_trigger)
        for profile in config.toggle_profiles or []:
            self.last_trigger_down[f"profile:{profile.id}"] = self._trigger_is_down(profile.trigger, optional=True)
        for macro in config.macros or []:
            self.last_trigger_down[f"macro:{macro.id}"] = self._trigger_is_down(macro.trigger)

    def _trigger_is_down(self, trigger: str, optional: bool = False) -> bool:
        keys = OPTIONAL_TRIGGER_KEYS if optional else TRIGGER_KEYS
        virtual_key = keys.get(trigger)
        return is_key_down(virtual_key) if virtual_key is not None else False

    def _toggle_macro(self, macro: MacroConfig) -> None:
        if macro.id in self.active_macros:
            self._deactivate_macro(macro)
            return
        self._activate_macro(macro)

    def _activate_macro(self, macro: MacroConfig) -> None:
        if macro.id in self.active_macros:
            return
        self.active_macros.add(macro.id)
        if self.native_enabled:
            self.native_kernel.set_active(macro.id, True)
            return
        if macro.action == ACTION_HOLD:
            for item in hold_items(macro):
                if not self._item_has_owner(item, excluding_hold_macro_id=macro.id):
                    self.press_hold_item(item)
        elif macro.action == ACTION_PRESS_CYCLE:
            self.next_press_at[macro.id] = 0.0
            self.sequence_index[macro.id] = 0
        elif macro.action == ACTION_RECORDED:
            self.playback_state[macro.id] = {"started_at": time.monotonic(), "index": 0}

    def _deactivate_macro(self, macro: MacroConfig) -> None:
        if macro.id in self.active_macros:
            self.active_macros.remove(macro.id)
            if self.native_enabled:
                self.native_kernel.set_active(macro.id, False)
                return
            if macro.action == ACTION_HOLD:
                for item in hold_items(macro):
                    if not self._item_has_owner(item):
                        self.release_hold_item(item)
            self.next_press_at.pop(macro.id, None)
            self.sequence_index.pop(macro.id, None)
            self.playback_state.pop(macro.id, None)
            if macro.action == ACTION_RECORDED:
                self.release_playback_items(macro.id)

    def _toggle_profile(self, profile: ToggleProfile, macros: list[MacroConfig]) -> None:
        selected_ids = set(profile.macro_ids or [])
        eligible = [macro for macro in macros if macro.id in selected_ids and macro.enabled and macro.action != ACTION_NONE]
        if not eligible:
            return
        if all(macro.id in self.active_macros for macro in eligible):
            for macro in eligible:
                self._deactivate_macro(macro)
            return
        for macro in eligible:
            self._activate_macro(macro)

    def _clear_macro_state_locked(self) -> None:
        self.active_macros.clear()
        self.next_press_at.clear()
        self.sequence_index.clear()
        self.playback_state.clear()
        if self.native_enabled:
            self.native_kernel.reset_active()

    def _item_has_owner(
        self,
        item: str,
        excluding_hold_macro_id: str = "",
        excluding_playback_macro_id: str = "",
    ) -> bool:
        hold_owner = any(
            macro.id != excluding_hold_macro_id
            and macro.id in self.active_macros
            and macro.enabled
            and macro.action == ACTION_HOLD
            and item in hold_items(macro)
            for macro in (self.config.macros or [])
        )
        playback_owner = any(
            macro_id != excluding_playback_macro_id and item in held_items
            for macro_id, held_items in self.playback_held_items.items()
        )
        return hold_owner or playback_owner

    def _has_tracked_inputs(self) -> bool:
        return bool(
            self.right_is_down
            or self.left_is_down
            or self.middle_is_down
            or self.held_keys
            or self.playback_held_items
            or has_pending_releases()
        )

    def _handle_recording_trigger_locked(self, config: Config, target_active: bool) -> bool:
        virtual_key = OPTIONAL_TRIGGER_KEYS.get(config.recording_trigger)
        down = is_key_down(virtual_key) if target_active and virtual_key is not None else False
        trigger_key = "recording:toggle"
        triggered = target_active and down and not self.last_trigger_down.get(trigger_key, False)
        if triggered:
            if self.recording_status == "idle":
                self._start_recording_countdown_locked(config)
            elif self.recording_status in {"countdown", "recording"}:
                if self.recording_status == "recording":
                    self._capture_recording_changes_locked(config, time.monotonic())
                self._finish_recording_locked()
        self.last_trigger_down[trigger_key] = down
        return triggered

    def _start_recording_countdown_locked(self, config: Config) -> None:
        self.active_macros.clear()
        self.next_press_at.clear()
        self.sequence_index.clear()
        self.playback_state.clear()
        self.release_all_inputs()
        self.recorded_events = []
        self.record_last_down = {}
        self.recording_status = "countdown"
        self.recording_countdown_until = time.monotonic() + max(int(config.recording_countdown_sec), 0)

    def _advance_recording_locked(self, config: Config, target_active: bool, now: float) -> None:
        if not target_active:
            return
        if self.recording_status == "countdown" and now >= self.recording_countdown_until:
            self.recording_status = "recording"
            self.recording_started_at = now
            self.record_last_down = self._current_recordable_states(config)
        if self.recording_status != "recording":
            return
        if now - self.recording_started_at >= max(int(config.recording_max_seconds), 1):
            self._finish_recording_locked()
            return
        self._capture_recording_changes_locked(config, now)

    def _capture_recording_changes_locked(self, config: Config, now: float) -> None:
        current = self._current_recordable_states(config)
        at_ms = int((now - self.recording_started_at) * 1000)
        for key_id, down in current.items():
            previous = self.record_last_down.get(key_id, False)
            if down != previous:
                event: dict[str, object] = {
                    "type": "key_down" if down else "key_up",
                    "key": key_id,
                    "at_ms": at_ms,
                }
                if key_id in {"left", "right", "middle"}:
                    cursor_pos = get_cursor_position()
                    if cursor_pos is not None:
                        event["x"] = cursor_pos[0]
                        event["y"] = cursor_pos[1]
                self.recorded_events.append(event)
                if len(self.recorded_events) >= MAX_RECORDED_EVENTS:
                    self._finish_recording_locked()
                    return
        self.record_last_down = current

    def _current_recordable_states(self, config: Config) -> dict[str, bool]:
        recording_virtual_key = OPTIONAL_TRIGGER_KEYS.get(config.recording_trigger)
        states: dict[str, bool] = {}
        for key_id, virtual_key in RECORDABLE_KEYS.items():
            if key_id in {"xbutton1", "xbutton2"}:
                continue
            if virtual_key == recording_virtual_key:
                continue
            states[key_id] = is_key_down(virtual_key)
        return states

    def _finish_recording_locked(self) -> None:
        if self.recording_status == "recording" and self.event_queue is not None:
            recording = self._trim_recording(self.recorded_events) if self.recorded_events else []
            self.event_queue.put({"type": "recording_done", "events": recording})
        self.recording_status = "idle"
        self.recording_countdown_until = 0.0
        self.recording_started_at = 0.0
        self.recorded_events = []
        self.record_last_down = {}
        self.release_all_inputs()

    def _cancel_recording_locked(self) -> None:
        self.recording_status = "idle"
        self.recording_countdown_until = 0.0
        self.recording_started_at = 0.0
        self.recorded_events = []
        self.record_last_down = {}

    def _trim_recording(self, events: list[dict[str, object]]) -> list[dict[str, object]]:
        if not events:
            return []
        first_at = int(events[0].get("at_ms", 0))
        trimmed = [
            {**event, "at_ms": max(0, int(event.get("at_ms", 0)) - first_at)}
            for event in events
        ]
        held_items: set[str] = set()
        for event in trimmed:
            item = press_key_label_to_id(str(event.get("key", "")))
            if str(event.get("type", "")) == "key_down":
                held_items.add(item)
            else:
                held_items.discard(item)
        last_at = int(trimmed[-1].get("at_ms", 0))
        for item in sorted(held_items):
            trimmed.append({"type": "key_up", "key": item, "at_ms": last_at + 10})
        return trimmed

    def _advance_recorded_playback(self, macro: MacroConfig, now: float) -> None:
        recording = normalize_recording(macro.recording)
        if not recording:
            with self.lock:
                self._deactivate_macro(macro)
            return
        state = self.playback_state.setdefault(macro.id, {"started_at": now, "index": 0})
        started_at = float(state.get("started_at", now))
        index = int(state.get("index", 0))
        elapsed_ms = int((now - started_at) * 1000)
        while index < len(recording) and int(recording[index].get("at_ms", 0)) <= elapsed_ms:
            self._play_recorded_event(macro.id, recording[index])
            index += 1
        if index >= len(recording):
            if macro.playback_mode == PLAYBACK_LOOP:
                self.release_playback_items(macro.id)
                loop_delay = max(macro.interval_ms, MIN_MACRO_INTERVAL_MS) / 1000
                state["started_at"] = now + loop_delay
                state["index"] = 0
            else:
                with self.lock:
                    self._deactivate_macro(macro)
        else:
            state["index"] = index

    def _play_recorded_event(self, macro_id: str, event: dict[str, object]) -> None:
        item = press_key_label_to_id(str(event.get("key", "")))
        held_items = self.playback_held_items.setdefault(macro_id, set())
        if str(event.get("type", "")) == "key_down":
            if item in held_items:
                return
            move_cursor_to_recorded_position(event)
            if not self._item_has_owner(item, excluding_playback_macro_id=macro_id):
                self.press_hold_item(item)
            held_items.add(item)
            return

        if item not in held_items:
            return
        held_items.discard(item)
        try:
            if not self._item_has_owner(item):
                move_cursor_to_recorded_position(event)
                self.release_hold_item(item)
        except OSError:
            held_items.add(item)
            raise
        if not held_items:
            self.playback_held_items.pop(macro_id, None)

    def press_right(self) -> None:
        if self.right_is_down:
            return
        send_mouse_input(MOUSEEVENTF_RIGHTDOWN)
        self.right_is_down = True

    def release_right(self) -> None:
        if self.right_is_down:
            send_mouse_input(MOUSEEVENTF_RIGHTUP)
            self.right_is_down = False

    def press_left(self) -> None:
        if self.left_is_down:
            return
        send_mouse_input(MOUSEEVENTF_LEFTDOWN)
        self.left_is_down = True

    def release_left(self) -> None:
        if self.left_is_down:
            send_mouse_input(MOUSEEVENTF_LEFTUP)
            self.left_is_down = False

    def press_middle(self) -> None:
        if self.middle_is_down:
            return
        send_mouse_input(MOUSEEVENTF_MIDDLEDOWN)
        self.middle_is_down = True

    def release_middle(self) -> None:
        if self.middle_is_down:
            send_mouse_input(MOUSEEVENTF_MIDDLEUP)
            self.middle_is_down = False

    def press_hold_item(self, item: str) -> None:
        if item == "left":
            self.press_left()
        elif item == "right":
            self.press_right()
        elif item == "middle":
            self.press_middle()
        elif item in PRESS_KEYS and isinstance(PRESS_KEYS[item], int):
            virtual_key = PRESS_KEYS[item]
            if virtual_key not in self.held_keys:
                send_key_input(virtual_key, 0)
                self.held_keys.add(virtual_key)

    def _press_cycle_item(self, item: str) -> None:
        restore_down = self._item_has_owner(item)
        press_sequence_item(item)
        if not restore_down:
            return
        if item == "left":
            send_mouse_input(MOUSEEVENTF_LEFTDOWN)
        elif item == "right":
            send_mouse_input(MOUSEEVENTF_RIGHTDOWN)
        elif item == "middle":
            send_mouse_input(MOUSEEVENTF_MIDDLEDOWN)
        elif item in PRESS_KEYS and isinstance(PRESS_KEYS[item], int):
            send_key_input(PRESS_KEYS[item], 0)

    def release_hold_item(self, item: str) -> None:
        if item == "left":
            self.release_left()
        elif item == "right":
            self.release_right()
        elif item == "middle":
            self.release_middle()
        elif item in PRESS_KEYS and isinstance(PRESS_KEYS[item], int):
            virtual_key = PRESS_KEYS[item]
            if virtual_key in self.held_keys:
                send_key_input(virtual_key, KEYEVENTF_KEYUP)
                self.held_keys.remove(virtual_key)

    def release_all_keys(self) -> None:
        for virtual_key in list(self.held_keys):
            try:
                send_key_input(virtual_key, KEYEVENTF_KEYUP)
            except OSError:
                continue
            self.held_keys.discard(virtual_key)

    def release_playback_items(self, macro_id: str | None = None) -> None:
        if macro_id is None:
            items = set().union(*self.playback_held_items.values()) if self.playback_held_items else set()
            self.playback_held_items.clear()
        else:
            items = self.playback_held_items.pop(macro_id, set())
        failed_items: set[str] = set()
        for item in items:
            if not self._item_has_owner(item):
                try:
                    self.release_hold_item(item)
                except OSError:
                    failed_items.add(item)
        if failed_items:
            failed_owner = macro_id or "__cleanup__"
            self.playback_held_items.setdefault(failed_owner, set()).update(failed_items)

    def release_all_inputs(self) -> bool:
        if self.native_enabled:
            self.native_kernel.reset_active()
        cleanup_actions: tuple[Callable[[], None], ...] = (
            self.release_playback_items,
            self.release_right,
            self.release_left,
            self.release_middle,
            self.release_all_keys,
        )
        for action in cleanup_actions:
            try:
                action()
            except OSError:
                pass
        retry_pending_releases()
        return not self._has_tracked_inputs()

    def release_all_inputs_with_retry(self, attempts: int = 4, delay_seconds: float = 0.02) -> bool:
        attempts = max(int(attempts), 1)
        for attempt in range(attempts):
            if self.release_all_inputs():
                return True
            if attempt + 1 < attempts:
                time.sleep(max(float(delay_seconds), 0.0))
        return False

class OverlayWindow:
    def __init__(
        self,
        root: tk.Tk,
        engine: MacroEngine,
        position_callback: Callable[[int, int], None] | None = None,
    ) -> None:
        self.root = root
        self.engine = engine
        self.position_callback = position_callback
        self.width = 252
        self.height = 56
        self.max_rows = 6
        self.window = tk.Toplevel(root)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg="#111111")
        self.window.attributes("-alpha", DEFAULT_OVERLAY_OPACITY)
        self._last_geometry = ""
        self._overlay_style_applied = False
        self.layout_mode = False
        self._dragging = False
        self._drag_offset = (0, 0)
        self._game_rect: wintypes.RECT | None = None
        self._drag_game_rect: wintypes.RECT | None = None

        self.canvas = tk.Canvas(
            self.window,
            width=self.width,
            height=self.height,
            bg="#111111",
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self.canvas.bind("<B1-Motion>", self._on_drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_end)

    def set_layout_mode(self, enabled: bool) -> None:
        self.layout_mode = bool(enabled)
        self._dragging = False
        self._drag_game_rect = None
        self.canvas.configure(cursor="fleur" if self.layout_mode else "")
        self._last_geometry = ""
        self._apply_window_style(transparent=not self.layout_mode, force=True)
        self.refresh()

    def refresh(self) -> None:
        snapshot = self.engine.snapshot()
        if (not snapshot.config.overlay_enabled and not self.layout_mode) or (not snapshot.target_active and not self.layout_mode):
            self.window.withdraw()
            return

        visible_macros, total_count = self._visible_macros(snapshot)
        recording_visible = snapshot.recording_status in {"countdown", "recording"}
        if not self.layout_mode and not recording_visible and not visible_macros and total_count == 0:
            self.window.withdraw()
            return

        self.height = 82 if recording_visible else self._height_for_rows(len(visible_macros))
        self._draw(snapshot, visible_macros, total_count)
        self.window.attributes("-alpha", clamp(snapshot.config.overlay_opacity, 0.2, 1.0))

        rect = rect_from_tuple(snapshot.target_window_rect) or self._game_rect
        if snapshot.target_window_rect is not None:
            self._game_rect = copy_window_rect(rect)
        if rect is not None:
            x = rect.left + snapshot.config.overlay_x
            y = rect.top + snapshot.config.overlay_y
        else:
            x = snapshot.config.overlay_x
            y = snapshot.config.overlay_y
        x, y = clamp_to_virtual_desktop(x, y, self.width, self.height)
        geometry = window_geometry(self.width, self.height, x, y)
        if not self._dragging and geometry != self._last_geometry:
            self.window.geometry(geometry)
            self._last_geometry = geometry
        if self.window.state() == "withdrawn":
            self.window.deiconify()
            self._apply_window_style(transparent=not self.layout_mode, force=True)
            self.window.attributes("-topmost", True)
            self.canvas.update_idletasks()

    def _apply_window_style(self, transparent: bool, force: bool = False) -> None:
        if not force and self._overlay_style_applied:
            return
        try:
            self.window.update_idletasks()
            hwnd = self.window.winfo_id()
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            if transparent:
                style |= WS_EX_TRANSPARENT
            else:
                style &= ~WS_EX_TRANSPARENT
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            user32.SetWindowPos(
                hwnd,
                HWND_TOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED,
            )
            self._overlay_style_applied = True
        except tk.TclError:
            pass

    def _visible_macros(self, snapshot: Snapshot) -> tuple[list[MacroConfig], int]:
        enabled_macros = [macro for macro in (snapshot.config.macros or []) if macro.enabled and macro.action != ACTION_NONE]
        return enabled_macros[:self.max_rows], len(enabled_macros)

    def _draw(self, snapshot: Snapshot, visible_macros: list[MacroConfig], total_count: int) -> None:
        self.canvas.delete("all")
        self.canvas.configure(width=self.width, height=self.height)
        border_color = "#f59e0b" if self.layout_mode else "#3a3a3a"
        self.canvas.create_rectangle(
            1,
            1,
            self.width - 2,
            self.height - 2,
            fill="#111111",
            outline=border_color,
            width=2 if self.layout_mode else 1,
        )
        if self.layout_mode:
            layout_key = trigger_id_to_label(snapshot.config.overlay_layout_trigger)
            self.canvas.create_text(
                10, 9, text="拖动状态浮层", fill="#fbbf24",
                font=("Microsoft YaHei UI", 9, "bold"), anchor="nw",
            )
            self.canvas.create_text(
                self.width - 10, 9, text=f"{layout_key} 完成", fill="#d4d4d8",
                font=("Microsoft YaHei UI", 8, "bold"), anchor="ne",
            )
            for index, macro in enumerate(visible_macros):
                self._draw_status_row(28 + index * 22, macro, snapshot.macro_states.get(macro.id, False))
            self.canvas.update_idletasks()
            return
        if snapshot.recording_status in {"countdown", "recording"}:
            self._draw_recording(snapshot)
            self.canvas.update_idletasks()
            return
        active_count = sum(1 for macro_id, enabled in snapshot.macro_states.items() if enabled)
        self.canvas.create_text(
            10,
            9,
            text="D4Helper",
            fill="#d6d6d6",
            font=("Microsoft YaHei UI", 9, "bold"),
            anchor="nw",
        )
        count_suffix = f"{active_count}/{total_count}"
        if total_count > len(visible_macros):
            count_suffix += f"  +{total_count - len(visible_macros)}"
        self.canvas.create_text(
            self.width - 10,
            9,
            text=count_suffix,
            fill="#9ca3af",
            font=("Microsoft YaHei UI", 8, "bold"),
            anchor="ne",
        )

        for index, macro in enumerate(visible_macros):
            self._draw_status_row(28 + index * 22, macro, snapshot.macro_states.get(macro.id, False))
        self.canvas.update_idletasks()

    def _on_drag_start(self, event: tk.Event) -> None:
        if not self.layout_mode:
            return
        self._dragging = True
        self._drag_offset = (int(event.x), int(event.y))
        self._drag_game_rect = copy_window_rect(self._game_rect)

    def _on_drag_motion(self, event: tk.Event) -> None:
        if not self.layout_mode or not self._dragging:
            return
        x = int(event.x_root) - self._drag_offset[0]
        y = int(event.y_root) - self._drag_offset[1]
        x, y = clamp_to_virtual_desktop(x, y, self.width, self.height)
        geometry = window_geometry(self.width, self.height, x, y)
        self.window.geometry(geometry)
        self._last_geometry = geometry

    def _on_drag_end(self, _event: tk.Event) -> None:
        if not self.layout_mode or not self._dragging:
            return
        self._dragging = False
        rect = self._drag_game_rect or self._game_rect
        self._drag_game_rect = None
        if rect is None:
            return
        self.window.update_idletasks()
        relative_x = int(clamp(self.window.winfo_x() - rect.left, -5000, 5000))
        relative_y = int(clamp(self.window.winfo_y() - rect.top, -5000, 5000))
        if self.position_callback is not None:
            self.position_callback(relative_x, relative_y)

    def _draw_recording(self, snapshot: Snapshot) -> None:
        self.canvas.create_text(
            10,
            9,
            text="D4Helper",
            fill="#d6d6d6",
            font=("Microsoft YaHei UI", 9, "bold"),
            anchor="nw",
        )
        trigger_text = optional_trigger_id_to_label(snapshot.recording_trigger)
        if snapshot.recording_status == "countdown":
            status_text = f"录制准备中：{snapshot.recording_countdown_remaining}"
            detail_text = f"按 {trigger_text} 停止"
            color = "#facc15"
        else:
            seconds = snapshot.recording_elapsed_ms // 1000
            status_text = "● 正在录制宏"
            detail_text = f"{seconds:02d}s / {snapshot.recording_event_count} 个动作，按 {trigger_text} 停止"
            color = "#ef4444"
        self.canvas.create_text(
            12,
            30,
            text=status_text,
            fill=color,
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="nw",
        )
        self.canvas.create_text(
            12,
            52,
            text=self._ellipsize(detail_text, 28),
            fill="#e5e7eb",
            font=("Microsoft YaHei UI", 8, "bold"),
            anchor="nw",
        )

    def _draw_status_row(self, y: int, macro: MacroConfig, enabled: bool) -> None:
        text_color = "#f4f4f5" if enabled else "#a1a1aa"
        trigger_text = self._ellipsize(trigger_id_to_label(macro.trigger), 6)
        name_text = self._ellipsize(macro.name, 12)
        if enabled:
            self.canvas.create_rectangle(8, y - 2, self.width - 8, y + 16, fill="#171717", outline="")
        self.canvas.create_text(
            12,
            y,
            text=trigger_text,
            fill=text_color,
            font=("Microsoft YaHei UI", 8, "bold"),
            anchor="nw",
        )
        self.canvas.create_text(
            66,
            y,
            text=name_text,
            fill=text_color,
            font=("Microsoft YaHei UI", 8, "bold"),
            anchor="nw",
        )
        self._draw_switch(self.width - 38, y + 1, enabled)

    def _draw_switch(self, x: int, y: int, enabled: bool) -> None:
        bg = "#22c55e" if enabled else "#4b5563"
        knob = "#ffffff" if enabled else "#d1d5db"
        self.canvas.create_rectangle(x + 6, y, x + 22, y + 12, fill=bg, outline=bg)
        self.canvas.create_oval(x, y, x + 12, y + 12, fill=bg, outline=bg)
        self.canvas.create_oval(x + 16, y, x + 28, y + 12, fill=bg, outline=bg)
        knob_x = x + 16 if enabled else x + 2
        self.canvas.create_oval(knob_x, y + 2, knob_x + 8, y + 10, fill=knob, outline="")

    def _ellipsize(self, text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 1] + "…"

    def _height_for_rows(self, row_count: int) -> int:
        return 30 + max(row_count, 1) * 22 + 8


class WormRouteOverlay:
    def __init__(
        self,
        root: tk.Tk,
        engine: MacroEngine,
        selection_callback: Callable[[str], None] | None = None,
        position_callback: Callable[[int, int], None] | None = None,
    ) -> None:
        self.root = root
        self.engine = engine
        self.selection_callback = selection_callback
        self.position_callback = position_callback
        self.mode = "hidden"
        self.return_mode = "hidden"
        self.layout_mode = False
        self._layout_return_mode = "hidden"
        self._dragging = False
        self._drag_offset = (0, 0)
        self._game_rect: wintypes.RECT | None = None
        self._drag_game_rect: wintypes.RECT | None = None
        self.selected_id = engine.snapshot().config.route_last_selected
        if self.selected_id not in WORM_ROUTE_MAP_BY_ID:
            self.selected_id = WORM_ROUTE_MAPS[0].id

        self.selector = tk.Toplevel(root)
        self.selector.withdraw()
        self.selector.overrideredirect(True)
        self.selector.attributes("-topmost", True)
        self.selector.configure(bg="#111111")
        self.selector_canvas = tk.Canvas(self.selector, bg="#111111", highlightthickness=0, bd=0)
        self.selector_canvas.pack(fill="both", expand=True)
        self.selector_canvas.bind("<Button-1>", self._on_selector_click)

        self.map_window = tk.Toplevel(root)
        self.map_window.withdraw()
        self.map_window.overrideredirect(True)
        self.map_window.attributes("-topmost", True)
        self.map_window.configure(bg="#111111")
        self.map_canvas = tk.Canvas(self.map_window, bg="#111111", highlightthickness=0, bd=0)
        self.map_canvas.pack(fill="both", expand=True)
        self.map_canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self.map_canvas.bind("<B1-Motion>", self._on_drag_motion)
        self.map_canvas.bind("<ButtonRelease-1>", self._on_drag_end)

        self._selector_style_applied = False
        self._map_style_applied = False
        self._selector_hitboxes: list[tuple[int, int, int, int, str]] = []
        self._selector_images: list[object] = []
        self._selector_signature: tuple[object, ...] | None = None
        self._map_image: object | None = None
        self._map_signature: tuple[object, ...] | None = None

    def set_layout_mode(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self.layout_mode:
            return
        self.layout_mode = enabled
        self._dragging = False
        self._drag_game_rect = None
        if enabled:
            self._layout_return_mode = self.return_mode if self.mode == "selector" else self.mode
            self.mode = "map"
            self.return_mode = "map"
            self.selector.withdraw()
        else:
            self.mode = self._layout_return_mode
            self.return_mode = self._layout_return_mode
        self.map_canvas.configure(cursor="fleur" if enabled else "")
        self._map_signature = None
        self._apply_window_style(self.map_window, transparent=not enabled, force=True)
        self.refresh()

    def toggle_selector(self) -> None:
        if self.layout_mode:
            return
        snapshot = self.engine.snapshot()
        if not snapshot.config.route_enabled or not snapshot.target_active:
            return
        if self.mode == "selector":
            self.mode = self.return_mode
        else:
            self.return_mode = self.mode if self.mode == "map" else "hidden"
            self.mode = "selector"
        self.refresh()

    def refresh(self) -> None:
        snapshot = self.engine.snapshot()
        config = snapshot.config
        if config.route_last_selected in WORM_ROUTE_MAP_BY_ID and config.route_last_selected != self.selected_id:
            self.selected_id = config.route_last_selected
            self._selector_signature = None
            self._map_signature = None

        if not config.route_enabled and not self.layout_mode:
            self.mode = "hidden"
            self.return_mode = "hidden"
            self._withdraw_all()
            return
        if not snapshot.target_active and not self.layout_mode:
            if self.mode == "selector":
                self.mode = self.return_mode
            self._withdraw_all()
            return

        rect = rect_from_tuple(snapshot.target_window_rect) or self._game_rect
        if rect is None:
            self._withdraw_all()
            return
        if snapshot.target_window_rect is not None:
            self._game_rect = copy_window_rect(rect)
        if self.mode == "selector":
            self.map_window.withdraw()
            self._show_selector(rect, config)
        elif self.mode == "map":
            self.selector.withdraw()
            self._show_map(rect, config)
        else:
            self._withdraw_all()

    def _show_selector(self, rect: wintypes.RECT, config: Config) -> None:
        available_width = max(rect.right - rect.left, 800)
        available_height = max(rect.bottom - rect.top, 600)
        width = min(1120, max(760, available_width - 80))
        margin = 16
        gap = 10
        header_height = 46
        tile_width = (width - margin * 2 - gap * 3) // 4
        image_height = min(158, max(92, int(tile_width * 0.58)))
        tile_height = image_height + 34
        height = header_height + margin + tile_height * 3 + gap * 2 + margin
        if height > available_height - 50:
            image_height = max(72, image_height - (height - available_height + 50) // 3)
            tile_height = image_height + 32
            height = header_height + margin + tile_height * 3 + gap * 2 + margin

        x = rect.left + (available_width - width) // 2
        y = rect.top + max(20, (available_height - height) // 2)
        trigger_text = trigger_id_to_label(config.route_trigger)
        signature = (width, height, tile_width, image_height, self.selected_id, trigger_text)
        if signature != self._selector_signature:
            self._draw_selector(width, height, tile_width, image_height, margin, gap, header_height, trigger_text)
            self._selector_signature = signature
        self.selector.geometry(window_geometry(width, height, x, y))
        if self.selector.state() == "withdrawn":
            self.selector.deiconify()
            self._apply_window_style(self.selector, transparent=False)
        self.selector.attributes("-topmost", True)

    def _draw_selector(
        self,
        width: int,
        height: int,
        tile_width: int,
        image_height: int,
        margin: int,
        gap: int,
        header_height: int,
        trigger_text: str,
    ) -> None:
        canvas = self.selector_canvas
        canvas.configure(width=width, height=height)
        canvas.delete("all")
        canvas.create_rectangle(0, 0, width, height, fill="#111111", outline="#4b5563")
        canvas.create_text(
            margin,
            14,
            text="地狱蠕虫线路图",
            fill="#f4f4f5",
            font=("Microsoft YaHei UI", 13, "bold"),
            anchor="nw",
        )
        canvas.create_text(
            width - margin,
            16,
            text=f"选择地区 · {trigger_text} 返回",
            fill="#a1a1aa",
            font=("Microsoft YaHei UI", 9),
            anchor="ne",
        )
        self._selector_hitboxes = []
        self._selector_images = []
        entries: list[WormRouteMap | None] = [*WORM_ROUTE_MAPS, None]
        for index, route in enumerate(entries):
            row, column = divmod(index, 4)
            left = margin + column * (tile_width + gap)
            top = header_height + margin + row * (image_height + 34 + gap)
            right = left + tile_width
            bottom = top + image_height + 34
            route_id = route.id if route is not None else "close"
            self._selector_hitboxes.append((left, top, right, bottom, route_id))
            selected = route is not None and route.id == self.selected_id
            fill = "#1f2937" if selected else "#18181b"
            outline = "#f59e0b" if selected else "#3f3f46"
            canvas.create_rectangle(left, top, right, bottom, fill=fill, outline=outline, width=2 if selected else 1)
            if route is None:
                center_x = (left + right) // 2
                center_y = top + image_height // 2
                canvas.create_oval(center_x - 22, center_y - 22, center_x + 22, center_y + 22, outline="#71717a", width=2)
                canvas.create_line(center_x - 10, center_y - 10, center_x + 10, center_y + 10, fill="#a1a1aa", width=3)
                canvas.create_line(center_x + 10, center_y - 10, center_x - 10, center_y + 10, fill="#a1a1aa", width=3)
                label = "关闭线路图"
            else:
                photo = self._load_photo(route.thumbnail_path, tile_width - 8, image_height - 8)
                if photo is not None:
                    self._selector_images.append(photo)
                    canvas.create_image((left + right) // 2, top + image_height // 2, image=photo, anchor="center")
                label = f"{route.id}  {route.name}"
            canvas.create_text(
                (left + right) // 2,
                bottom - 17,
                text=label,
                fill="#fafafa" if selected else "#d4d4d8",
                font=("Microsoft YaHei UI", 9, "bold" if selected else "normal"),
                anchor="center",
            )
        canvas.update_idletasks()

    def _show_map(self, rect: wintypes.RECT, config: Config) -> None:
        route = WORM_ROUTE_MAP_BY_ID.get(self.selected_id)
        if route is None or not route.image_path.exists():
            self.mode = "hidden"
            self.map_window.withdraw()
            return
        available_width = max(rect.right - rect.left, 800)
        available_height = max(rect.bottom - rect.top, 600)
        width_ratio = {"small": 0.34, "medium": 0.46, "large": 0.60}.get(config.route_size, 0.46)
        height_ratio = {"small": 0.62, "medium": 0.76, "large": 0.88}.get(config.route_size, 0.76)
        max_image_width = max(360, int(available_width * width_ratio))
        max_image_height = max(320, int(available_height * height_ratio) - 34)
        trigger_text = trigger_id_to_label(config.route_trigger)
        layout_text = trigger_id_to_label(config.overlay_layout_trigger)
        signature = (route.id, max_image_width, max_image_height, trigger_text, self.layout_mode, layout_text)
        if signature != self._map_signature:
            photo = self._load_photo(route.image_path, max_image_width, max_image_height)
            if photo is None:
                self.mode = "hidden"
                self.map_window.withdraw()
                return
            self._map_image = photo
            self._map_signature = signature
            width = photo.width()
            height = photo.height() + 34
            self.map_canvas.configure(width=width, height=height)
            self.map_canvas.delete("all")
            border_color = "#f59e0b" if self.layout_mode else "#52525b"
            self.map_canvas.create_rectangle(0, 0, width, 34, fill="#111111", outline="")
            self.map_canvas.create_text(
                12,
                9,
                text="拖动线路图浮层" if self.layout_mode else f"地狱蠕虫路线 · {route.name}",
                fill="#fbbf24" if self.layout_mode else "#f4f4f5",
                font=("Microsoft YaHei UI", 10, "bold"),
                anchor="nw",
            )
            self.map_canvas.create_text(
                width - 12,
                10,
                text=f"{layout_text} 完成" if self.layout_mode else f"{trigger_text} 切换",
                fill="#a1a1aa",
                font=("Microsoft YaHei UI", 8),
                anchor="ne",
            )
            self.map_canvas.create_image(0, 34, image=photo, anchor="nw")
            self.map_canvas.create_rectangle(
                1, 1, width - 2, height - 2,
                outline=border_color,
                width=3 if self.layout_mode else 1,
            )
            self.map_canvas.update_idletasks()
        if self._map_image is None:
            return
        width = self._map_image.width()
        height = self._map_image.height() + 34
        desired_x = rect.left + config.route_x
        desired_y = rect.top + config.route_y
        x, y = clamp_to_virtual_desktop(desired_x, desired_y, width, height)
        geometry = window_geometry(width, height, x, y)
        if not self._dragging:
            self.map_window.geometry(geometry)
        self._game_rect = rect
        self.map_window.attributes("-alpha", clamp(config.route_opacity, 0.4, 1.0))
        if self.map_window.state() == "withdrawn":
            self.map_window.deiconify()
            self._apply_window_style(self.map_window, transparent=not self.layout_mode, force=True)
        self.map_window.attributes("-topmost", True)

    def _on_selector_click(self, event: tk.Event) -> None:
        for left, top, right, bottom, route_id in self._selector_hitboxes:
            if left <= event.x <= right and top <= event.y <= bottom:
                if route_id == "close":
                    self.mode = "hidden"
                    self.return_mode = "hidden"
                elif route_id in WORM_ROUTE_MAP_BY_ID:
                    self.selected_id = route_id
                    self.mode = "map"
                    self.return_mode = "map"
                    self._selector_signature = None
                    self._map_signature = None
                    if self.selection_callback is not None:
                        self.selection_callback(route_id)
                self.refresh()
                return

    def _on_drag_start(self, event: tk.Event) -> None:
        if not self.layout_mode:
            return
        self._dragging = True
        self._drag_offset = (int(event.x), int(event.y))
        self._drag_game_rect = copy_window_rect(self._game_rect)

    def _on_drag_motion(self, event: tk.Event) -> None:
        if not self.layout_mode or not self._dragging:
            return
        width = self.map_window.winfo_width()
        height = self.map_window.winfo_height()
        x = int(event.x_root) - self._drag_offset[0]
        y = int(event.y_root) - self._drag_offset[1]
        x, y = clamp_to_virtual_desktop(x, y, width, height)
        self.map_window.geometry(window_geometry(width, height, x, y))

    def _on_drag_end(self, _event: tk.Event) -> None:
        if not self.layout_mode or not self._dragging:
            return
        self._dragging = False
        rect = self._drag_game_rect or self._game_rect
        self._drag_game_rect = None
        if rect is None:
            return
        self.map_window.update_idletasks()
        relative_x = int(clamp(self.map_window.winfo_x() - rect.left, -5000, 5000))
        relative_y = int(clamp(self.map_window.winfo_y() - rect.top, -5000, 5000))
        if self.position_callback is not None:
            self.position_callback(relative_x, relative_y)

    def _load_photo(self, path: Path, max_width: int, max_height: int) -> object | None:
        if Image is None or ImageTk is None or not path.exists():
            return None
        try:
            with Image.open(path) as source:
                image = source.convert("RGB")
                image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(image)
        except Exception:
            return None

    def _apply_window_style(self, window: tk.Toplevel, transparent: bool, force: bool = False) -> None:
        if not force and window is self.selector and self._selector_style_applied:
            return
        if not force and window is self.map_window and self._map_style_applied:
            return
        try:
            window.update_idletasks()
            hwnd = window.winfo_id()
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            if transparent:
                style |= WS_EX_TRANSPARENT
            else:
                style &= ~WS_EX_TRANSPARENT
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            user32.SetWindowPos(
                hwnd,
                HWND_TOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED,
            )
            if window is self.selector:
                self._selector_style_applied = True
            else:
                self._map_style_applied = True
        except tk.TclError:
            pass

    def _withdraw_all(self) -> None:
        self.selector.withdraw()
        self.map_window.withdraw()


class ConfigWindow:
    def __init__(self, root: tk.Tk, engine: MacroEngine, command_queue: queue.Queue[object], config_path: Path) -> None:
        self.root = root
        self.engine = engine
        self.command_queue = command_queue
        self.config_path = config_path
        self.window = root
        self.window.title(APP_TITLE)
        self._set_window_icon()
        self.window.resizable(False, False)
        self.window.protocol("WM_DELETE_WINDOW", self.hide)

        self.title_var = tk.StringVar()
        self.process_var = tk.StringVar()
        self.overlay_enabled_var = tk.BooleanVar()
        self.overlay_x_var = tk.IntVar()
        self.overlay_y_var = tk.IntVar()
        self.overlay_opacity_var = tk.DoubleVar()
        self.overlay_opacity_text_var = tk.StringVar()
        self.recording_trigger_var = tk.StringVar()
        self.recording_countdown_var = tk.IntVar()
        self.recording_max_seconds_var = tk.IntVar()
        self.recording_hint_var = tk.StringVar()
        self.route_enabled_var = tk.BooleanVar()
        self.route_trigger_var = tk.StringVar()
        self.overlay_layout_trigger_var = tk.StringVar()
        self.overlay_layout_hint_var = tk.StringVar()
        self.route_x_var = tk.IntVar()
        self.route_y_var = tk.IntVar()
        self.route_size_var = tk.StringVar()
        self.route_opacity_var = tk.DoubleVar()
        self.route_opacity_text_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.version_status_var = tk.StringVar(value=f"当前版本：v{APP_VERSION}")
        self.latest_release_url = GITHUB_RELEASES_URL
        self.macro_vars: list[dict[str, object]] = []
        self.macro_rows_container: ttk.Frame | None = None
        self.toggle_profile_vars: list[dict[str, object]] = []
        self.toggle_profiles_container: ttk.Frame | None = None
        self.donate_image: object | None = None
        self.advanced_window: tk.Toplevel | None = None
        self.record_target_var: tk.StringVar | None = None
        self.record_target_kind = ""
        self.record_started_at = 0.0

        self._build()
        self.load_from_engine()
        self.overlay_opacity_var.trace_add("write", lambda *_args: self._update_opacity_text())
        self.route_opacity_var.trace_add("write", lambda *_args: self._update_route_opacity_text())
        self.recording_trigger_var.trace_add("write", lambda *_args: self._update_recording_hint())
        self.overlay_layout_trigger_var.trace_add("write", lambda *_args: self._update_overlay_layout_hint())
        self._fit_to_content()

    def _help_label(self, parent: tk.Widget, text: str) -> ttk.Label:
        return ttk.Label(parent, text=text, foreground="#666666", wraplength=760, justify="left")

    def _set_window_icon(self) -> None:
        if Image is None or ImageTk is None or not APP_ICON_PATH.exists():
            return
        try:
            icon = ImageTk.PhotoImage(Image.open(APP_ICON_PATH))
            self.window.iconphoto(True, icon)
            self.window_icon = icon
        except Exception:
            pass

    def _fit_to_content(self) -> None:
        self._fit_window_to_content(self.window)

    def _fit_window_to_content(self, window: tk.Toplevel | tk.Tk) -> None:
        window.update_idletasks()
        width = window.winfo_reqwidth() + 18
        height = window.winfo_reqheight() + 10
        window.geometry(f"{width}x{height}")

    def _build_menu(self) -> None:
        menu = tk.Menu(self.window)

        settings_menu = tk.Menu(menu, tearoff=False)
        settings_menu.add_command(label="高级设置", command=self.show_advanced_settings)
        settings_menu.add_command(label="读取当前窗口为目标", command=self.detect_foreground)
        settings_menu.add_separator()
        settings_menu.add_command(label="恢复默认", command=self.defaults)
        settings_menu.add_command(label="隐藏到托盘", command=self.hide)
        menu.add_cascade(label="设置", menu=settings_menu)

        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="检查更新", command=self.check_update)
        help_menu.add_command(label="查看更新", command=self.open_release_page)
        help_menu.add_separator()
        help_menu.add_command(label="支持与反馈", command=self.show_support)
        menu.add_cascade(label="帮助", menu=help_menu)

        self.window.config(menu=menu)

    def _build(self) -> None:
        pad = {"padx": 5, "pady": 4}
        self._build_menu()
        bottom = tk.Frame(self.window, bg="#f0f0f0", padx=10, pady=10, height=54)
        bottom.pack(fill="x", side="bottom")
        bottom.pack_propagate(False)
        tk.Label(bottom, textvariable=self.status_var, fg="#555555", bg="#f0f0f0", anchor="w").pack(side="left", fill="x", expand=True)
        tk.Button(bottom, text="隐藏到托盘", command=self.hide, width=12, height=1).pack(side="right", padx=(8, 0))
        tk.Button(bottom, text="高级设置", command=self.show_advanced_settings, width=12, height=1).pack(side="right", padx=(8, 0))
        tk.Button(bottom, text="保存并应用", command=self.save, width=12, height=1).pack(side="right", padx=(8, 0))

        main = ttk.Frame(self.window, padding=10)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)

        summary = ttk.Frame(main)
        summary.pack(fill="x", pady=(0, 8))
        summary.columnconfigure(0, weight=1)
        self._help_label(
            summary,
            "默认只在暗黑4窗口前台时生效。浮层位置可在游戏内直接拖动调整，窗口匹配位于“高级设置”。",
        ).grid(row=0, column=0, sticky="w", **pad)
        ttk.Checkbutton(summary, text="显示游戏内浮层", variable=self.overlay_enabled_var).grid(row=0, column=1, sticky="e", padx=(12, 5), pady=4)

        macros = ttk.LabelFrame(main, text="宏配置")
        macros.pack(fill="x", pady=(0, 8))
        self._help_label(macros, "每个按键格右侧都有“录”和“选”。自动按住会同时按住槽位 1-4 里的按键；循环连按会按槽位顺序短按，间隔只对循环连按生效。录入时按 Esc 取消。").pack(anchor="w", padx=5, pady=(4, 6))
        self.macro_rows_container = ttk.Frame(macros)
        self.macro_rows_container.pack(fill="x", padx=5, pady=(0, 6))
        self._render_macro_rows()

        all_toggle = ttk.LabelFrame(main, text="一键启动")
        all_toggle.pack(fill="x", pady=(0, 8))
        self.toggle_profiles_container = ttk.Frame(all_toggle)
        self.toggle_profiles_container.pack(fill="x", padx=5, pady=(6, 6))
        self._render_toggle_profile_rows()

        lower = ttk.Frame(main)
        lower.pack(fill="x")
        lower.columnconfigure(0, weight=3, uniform="main_bottom")
        lower.columnconfigure(1, weight=2, uniform="main_bottom")

        routes = ttk.LabelFrame(lower, text="地狱蠕虫线路图")
        routes.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        routes.columnconfigure(0, weight=1)
        ttk.Label(
            routes,
            text="使用线路图快捷键选择地区；进入布局模式后可直接拖动状态浮层和线路图。",
            foreground="#666666",
        ).grid(row=0, column=0, sticky="w", padx=8, pady=(6, 2))
        route_options = ttk.Frame(routes)
        route_options.grid(row=1, column=0, sticky="ew", padx=5, pady=(2, 6))
        route_options.columnconfigure(2, weight=1)
        ttk.Checkbutton(route_options, text="启用", variable=self.route_enabled_var).grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Label(route_options, text="选择器键").grid(row=0, column=1, sticky="w")
        self._key_picker(route_options, 0, 2, self.route_trigger_var, "trigger", 7)
        ttk.Label(route_options, text="大小").grid(row=0, column=3, sticky="w", padx=(8, 3))
        ttk.Combobox(route_options, textvariable=self.route_size_var, values=list(ROUTE_SIZE_LABELS.values()), state="readonly", width=3).grid(row=0, column=4, sticky="w")
        ttk.Label(route_options, text="透明度").grid(row=0, column=5, sticky="w", padx=(8, 3))
        route_opacity = ttk.Frame(route_options)
        route_opacity.grid(row=0, column=6, sticky="w")
        ttk.Scale(route_opacity, from_=0.4, to=1.0, variable=self.route_opacity_var, orient="horizontal", length=90).pack(side="left")
        ttk.Label(route_opacity, textvariable=self.route_opacity_text_var, width=5).pack(side="left", padx=(4, 0))
        ttk.Label(route_options, text="浮层位置").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Label(
            route_options,
            textvariable=self.overlay_layout_hint_var,
            foreground="#666666",
        ).grid(row=1, column=1, columnspan=5, sticky="w", padx=(6, 8), pady=(6, 0))
        ttk.Button(route_options, text="重置浮层位置", command=self.reset_overlay_positions).grid(
            row=1, column=6, sticky="e", pady=(6, 0)
        )

        support = ttk.LabelFrame(lower, text="支持与反馈")
        support.grid(row=0, column=1, sticky="nsew")
        support.columnconfigure(0, weight=1)
        support_text = ttk.Frame(support)
        support_text.grid(row=0, column=0, sticky="nsew", padx=(10, 6), pady=8)
        ttk.Label(support_text, text="QQ 交流群", foreground="#666666").pack(anchor="w")
        ttk.Label(support_text, text=SUPPORT_QQ_GROUP, font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w", pady=(1, 5))
        ttk.Label(
            support_text,
            text="问题反馈、功能建议、使用交流，欢迎加入群聊。\n工具对你有帮助，可以扫描右侧二维码支持。",
            foreground="#666666",
            justify="left",
            wraplength=270,
        ).pack(anchor="w")
        donate_label = self._donate_label(support, 112)
        if donate_label is not None:
            donate_label.grid(row=0, column=1, sticky="e", padx=(4, 8), pady=8)

    def _new_macro_vars(self, macro: MacroConfig) -> dict[str, object]:
        sequence = normalize_sequence(macro.sequence)
        return {
            "id": macro.id,
            "enabled": tk.BooleanVar(value=macro.enabled),
            "name": tk.StringVar(value=macro.name),
            "trigger": tk.StringVar(value=trigger_id_to_label(macro.trigger)),
            "action": tk.StringVar(value=action_id_to_label(macro.action)),
            "slot1": tk.StringVar(value=press_key_id_to_label(sequence[0])),
            "slot2": tk.StringVar(value=press_key_id_to_label(sequence[1])),
            "slot3": tk.StringVar(value=press_key_id_to_label(sequence[2])),
            "slot4": tk.StringVar(value=press_key_id_to_label(sequence[3])),
            "interval": tk.StringVar(value=str(macro.interval_ms)),
            "playback_mode": tk.StringVar(value=playback_mode_id_to_label(macro.playback_mode)),
            "recording": normalize_recording(macro.recording),
        }

    def _render_macro_rows(self) -> None:
        if self.macro_rows_container is None:
            return
        for child in self.macro_rows_container.winfo_children():
            child.destroy()

        pad = {"padx": 5, "pady": 4}
        headers = ["启用", "名称", "开关键", "动作", "动作配置", "间隔(ms)", "操作"]
        for col, header in enumerate(headers):
            ttk.Label(self.macro_rows_container, text=header).grid(row=0, column=col, sticky="w", **pad)
        self.macro_rows_container.columnconfigure(4, weight=1)

        action_values = list(ACTION_LABELS.values())
        for index, vars_for_row in enumerate(self.macro_vars):
            row = index + 1
            ttk.Checkbutton(self.macro_rows_container, variable=vars_for_row["enabled"]).grid(row=row, column=0, sticky="w", **pad)
            ttk.Entry(self.macro_rows_container, textvariable=vars_for_row["name"], width=11).grid(row=row, column=1, sticky="w", **pad)
            self._key_picker(self.macro_rows_container, row, 2, vars_for_row["trigger"], "trigger", 8)
            action_combo = ttk.Combobox(self.macro_rows_container, textvariable=vars_for_row["action"], values=action_values, state="readonly", width=10)
            action_combo.grid(row=row, column=3, sticky="w", **pad)
            action_combo.bind("<<ComboboxSelected>>", lambda _event, row_vars=vars_for_row: self._on_macro_action_changed(row_vars))
            vars_for_row["action_widget"] = action_combo
            action_config = ttk.Frame(self.macro_rows_container)
            action_config.grid(row=row, column=4, sticky="w", **pad)
            vars_for_row["action_config_frame"] = action_config
            interval_frame = ttk.Frame(self.macro_rows_container)
            interval_frame.grid(row=row, column=5, sticky="w", **pad)
            vars_for_row["interval_frame"] = interval_frame
            ttk.Button(self.macro_rows_container, text="删除", width=6, command=lambda row_index=index: self.remove_macro_row(row_index)).grid(row=row, column=6, sticky="w", **pad)
            self._update_macro_row_state(vars_for_row)

        footer_row = len(self.macro_vars) + 1
        ttk.Button(self.macro_rows_container, text="添加宏", command=self.add_macro_row).grid(row=footer_row, column=0, sticky="w", padx=5, pady=(6, 4))
        ttk.Label(self.macro_rows_container, textvariable=self.recording_hint_var, foreground="#666666").grid(row=footer_row, column=1, columnspan=5, sticky="w", padx=5, pady=(6, 4))
        if not self.macro_vars:
            ttk.Label(self.macro_rows_container, text="当前还没有宏，点击“添加宏”开始配置。", foreground="#666666").grid(row=footer_row + 1, column=1, columnspan=5, sticky="w", padx=5, pady=(0, 4))
        if self.toggle_profiles_container is not None:
            self._render_toggle_profile_rows()

    def set_macro_rows(self, macros: list[MacroConfig]) -> None:
        self.macro_vars = [self._new_macro_vars(macro) for macro in macros]
        self._render_macro_rows()

    def _next_blank_macro_index(self) -> int:
        existing_names = {str(vars_for_row["name"].get()).strip() for vars_for_row in self.macro_vars}
        next_index = 1
        while f"宏 {next_index}" in existing_names:
            next_index += 1
        return next_index

    def add_macro_row(self) -> None:
        self.macro_vars.append(self._new_macro_vars(blank_macro_config(self._next_blank_macro_index())))
        self._render_macro_rows()
        self._fit_to_content()
        self.status_var.set("已添加宏")

    def remove_macro_row(self, index: int) -> None:
        if index < 0 or index >= len(self.macro_vars):
            return
        del self.macro_vars[index]
        self._render_macro_rows()
        self._fit_to_content()
        self.status_var.set("已删除宏")

    def add_recorded_macro(self, events: list[dict[str, object]]) -> None:
        recording = normalize_recording(events)
        if not recording:
            self.status_var.set("录制结束，但没有捕获到有效动作")
            self._reveal_window()
            return
        index = self._next_blank_macro_index()
        macro = MacroConfig(
            enabled=False,
            name=f"录制宏 {index}",
            trigger=self._suggest_macro_trigger(),
            action=ACTION_RECORDED,
            sequence=["none", "none", "none", "none"],
            interval_ms=DEFAULT_INTERVAL_MS,
            id=make_stable_id("macro"),
            playback_mode=PLAYBACK_ONCE,
            recording=recording,
        )
        self.macro_vars.append(self._new_macro_vars(macro))
        self._render_macro_rows()
        self._reveal_window()
        self._fit_to_content()
        self.status_var.set(f"已新增录制宏：{recording_summary(recording)}。请修改名称、开关键并勾选启用后保存。")

    def _suggest_macro_trigger(self) -> str:
        used = {trigger_label_to_id(str(vars_for_row["trigger"].get())) for vars_for_row in self.macro_vars}
        used.update(optional_trigger_label_to_id(str(profile_vars["trigger"].get())) for profile_vars in self.toggle_profile_vars)
        used.add(optional_trigger_label_to_id(str(self.recording_trigger_var.get())))
        for key_id in COMMON_TRIGGER_KEYS:
            if key_id not in used:
                return key_id
        return "f12"

    def _new_toggle_profile_vars(self, profile: ToggleProfile) -> dict[str, object]:
        return {
            "id": profile.id,
            "enabled": tk.BooleanVar(value=profile.enabled),
            "trigger": tk.StringVar(value=optional_trigger_id_to_label(profile.trigger)),
            "selected_macro_ids": set(profile.macro_ids or []),
            "selected_vars": {},
        }

    def _sync_toggle_profile_macro_vars(self) -> None:
        macro_ids = [str(vars_for_row["id"]) for vars_for_row in self.macro_vars]
        for profile_vars in self.toggle_profile_vars:
            previous_vars = profile_vars.get("selected_vars", {})
            previous_selected = {
                macro_id for macro_id, selected_var in previous_vars.items()
                if selected_var.get()
            }
            previous_selected.update(profile_vars.get("selected_macro_ids", set()))
            selected_vars: dict[str, tk.BooleanVar] = {}
            for macro_id in macro_ids:
                selected_vars[macro_id] = tk.BooleanVar(value=macro_id in previous_selected)
            profile_vars["selected_vars"] = selected_vars
            profile_vars["selected_macro_ids"] = {
                macro_id for macro_id, selected_var in selected_vars.items() if selected_var.get()
            }

    def _render_toggle_profile_rows(self) -> None:
        if self.toggle_profiles_container is None:
            return
        self._sync_toggle_profile_macro_vars()
        for child in self.toggle_profiles_container.winfo_children():
            child.destroy()

        pad = {"padx": 4, "pady": 2}
        headers = ["启用", "快捷键", "控制宏", "操作"]
        for col, header in enumerate(headers):
            ttk.Label(self.toggle_profiles_container, text=header).grid(row=0, column=col, sticky="w", **pad)

        if not self.toggle_profile_vars:
            ttk.Label(
                self.toggle_profiles_container,
                text="当前还没有一键启动配置，点击“添加一键启动”创建。",
                foreground="#666666",
            ).grid(row=1, column=1, columnspan=3, sticky="w", **pad)

        for index, profile_vars in enumerate(self.toggle_profile_vars):
            row = index + 1
            ttk.Checkbutton(self.toggle_profiles_container, variable=profile_vars["enabled"]).grid(row=row, column=0, sticky="w", **pad)
            self._key_picker(self.toggle_profiles_container, row, 1, profile_vars["trigger"], "optional_trigger", 8)
            checks = ttk.Frame(self.toggle_profiles_container)
            checks.grid(row=row, column=2, sticky="w", **pad)
            selected_vars = profile_vars["selected_vars"]
            if not self.macro_vars:
                ttk.Label(checks, text="请先在上方添加宏。", foreground="#666666").pack(side="left")
            else:
                for macro_index, macro_vars in enumerate(self.macro_vars):
                    macro_id = str(macro_vars["id"])
                    ttk.Checkbutton(
                        checks,
                        textvariable=macro_vars["name"],
                        variable=selected_vars[macro_id],
                    ).grid(row=0, column=macro_index, sticky="w", padx=(0, 10), pady=(0, 4))
            ttk.Button(self.toggle_profiles_container, text="删除", width=6, command=lambda row_index=index: self.remove_toggle_profile_row(row_index)).grid(row=row, column=3, sticky="w", **pad)

        footer_row = len(self.toggle_profile_vars) + 1
        ttk.Button(self.toggle_profiles_container, text="添加一键启动", command=self.add_toggle_profile_row).grid(row=footer_row, column=0, sticky="w", padx=5, pady=(6, 4))

    def set_toggle_profile_rows(self, profiles: list[ToggleProfile]) -> None:
        self.toggle_profile_vars = [self._new_toggle_profile_vars(profile) for profile in profiles]
        self._render_toggle_profile_rows()

    def add_toggle_profile_row(self) -> None:
        self.toggle_profile_vars.append(self._new_toggle_profile_vars(blank_toggle_profile()))
        self._render_toggle_profile_rows()
        self._fit_to_content()
        self.status_var.set("已添加一键启动配置")

    def remove_toggle_profile_row(self, index: int) -> None:
        if index < 0 or index >= len(self.toggle_profile_vars):
            return
        del self.toggle_profile_vars[index]
        self._render_toggle_profile_rows()
        self._fit_to_content()
        self.status_var.set("已删除一键启动配置")

    def _on_macro_action_changed(self, vars_for_row: dict[str, object]) -> None:
        self._update_macro_row_state(vars_for_row)
        self._fit_to_content()
        action = action_label_to_id(str(vars_for_row["action"].get()))
        if action == ACTION_HOLD:
            self.status_var.set("自动按住会同时按住所有非“无”的槽位，间隔不生效")
        elif action == ACTION_PRESS_CYCLE:
            self.status_var.set("循环连按会按槽位顺序短按，间隔越小触发越快")
        elif action == ACTION_RECORDED:
            self.status_var.set("录制回放由游戏内快捷键生成；循环执行时，间隔表示两轮回放之间的等待时间")
        else:
            self.status_var.set("当前宏动作已设为无")

    def _update_macro_row_state(self, vars_for_row: dict[str, object]) -> None:
        action = action_label_to_id(str(vars_for_row["action"].get()))
        frame = vars_for_row.get("action_config_frame")
        if not isinstance(frame, tk.Widget):
            return
        for child in frame.winfo_children():
            child.destroy()
        if action == ACTION_HOLD:
            for offset, slot_name in enumerate(["slot1", "slot2", "slot3", "slot4"]):
                self._key_picker(frame, 0, offset, vars_for_row[slot_name], "press", 6)
        elif action == ACTION_PRESS_CYCLE:
            for offset, slot_name in enumerate(["slot1", "slot2", "slot3", "slot4"]):
                self._key_picker(frame, 0, offset, vars_for_row[slot_name], "press", 6)
        elif action == ACTION_RECORDED:
            ttk.Label(frame, text=f"已录制：{recording_summary(vars_for_row.get('recording'))}").grid(row=0, column=0, sticky="w", padx=(0, 10))
            ttk.Label(frame, text="回放").grid(row=0, column=1, sticky="w", padx=(0, 3))
            playback_combo = ttk.Combobox(frame, textvariable=vars_for_row["playback_mode"], values=list(PLAYBACK_MODE_LABELS.values()), state="readonly", width=8)
            playback_combo.grid(row=0, column=2, sticky="w")
            playback_combo.bind("<<ComboboxSelected>>", lambda _event, row_vars=vars_for_row: self._on_macro_action_changed(row_vars))
        else:
            ttk.Label(frame, text="不执行任何动作", foreground="#777777").grid(row=0, column=0, sticky="w")
        interval_frame = vars_for_row.get("interval_frame")
        if isinstance(interval_frame, tk.Widget):
            for child in interval_frame.winfo_children():
                child.destroy()
            if action == ACTION_PRESS_CYCLE or (action == ACTION_RECORDED and playback_mode_label_to_id(str(vars_for_row["playback_mode"].get())) == PLAYBACK_LOOP):
                ttk.Spinbox(interval_frame, from_=MIN_MACRO_INTERVAL_MS, to=5000, increment=1, textvariable=vars_for_row["interval"], width=7).grid(row=0, column=0, sticky="w")

    def _set_widget_tree_enabled(self, widget: tk.Widget, enabled: bool) -> None:
        self._set_widget_enabled(widget, enabled)
        for child in widget.winfo_children():
            self._set_widget_tree_enabled(child, enabled)

    def _set_widget_enabled(self, widget: tk.Widget, enabled: bool) -> None:
        try:
            if isinstance(widget, ttk.Entry):
                widget.configure(state="readonly" if enabled else "disabled")
            elif isinstance(widget, ttk.Combobox):
                widget.configure(state="readonly" if enabled else "disabled")
            else:
                widget.configure(state="normal" if enabled else "disabled")
        except tk.TclError:
            return

    def _key_picker(self, parent: tk.Widget, row: int, column: int, value_var: tk.StringVar, kind: str, width: int) -> ttk.Frame:
        pad = {"padx": 3, "pady": 1}
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=column, sticky="w", **pad)
        ttk.Entry(frame, textvariable=value_var, width=width, state="readonly").pack(side="left")
        ttk.Button(frame, text="录", width=3, command=lambda: self.record_key(value_var, kind)).pack(side="left", padx=(3, 0))
        ttk.Button(frame, text="选", width=3, command=lambda: self.show_key_menu(frame, value_var, kind)).pack(side="left", padx=(3, 0))
        return frame

    def show_key_menu(self, anchor: tk.Widget, value_var: tk.StringVar, kind: str) -> None:
        menu = tk.Menu(anchor, tearoff=False)
        if kind == "trigger":
            key_ids = COMMON_TRIGGER_KEYS
            labels = TRIGGER_LABELS
        elif kind == "optional_trigger":
            key_ids = COMMON_OPTIONAL_TRIGGER_KEYS
            labels = OPTIONAL_TRIGGER_LABELS
        else:
            key_ids = COMMON_PRESS_KEYS
            labels = PRESS_KEY_LABELS
        for key_id in key_ids:
            menu.add_command(label=labels[key_id], command=lambda selected=key_id: self._select_key(value_var, selected, kind))
        menu.tk_popup(anchor.winfo_rootx(), anchor.winfo_rooty() + anchor.winfo_height())

    def _select_key(self, value_var: tk.StringVar, key_id: str, kind: str) -> None:
        if kind == "trigger":
            labels = TRIGGER_LABELS
        elif kind == "optional_trigger":
            labels = OPTIONAL_TRIGGER_LABELS
        else:
            labels = PRESS_KEY_LABELS
        value_var.set(labels[key_id])
        self.status_var.set(f"已选择：{value_var.get()}")

    def record_key(self, value_var: tk.StringVar, kind: str) -> None:
        self.record_target_var = value_var
        self.record_target_kind = kind
        self.record_started_at = time.monotonic() + 0.2
        self.status_var.set("请按一个键，Esc 取消")
        self.root.after(30, self._poll_record_key)

    def _poll_record_key(self) -> None:
        if self.record_target_var is None:
            return
        if time.monotonic() < self.record_started_at:
            self.root.after(30, self._poll_record_key)
            return
        if is_key_down(RECORD_CANCEL_KEY):
            self._finish_recording(None)
            return
        for key_id, virtual_key in RECORDABLE_KEYS.items():
            if self.record_target_kind in {"trigger", "optional_trigger"} and key_id == "left":
                continue
            if is_key_down(virtual_key):
                self._finish_recording(key_id)
                return
        self.root.after(30, self._poll_record_key)

    def _finish_recording(self, key_id: str | None) -> None:
        target = self.record_target_var
        target_kind = self.record_target_kind
        self.record_target_var = None
        self.record_target_kind = ""
        if target is None:
            return
        if key_id is None:
            self.status_var.set("已取消录入")
            return
        if target_kind == "optional_trigger" and key_id in OPTIONAL_TRIGGER_LABELS:
            target.set(OPTIONAL_TRIGGER_LABELS[key_id])
        elif key_id in PRESS_KEY_LABELS:
            target.set(PRESS_KEY_LABELS[key_id])
        elif key_id in TRIGGER_LABELS:
            target.set(TRIGGER_LABELS[key_id])
        self.status_var.set(f"已录入：{target.get()}")

    def _donate_label(self, parent: tk.Widget, max_size: int = 150) -> ttk.Label | None:
        if Image is None or ImageTk is None or not DONATE_IMAGE_PATH.exists():
            return None
        image = Image.open(DONATE_IMAGE_PATH)
        image.thumbnail((max_size, max_size))
        self.donate_image = ImageTk.PhotoImage(image)
        return ttk.Label(parent, image=self.donate_image)

    def check_update(self) -> None:
        self.version_status_var.set(f"当前版本：v{APP_VERSION}，正在检查更新...")
        threading.Thread(target=self._check_update_worker, name="check-update", daemon=True).start()

    def _check_update_worker(self) -> None:
        try:
            latest_version, release_url = fetch_latest_release()
            self.root.after(0, lambda: self._show_update_result(latest_version, release_url))
        except Exception as exc:
            error_message = str(exc)
            self.root.after(0, lambda: self.version_status_var.set(f"当前版本：v{APP_VERSION}，更新检查失败：{error_message}"))

    def _show_update_result(self, latest_version: str, release_url: str) -> None:
        self.latest_release_url = release_url
        if is_newer_version(latest_version, APP_VERSION):
            self.version_status_var.set(f"当前版本：v{APP_VERSION}，发现新版本：v{latest_version}")
        else:
            self.version_status_var.set(f"当前版本：v{APP_VERSION}，已是最新版本")

    def open_release_page(self) -> None:
        webbrowser.open(self.latest_release_url)

    def load_from_engine(self) -> None:
        config = self.engine.snapshot().config
        self.title_var.set(config.window_title_contains)
        self.process_var.set(config.process_name)
        self.set_macro_rows(normalize_macros(config.macros))
        self.set_toggle_profile_rows(normalize_toggle_profiles(config.toggle_profiles, normalize_macros(config.macros)))
        self.overlay_enabled_var.set(config.overlay_enabled)
        self.overlay_x_var.set(config.overlay_x)
        self.overlay_y_var.set(config.overlay_y)
        self.overlay_opacity_var.set(config.overlay_opacity)
        self.recording_trigger_var.set(optional_trigger_id_to_label(config.recording_trigger))
        self.recording_countdown_var.set(config.recording_countdown_sec)
        self.recording_max_seconds_var.set(config.recording_max_seconds)
        self.route_enabled_var.set(config.route_enabled)
        self.route_trigger_var.set(trigger_id_to_label(config.route_trigger))
        self.overlay_layout_trigger_var.set(trigger_id_to_label(config.overlay_layout_trigger))
        self.route_x_var.set(config.route_x)
        self.route_y_var.set(config.route_y)
        self.route_size_var.set(ROUTE_SIZE_LABELS.get(config.route_size, "中"))
        self.route_opacity_var.set(config.route_opacity)
        self._update_opacity_text()
        self._update_route_opacity_text()
        self._update_recording_hint()
        self._update_overlay_layout_hint()
        self._fit_to_content()

    def _update_opacity_text(self) -> None:
        self.overlay_opacity_text_var.set(f"{int(float(self.overlay_opacity_var.get()) * 100)}%")

    def _update_route_opacity_text(self) -> None:
        self.route_opacity_text_var.set(f"{int(float(self.route_opacity_var.get()) * 100)}%")

    def _update_recording_hint(self) -> None:
        trigger_text = str(self.recording_trigger_var.get()).strip() or "未设置"
        self.recording_hint_var.set(f"在游戏中使用 {trigger_text} 录制宏")

    def _update_overlay_layout_hint(self) -> None:
        trigger_text = str(self.overlay_layout_trigger_var.get()).strip() or "未设置"
        self.overlay_layout_hint_var.set(f"游戏内按 {trigger_text} 进入布局模式，拖动浮层，松开即保存")

    def update_overlay_position_fields(self, overlay_name: str, x: int, y: int) -> None:
        if overlay_name == "status":
            self.overlay_x_var.set(x)
            self.overlay_y_var.set(y)
        elif overlay_name == "route":
            self.route_x_var.set(x)
            self.route_y_var.set(y)

    def reset_overlay_positions(self) -> None:
        self.overlay_x_var.set(20)
        self.overlay_y_var.set(20)
        self.route_x_var.set(DEFAULT_ROUTE_X)
        self.route_y_var.set(DEFAULT_ROUTE_Y)
        try:
            config = self.engine.snapshot().config
            config.overlay_x = 20
            config.overlay_y = 20
            config.route_x = DEFAULT_ROUTE_X
            config.route_y = DEFAULT_ROUTE_Y
            validate_config(config)
            save_config(self.config_path, config)
            self.engine.update_config(config)
            self.status_var.set("已重置并保存浮层位置")
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self.window)

    def show_advanced_settings(self) -> None:
        if self.advanced_window is not None and self.advanced_window.winfo_exists():
            self.advanced_window.deiconify()
            self.advanced_window.lift()
            self.advanced_window.focus_force()
            return

        pad = {"padx": 5, "pady": 4}
        window = tk.Toplevel(self.window)
        window.title(f"{APP_NAME} 高级设置")
        window.resizable(False, False)
        window.transient(self.window)
        window.protocol("WM_DELETE_WINDOW", self._close_advanced_settings)
        self.advanced_window = window

        main = ttk.Frame(window, padding=10)
        main.pack(fill="both", expand=True)

        target = ttk.LabelFrame(main, text="窗口匹配")
        target.pack(fill="x", pady=(0, 8))
        target.columnconfigure(1, weight=1)
        self._help_label(target, "默认值已经适配暗黑4。只有在你的窗口标题或进程名与默认值不一致时，才需要改这里。").grid(row=0, column=0, columnspan=2, sticky="w", **pad)
        ttk.Label(target, text="标题包含").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(target, textvariable=self.title_var, width=42).grid(row=1, column=1, sticky="ew", **pad)
        ttk.Label(target, text="进程名").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(target, textvariable=self.process_var, width=42).grid(row=2, column=1, sticky="ew", **pad)
        target_actions = ttk.Frame(target)
        target_actions.grid(row=3, column=1, sticky="e", **pad)
        ttk.Button(target_actions, text="恢复默认目标", command=self.reset_target_defaults).pack(side="left")
        ttk.Button(target_actions, text="读取当前窗口", command=self.detect_foreground).pack(side="left", padx=(8, 0))

        overlay = ttk.LabelFrame(main, text="浮层设置")
        overlay.pack(fill="x", pady=(0, 8))
        overlay.columnconfigure(1, weight=1)
        self._help_label(overlay, "用于调整游戏内浮层显示和布局快捷键，修改后点击“保存并应用”。").grid(row=0, column=0, columnspan=2, sticky="w", **pad)
        ttk.Checkbutton(overlay, text="显示游戏内浮层", variable=self.overlay_enabled_var).grid(row=1, column=0, columnspan=2, sticky="w", padx=8, pady=(6, 6))
        ttk.Label(overlay, text="布局快捷键").grid(row=2, column=0, sticky="w", **pad)
        layout_shortcut = ttk.Frame(overlay)
        layout_shortcut.grid(row=2, column=1, sticky="ew", **pad)
        self._key_picker(layout_shortcut, 0, 0, self.overlay_layout_trigger_var, "trigger", 8)
        ttk.Label(
            layout_shortcut,
            textvariable=self.overlay_layout_hint_var,
            foreground="#666666",
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Label(overlay, text="透明度").grid(row=3, column=0, sticky="w", **pad)
        opacity_row = ttk.Frame(overlay)
        opacity_row.grid(row=3, column=1, sticky="ew", **pad)
        opacity_row.columnconfigure(0, weight=1)
        ttk.Scale(opacity_row, from_=0.2, to=1.0, variable=self.overlay_opacity_var, orient="horizontal").grid(row=0, column=0, sticky="ew")
        ttk.Label(opacity_row, textvariable=self.overlay_opacity_text_var, width=6).grid(row=0, column=1, padx=(8, 0))

        recording = ttk.LabelFrame(main, text="宏录制")
        recording.pack(fill="x", pady=(0, 8))
        recording.columnconfigure(1, weight=1)
        self._help_label(recording, "在游戏窗口内按录制快捷键开始倒计时，再按一次停止。录制完成后会自动新增一条“录制回放”宏并打开配置。").grid(row=0, column=0, columnspan=2, sticky="w", **pad)
        ttk.Label(recording, text="录制快捷键").grid(row=1, column=0, sticky="w", **pad)
        self._key_picker(recording, 1, 1, self.recording_trigger_var, "optional_trigger", 8)
        ttk.Label(recording, text="倒计时/最长时长").grid(row=2, column=0, sticky="w", **pad)
        recording_limits = ttk.Frame(recording)
        recording_limits.grid(row=2, column=1, sticky="w", **pad)
        ttk.Spinbox(recording_limits, from_=0, to=10, increment=1, textvariable=self.recording_countdown_var, width=6).pack(side="left")
        ttk.Label(recording_limits, text="秒后开始，最多").pack(side="left", padx=(6, 6))
        ttk.Spinbox(recording_limits, from_=1, to=120, increment=1, textvariable=self.recording_max_seconds_var, width=6).pack(side="left")
        ttk.Label(recording_limits, text="秒").pack(side="left", padx=(6, 0))

        update = ttk.LabelFrame(main, text="版本更新")
        update.pack(fill="x", pady=(0, 8))
        update.columnconfigure(0, weight=1)
        ttk.Label(update, textvariable=self.version_status_var, foreground="#555555").grid(row=0, column=0, sticky="w", **pad)
        ttk.Button(update, text="检查更新", command=self.check_update).grid(row=0, column=1, sticky="e", **pad)
        ttk.Button(update, text="查看更新", command=self.open_release_page).grid(row=0, column=2, sticky="e", **pad)

        support = ttk.Frame(main)
        support.pack(fill="x")
        self._help_label(support, f"支持与反馈：QQ 交流群 {SUPPORT_QQ_GROUP}").pack(side="left", padx=5, pady=4)
        ttk.Button(support, text="查看说明", command=self.show_support).pack(side="right", padx=5, pady=4)
        ttk.Button(support, text="关闭", command=self._close_advanced_settings).pack(side="right", padx=5, pady=4)

        self._fit_window_to_content(window)
        window.lift()
        window.focus_force()

    def _close_advanced_settings(self) -> None:
        if self.advanced_window is None:
            return
        if self.advanced_window.winfo_exists():
            self.advanced_window.destroy()
        self.advanced_window = None

    def reset_target_defaults(self) -> None:
        self.title_var.set(DEFAULT_WINDOW_TITLE_CONTAINS)
        self.process_var.set(DEFAULT_PROCESS_NAME)
        self.status_var.set("已恢复默认的暗黑4窗口匹配")

    def show_support(self) -> None:
        messagebox.showinfo(
            APP_NAME,
            f"QQ 交流群：{SUPPORT_QQ_GROUP}\n\n如果工具对你有帮助，欢迎支持与反馈。发布页和更新检查可在“帮助”菜单里打开。",
            parent=self.advanced_window if self.advanced_window and self.advanced_window.winfo_exists() else self.window,
        )

    def save(self) -> None:
        try:
            macros: list[MacroConfig] = []
            for vars_for_row in self.macro_vars:
                macro_name = str(vars_for_row["name"].get()).strip() or "未命名宏"
                trigger_text = str(vars_for_row["trigger"].get()).strip()
                if not is_valid_key_text(trigger_text, TRIGGER_KEYS) or trigger_label_to_id(trigger_text) == "left":
                    raise ValueError(f"{macro_name} 的开关键无效：{trigger_text}")
                for slot_name in ["slot1", "slot2", "slot3", "slot4"]:
                    slot_text = str(vars_for_row[slot_name].get()).strip()
                    if not is_valid_key_text(slot_text, PRESS_KEYS):
                        raise ValueError(f"{macro_name} 的{slot_name.replace('slot', '槽位')}无效：{slot_text}")
                macros.append(MacroConfig(
                    enabled=bool(vars_for_row["enabled"].get()),
                    name=macro_name,
                    trigger=trigger_label_to_id(trigger_text),
                    action=action_label_to_id(str(vars_for_row["action"].get())),
                    sequence=[press_key_label_to_id(str(vars_for_row[name].get())) for name in ["slot1", "slot2", "slot3", "slot4"]],
                    interval_ms=parse_interval_ms(vars_for_row["interval"].get(), macro_name),
                    id=str(vars_for_row["id"]),
                    playback_mode=playback_mode_label_to_id(str(vars_for_row["playback_mode"].get())),
                    recording=normalize_recording(vars_for_row.get("recording")),
                ))
            toggle_profiles: list[ToggleProfile] = []
            for profile_vars in self.toggle_profile_vars:
                selected_vars = profile_vars["selected_vars"]
                toggle_profiles.append(ToggleProfile(
                    enabled=bool(profile_vars["enabled"].get()),
                    trigger=optional_trigger_label_to_id(str(profile_vars["trigger"].get()).strip()),
                    macro_ids=[macro_id for macro_id, selected_var in selected_vars.items() if selected_var.get()],
                    id=str(profile_vars["id"]),
                ))
            config = Config(
                window_title_contains=self.title_var.get().strip(),
                process_name=self.process_var.get().strip(),
                macros=macros,
                toggle_profiles=toggle_profiles,
                poll_interval_ms=DEFAULT_POLL_INTERVAL_MS,
                overlay_enabled=bool(self.overlay_enabled_var.get()),
                overlay_x=int(self.overlay_x_var.get()),
                overlay_y=int(self.overlay_y_var.get()),
                overlay_opacity=float(self.overlay_opacity_var.get()),
                recording_trigger=optional_trigger_label_to_id(str(self.recording_trigger_var.get()).strip()),
                recording_countdown_sec=int(self.recording_countdown_var.get()),
                recording_max_seconds=int(self.recording_max_seconds_var.get()),
                route_enabled=bool(self.route_enabled_var.get()),
                route_trigger=trigger_label_to_id(str(self.route_trigger_var.get()).strip()),
                overlay_layout_trigger=trigger_label_to_id(str(self.overlay_layout_trigger_var.get()).strip()),
                route_x=int(self.route_x_var.get()),
                route_y=int(self.route_y_var.get()),
                route_size=next((key for key, label in ROUTE_SIZE_LABELS.items() if label == self.route_size_var.get()), "medium"),
                route_opacity=float(self.route_opacity_var.get()),
                route_last_selected=self.engine.snapshot().config.route_last_selected,
            )
            validate_config(config)
            save_config(self.config_path, config)
            self.engine.update_config(config)
            self.status_var.set("已保存并应用")
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self.window)

    def defaults(self) -> None:
        config = Config(macros=default_macros())
        self.engine.update_config(config)
        save_config(self.config_path, config)
        self.load_from_engine()
        self.status_var.set("已恢复默认")

    def detect_foreground(self) -> None:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            self.status_var.set("未读取到当前前台窗口")
            return
        self.title_var.set(get_window_title(hwnd))
        self.process_var.set(get_process_name(hwnd))
        self.status_var.set("已读取当前前台窗口")

    def show(self) -> None:
        self.load_from_engine()
        self._reveal_window()

    def _reveal_window(self) -> None:
        self.window.deiconify()
        self.window.lift()
        self.window.attributes("-topmost", True)
        self.window.after(250, lambda: self.window.attributes("-topmost", False))
        self.window.after(20, self.window.focus_force)

    def hide(self) -> None:
        self.window.withdraw()

def action_label_to_id(label: str) -> str:
    for key, value in ACTION_LABELS.items():
        if value == label:
            return key
    return ACTION_NONE


def action_id_to_label(action_id: str) -> str:
    return ACTION_LABELS.get(action_id, ACTION_LABELS[ACTION_NONE])


def playback_mode_label_to_id(label: str) -> str:
    for key, value in PLAYBACK_MODE_LABELS.items():
        if value == label:
            return key
    return PLAYBACK_ONCE


def playback_mode_id_to_label(mode_id: str) -> str:
    return PLAYBACK_MODE_LABELS.get(mode_id, PLAYBACK_MODE_LABELS[PLAYBACK_ONCE])


def recording_summary(recording: object) -> str:
    events = normalize_recording(recording if isinstance(recording, list) else None)
    if not events:
        return "未录制"
    duration_ms = int(events[-1].get("at_ms", 0))
    return f"{len(events)} 个动作 / {duration_ms / 1000:.1f} 秒"


def key_text_to_id(text: str, allowed: dict[str, object], fallback: str) -> str:
    raw = text.strip()
    if not raw:
        return fallback
    if raw in allowed:
        return raw
    lowered = raw.lower().replace("_", "").replace("-", "").replace(" ", "")
    if lowered in allowed:
        return lowered
    if lowered in KEY_ALIASES and KEY_ALIASES[lowered] in allowed:
        return KEY_ALIASES[lowered]
    label_key = raw.lower()
    if label_key in LABEL_TO_KEY_ID and LABEL_TO_KEY_ID[label_key] in allowed:
        return LABEL_TO_KEY_ID[label_key]
    if len(raw) == 1 and raw.isalpha() and raw.lower() in allowed:
        return raw.lower()
    if len(raw) == 1 and raw.isdigit() and raw in allowed:
        return raw
    return fallback


def is_valid_key_text(text: str, allowed: dict[str, object]) -> bool:
    return key_text_to_id(text, allowed, "") != ""


def trigger_label_to_id(label: str) -> str:
    return key_text_to_id(label, TRIGGER_KEYS, "xbutton1")


def trigger_id_to_label(trigger_id: str) -> str:
    normalized = trigger_label_to_id(trigger_id)
    return TRIGGER_LABELS.get(normalized, TRIGGER_LABELS["xbutton1"])


def optional_trigger_label_to_id(label: str) -> str:
    return key_text_to_id(label, OPTIONAL_TRIGGER_KEYS, "none")


def optional_trigger_id_to_label(trigger_id: str) -> str:
    normalized = optional_trigger_label_to_id(trigger_id)
    return OPTIONAL_TRIGGER_LABELS.get(normalized, OPTIONAL_TRIGGER_LABELS["none"])


def press_key_label_to_id(label: str) -> str:
    return key_text_to_id(label, PRESS_KEYS, "none")


def press_key_id_to_label(key_id: str) -> str:
    normalized = press_key_label_to_id(key_id)
    return PRESS_KEY_LABELS.get(normalized, PRESS_KEY_LABELS["none"])


def parse_interval_ms(value: object, macro_name: str) -> int:
    try:
        interval_ms = int(value)
    except (TypeError, ValueError, tk.TclError) as exc:
        raise ValueError(f"{macro_name} 的间隔必须是数字。") from exc
    if interval_ms < MIN_MACRO_INTERVAL_MS:
        raise ValueError(f"{macro_name} 的间隔不能小于 {MIN_MACRO_INTERVAL_MS}ms。")
    return interval_ms


def parse_version(version: str) -> tuple[int, ...]:
    normalized = version.strip().lstrip("vV")
    parts: list[int] = []
    for part in normalized.split("."):
        digits = ""
        for char in part:
            if char.isdigit():
                digits += char
            else:
                break
        parts.append(int(digits) if digits else 0)
    return tuple(parts or [0])


def is_newer_version(latest: str, current: str) -> bool:
    latest_parts = parse_version(latest)
    current_parts = parse_version(current)
    max_len = max(len(latest_parts), len(current_parts))
    latest_parts += (0,) * (max_len - len(latest_parts))
    current_parts += (0,) * (max_len - len(current_parts))
    return latest_parts > current_parts


def fetch_latest_release() -> tuple[str, str]:
    request = urllib.request.Request(
        GITHUB_LATEST_RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": APP_NAME,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError("网络不可用或 GitHub 访问失败") from exc

    data = json.loads(raw)
    tag_name = str(data.get("tag_name", "")).strip()
    if not tag_name:
        raise RuntimeError("未读取到最新版本号")
    release_url = str(data.get("html_url", "")).strip() or GITHUB_RELEASES_URL
    return tag_name.lstrip("vV"), release_url


def make_stable_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def default_macros() -> list[MacroConfig]:
    return [
        MacroConfig(True, "交互", "f1", ACTION_PRESS_CYCLE, ["f", "none", "none", "none"], 100, "macro_6cabdbdd74c7", PLAYBACK_ONCE, []),
        MacroConfig(True, "右键连点", "f2", ACTION_PRESS_CYCLE, ["right", "none", "none", "none"], 100, "macro_795e8f90f19b", PLAYBACK_ONCE, []),
        MacroConfig(True, "旋风斩", "f3", ACTION_HOLD, ["right", "none", "none", "none"], 100, "macro_d5e130410039", PLAYBACK_ONCE, []),
        MacroConfig(True, "增益技能", "f4", ACTION_PRESS_CYCLE, ["2", "1", "3", "4"], 100, "macro_639ed922028b", PLAYBACK_ONCE, []),
        MacroConfig(True, "大招", "f5", ACTION_PRESS_CYCLE, ["left", "none", "none", "none"], 1000, "macro_1ab382a5f373", PLAYBACK_ONCE, []),
    ]


def blank_macro_config(index: int) -> MacroConfig:
    return MacroConfig(
        enabled=False,
        name=f"宏 {index}",
        trigger="xbutton1",
        action=ACTION_NONE,
        sequence=["none", "none", "none", "none"],
        interval_ms=DEFAULT_INTERVAL_MS,
        id=make_stable_id("macro"),
    )


def blank_toggle_profile() -> ToggleProfile:
    return ToggleProfile(
        enabled=True,
        trigger="none",
        macro_ids=[],
        id=make_stable_id("profile"),
    )


def default_toggle_profiles(macros: list[MacroConfig]) -> list[ToggleProfile]:
    return [
        ToggleProfile(
            enabled=True,
            trigger="middle",
            macro_ids=[
                "macro_6cabdbdd74c7",
                "macro_d5e130410039",
                "macro_639ed922028b",
                "macro_1ab382a5f373",
            ],
            id="profile_1c6916323e1f",
        )
    ]


def parse_macros(raw: dict[str, object]) -> list[MacroConfig]:
    if isinstance(raw.get("macros"), list):
        parsed = []
        for item in raw["macros"]:
            if not isinstance(item, dict):
                continue
            action = str(item.get("action", ACTION_NONE))
            sequence = [str(value) for value in item.get("sequence", ["none", "none", "none", "none"])]
            if action == "hold_right":
                action = ACTION_HOLD
                sequence = ["right", "none", "none", "none"]
            elif action == "hold_left":
                action = ACTION_HOLD
                sequence = ["left", "none", "none", "none"]
            parsed.append(MacroConfig(
                enabled=bool(item.get("enabled", False)),
                name=str(item.get("name", "")).strip(),
                trigger=str(item.get("trigger", "xbutton1")),
                action=action,
                sequence=sequence,
                interval_ms=int(item.get("interval_ms", DEFAULT_INTERVAL_MS)),
                id=str(item.get("id", "")).strip(),
                playback_mode=str(item.get("playback_mode", PLAYBACK_ONCE)).strip(),
                recording=item.get("recording") if isinstance(item.get("recording"), list) else None,
            ))
        return normalize_macros(parsed)

    macros = default_macros()
    macros[0].enabled = bool(raw.get("right_hold_enabled", True))
    macros[0].trigger = str(raw.get("right_hold_trigger", "xbutton1"))
    macros[1].enabled = bool(raw.get("left_click_loop_enabled", True))
    macros[1].trigger = str(raw.get("left_click_loop_trigger", "xbutton2"))
    macros[1].interval_ms = int(raw.get("left_click_interval_ms", DEFAULT_INTERVAL_MS))
    macros[2].enabled = bool(raw.get("f1_combo_enabled", True))
    macros[2].trigger = str(raw.get("f1_combo_trigger", "f1"))
    macros[2].interval_ms = int(raw.get("f1_combo_interval_ms", DEFAULT_INTERVAL_MS))

    old_xbutton1_action = str(raw.get("xbutton1_action", ""))
    old_xbutton2_action = str(raw.get("xbutton2_action", ""))
    for trigger_id, action_name in [("xbutton1", old_xbutton1_action), ("xbutton2", old_xbutton2_action)]:
        if action_name in ["right_hold", "right_hold_toggle"]:
            macros[0].enabled = True
            macros[0].trigger = trigger_id
        elif action_name == "left_click_loop":
            macros[1].enabled = True
            macros[1].trigger = trigger_id
        elif action_name == "right_click_loop":
            macros[3].enabled = True
            macros[3].name = "右键连点"
            macros[3].trigger = trigger_id
            macros[3].action = ACTION_PRESS_CYCLE
            macros[3].sequence = ["right", "none", "none", "none"]
            macros[3].interval_ms = int(raw.get("right_click_interval_ms", DEFAULT_INTERVAL_MS))
    return normalize_macros(macros)


def normalize_sequence(sequence: list[str] | None) -> list[str]:
    values = list(sequence or [])
    normalized = [press_key_label_to_id(str(value)) for value in values[:4]]
    while len(normalized) < 4:
        normalized.append("none")
    return normalized


def hold_items(macro: MacroConfig) -> list[str]:
    sequence = normalize_sequence(macro.sequence)
    return [item for item in sequence if item != "none"]


def normalize_recording(recording: list[dict[str, object]] | None) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    if not isinstance(recording, list):
        return normalized
    for event in recording[:MAX_RECORDED_EVENTS]:
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("type", "")).strip()
        key_id = press_key_label_to_id(str(event.get("key", "")))
        if event_type not in {"key_down", "key_up"} or key_id == "none":
            continue
        try:
            at_ms = max(0, int(event.get("at_ms", 0)))
        except (TypeError, ValueError):
            at_ms = 0
        normalized_event: dict[str, object] = {"type": event_type, "key": key_id, "at_ms": at_ms}
        if key_id in {"left", "right", "middle"}:
            try:
                normalized_event["x"] = int(event["x"])
                normalized_event["y"] = int(event["y"])
            except (KeyError, TypeError, ValueError):
                pass
        normalized.append(normalized_event)
    normalized.sort(key=lambda item: int(item.get("at_ms", 0)))
    balanced: list[dict[str, object]] = []
    held_items: set[str] = set()
    for event in normalized:
        key_id = str(event["key"])
        if event["type"] == "key_down":
            if key_id in held_items:
                continue
            held_items.add(key_id)
            balanced.append(event)
        elif key_id in held_items:
            held_items.remove(key_id)
            balanced.append(event)
    last_at = int(balanced[-1].get("at_ms", 0)) if balanced else 0
    for key_id in sorted(held_items):
        balanced.append({"type": "key_up", "key": key_id, "at_ms": last_at + 10})
    return balanced


def normalize_macros(macros: list[MacroConfig] | None) -> list[MacroConfig]:
    source = default_macros() if macros is None else list(macros)
    normalized: list[MacroConfig] = []
    defaults = default_macros()
    for index, macro in enumerate(source):
        fallback = defaults[index] if index < len(defaults) else blank_macro_config(index + 1)
        normalized.append(MacroConfig(
            enabled=bool(macro.enabled),
            name=(macro.name or f"宏 {index + 1}").strip(),
            trigger=trigger_label_to_id(macro.trigger) if trigger_label_to_id(macro.trigger) in TRIGGER_KEYS else fallback.trigger,
            action=macro.action if macro.action in ACTION_LABELS else ACTION_NONE,
            sequence=normalize_sequence(macro.sequence),
            interval_ms=max(int(macro.interval_ms), MIN_MACRO_INTERVAL_MS),
            id=str(macro.id).strip() or make_stable_id("macro"),
            playback_mode=macro.playback_mode if macro.playback_mode in PLAYBACK_MODE_LABELS else PLAYBACK_ONCE,
            recording=normalize_recording(macro.recording),
        ))
    return normalized


def parse_toggle_profiles(raw: dict[str, object], macros: list[MacroConfig]) -> list[ToggleProfile]:
    if isinstance(raw.get("toggle_profiles"), list):
        parsed: list[ToggleProfile] = []
        for item in raw["toggle_profiles"]:
            if not isinstance(item, dict):
                continue
            macro_ids = item.get("macro_ids", [])
            parsed.append(ToggleProfile(
                enabled=bool(item.get("enabled", True)),
                trigger=str(item.get("trigger", "none")).strip(),
                macro_ids=[str(value).strip() for value in macro_ids] if isinstance(macro_ids, list) else [],
                id=str(item.get("id", "")).strip(),
            ))
        return normalize_toggle_profiles(parsed, macros)

    legacy_trigger = str(raw.get("all_toggle_trigger", "f3")).strip()
    if not legacy_trigger or legacy_trigger == "none":
        return []
    return normalize_toggle_profiles([
        ToggleProfile(
            enabled=True,
            trigger=legacy_trigger,
            macro_ids=[macro.id for macro in macros],
            id=make_stable_id("profile"),
        )
    ], macros)


def normalize_toggle_profiles(profiles: list[ToggleProfile] | None, macros: list[MacroConfig]) -> list[ToggleProfile]:
    existing_macro_ids = {macro.id for macro in macros}
    if profiles is None:
        return default_toggle_profiles(macros)
    normalized: list[ToggleProfile] = []
    for profile in profiles:
        selected_ids: list[str] = []
        for macro_id in profile.macro_ids or []:
            macro_id = str(macro_id).strip()
            if macro_id and macro_id in existing_macro_ids and macro_id not in selected_ids:
                selected_ids.append(macro_id)
        normalized.append(ToggleProfile(
            enabled=bool(profile.enabled),
            trigger=optional_trigger_label_to_id(str(profile.trigger)),
            macro_ids=selected_ids,
            id=str(profile.id).strip() or make_stable_id("profile"),
        ))
    return normalized


def normalize_config(config: Config) -> Config:
    window_title_contains = str(config.window_title_contains).strip()
    process_name = str(config.process_name).strip()
    if not window_title_contains and not process_name:
        window_title_contains = DEFAULT_WINDOW_TITLE_CONTAINS
        process_name = DEFAULT_PROCESS_NAME
    macros = normalize_macros(config.macros)
    return Config(
        window_title_contains=window_title_contains,
        process_name=process_name,
        macros=macros,
        toggle_profiles=normalize_toggle_profiles(config.toggle_profiles, macros),
        poll_interval_ms=DEFAULT_POLL_INTERVAL_MS,
        overlay_enabled=bool(config.overlay_enabled),
        overlay_x=int(config.overlay_x),
        overlay_y=int(config.overlay_y),
        overlay_opacity=float(config.overlay_opacity),
        recording_trigger=optional_trigger_label_to_id(str(config.recording_trigger)),
        recording_countdown_sec=max(int(config.recording_countdown_sec), 0),
        recording_max_seconds=max(int(config.recording_max_seconds), 1),
        route_enabled=bool(config.route_enabled),
        route_trigger=trigger_label_to_id(str(config.route_trigger)),
        overlay_layout_trigger=trigger_label_to_id(str(config.overlay_layout_trigger)),
        route_x=int(config.route_x),
        route_y=int(config.route_y),
        route_size=str(config.route_size) if str(config.route_size) in ROUTE_SIZE_LABELS else "medium",
        route_opacity=clamp(float(config.route_opacity), 0.4, 1.0),
        route_last_selected=str(config.route_last_selected) if str(config.route_last_selected) in WORM_ROUTE_MAP_BY_ID else WORM_ROUTE_MAPS[0].id,
    )


def clone_config(config: Config) -> Config:
    normalized = normalize_config(config)
    return Config(
        window_title_contains=normalized.window_title_contains,
        process_name=normalized.process_name,
        macros=[
            MacroConfig(m.enabled, m.name, m.trigger, m.action, list(m.sequence), m.interval_ms, m.id, m.playback_mode, normalize_recording(m.recording))
            for m in (normalized.macros or [])
        ],
        toggle_profiles=[
            ToggleProfile(profile.enabled, profile.trigger, list(profile.macro_ids), profile.id)
            for profile in (normalized.toggle_profiles or [])
        ],
        poll_interval_ms=normalized.poll_interval_ms,
        overlay_enabled=normalized.overlay_enabled,
        overlay_x=normalized.overlay_x,
        overlay_y=normalized.overlay_y,
        overlay_opacity=normalized.overlay_opacity,
        recording_trigger=normalized.recording_trigger,
        recording_countdown_sec=normalized.recording_countdown_sec,
        recording_max_seconds=normalized.recording_max_seconds,
        route_enabled=normalized.route_enabled,
        route_trigger=normalized.route_trigger,
        overlay_layout_trigger=normalized.overlay_layout_trigger,
        route_x=normalized.route_x,
        route_y=normalized.route_y,
        route_size=normalized.route_size,
        route_opacity=normalized.route_opacity,
        route_last_selected=normalized.route_last_selected,
    )


def press_sequence_item(item: str) -> None:
    if item == "left":
        click_left()
    elif item == "right":
        click_right()
    elif item == "middle":
        click_middle()
    elif item in PRESS_KEYS and isinstance(PRESS_KEYS[item], int):
        tap_key(PRESS_KEYS[item])


def move_cursor_to_recorded_position(event: dict[str, object]) -> None:
    x = event.get("x")
    y = event.get("y")
    if x is None or y is None:
        return
    try:
        cursor_x = int(x)
        cursor_y = int(y)
    except (TypeError, ValueError):
        return
    user32.SetCursorPos(cursor_x, cursor_y)


def get_cursor_position() -> tuple[int, int] | None:
    point = wintypes.POINT()
    if not user32.GetCursorPos(ctypes.byref(point)):
        return None
    return point.x, point.y


def send_mouse_input(flags: int) -> None:
    extra = ctypes.c_ulong(0)
    mouse_input = MOUSEINPUT(0, 0, 0, flags, 0, ctypes.pointer(extra))
    input_struct = INPUT(INPUT_MOUSE, INPUT_UNION(mi=mouse_input))
    sent = user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(INPUT))
    if sent != 1:
        raise ctypes.WinError(ctypes.get_last_error())


def mark_pending_release(kind: str, value: int) -> None:
    with PENDING_RELEASES_LOCK:
        PENDING_RELEASES.add((kind, int(value)))


def clear_pending_release(kind: str, value: int) -> None:
    with PENDING_RELEASES_LOCK:
        PENDING_RELEASES.discard((kind, int(value)))


def has_pending_releases() -> bool:
    with PENDING_RELEASES_LOCK:
        return bool(PENDING_RELEASES)


def retry_pending_releases() -> bool:
    with PENDING_RELEASES_LOCK:
        pending = list(PENDING_RELEASES)
    for kind, value in pending:
        try:
            if kind == "mouse":
                send_mouse_input(value)
            elif kind == "key":
                send_key_input(value, KEYEVENTF_KEYUP)
            else:
                clear_pending_release(kind, value)
                continue
        except OSError:
            continue
        clear_pending_release(kind, value)
    return not has_pending_releases()


def send_mouse_input_pair(down_flags: int, up_flags: int) -> None:
    extra = ctypes.c_ulong(0)
    extra_pointer = ctypes.pointer(extra)
    inputs = (INPUT * 2)(
        INPUT(INPUT_MOUSE, INPUT_UNION(mi=MOUSEINPUT(0, 0, 0, down_flags, 0, extra_pointer))),
        INPUT(INPUT_MOUSE, INPUT_UNION(mi=MOUSEINPUT(0, 0, 0, up_flags, 0, extra_pointer))),
    )
    sent = user32.SendInput(2, inputs, ctypes.sizeof(INPUT))
    if sent != 2:
        error_code = ctypes.get_last_error()
        if sent == 1:
            mark_pending_release("mouse", up_flags)
            try:
                send_mouse_input(up_flags)
            except OSError:
                pass
            else:
                clear_pending_release("mouse", up_flags)
            raise ctypes.WinError(error_code)
        raise ctypes.WinError(error_code)


def click_left() -> None:
    send_mouse_input_pair(MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP)


def click_right() -> None:
    send_mouse_input_pair(MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP)


def click_middle() -> None:
    send_mouse_input_pair(MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP)


def send_key_input(virtual_key: int, flags: int) -> None:
    extra = ctypes.c_ulong(0)
    keyboard_input = KEYBDINPUT(virtual_key, 0, flags, 0, ctypes.pointer(extra))
    input_struct = INPUT(1, INPUT_UNION(ki=keyboard_input))
    sent = user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(INPUT))
    if sent != 1:
        raise ctypes.WinError(ctypes.get_last_error())


def tap_key(virtual_key: int) -> None:
    extra = ctypes.c_ulong(0)
    extra_pointer = ctypes.pointer(extra)
    inputs = (INPUT * 2)(
        INPUT(1, INPUT_UNION(ki=KEYBDINPUT(virtual_key, 0, 0, 0, extra_pointer))),
        INPUT(1, INPUT_UNION(ki=KEYBDINPUT(virtual_key, 0, KEYEVENTF_KEYUP, 0, extra_pointer))),
    )
    sent = user32.SendInput(2, inputs, ctypes.sizeof(INPUT))
    if sent != 2:
        error_code = ctypes.get_last_error()
        if sent == 1:
            mark_pending_release("key", virtual_key)
            try:
                send_key_input(virtual_key, KEYEVENTF_KEYUP)
            except OSError:
                pass
            else:
                clear_pending_release("key", virtual_key)
            raise ctypes.WinError(error_code)
        raise ctypes.WinError(error_code)


def is_key_down(virtual_key: int) -> bool:
    return bool(user32.GetAsyncKeyState(virtual_key) & 0x8000)


def foreground_matches_values(config: Config, title: str, process: str) -> bool:
    title_filter = config.window_title_contains.lower()
    process_filter = config.process_name.lower()
    if title_filter and title_filter not in title.lower():
        return False
    if process_filter and process_filter != process.lower():
        return False
    return bool(title_filter or process_filter)


def get_window_title(hwnd: wintypes.HWND) -> str:
    buffer = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return buffer.value


def get_process_name(hwnd: wintypes.HWND) -> str:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""

    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ""

    try:
        buffer = ctypes.create_unicode_buffer(MAX_PATH)
        size = wintypes.DWORD(len(buffer))
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return ""
        return Path(buffer.value).name
    finally:
        kernel32.CloseHandle(handle)


def detect_foreground() -> None:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        print("No foreground window detected.")
        return
    print(f"title: {get_window_title(hwnd)}")
    print(f"process: {get_process_name(hwnd)}")


def load_config(path: Path) -> Config:
    if not path.exists():
        config = Config(macros=default_macros())
        save_config(path, config)
        return config

    raw = json.loads(path.read_text(encoding="utf-8"))
    macros = parse_macros(raw)
    toggle_profiles = parse_toggle_profiles(raw, macros)
    legacy_route_position = str(raw.get("route_position", "right")).strip()
    legacy_route_x = {"left": 24, "center": 600, "right": DEFAULT_ROUTE_X}.get(legacy_route_position, DEFAULT_ROUTE_X)

    config = Config(
        window_title_contains=str(raw.get("window_title_contains", "")).strip(),
        process_name=str(raw.get("process_name", "")).strip(),
        macros=macros,
        toggle_profiles=toggle_profiles,
        poll_interval_ms=DEFAULT_POLL_INTERVAL_MS,
        overlay_enabled=bool(raw.get("overlay_enabled", True)),
        overlay_x=int(raw.get("overlay_x", 20)),
        overlay_y=int(raw.get("overlay_y", 20)),
        overlay_opacity=float(raw.get("overlay_opacity", DEFAULT_OVERLAY_OPACITY)),
        recording_trigger=str(raw.get("recording_trigger", DEFAULT_RECORD_TRIGGER)).strip(),
        recording_countdown_sec=int(raw.get("recording_countdown_sec", DEFAULT_RECORD_COUNTDOWN_SEC)),
        recording_max_seconds=int(raw.get("recording_max_seconds", DEFAULT_RECORD_MAX_SECONDS)),
        route_enabled=bool(raw.get("route_enabled", True)),
        route_trigger=str(raw.get("route_trigger", DEFAULT_ROUTE_TRIGGER)).strip(),
        overlay_layout_trigger=str(raw.get("overlay_layout_trigger", DEFAULT_OVERLAY_LAYOUT_TRIGGER)).strip(),
        route_x=int(raw.get("route_x", legacy_route_x)),
        route_y=int(raw.get("route_y", DEFAULT_ROUTE_Y)),
        route_size=str(raw.get("route_size", "medium")).strip(),
        route_opacity=float(raw.get("route_opacity", DEFAULT_ROUTE_OPACITY)),
        route_last_selected=str(raw.get("route_last_selected", WORM_ROUTE_MAPS[0].id)).strip(),
    )

    validate_config(config)
    save_config(path, config)
    return config


def save_config(path: Path, config: Config) -> None:
    path.write_text(json.dumps(asdict(normalize_config(config)), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_config(config: Config) -> None:
    config = normalize_config(config)
    active_triggers = []
    names = set()
    for macro in config.macros or []:
        if not macro.name:
            raise ValueError("宏名称不能为空。")
        if macro.name in names:
            raise ValueError(f"宏名称重复：{macro.name}")
        names.add(macro.name)
        if macro.trigger not in TRIGGER_KEYS:
            raise ValueError(f"{macro.name} 的开关键无效。")
        if macro.action not in ACTION_LABELS:
            raise ValueError(f"{macro.name} 的动作无效。")
        if macro.action == ACTION_HOLD and not hold_items(macro):
            raise ValueError(f"{macro.name} 的自动按住槽位不能全为“无”。")
        if macro.action == ACTION_PRESS_CYCLE and not [item for item in macro.sequence if item != "none"]:
            raise ValueError(f"{macro.name} 的循环槽位不能全为“无”。")
        if macro.enabled and macro.action == ACTION_RECORDED and not normalize_recording(macro.recording):
            raise ValueError(f"{macro.name} 没有录制内容。")
        if macro.enabled and macro.action != ACTION_NONE:
            active_triggers.append((macro.trigger, macro.name))
    seen: dict[str, str] = {}
    for trigger_id, label in active_triggers:
        if trigger_id in seen:
            raise ValueError(f"{label} 和 {seen[trigger_id]} 使用了同一个开关键：{trigger_id_to_label(trigger_id)}。")
        seen[trigger_id] = label
    for index, profile in enumerate(config.toggle_profiles or []):
        if profile.trigger not in OPTIONAL_TRIGGER_KEYS:
            raise ValueError(f"一键启动配置 {index + 1} 的快捷键无效。")
        if not profile.enabled:
            continue
        if profile.trigger == "none":
            continue
        if profile.trigger in seen:
            raise ValueError(f"一键启动配置 {index + 1} 不能和 {seen[profile.trigger]} 使用同一个按键：{trigger_id_to_label(profile.trigger)}。")
        seen[profile.trigger] = f"一键启动配置 {index + 1}"
    if config.recording_trigger not in OPTIONAL_TRIGGER_KEYS:
        raise ValueError("录制快捷键无效。")
    if config.recording_trigger != "none" and config.recording_trigger in seen:
        raise ValueError(f"宏录制不能和 {seen[config.recording_trigger]} 使用同一个按键：{trigger_id_to_label(config.recording_trigger)}。")
    if config.route_trigger not in TRIGGER_KEYS:
        raise ValueError("线路图快捷键无效。")
    if config.route_enabled and config.route_trigger in seen:
        raise ValueError(f"线路图不能和 {seen[config.route_trigger]} 使用同一个按键：{trigger_id_to_label(config.route_trigger)}。")
    if config.route_enabled and config.route_trigger == config.recording_trigger:
        raise ValueError(f"线路图不能和宏录制使用同一个按键：{trigger_id_to_label(config.route_trigger)}。")
    if config.overlay_layout_trigger not in TRIGGER_KEYS:
        raise ValueError("浮层调整快捷键无效。")
    if config.overlay_layout_trigger in seen:
        raise ValueError(f"浮层调整不能和 {seen[config.overlay_layout_trigger]} 使用同一个按键：{trigger_id_to_label(config.overlay_layout_trigger)}。")
    if config.overlay_layout_trigger == config.recording_trigger:
        raise ValueError(f"浮层调整不能和宏录制使用同一个按键：{trigger_id_to_label(config.overlay_layout_trigger)}。")
    if config.route_enabled and config.overlay_layout_trigger == config.route_trigger:
        raise ValueError(f"浮层调整不能和线路图使用同一个按键：{trigger_id_to_label(config.overlay_layout_trigger)}。")
    if not -5000 <= config.overlay_x <= 5000 or not -5000 <= config.overlay_y <= 5000:
        raise ValueError("状态浮层坐标必须在 -5000 到 5000 之间。")
    if not -5000 <= config.route_x <= 5000 or not -5000 <= config.route_y <= 5000:
        raise ValueError("线路图坐标必须在 -5000 到 5000 之间。")
    if config.route_size not in ROUTE_SIZE_LABELS:
        raise ValueError("线路图大小无效。")
    if not 0.4 <= config.route_opacity <= 1.0:
        raise ValueError("线路图透明度必须在 40% 到 100% 之间。")
    if config.poll_interval_ms < 50:
        raise ValueError("轮询间隔不能小于 50ms。")
    if config.recording_countdown_sec < 0:
        raise ValueError("录制倒计时不能小于 0 秒。")
    if config.recording_max_seconds < 1:
        raise ValueError("最长录制时长不能小于 1 秒。")


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def window_geometry(width: int, height: int, x: int, y: int) -> str:
    return f"{int(width)}x{int(height)}{int(x):+d}{int(y):+d}"


def virtual_desktop_bounds() -> tuple[int, int, int, int]:
    left = int(user32.GetSystemMetrics(SM_XVIRTUALSCREEN))
    top = int(user32.GetSystemMetrics(SM_YVIRTUALSCREEN))
    width = int(user32.GetSystemMetrics(SM_CXVIRTUALSCREEN))
    height = int(user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))
    if width <= 0 or height <= 0:
        return 0, 0, 1920, 1080
    return left, top, left + width, top + height


def clamp_to_virtual_desktop(x: int, y: int, width: int, height: int, visible: int = 32) -> tuple[int, int]:
    left, top, right, bottom = virtual_desktop_bounds()
    visible_x = min(max(int(visible), 1), max(int(width), 1))
    visible_y = min(max(int(visible), 1), max(int(height), 1))
    min_x = left - max(int(width) - visible_x, 0)
    max_x = right - visible_x
    min_y = top - max(int(height) - visible_y, 0)
    max_y = bottom - visible_y
    return int(clamp(int(x), min_x, max_x)), int(clamp(int(y), min_y, max_y))


def get_window_rect(hwnd: int) -> wintypes.RECT | None:
    rect = wintypes.RECT()
    if not hwnd or not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return rect


def rect_to_tuple(rect: wintypes.RECT) -> tuple[int, int, int, int]:
    return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)


def rect_from_tuple(bounds: tuple[int, int, int, int] | None) -> wintypes.RECT | None:
    if bounds is None:
        return None
    return wintypes.RECT(*[int(value) for value in bounds])


def copy_window_rect(rect: wintypes.RECT | None) -> wintypes.RECT | None:
    return rect_from_tuple(rect_to_tuple(rect)) if rect is not None else None


def root_window_handle(hwnd: int) -> int:
    if not hwnd:
        return 0
    return int(user32.GetAncestor(wintypes.HWND(hwnd), GA_ROOT) or hwnd)


def create_tray_icon(command_queue: queue.Queue[object]) -> object | None:
    if pystray is None or Image is None or ImageDraw is None:
        return None

    if APP_ICON_PATH.exists():
        image = Image.open(APP_ICON_PATH).resize((64, 64))
    else:
        image = Image.new("RGB", (64, 64), "#221a15")
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((6, 6, 58, 58), radius=12, fill="#4a1915", outline="#d8a84e", width=3)
        draw.text((18, 20), "D4", fill="#ffeab4")

    def show_config(_icon: object, _item: object) -> None:
        command_queue.put("show")

    def quit_app(icon: object, _item: object) -> None:
        command_queue.put("quit")
        icon.stop()

    return pystray.Icon(
        APP_NAME,
        image,
        APP_NAME,
        pystray.Menu(
            pystray.MenuItem("打开配置", show_config, default=True),
            pystray.MenuItem("退出", quit_app),
        ),
    )


def run_gui(config: Config, config_path: Path) -> int:
    command_queue: queue.Queue[object] = queue.Queue()
    engine = MacroEngine(config, command_queue)
    engine.start()

    root = tk.Tk()
    app = ConfigWindow(root, engine, command_queue, config_path)

    def persist_overlay_position(overlay_name: str, x: int, y: int) -> None:
        try:
            updated_config = engine.update_overlay_position(overlay_name, x, y)
            save_config(config_path, updated_config)
            app.update_overlay_position_fields(overlay_name, x, y)
            app.status_var.set(f"已保存{'状态浮层' if overlay_name == 'status' else '线路图浮层'}位置：X {x} / Y {y}")
        except Exception as exc:
            app.status_var.set(f"保存浮层位置失败：{exc}")

    overlay = OverlayWindow(
        root,
        engine,
        lambda x, y: persist_overlay_position("status", x, y),
    )

    def persist_route_selection(route_id: str) -> None:
        try:
            updated_config = engine.update_route_selection(route_id)
            save_config(config_path, updated_config)
        except Exception as exc:
            app.status_var.set(f"保存线路图选择失败：{exc}")

    route_overlay = WormRouteOverlay(
        root,
        engine,
        persist_route_selection,
        lambda x, y: persist_overlay_position("route", x, y),
    )
    layout_mode = False

    def set_layout_mode(enabled: bool) -> None:
        nonlocal layout_mode
        enabled = bool(enabled)
        if layout_mode == enabled:
            return
        layout_mode = enabled
        engine.set_overlay_layout_active(enabled)
        overlay.set_layout_mode(enabled)
        route_overlay.set_layout_mode(enabled)
        app.status_var.set("浮层布局模式：拖动浮层，松开即保存" if enabled else "已退出浮层布局模式")

    tray_icon = create_tray_icon(command_queue)
    if tray_icon:
        threading.Thread(target=tray_icon.run, name="tray-icon", daemon=True).start()

    def quit_all() -> None:
        engine.stop()
        if tray_icon:
            tray_icon.stop()
        root.destroy()

    def tick() -> None:
        def handle_recording_done(events: list[dict[str, object]]) -> None:
            try:
                app.add_recorded_macro(events)
            except Exception as exc:
                app.status_var.set(f"添加录制宏失败：{exc}")
                app._reveal_window()

        try:
            while True:
                command = command_queue.get_nowait()
                if isinstance(command, dict) and command.get("type") == "recording_done":
                    root.after(0, lambda events=normalize_recording(command.get("events")): handle_recording_done(events))
                elif isinstance(command, dict) and command.get("type") == "overlay_layout_toggle":
                    set_layout_mode(not layout_mode)
                elif isinstance(command, dict) and command.get("type") == "route_toggle":
                    set_layout_mode(False)
                    route_overlay.toggle_selector()
                elif isinstance(command, dict) and command.get("type") == "engine_error":
                    if command.get("released", False):
                        app.status_var.set(f"宏引擎已停止，输入已释放：{command.get('message', '未知错误')}")
                    else:
                        app.status_var.set(f"宏引擎已停止，部分输入释放失败，请退出程序：{command.get('message', '未知错误')}")
                elif command == "show":
                    app.show()
                elif command == "quit":
                    quit_all()
                    return
        except queue.Empty:
            pass
        except Exception as exc:
            app.status_var.set(f"处理后台命令失败：{exc}")
            app._reveal_window()

        if layout_mode and not engine.snapshot().target_active:
            foreground_root = root_window_handle(int(user32.GetForegroundWindow() or 0))
            layout_roots = {
                root_window_handle(overlay.window.winfo_id()),
                root_window_handle(route_overlay.map_window.winfo_id()),
            }
            dragging = (
                (overlay._dragging or route_overlay._dragging)
                and is_key_down(0x01)
            )
            if foreground_root not in layout_roots and not dragging:
                set_layout_mode(False)
        overlay.refresh()
        route_overlay.refresh()
        root.after(120, tick)

    def handle_stop(_signum: int, _frame: object) -> None:
        command_queue.put("quit")

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)
    root.after(120, tick)

    try:
        root.mainloop()
    finally:
        engine.stop()
    return 0


def main() -> int:
    if not acquire_single_instance():
        try:
            messagebox.showinfo(APP_NAME, "D4Helper 已经在运行。")
        except Exception:
            print("D4Helper 已经在运行。")
        return 0

    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--detect", action="store_true", help="打印当前前台窗口标题和进程名")
    parser.add_argument("--config", default=str(CONFIG_PATH), help="配置文件路径")
    parser.add_argument("--no-gui", action="store_true", help="无配置窗口、托盘和浮层运行")
    args = parser.parse_args()

    if args.detect:
        detect_foreground()
        return 0

    config_path = Path(args.config)
    config = load_config(config_path)

    if args.no_gui:
        engine = MacroEngine(config)
        engine.start()
        print("运行中。按 Ctrl+C 退出。")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            engine.stop()
        return 0

    return run_gui(config, config_path)


if __name__ == "__main__":
    raise SystemExit(main())







