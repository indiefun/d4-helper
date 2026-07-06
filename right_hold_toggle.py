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
MIN_MACRO_INTERVAL_MS = 25


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


user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = wintypes.LONG
user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
user32.SetWindowLongW.restype = wintypes.LONG

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


@dataclass
class MacroConfig:
    enabled: bool
    name: str
    trigger: str
    action: str
    sequence: list[str]
    interval_ms: int = DEFAULT_INTERVAL_MS
    id: str = ""


@dataclass
class ToggleProfile:
    trigger: str
    macro_ids: list[str]
    id: str = ""


@dataclass
class Config:
    window_title_contains: str = DEFAULT_WINDOW_TITLE_CONTAINS
    process_name: str = DEFAULT_PROCESS_NAME
    macros: list[MacroConfig] | None = None
    toggle_profiles: list[ToggleProfile] | None = None
    poll_interval_ms: int = 100
    overlay_enabled: bool = True
    overlay_x: int = 20
    overlay_y: int = 20
    overlay_opacity: float = 0.82


@dataclass(frozen=True)
class Snapshot:
    target_active: bool
    macro_states: dict[str, bool]
    config: Config
    foreground_title: str
    foreground_process: str


class MacroEngine:
    def __init__(self, config: Config) -> None:
        self.lock = threading.RLock()
        self.config = normalize_config(config)
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
        self.target_active = False
        self.foreground_title = ""
        self.foreground_process = ""

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, name="macro-engine", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.5)
        with self.lock:
            self.active_macros.clear()
        self.release_all_inputs()

    def update_config(self, config: Config) -> None:
        config = normalize_config(config)
        validate_config(config)
        with self.lock:
            self.config = config
            self.active_macros.clear()
            self.last_trigger_down = {}
            self.next_press_at = {}
            self.sequence_index = {}
        self.release_all_inputs()

    def snapshot(self) -> Snapshot:
        with self.lock:
            return Snapshot(
                target_active=self.target_active,
                macro_states={macro.id: macro.id in self.active_macros for macro in self.config.macros or []},
                config=clone_config(self.config),
                foreground_title=self.foreground_title,
                foreground_process=self.foreground_process,
            )

    def _run(self) -> None:
        while self.running:
            with self.lock:
                config = clone_config(self.config)

            hwnd = user32.GetForegroundWindow()
            title = get_window_title(hwnd) if hwnd else ""
            process = get_process_name(hwnd) if hwnd else ""
            target_active = foreground_matches_values(config, title, process)

            with self.lock:
                self.target_active = target_active
                self.foreground_title = title
                self.foreground_process = process

                if not target_active:
                    self.active_macros.clear()

                for profile in config.toggle_profiles or []:
                    virtual_key = TRIGGER_KEYS.get(profile.trigger)
                    down = is_key_down(virtual_key) if target_active and virtual_key is not None else False
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
                    down = is_key_down(virtual_key)
                    trigger_key = f"macro:{macro.id}"
                    if target_active and down and not self.last_trigger_down.get(trigger_key, False):
                        self._toggle_macro(macro)
                    self.last_trigger_down[trigger_key] = down

                active_cycle_macros = [
                    macro for macro in (config.macros or [])
                    if target_active and macro.enabled and macro.action == ACTION_PRESS_CYCLE and macro.id in self.active_macros
                ]

            if not target_active:
                self.release_all_inputs()

            now = time.monotonic()
            for macro in active_cycle_macros:
                if now >= self.next_press_at.get(macro.id, 0.0):
                    sequence = [item for item in macro.sequence if item != "none"]
                    if sequence:
                        index = self.sequence_index.get(macro.id, 0) % len(sequence)
                        press_sequence_item(sequence[index])
                        self.sequence_index[macro.id] = index + 1
                        self.next_press_at[macro.id] = now + (max(macro.interval_ms, MIN_MACRO_INTERVAL_MS) / 1000)

            time.sleep(max(config.poll_interval_ms, 50) / 1000)

        self.release_all_inputs()

    def _toggle_macro(self, macro: MacroConfig) -> None:
        if macro.id in self.active_macros:
            self._deactivate_macro(macro)
            return
        self._activate_macro(macro)

    def _activate_macro(self, macro: MacroConfig) -> None:
        if macro.id in self.active_macros:
            return
        self.active_macros.add(macro.id)
        if macro.action == ACTION_HOLD:
            self.press_hold_item(first_hold_item(macro))
        elif macro.action == ACTION_PRESS_CYCLE:
            self.next_press_at[macro.id] = 0.0
            self.sequence_index[macro.id] = 0

    def _deactivate_macro(self, macro: MacroConfig) -> None:
        if macro.id in self.active_macros:
            self.active_macros.remove(macro.id)
            if macro.action == ACTION_HOLD:
                self.release_hold_item(first_hold_item(macro))
            self.next_press_at.pop(macro.id, None)
            self.sequence_index.pop(macro.id, None)

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
            send_key_input(virtual_key, KEYEVENTF_KEYUP)
            self.held_keys.remove(virtual_key)

    def release_all_inputs(self) -> None:
        self.release_right()
        self.release_left()
        self.release_middle()
        self.release_all_keys()

class OverlayWindow:
    def __init__(self, root: tk.Tk, engine: MacroEngine) -> None:
        self.root = root
        self.engine = engine
        self.width = 252
        self.height = 56
        self.max_rows = 6
        self.window = tk.Toplevel(root)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg="#111111")
        self.window.attributes("-alpha", 0.62)

        self.canvas = tk.Canvas(
            self.window,
            width=self.width,
            height=self.height,
            bg="#111111",
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

    def refresh(self) -> None:
        snapshot = self.engine.snapshot()
        if not snapshot.config.overlay_enabled or not snapshot.target_active:
            self.window.withdraw()
            return

        visible_macros, total_count = self._visible_macros(snapshot)
        if not visible_macros and total_count == 0:
            self.window.withdraw()
            return

        self.height = self._height_for_rows(len(visible_macros))
        self._draw(snapshot, visible_macros, total_count)
        self.window.attributes("-alpha", clamp(snapshot.config.overlay_opacity, 0.2, 1.0))

        hwnd = user32.GetForegroundWindow()
        rect = wintypes.RECT()
        if hwnd and user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            x = rect.left + snapshot.config.overlay_x
            y = rect.top + snapshot.config.overlay_y
            x, y = self._avoid_cursor(x, y, rect)
        else:
            x = snapshot.config.overlay_x
            y = snapshot.config.overlay_y
        self.window.geometry(f"{self.width}x{self.height}+{x}+{y}")
        self.window.deiconify()
        self.window.lift()
        self.window.attributes("-topmost", True)

    def _visible_macros(self, snapshot: Snapshot) -> tuple[list[MacroConfig], int]:
        enabled_macros = [macro for macro in (snapshot.config.macros or []) if macro.enabled and macro.action != ACTION_NONE]
        return enabled_macros[:self.max_rows], len(enabled_macros)

    def _draw(self, snapshot: Snapshot, visible_macros: list[MacroConfig], total_count: int) -> None:
        self.canvas.delete("all")
        self.canvas.configure(width=self.width, height=self.height)
        self.canvas.create_rectangle(0, 0, self.width, self.height, fill="#111111", outline="#3a3a3a")
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

    def _avoid_cursor(self, x: int, y: int, window_rect: wintypes.RECT) -> tuple[int, int]:
        point = wintypes.POINT()
        if not user32.GetCursorPos(ctypes.byref(point)):
            return x, y
        in_overlay = x <= point.x <= x + self.width and y <= point.y <= y + self.height
        if not in_overlay:
            return x, y

        moved_y = y + self.height + 12
        if moved_y + self.height > window_rect.bottom:
            moved_y = max(window_rect.top, y - self.height - 12)
        return x, moved_y

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

class ConfigWindow:
    def __init__(self, root: tk.Tk, engine: MacroEngine, command_queue: queue.Queue[str], config_path: Path) -> None:
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
        self.poll_interval_var = tk.IntVar()
        self.overlay_enabled_var = tk.BooleanVar()
        self.overlay_x_var = tk.IntVar()
        self.overlay_y_var = tk.IntVar()
        self.overlay_opacity_var = tk.DoubleVar()
        self.overlay_opacity_text_var = tk.StringVar()
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
            "默认只在暗黑4窗口前台时生效。窗口匹配、浮层位置和轮询间隔已收进“高级设置”，主界面只保留常用宏配置。",
        ).grid(row=0, column=0, sticky="w", **pad)
        ttk.Checkbutton(summary, text="显示游戏内浮层", variable=self.overlay_enabled_var).grid(row=0, column=1, sticky="e", padx=(12, 5), pady=4)

        macros = ttk.LabelFrame(main, text="宏配置")
        macros.pack(fill="x", pady=(0, 8))
        self._help_label(macros, "每个按键格右侧都有“录”和“选”。推荐点“录”后按一次目标键；常用键可以点“选”。支持自由添加或删除宏。录入时按 Esc 取消。").pack(anchor="w", padx=5, pady=(4, 6))
        self.macro_rows_container = ttk.Frame(macros)
        self.macro_rows_container.pack(fill="x", padx=5, pady=(0, 6))
        self._render_macro_rows()

        all_toggle = ttk.LabelFrame(main, text="一键启动")
        all_toggle.pack(fill="x", pady=(0, 8))
        self._help_label(
            all_toggle,
            "可以添加多个一键启动配置。每个配置单独设置快捷键，并勾选它要控制的宏；按一次全部打开，再按一次全部关闭。",
        ).pack(anchor="w", padx=5, pady=(4, 6))
        self.toggle_profiles_container = ttk.Frame(all_toggle)
        self.toggle_profiles_container.pack(fill="x", padx=5, pady=(0, 6))
        self._render_toggle_profile_rows()

        support = ttk.LabelFrame(main, text="支持与反馈")
        support.pack(fill="x")
        support.columnconfigure(0, weight=1)
        self._help_label(support, f"如果这个工具对你有帮助，可以扫码打赏支持。遇到问题或有建议，欢迎加入 QQ 交流群：{SUPPORT_QQ_GROUP}。").grid(row=0, column=0, sticky="nw", **pad)
        donate_label = self._donate_label(support)
        if donate_label is not None:
            donate_label.grid(row=0, column=1, sticky="e", padx=8, pady=8)

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
        }

    def _render_macro_rows(self) -> None:
        if self.macro_rows_container is None:
            return
        for child in self.macro_rows_container.winfo_children():
            child.destroy()

        pad = {"padx": 5, "pady": 4}
        headers = ["启用", "名称", "开关键", "动作", "槽位1", "槽位2", "槽位3", "槽位4", "间隔(ms)", "操作"]
        for col, header in enumerate(headers):
            ttk.Label(self.macro_rows_container, text=header).grid(row=0, column=col, sticky="w", **pad)

        action_values = list(ACTION_LABELS.values())
        for index, vars_for_row in enumerate(self.macro_vars):
            row = index + 1
            ttk.Checkbutton(self.macro_rows_container, variable=vars_for_row["enabled"]).grid(row=row, column=0, sticky="w", **pad)
            ttk.Entry(self.macro_rows_container, textvariable=vars_for_row["name"], width=11).grid(row=row, column=1, sticky="w", **pad)
            self._key_picker(self.macro_rows_container, row, 2, vars_for_row["trigger"], "trigger", 8)
            ttk.Combobox(self.macro_rows_container, textvariable=vars_for_row["action"], values=action_values, state="readonly", width=10).grid(row=row, column=3, sticky="w", **pad)
            for offset, slot_name in enumerate(["slot1", "slot2", "slot3", "slot4"]):
                self._key_picker(self.macro_rows_container, row, 4 + offset, vars_for_row[slot_name], "press", 6)
            ttk.Spinbox(self.macro_rows_container, from_=MIN_MACRO_INTERVAL_MS, to=5000, increment=5, textvariable=vars_for_row["interval"], width=8).grid(row=row, column=8, sticky="w", **pad)
            ttk.Button(self.macro_rows_container, text="删除", width=6, command=lambda row_index=index: self.remove_macro_row(row_index)).grid(row=row, column=9, sticky="w", **pad)

        footer_row = len(self.macro_vars) + 1
        ttk.Button(self.macro_rows_container, text="添加宏", command=self.add_macro_row).grid(row=footer_row, column=0, sticky="w", padx=5, pady=(6, 4))
        if not self.macro_vars:
            ttk.Label(self.macro_rows_container, text="当前还没有宏，点击“添加宏”开始配置。", foreground="#666666").grid(row=footer_row, column=1, columnspan=8, sticky="w", padx=5, pady=(6, 4))
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

    def _new_toggle_profile_vars(self, profile: ToggleProfile) -> dict[str, object]:
        return {
            "id": profile.id,
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

        if not self.toggle_profile_vars:
            ttk.Label(
                self.toggle_profiles_container,
                text="当前还没有一键启动配置，点击“添加一键启动”创建。",
                foreground="#666666",
            ).pack(anchor="w", pady=(0, 6))

        for index, profile_vars in enumerate(self.toggle_profile_vars):
            frame = ttk.LabelFrame(self.toggle_profiles_container, text=f"配置 {index + 1}")
            frame.pack(fill="x", pady=(0, 6))
            pad = {"padx": 5, "pady": 4}
            ttk.Label(frame, text="快捷键").grid(row=0, column=0, sticky="w", **pad)
            self._key_picker(frame, 0, 1, profile_vars["trigger"], "optional_trigger", 8)
            ttk.Button(frame, text="删除", width=6, command=lambda row_index=index: self.remove_toggle_profile_row(row_index)).grid(row=0, column=2, sticky="e", **pad)
            ttk.Label(frame, text="包含宏").grid(row=1, column=0, sticky="nw", **pad)
            checks = ttk.Frame(frame)
            checks.grid(row=1, column=1, columnspan=2, sticky="w", **pad)
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
                    ).grid(row=macro_index // 4, column=macro_index % 4, sticky="w", padx=(0, 10), pady=(0, 4))

        ttk.Button(self.toggle_profiles_container, text="添加一键启动", command=self.add_toggle_profile_row).pack(anchor="w")

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

    def _key_picker(self, parent: tk.Widget, row: int, column: int, value_var: tk.StringVar, kind: str, width: int) -> None:
        pad = {"padx": 5, "pady": 4}
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=column, sticky="w", **pad)
        ttk.Entry(frame, textvariable=value_var, width=width, state="readonly").pack(side="left")
        ttk.Button(frame, text="录", width=3, command=lambda: self.record_key(value_var, kind)).pack(side="left", padx=(3, 0))
        ttk.Button(frame, text="选", width=3, command=lambda: self.show_key_menu(frame, value_var, kind)).pack(side="left", padx=(3, 0))

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
            if self.record_target_kind == "trigger" and key_id == "left":
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

    def _donate_label(self, parent: tk.Widget) -> ttk.Label | None:
        if Image is None or ImageTk is None or not DONATE_IMAGE_PATH.exists():
            return None
        image = Image.open(DONATE_IMAGE_PATH)
        image.thumbnail((150, 150))
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
        self.poll_interval_var.set(config.poll_interval_ms)
        self.overlay_enabled_var.set(config.overlay_enabled)
        self.overlay_x_var.set(config.overlay_x)
        self.overlay_y_var.set(config.overlay_y)
        self.overlay_opacity_var.set(config.overlay_opacity)
        self._update_opacity_text()
        self._fit_to_content()

    def _update_opacity_text(self) -> None:
        self.overlay_opacity_text_var.set(f"{int(float(self.overlay_opacity_var.get()) * 100)}%")

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

        overlay = ttk.LabelFrame(main, text="浮层与轮询")
        overlay.pack(fill="x", pady=(0, 8))
        overlay.columnconfigure(1, weight=1)
        self._help_label(overlay, "这些选项会和主界面的宏配置一起，在“保存并应用”后生效。一般不需要频繁调整。").grid(row=0, column=0, columnspan=2, sticky="w", **pad)
        ttk.Checkbutton(overlay, text="显示游戏内浮层", variable=self.overlay_enabled_var).grid(row=1, column=0, columnspan=2, sticky="w", padx=8, pady=(6, 6))
        ttk.Label(overlay, text="位置 X/Y").grid(row=2, column=0, sticky="w", **pad)
        pos = ttk.Frame(overlay)
        pos.grid(row=2, column=1, sticky="w", **pad)
        ttk.Spinbox(pos, from_=0, to=3000, increment=5, textvariable=self.overlay_x_var, width=8).pack(side="left")
        ttk.Spinbox(pos, from_=0, to=3000, increment=5, textvariable=self.overlay_y_var, width=8).pack(side="left", padx=(8, 0))
        ttk.Label(overlay, text="透明度").grid(row=3, column=0, sticky="w", **pad)
        opacity_row = ttk.Frame(overlay)
        opacity_row.grid(row=3, column=1, sticky="ew", **pad)
        opacity_row.columnconfigure(0, weight=1)
        ttk.Scale(opacity_row, from_=0.2, to=1.0, variable=self.overlay_opacity_var, orient="horizontal").grid(row=0, column=0, sticky="ew")
        ttk.Label(opacity_row, textvariable=self.overlay_opacity_text_var, width=6).grid(row=0, column=1, padx=(8, 0))
        ttk.Label(overlay, text="轮询间隔").grid(row=4, column=0, sticky="w", **pad)
        ttk.Spinbox(overlay, from_=50, to=1000, increment=10, textvariable=self.poll_interval_var, width=10).grid(row=4, column=1, sticky="w", **pad)

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
                ))
            toggle_profiles: list[ToggleProfile] = []
            for profile_vars in self.toggle_profile_vars:
                selected_vars = profile_vars["selected_vars"]
                toggle_profiles.append(ToggleProfile(
                    trigger=optional_trigger_label_to_id(str(profile_vars["trigger"].get()).strip()),
                    macro_ids=[macro_id for macro_id, selected_var in selected_vars.items() if selected_var.get()],
                    id=str(profile_vars["id"]),
                ))
            config = Config(
                window_title_contains=self.title_var.get().strip(),
                process_name=self.process_var.get().strip(),
                macros=macros,
                toggle_profiles=toggle_profiles,
                poll_interval_ms=int(self.poll_interval_var.get()),
                overlay_enabled=bool(self.overlay_enabled_var.get()),
                overlay_x=int(self.overlay_x_var.get()),
                overlay_y=int(self.overlay_y_var.get()),
                overlay_opacity=float(self.overlay_opacity_var.get()),
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
        self.window.deiconify()
        self.window.lift()

    def hide(self) -> None:
        self.window.withdraw()

def action_label_to_id(label: str) -> str:
    for key, value in ACTION_LABELS.items():
        if value == label:
            return key
    return ACTION_NONE


def action_id_to_label(action_id: str) -> str:
    return ACTION_LABELS.get(action_id, ACTION_LABELS[ACTION_NONE])


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
        MacroConfig(True, "右键长按", "xbutton1", ACTION_HOLD, ["right", "none", "none", "none"], 100, make_stable_id("macro")),
        MacroConfig(True, "左键连点", "xbutton2", ACTION_PRESS_CYCLE, ["left", "none", "none", "none"], 100, make_stable_id("macro")),
        MacroConfig(True, "2/3连按", "f1", ACTION_PRESS_CYCLE, ["2", "3", "none", "none"], 100, make_stable_id("macro")),
        MacroConfig(True, "右键连点", "f2", ACTION_PRESS_CYCLE, ["right", "none", "none", "none"], 100, make_stable_id("macro")),
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
        trigger="none",
        macro_ids=[],
        id=make_stable_id("profile"),
    )


def default_toggle_profiles(macros: list[MacroConfig]) -> list[ToggleProfile]:
    return [
        ToggleProfile(
            trigger="f3",
            macro_ids=[macro.id for macro in macros],
            id=make_stable_id("profile"),
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


def first_hold_item(macro: MacroConfig) -> str:
    sequence = normalize_sequence(macro.sequence)
    return sequence[0] if sequence[0] != "none" else "right"


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
        poll_interval_ms=max(int(config.poll_interval_ms), 50),
        overlay_enabled=bool(config.overlay_enabled),
        overlay_x=int(config.overlay_x),
        overlay_y=int(config.overlay_y),
        overlay_opacity=float(config.overlay_opacity),
    )


def clone_config(config: Config) -> Config:
    normalized = normalize_config(config)
    return Config(
        window_title_contains=normalized.window_title_contains,
        process_name=normalized.process_name,
        macros=[
            MacroConfig(m.enabled, m.name, m.trigger, m.action, list(m.sequence), m.interval_ms, m.id)
            for m in (normalized.macros or [])
        ],
        toggle_profiles=[
            ToggleProfile(profile.trigger, list(profile.macro_ids), profile.id)
            for profile in (normalized.toggle_profiles or [])
        ],
        poll_interval_ms=normalized.poll_interval_ms,
        overlay_enabled=normalized.overlay_enabled,
        overlay_x=normalized.overlay_x,
        overlay_y=normalized.overlay_y,
        overlay_opacity=normalized.overlay_opacity,
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


def send_mouse_input(flags: int) -> None:
    extra = ctypes.c_ulong(0)
    mouse_input = MOUSEINPUT(0, 0, 0, flags, 0, ctypes.pointer(extra))
    input_struct = INPUT(INPUT_MOUSE, INPUT_UNION(mi=mouse_input))
    sent = user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(INPUT))
    if sent != 1:
        raise ctypes.WinError(ctypes.get_last_error())


def click_left() -> None:
    send_mouse_input(MOUSEEVENTF_LEFTDOWN)
    send_mouse_input(MOUSEEVENTF_LEFTUP)


def click_right() -> None:
    send_mouse_input(MOUSEEVENTF_RIGHTDOWN)
    send_mouse_input(MOUSEEVENTF_RIGHTUP)


def click_middle() -> None:
    send_mouse_input(MOUSEEVENTF_MIDDLEDOWN)
    send_mouse_input(MOUSEEVENTF_MIDDLEUP)


def send_key_input(virtual_key: int, flags: int) -> None:
    extra = ctypes.c_ulong(0)
    keyboard_input = KEYBDINPUT(virtual_key, 0, flags, 0, ctypes.pointer(extra))
    input_struct = INPUT(1, INPUT_UNION(ki=keyboard_input))
    sent = user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(INPUT))
    if sent != 1:
        raise ctypes.WinError(ctypes.get_last_error())


def tap_key(virtual_key: int) -> None:
    send_key_input(virtual_key, 0)
    send_key_input(virtual_key, KEYEVENTF_KEYUP)


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

    config = Config(
        window_title_contains=str(raw.get("window_title_contains", "")).strip(),
        process_name=str(raw.get("process_name", "")).strip(),
        macros=macros,
        toggle_profiles=toggle_profiles,
        poll_interval_ms=int(raw.get("poll_interval_ms", 100)),
        overlay_enabled=bool(raw.get("overlay_enabled", True)),
        overlay_x=int(raw.get("overlay_x", 20)),
        overlay_y=int(raw.get("overlay_y", 20)),
        overlay_opacity=float(raw.get("overlay_opacity", 0.62)),
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
        if macro.action == ACTION_HOLD and first_hold_item(macro) == "none":
            raise ValueError(f"{macro.name} 的自动按住槽位 1 不能为“无”。")
        if macro.action == ACTION_PRESS_CYCLE and not [item for item in macro.sequence if item != "none"]:
            raise ValueError(f"{macro.name} 的循环槽位不能全为“无”。")
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
        if profile.trigger == "none":
            continue
        if profile.trigger in seen:
            raise ValueError(f"一键启动配置 {index + 1} 不能和 {seen[profile.trigger]} 使用同一个按键：{trigger_id_to_label(profile.trigger)}。")
        seen[profile.trigger] = f"一键启动配置 {index + 1}"
    if config.poll_interval_ms < 50:
        raise ValueError("轮询间隔不能小于 50ms。")


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def create_tray_icon(command_queue: queue.Queue[str]) -> object | None:
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
    command_queue: queue.Queue[str] = queue.Queue()
    engine = MacroEngine(config)
    engine.start()

    root = tk.Tk()
    app = ConfigWindow(root, engine, command_queue, config_path)
    overlay = OverlayWindow(root, engine)

    tray_icon = create_tray_icon(command_queue)
    if tray_icon:
        threading.Thread(target=tray_icon.run, name="tray-icon", daemon=True).start()

    def quit_all() -> None:
        engine.stop()
        if tray_icon:
            tray_icon.stop()
        root.destroy()

    def tick() -> None:
        try:
            while True:
                command = command_queue.get_nowait()
                if command == "show":
                    app.show()
                elif command == "quit":
                    quit_all()
                    return
        except queue.Empty:
            pass

        overlay.refresh()
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







