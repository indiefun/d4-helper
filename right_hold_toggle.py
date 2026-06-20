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
from dataclasses import asdict, dataclass
from pathlib import Path
from tkinter import messagebox, ttk

try:
    import pystray
    from PIL import Image, ImageDraw
except Exception:
    pystray = None
    Image = None
    ImageDraw = None


APP_NAME = "暗黑4鼠标助手"


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


CONFIG_PATH = app_dir() / "config.json"

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080

VK_XBUTTON1 = 0x05
VK_XBUTTON2 = 0x06
VK_SPACE = 0x20
VK_F1 = 0x70
VK_F2 = 0x71
VK_F3 = 0x72
VK_F4 = 0x73
VK_F5 = 0x74
VK_F6 = 0x75

INPUT_MOUSE = 0
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
KEYEVENTF_KEYUP = 0x0002

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MAX_PATH = 260

ACTION_NONE = "none"
ACTION_HOLD = "hold"
ACTION_PRESS_CYCLE = "press_cycle"

TRIGGER_KEYS = {
    "xbutton1": VK_XBUTTON1,
    "xbutton2": VK_XBUTTON2,
    "f1": VK_F1,
    "f2": VK_F2,
    "f3": VK_F3,
    "f4": VK_F4,
    "f5": VK_F5,
    "f6": VK_F6,
}
TRIGGER_LABELS = {
    "xbutton1": "侧键 1",
    "xbutton2": "侧键 2",
    "f1": "F1",
    "f2": "F2",
    "f3": "F3",
    "f4": "F4",
    "f5": "F5",
    "f6": "F6",
}
ACTION_LABELS = {
    ACTION_NONE: "无",
    ACTION_HOLD: "自动按住",
    ACTION_PRESS_CYCLE: "循环连按",
}
PRESS_KEYS = {
    "none": None,
    "1": 0x31,
    "2": 0x32,
    "3": 0x33,
    "4": 0x34,
    "space": VK_SPACE,
    "left": "left",
    "right": "right",
}
PRESS_KEY_LABELS = {
    "none": "无",
    "1": "1",
    "2": "2",
    "3": "3",
    "4": "4",
    "space": "空格",
    "left": "左键",
    "right": "右键",
}
INTERVAL_PRESETS = {
    "standard": ("标准 - 100ms", 100),
    "stable": ("稳定 - 150ms", 150),
    "slow": ("慢速 - 250ms", 250),
    "very_slow": ("很慢 - 500ms", 500),
}


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
    interval_ms: int = 100


@dataclass
class Config:
    window_title_contains: str = "暗黑破坏神IV"
    process_name: str = "Diablo IV.exe"
    macros: list[MacroConfig] | None = None
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
        self.release_right()
        self.release_left()
        self.release_all_keys()

    def update_config(self, config: Config) -> None:
        config = normalize_config(config)
        validate_config(config)
        with self.lock:
            self.config = config
            self.active_macros.clear()
            self.last_trigger_down = {}
            self.next_press_at = {}
            self.sequence_index = {}
        self.release_right()
        self.release_left()
        self.release_all_keys()

    def snapshot(self) -> Snapshot:
        with self.lock:
            return Snapshot(
                target_active=self.target_active,
                macro_states={macro.name: macro.name in self.active_macros for macro in self.config.macros or []},
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

                for macro in config.macros or []:
                    if not macro.enabled or macro.action == ACTION_NONE:
                        continue
                    virtual_key = TRIGGER_KEYS.get(macro.trigger)
                    if virtual_key is None:
                        continue
                    down = is_key_down(virtual_key)
                    trigger_key = macro.name
                    if target_active and down and not self.last_trigger_down.get(trigger_key, False):
                        self._toggle_macro(macro)
                    self.last_trigger_down[trigger_key] = down

                active_cycle_macros = [
                    macro for macro in (config.macros or [])
                    if target_active and macro.enabled and macro.action == ACTION_PRESS_CYCLE and macro.name in self.active_macros
                ]

            if not target_active:
                self.release_right()
                self.release_left()
                self.release_all_keys()

            now = time.monotonic()
            for macro in active_cycle_macros:
                if now >= self.next_press_at.get(macro.name, 0.0):
                    sequence = [item for item in macro.sequence if item != "none"]
                    if sequence:
                        index = self.sequence_index.get(macro.name, 0) % len(sequence)
                        press_sequence_item(sequence[index])
                        self.sequence_index[macro.name] = index + 1
                        self.next_press_at[macro.name] = now + (max(macro.interval_ms, 100) / 1000)

            time.sleep(max(config.poll_interval_ms, 50) / 1000)

        self.release_right()
        self.release_left()

    def _toggle_macro(self, macro: MacroConfig) -> None:
        if macro.name in self.active_macros:
            self.active_macros.remove(macro.name)
            if macro.action == ACTION_HOLD:
                self.release_hold_item(first_hold_item(macro))
            return

        self.active_macros.add(macro.name)
        if macro.action == ACTION_HOLD:
            self.press_hold_item(first_hold_item(macro))
        elif macro.action == ACTION_PRESS_CYCLE:
            self.next_press_at[macro.name] = 0.0
            self.sequence_index[macro.name] = 0

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

    def press_hold_item(self, item: str) -> None:
        if item == "left":
            self.press_left()
        elif item == "right":
            self.press_right()
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
        elif item in PRESS_KEYS and isinstance(PRESS_KEYS[item], int):
            virtual_key = PRESS_KEYS[item]
            if virtual_key in self.held_keys:
                send_key_input(virtual_key, KEYEVENTF_KEYUP)
                self.held_keys.remove(virtual_key)

    def release_all_keys(self) -> None:
        for virtual_key in list(self.held_keys):
            send_key_input(virtual_key, KEYEVENTF_KEYUP)
            self.held_keys.remove(virtual_key)

class OverlayWindow:
    def __init__(self, root: tk.Tk, engine: MacroEngine) -> None:
        self.root = root
        self.engine = engine
        self.width = 320
        self.height = 70
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

        enabled_macros = [macro for macro in (snapshot.config.macros or []) if macro.enabled and macro.action != ACTION_NONE]
        self.height = self._height_for_rows(len(enabled_macros[:4]))
        self._draw(snapshot)
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

    def _draw(self, snapshot: Snapshot) -> None:
        self.canvas.delete("all")
        self.canvas.configure(width=self.width, height=self.height)
        self.canvas.create_rectangle(0, 0, self.width, self.height, fill="#111111", outline="#3a3a3a")
        self.canvas.create_text(
            12,
            12,
            text="暗黑4助手",
            fill="#d6d6d6",
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="nw",
        )
        self.canvas.create_text(18, 36, text="开关键", fill="#9ca3af", font=("Microsoft YaHei UI", 8), anchor="nw")
        self.canvas.create_text(92, 36, text="名称", fill="#9ca3af", font=("Microsoft YaHei UI", 8), anchor="nw")
        self.canvas.create_text(self.width - 58, 36, text="状态", fill="#9ca3af", font=("Microsoft YaHei UI", 8), anchor="nw")

        enabled_macros = [macro for macro in (snapshot.config.macros or []) if macro.enabled and macro.action != ACTION_NONE]
        for index, macro in enumerate(enabled_macros[:4]):
            self._draw_status_row(56 + index * 28, macro, snapshot.macro_states.get(macro.name, False))
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
        text_color = "#f4f4f5" if enabled else "#d1d5db"
        self.canvas.create_text(
            18,
            y,
            text=trigger_id_to_label(macro.trigger),
            fill=text_color,
            font=("Microsoft YaHei UI", 9, "bold"),
            anchor="nw",
        )
        self.canvas.create_text(
            92,
            y,
            text=macro.name,
            fill=text_color,
            font=("Microsoft YaHei UI", 9, "bold"),
            anchor="nw",
        )
        self._draw_switch(self.width - 58, y + 1, enabled)

    def _draw_switch(self, x: int, y: int, enabled: bool) -> None:
        bg = "#22c55e" if enabled else "#4b5563"
        knob = "#ffffff" if enabled else "#d1d5db"
        self.canvas.create_rectangle(x + 8, y, x + 30, y + 16, fill=bg, outline=bg)
        self.canvas.create_oval(x, y, x + 16, y + 16, fill=bg, outline=bg)
        self.canvas.create_oval(x + 22, y, x + 38, y + 16, fill=bg, outline=bg)
        knob_x = x + 22 if enabled else x + 2
        self.canvas.create_oval(knob_x, y + 2, knob_x + 12, y + 14, fill=knob, outline="")

    def _height_for_rows(self, row_count: int) -> int:
        return 58 + max(row_count, 1) * 28 + 10

class ConfigWindow:
    def __init__(self, root: tk.Tk, engine: MacroEngine, command_queue: queue.Queue[str], config_path: Path) -> None:
        self.root = root
        self.engine = engine
        self.command_queue = command_queue
        self.config_path = config_path
        self.window = root
        self.window.title(APP_NAME)
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
        self.macro_vars: list[dict[str, object]] = []

        self._build()
        self.load_from_engine()
        self.overlay_opacity_var.trace_add("write", lambda *_args: self._update_opacity_text())
        self._fit_to_content()

    def _help_label(self, parent: tk.Widget, text: str) -> ttk.Label:
        return ttk.Label(parent, text=text, foreground="#666666", wraplength=760, justify="left")

    def _fit_to_content(self) -> None:
        self.window.update_idletasks()
        width = self.window.winfo_reqwidth() + 18
        height = self.window.winfo_reqheight() + 10
        self.window.geometry(f"{width}x{height}")

    def _build(self) -> None:
        pad = {"padx": 5, "pady": 4}
        bottom = tk.Frame(self.window, bg="#f0f0f0", padx=10, pady=10, height=54)
        bottom.pack(fill="x", side="bottom")
        bottom.pack_propagate(False)
        tk.Label(bottom, textvariable=self.status_var, fg="#555555", bg="#f0f0f0", anchor="w").pack(side="left", fill="x", expand=True)
        tk.Button(bottom, text="隐藏到托盘", command=self.hide, width=12, height=1).pack(side="right", padx=(8, 0))
        tk.Button(bottom, text="恢复默认", command=self.defaults, width=12, height=1).pack(side="right", padx=(8, 0))
        tk.Button(bottom, text="保存并应用", command=self.save, width=12, height=1).pack(side="right", padx=(8, 0))

        main = ttk.Frame(self.window, padding=10)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)

        target = ttk.LabelFrame(main, text="暗黑4窗口")
        target.pack(fill="x", pady=(0, 8))
        target.columnconfigure(1, weight=1)
        self._help_label(target, "只在匹配到这个窗口处于前台时生效。标题和进程名至少填写一项；两项都填时需要同时匹配。").grid(row=0, column=0, columnspan=2, sticky="w", **pad)
        ttk.Label(target, text="标题包含").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(target, textvariable=self.title_var, width=42).grid(row=1, column=1, sticky="ew", **pad)
        ttk.Label(target, text="进程名").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(target, textvariable=self.process_var, width=42).grid(row=2, column=1, sticky="ew", **pad)
        ttk.Button(target, text="读取当前窗口", command=self.detect_foreground).grid(row=3, column=1, sticky="e", **pad)

        macros = ttk.LabelFrame(main, text="宏配置")
        macros.pack(fill="x", pady=(0, 8))
        self._help_label(macros, "每个宏都有自己的开关键和动作。循环连按会按槽位顺序循环，自动跳过“无”。间隔推荐从“标准 - 100ms”开始，越慢越稳定。").grid(row=0, column=0, columnspan=10, sticky="w", **pad)
        headers = ["启用", "名称", "开关键", "动作", "槽位1", "槽位2", "槽位3", "槽位4", "间隔档位"]
        for col, header in enumerate(headers):
            ttk.Label(macros, text=header).grid(row=1, column=col, sticky="w", **pad)

        trigger_values = list(TRIGGER_LABELS.values())
        action_values = list(ACTION_LABELS.values())
        press_values = list(PRESS_KEY_LABELS.values())
        interval_values = [label for label, _ms in INTERVAL_PRESETS.values()]
        for index in range(4):
            self._macro_row(macros, index + 2, index, trigger_values, action_values, press_values, interval_values)

        overlay = ttk.LabelFrame(main, text="浮层")
        overlay.pack(fill="x", pady=(0, 8))
        overlay.columnconfigure(1, weight=1)
        self._help_label(overlay, "浮层只在暗黑4窗口激活时显示，用来确认当前宏是否开启。最多显示前 4 个启用宏。").grid(row=0, column=0, columnspan=2, sticky="w", **pad)
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

    def _macro_row(self, parent: tk.Widget, row: int, index: int, trigger_values: list[str], action_values: list[str], press_values: list[str], interval_values: list[str]) -> None:
        pad = {"padx": 5, "pady": 4}
        vars_for_row = {
            "enabled": tk.BooleanVar(),
            "name": tk.StringVar(),
            "trigger": tk.StringVar(),
            "action": tk.StringVar(),
            "slot1": tk.StringVar(),
            "slot2": tk.StringVar(),
            "slot3": tk.StringVar(),
            "slot4": tk.StringVar(),
            "interval": tk.StringVar(),
        }
        self.macro_vars.append(vars_for_row)
        ttk.Checkbutton(parent, variable=vars_for_row["enabled"]).grid(row=row, column=0, sticky="w", **pad)
        ttk.Entry(parent, textvariable=vars_for_row["name"], width=11).grid(row=row, column=1, sticky="w", **pad)
        ttk.Combobox(parent, textvariable=vars_for_row["trigger"], values=trigger_values, state="readonly", width=8).grid(row=row, column=2, sticky="w", **pad)
        ttk.Combobox(parent, textvariable=vars_for_row["action"], values=action_values, state="readonly", width=10).grid(row=row, column=3, sticky="w", **pad)
        for offset, slot_name in enumerate(["slot1", "slot2", "slot3", "slot4"]):
            ttk.Combobox(parent, textvariable=vars_for_row[slot_name], values=press_values, state="readonly", width=6).grid(row=row, column=4 + offset, sticky="w", **pad)
        ttk.Combobox(parent, textvariable=vars_for_row["interval"], values=interval_values, state="readonly", width=13).grid(row=row, column=8, sticky="w", **pad)

    def load_from_engine(self) -> None:
        config = self.engine.snapshot().config
        self.title_var.set(config.window_title_contains)
        self.process_var.set(config.process_name)
        macros = normalize_macros(config.macros or [])
        for index, vars_for_row in enumerate(self.macro_vars):
            macro = macros[index]
            vars_for_row["enabled"].set(macro.enabled)
            vars_for_row["name"].set(macro.name)
            vars_for_row["trigger"].set(trigger_id_to_label(macro.trigger))
            vars_for_row["action"].set(action_id_to_label(macro.action))
            sequence = normalize_sequence(macro.sequence)
            for slot_index, slot_name in enumerate(["slot1", "slot2", "slot3", "slot4"]):
                vars_for_row[slot_name].set(press_key_id_to_label(sequence[slot_index]))
            vars_for_row["interval"].set(interval_ms_to_label(macro.interval_ms))
        self.poll_interval_var.set(config.poll_interval_ms)
        self.overlay_enabled_var.set(config.overlay_enabled)
        self.overlay_x_var.set(config.overlay_x)
        self.overlay_y_var.set(config.overlay_y)
        self.overlay_opacity_var.set(config.overlay_opacity)
        self._update_opacity_text()

    def _update_opacity_text(self) -> None:
        self.overlay_opacity_text_var.set(f"{int(float(self.overlay_opacity_var.get()) * 100)}%")

    def save(self) -> None:
        try:
            macros: list[MacroConfig] = []
            for vars_for_row in self.macro_vars:
                macros.append(MacroConfig(
                    enabled=bool(vars_for_row["enabled"].get()),
                    name=str(vars_for_row["name"].get()).strip(),
                    trigger=trigger_label_to_id(str(vars_for_row["trigger"].get())),
                    action=action_label_to_id(str(vars_for_row["action"].get())),
                    sequence=[press_key_label_to_id(str(vars_for_row[name].get())) for name in ["slot1", "slot2", "slot3", "slot4"]],
                    interval_ms=interval_label_to_ms(str(vars_for_row["interval"].get())),
                ))
            config = Config(
                window_title_contains=self.title_var.get().strip(),
                process_name=self.process_var.get().strip(),
                macros=macros,
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
            return
        self.title_var.set(get_window_title(hwnd))
        self.process_var.set(get_process_name(hwnd))

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


def trigger_label_to_id(label: str) -> str:
    for key, value in TRIGGER_LABELS.items():
        if value == label:
            return key
    return "xbutton1"


def trigger_id_to_label(trigger_id: str) -> str:
    return TRIGGER_LABELS.get(trigger_id, TRIGGER_LABELS["xbutton1"])


def press_key_label_to_id(label: str) -> str:
    for key, value in PRESS_KEY_LABELS.items():
        if value == label:
            return key
    return "none"


def press_key_id_to_label(key_id: str) -> str:
    return PRESS_KEY_LABELS.get(key_id, PRESS_KEY_LABELS["none"])


def interval_label_to_ms(label: str) -> int:
    for _key, (preset_label, ms) in INTERVAL_PRESETS.items():
        if preset_label == label:
            return ms
    return 100


def interval_ms_to_label(interval_ms: int) -> str:
    for _key, (label, ms) in INTERVAL_PRESETS.items():
        if ms == interval_ms:
            return label
    return INTERVAL_PRESETS["standard"][0]


def default_macros() -> list[MacroConfig]:
    return [
        MacroConfig(True, "右键长按", "xbutton1", ACTION_HOLD, ["right", "none", "none", "none"], 100),
        MacroConfig(True, "左键连点", "xbutton2", ACTION_PRESS_CYCLE, ["left", "none", "none", "none"], 100),
        MacroConfig(True, "2/3连按", "f1", ACTION_PRESS_CYCLE, ["2", "3", "none", "none"], 100),
        MacroConfig(False, "空宏", "f2", ACTION_NONE, ["none", "none", "none", "none"], 100),
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
                interval_ms=int(item.get("interval_ms", 100)),
            ))
        return normalize_macros(parsed)

    macros = default_macros()
    macros[0].enabled = bool(raw.get("right_hold_enabled", True))
    macros[0].trigger = str(raw.get("right_hold_trigger", "xbutton1"))
    macros[1].enabled = bool(raw.get("left_click_loop_enabled", True))
    macros[1].trigger = str(raw.get("left_click_loop_trigger", "xbutton2"))
    macros[1].interval_ms = int(raw.get("left_click_interval_ms", 100))
    macros[2].enabled = bool(raw.get("f1_combo_enabled", True))
    macros[2].trigger = str(raw.get("f1_combo_trigger", "f1"))
    macros[2].interval_ms = max(int(raw.get("f1_combo_interval_ms", 100)), 100)

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
            macros[3].interval_ms = int(raw.get("right_click_interval_ms", 100))
    return normalize_macros(macros)


def normalize_sequence(sequence: list[str] | None) -> list[str]:
    values = list(sequence or [])
    normalized = [(value if value in PRESS_KEYS else "none") for value in values[:4]]
    while len(normalized) < 4:
        normalized.append("none")
    return normalized


def first_hold_item(macro: MacroConfig) -> str:
    sequence = normalize_sequence(macro.sequence)
    return sequence[0] if sequence[0] != "none" else "right"


def normalize_macros(macros: list[MacroConfig] | None) -> list[MacroConfig]:
    source = list(macros or default_macros())
    normalized: list[MacroConfig] = []
    defaults = default_macros()
    for index in range(4):
        macro = source[index] if index < len(source) else defaults[index]
        normalized.append(MacroConfig(
            enabled=bool(macro.enabled),
            name=(macro.name or f"宏 {index + 1}").strip(),
            trigger=macro.trigger if macro.trigger in TRIGGER_KEYS else defaults[index].trigger,
            action=macro.action if macro.action in ACTION_LABELS else ACTION_NONE,
            sequence=normalize_sequence(macro.sequence),
            interval_ms=max(int(macro.interval_ms), 100),
        ))
    return normalized


def normalize_config(config: Config) -> Config:
    return Config(
        window_title_contains=config.window_title_contains,
        process_name=config.process_name,
        macros=normalize_macros(config.macros),
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
            MacroConfig(m.enabled, m.name, m.trigger, m.action, list(m.sequence), m.interval_ms)
            for m in (normalized.macros or [])
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

    config = Config(
        window_title_contains=str(raw.get("window_title_contains", "")).strip(),
        process_name=str(raw.get("process_name", "")).strip(),
        macros=macros,
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
    if not config.window_title_contains and not config.process_name:
        raise ValueError("请填写窗口标题或进程名，至少一项。")
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
    if config.poll_interval_ms < 50:
        raise ValueError("轮询间隔不能小于 50ms。")


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def create_tray_icon(command_queue: queue.Queue[str]) -> object | None:
    if pystray is None or Image is None or ImageDraw is None:
        return None

    image = Image.new("RGB", (64, 64), "#202124")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((10, 10, 54, 54), radius=10, fill="#2f7de1")
    draw.rectangle((28, 18, 36, 46), fill="#ffffff")

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
            pystray.MenuItem("打开配置", show_config),
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







