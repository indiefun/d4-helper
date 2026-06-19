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
ACTION_RIGHT_HOLD = "right_hold_toggle"
ACTION_LEFT_HOLD = "left_hold_toggle"
ACTION_LEFT_CLICK_LOOP = "left_click_loop"
ACTION_RIGHT_CLICK_LOOP = "right_click_loop"
ACTION_KEY_LOOP = "key_loop"

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
    ACTION_RIGHT_HOLD: "自动按住右键",
    ACTION_LEFT_HOLD: "自动按住左键",
    ACTION_LEFT_CLICK_LOOP: "左键自动连点",
    ACTION_RIGHT_CLICK_LOOP: "右键自动连点",
    ACTION_KEY_LOOP: "技能键自动循环",
}
SKILL_KEYS = {
    "1": 0x31,
    "2": 0x32,
    "3": 0x33,
    "4": 0x34,
    "Space": VK_SPACE,
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
class Config:
    window_title_contains: str = "暗黑破坏神IV"
    process_name: str = "Diablo IV.exe"
    right_hold_enabled: bool = True
    right_hold_trigger: str = "xbutton1"
    left_click_loop_enabled: bool = True
    left_click_loop_trigger: str = "xbutton2"
    left_click_interval_ms: int = 100
    right_click_loop_enabled: bool = False
    right_click_loop_trigger: str = "f3"
    right_click_interval_ms: int = 100
    skill_loop_enabled: bool = False
    skill_loop_key: str = "1"
    skill_loop_interval_ms: int = 500
    f1_combo_enabled: bool = True
    f1_combo_trigger: str = "f1"
    f1_combo_interval_ms: int = 80
    poll_interval_ms: int = 100
    overlay_enabled: bool = True
    overlay_x: int = 20
    overlay_y: int = 20
    overlay_opacity: float = 0.82


@dataclass(frozen=True)
class Snapshot:
    target_active: bool
    right_hold_enabled: bool
    left_hold_enabled: bool
    left_click_loop_enabled: bool
    right_click_loop_enabled: bool
    skill_loop_active: bool
    f1_combo_active: bool
    config: Config
    foreground_title: str
    foreground_process: str


class MacroEngine:
    def __init__(self, config: Config) -> None:
        self.lock = threading.RLock()
        self.config = config
        self.running = False
        self.thread: threading.Thread | None = None
        self.right_is_down = False
        self.left_is_down = False
        self.right_hold_enabled = False
        self.left_hold_enabled = False
        self.left_click_loop_enabled = False
        self.right_click_loop_enabled = False
        self.skill_loop_active = False
        self.f1_combo_active = False
        self.last_trigger_down: dict[str, bool] = {}
        self.next_left_click_at = 0.0
        self.next_right_click_at = 0.0
        self.next_skill_press_at = 0.0
        self.next_f1_combo_at = 0.0
        self.f1_combo_index = 0
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
            self.right_hold_enabled = False
            self.left_hold_enabled = False
            self.left_click_loop_enabled = False
            self.right_click_loop_enabled = False
            self.skill_loop_active = False
            self.f1_combo_active = False
        self.release_right()
        self.release_left()

    def update_config(self, config: Config) -> None:
        validate_config(config)
        with self.lock:
            self.config = config
            self.last_trigger_down = {}

    def snapshot(self) -> Snapshot:
        with self.lock:
            return Snapshot(
                target_active=self.target_active,
                right_hold_enabled=self.right_hold_enabled,
                left_hold_enabled=self.left_hold_enabled,
                left_click_loop_enabled=self.left_click_loop_enabled,
                right_click_loop_enabled=self.right_click_loop_enabled,
                skill_loop_active=self.skill_loop_active,
                f1_combo_active=self.f1_combo_active,
                config=Config(**asdict(self.config)),
                foreground_title=self.foreground_title,
                foreground_process=self.foreground_process,
            )

    def _run(self) -> None:
        while self.running:
            with self.lock:
                config = Config(**asdict(self.config))

            hwnd = user32.GetForegroundWindow()
            title = get_window_title(hwnd) if hwnd else ""
            process = get_process_name(hwnd) if hwnd else ""
            target_active = foreground_matches_values(config, title, process)

            with self.lock:
                self.target_active = target_active
                self.foreground_title = title
                self.foreground_process = process

                if not target_active:
                    self.right_hold_enabled = False
                    self.left_hold_enabled = False
                    self.left_click_loop_enabled = False
                    self.right_click_loop_enabled = False
                    self.skill_loop_active = False
                    self.f1_combo_active = False

                for trigger_id, action_name in get_active_triggers(config).items():
                    virtual_key = TRIGGER_KEYS[trigger_id]
                    down = is_key_down(virtual_key)
                    if target_active and down and not self.last_trigger_down.get(trigger_id, False):
                        self._toggle_action(action_name)
                    self.last_trigger_down[trigger_id] = down

                left_click_loop = target_active and config.left_click_loop_enabled and self.left_click_loop_enabled
                right_click_loop = target_active and config.right_click_loop_enabled and self.right_click_loop_enabled
                skill_loop = target_active and config.skill_loop_enabled and self.skill_loop_active
                f1_combo_loop = target_active and config.f1_combo_enabled and self.f1_combo_active
                left_interval = max(config.left_click_interval_ms, 10) / 1000
                right_interval = max(config.right_click_interval_ms, 10) / 1000
                skill_interval = max(config.skill_loop_interval_ms, 50) / 1000
                f1_combo_interval = max(config.f1_combo_interval_ms, 30) / 1000
                skill_key = SKILL_KEYS.get(config.skill_loop_key, SKILL_KEYS["1"])

            if not target_active:
                self.release_right()
                self.release_left()

            if left_click_loop:
                now = time.monotonic()
                if now >= self.next_left_click_at:
                    click_left()
                    self.next_left_click_at = now + left_interval

            if right_click_loop:
                now = time.monotonic()
                if now >= self.next_right_click_at:
                    click_right()
                    self.next_right_click_at = now + right_interval

            if skill_loop:
                now = time.monotonic()
                if now >= self.next_skill_press_at:
                    tap_key(skill_key)
                    self.next_skill_press_at = now + skill_interval

            if f1_combo_loop:
                now = time.monotonic()
                if now >= self.next_f1_combo_at:
                    tap_key(SKILL_KEYS["2"] if self.f1_combo_index % 2 == 0 else SKILL_KEYS["3"])
                    self.f1_combo_index += 1
                    self.next_f1_combo_at = now + f1_combo_interval

            time.sleep(max(config.poll_interval_ms, 10) / 1000)

        self.release_right()
        self.release_left()

    def _toggle_action(self, action_name: str) -> None:
        if action_name == ACTION_RIGHT_HOLD:
            self.right_hold_enabled = not self.right_hold_enabled
            if self.right_hold_enabled:
                self.press_right()
            else:
                self.release_right()
        elif action_name == ACTION_LEFT_HOLD:
            self.left_hold_enabled = not self.left_hold_enabled
            if self.left_hold_enabled:
                self.press_left()
            else:
                self.release_left()
        elif action_name == ACTION_LEFT_CLICK_LOOP:
            self.left_click_loop_enabled = not self.left_click_loop_enabled
            if self.left_click_loop_enabled:
                self.next_left_click_at = 0.0
        elif action_name == ACTION_RIGHT_CLICK_LOOP:
            self.right_click_loop_enabled = not self.right_click_loop_enabled
            if self.right_click_loop_enabled:
                self.next_right_click_at = 0.0
        elif action_name == ACTION_KEY_LOOP:
            self.skill_loop_active = not self.skill_loop_active
            if self.skill_loop_active:
                self.next_skill_press_at = 0.0
        elif action_name == "f1_combo":
            self.f1_combo_active = not self.f1_combo_active
            if self.f1_combo_active:
                self.next_f1_combo_at = 0.0
                self.f1_combo_index = 0

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


class OverlayWindow:
    def __init__(self, root: tk.Tk, engine: MacroEngine) -> None:
        self.root = root
        self.engine = engine
        self.width = 260
        self.height = 118
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

        self._draw(snapshot)
        self.window.attributes("-alpha", clamp(snapshot.config.overlay_opacity, 0.2, 1.0))

        hwnd = user32.GetForegroundWindow()
        rect = wintypes.RECT()
        if hwnd and user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            x = rect.left + snapshot.config.overlay_x
            y = rect.top + snapshot.config.overlay_y
        else:
            x = snapshot.config.overlay_x
            y = snapshot.config.overlay_y
        self.window.geometry(f"{self.width}x{self.height}+{x}+{y}")
        self.window.deiconify()
        self.window.lift()
        self.window.attributes("-topmost", True)

    def _draw(self, snapshot: Snapshot) -> None:
        self.canvas.delete("all")
        self.canvas.create_rectangle(0, 0, self.width, self.height, fill="#111111", outline="#3a3a3a")
        self.canvas.create_text(
            12,
            12,
            text="暗黑4鼠标助手",
            fill="#d6d6d6",
            font=("Segoe UI", 10, "bold"),
            anchor="nw",
        )
        self._draw_status_row(36, "右键长按", snapshot.right_hold_enabled)
        self._draw_status_row(62, "左键连点", snapshot.left_click_loop_enabled)
        self._draw_status_row(88, "F1 2/3连按", snapshot.f1_combo_active)
        self.canvas.update_idletasks()

    def _draw_status_row(self, y: int, label: str, enabled: bool) -> None:
        state = "开" if enabled else "关"
        dot_color = "#22c55e" if enabled else "#6b7280"
        text_color = "#f4f4f5" if enabled else "#d1d5db"
        self.canvas.create_oval(13, y + 4, 23, y + 14, fill=dot_color, outline="")
        self.canvas.create_text(
            34,
            y,
            text=label,
            fill=text_color,
            font=("Segoe UI", 10, "bold"),
            anchor="nw",
        )
        self.canvas.create_text(
            self.width - 44,
            y,
            text=state,
            fill=dot_color,
            font=("Segoe UI", 10, "bold"),
            anchor="nw",
        )

class ConfigWindow:
    def __init__(self, root: tk.Tk, engine: MacroEngine, command_queue: queue.Queue[str], config_path: Path) -> None:
        self.root = root
        self.engine = engine
        self.command_queue = command_queue
        self.config_path = config_path
        self.window = root
        self.window.title(APP_NAME)
        self.window.geometry("600x710")
        self.window.minsize(580, 660)
        self.window.resizable(True, True)
        self.window.protocol("WM_DELETE_WINDOW", self.hide)

        self.title_var = tk.StringVar()
        self.process_var = tk.StringVar()
        self.right_hold_enabled_var = tk.BooleanVar()
        self.right_hold_trigger_var = tk.StringVar()
        self.left_loop_enabled_var = tk.BooleanVar()
        self.left_loop_trigger_var = tk.StringVar()
        self.left_interval_var = tk.IntVar()
        self.right_loop_enabled_var = tk.BooleanVar()
        self.right_loop_trigger_var = tk.StringVar()
        self.right_interval_var = tk.IntVar()
        self.f1_combo_enabled_var = tk.BooleanVar()
        self.f1_combo_trigger_var = tk.StringVar()
        self.f1_combo_interval_var = tk.IntVar()
        self.poll_interval_var = tk.IntVar()
        self.overlay_enabled_var = tk.BooleanVar()
        self.overlay_x_var = tk.IntVar()
        self.overlay_y_var = tk.IntVar()
        self.overlay_opacity_var = tk.DoubleVar()
        self.overlay_opacity_text_var = tk.StringVar()
        self.status_var = tk.StringVar()

        self._build()
        self.load_from_engine()
        self.overlay_opacity_var.trace_add("write", lambda *_args: self._update_opacity_text())

    def _help_label(self, parent: tk.Widget, text: str) -> ttk.Label:
        return ttk.Label(parent, text=text, foreground="#666666", wraplength=520, justify="left")

    def _build(self) -> None:
        pad = {"padx": 10, "pady": 5}
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
        ttk.Entry(target, textvariable=self.title_var, width=40).grid(row=1, column=1, sticky="ew", **pad)
        ttk.Label(target, text="进程名").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(target, textvariable=self.process_var, width=40).grid(row=2, column=1, sticky="ew", **pad)
        ttk.Button(target, text="读取当前窗口", command=self.detect_foreground).grid(row=3, column=1, sticky="e", **pad)

        macros = ttk.LabelFrame(main, text="宏开关绑定")
        macros.pack(fill="x", pady=(0, 8))
        for col in range(5):
            macros.columnconfigure(col, weight=1 if col == 2 else 0)
        self._help_label(macros, "每个功能都可以单独选择开关键。按一次开关键开启，再按一次关闭；只在暗黑4窗口激活时生效。").grid(row=0, column=0, columnspan=5, sticky="w", **pad)
        ttk.Label(macros, text="启用").grid(row=1, column=0, sticky="w", **pad)
        ttk.Label(macros, text="功能").grid(row=1, column=1, sticky="w", **pad)
        ttk.Label(macros, text="开关键").grid(row=1, column=2, sticky="w", **pad)
        ttk.Label(macros, text="间隔(ms)").grid(row=1, column=3, sticky="w", **pad)

        trigger_values = list(TRIGGER_LABELS.values())
        self._macro_row(macros, 2, self.right_hold_enabled_var, "自动按住右键", self.right_hold_trigger_var, trigger_values, None)
        self._macro_row(macros, 3, self.left_loop_enabled_var, "左键自动连点", self.left_loop_trigger_var, trigger_values, self.left_interval_var)
        self._macro_row(macros, 4, self.right_loop_enabled_var, "右键自动连点", self.right_loop_trigger_var, trigger_values, self.right_interval_var)
        self._macro_row(macros, 5, self.f1_combo_enabled_var, "2/3快速连按", self.f1_combo_trigger_var, trigger_values, self.f1_combo_interval_var)

        overlay = ttk.LabelFrame(main, text="浮层")
        overlay.pack(fill="x", pady=(0, 8))
        overlay.columnconfigure(1, weight=1)
        self._help_label(overlay, "浮层只在暗黑4窗口激活时显示，用来确认当前功能是否开启。").grid(row=0, column=0, columnspan=2, sticky="w", **pad)
        ttk.Checkbutton(overlay, text="显示游戏内浮层", variable=self.overlay_enabled_var).grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=(8, 8))
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

    def _macro_row(self, parent: tk.Widget, row: int, enabled_var: tk.BooleanVar, label: str, trigger_var: tk.StringVar, trigger_values: list[str], interval_var: tk.IntVar | None) -> None:
        pad = {"padx": 10, "pady": 4}
        ttk.Checkbutton(parent, variable=enabled_var).grid(row=row, column=0, sticky="w", **pad)
        ttk.Label(parent, text=label).grid(row=row, column=1, sticky="w", **pad)
        ttk.Combobox(parent, textvariable=trigger_var, values=trigger_values, state="readonly", width=12).grid(row=row, column=2, sticky="w", **pad)
        if interval_var is None:
            ttk.Label(parent, text="-").grid(row=row, column=3, sticky="w", **pad)
        else:
            ttk.Spinbox(parent, from_=30, to=1000, increment=10, textvariable=interval_var, width=10).grid(row=row, column=3, sticky="w", **pad)

    def load_from_engine(self) -> None:
        config = self.engine.snapshot().config
        self.title_var.set(config.window_title_contains)
        self.process_var.set(config.process_name)
        self.right_hold_enabled_var.set(config.right_hold_enabled)
        self.right_hold_trigger_var.set(trigger_id_to_label(config.right_hold_trigger))
        self.left_loop_enabled_var.set(config.left_click_loop_enabled)
        self.left_loop_trigger_var.set(trigger_id_to_label(config.left_click_loop_trigger))
        self.left_interval_var.set(config.left_click_interval_ms)
        self.right_loop_enabled_var.set(config.right_click_loop_enabled)
        self.right_loop_trigger_var.set(trigger_id_to_label(config.right_click_loop_trigger))
        self.right_interval_var.set(config.right_click_interval_ms)
        self.f1_combo_enabled_var.set(config.f1_combo_enabled)
        self.f1_combo_trigger_var.set(trigger_id_to_label(config.f1_combo_trigger))
        self.f1_combo_interval_var.set(config.f1_combo_interval_ms)
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
            config = Config(
                window_title_contains=self.title_var.get().strip(),
                process_name=self.process_var.get().strip(),
                right_hold_enabled=bool(self.right_hold_enabled_var.get()),
                right_hold_trigger=trigger_label_to_id(self.right_hold_trigger_var.get()),
                left_click_loop_enabled=bool(self.left_loop_enabled_var.get()),
                left_click_loop_trigger=trigger_label_to_id(self.left_loop_trigger_var.get()),
                left_click_interval_ms=int(self.left_interval_var.get()),
                right_click_loop_enabled=bool(self.right_loop_enabled_var.get()),
                right_click_loop_trigger=trigger_label_to_id(self.right_loop_trigger_var.get()),
                right_click_interval_ms=int(self.right_interval_var.get()),
                skill_loop_enabled=False,
                skill_loop_key="1",
                skill_loop_interval_ms=500,
                f1_combo_enabled=bool(self.f1_combo_enabled_var.get()),
                f1_combo_trigger=trigger_label_to_id(self.f1_combo_trigger_var.get()),
                f1_combo_interval_ms=int(self.f1_combo_interval_var.get()),
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
        config = Config()
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

def label_to_action(label: str) -> str:
    for key, value in ACTION_LABELS.items():
        if value == label:
            return key
    return ACTION_NONE


def trigger_label_to_id(label: str) -> str:
    for key, value in TRIGGER_LABELS.items():
        if value == label:
            return key
    return "xbutton1"


def trigger_id_to_label(trigger_id: str) -> str:
    return TRIGGER_LABELS.get(trigger_id, TRIGGER_LABELS["xbutton1"])


def get_active_triggers(config: Config) -> dict[str, str]:
    triggers: dict[str, str] = {}
    if config.right_hold_enabled:
        triggers[config.right_hold_trigger] = ACTION_RIGHT_HOLD
    if config.left_click_loop_enabled:
        triggers[config.left_click_loop_trigger] = ACTION_LEFT_CLICK_LOOP
    if config.right_click_loop_enabled:
        triggers[config.right_click_loop_trigger] = ACTION_RIGHT_CLICK_LOOP
    if config.f1_combo_enabled:
        triggers[config.f1_combo_trigger] = "f1_combo"
    return triggers


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
        config = Config()
        save_config(path, config)
        return config

    raw = json.loads(path.read_text(encoding="utf-8"))
    right_hold_enabled = bool(raw.get("right_hold_enabled", True))
    right_hold_trigger = str(raw.get("right_hold_trigger", "xbutton1"))
    left_click_loop_enabled = bool(raw.get("left_click_loop_enabled", True))
    left_click_loop_trigger = str(raw.get("left_click_loop_trigger", "xbutton2"))
    right_click_loop_enabled = bool(raw.get("right_click_loop_enabled", False))
    right_click_loop_trigger = str(raw.get("right_click_loop_trigger", "f3"))

    # Migrate earlier "button chooses action" config to the new "macro chooses trigger" model.
    old_xbutton1_action = str(raw.get("xbutton1_action", ""))
    old_xbutton2_action = str(raw.get("xbutton2_action", ""))
    for trigger_id, action_name in [("xbutton1", old_xbutton1_action), ("xbutton2", old_xbutton2_action)]:
        if action_name == "right_hold":
            action_name = ACTION_RIGHT_HOLD
        if action_name == ACTION_RIGHT_HOLD and "right_hold_trigger" not in raw:
            right_hold_enabled = True
            right_hold_trigger = trigger_id
        elif action_name == ACTION_LEFT_CLICK_LOOP and "left_click_loop_trigger" not in raw:
            left_click_loop_enabled = True
            left_click_loop_trigger = trigger_id
        elif action_name == ACTION_RIGHT_CLICK_LOOP and "right_click_loop_trigger" not in raw:
            right_click_loop_enabled = True
            right_click_loop_trigger = trigger_id

    config = Config(
        window_title_contains=str(raw.get("window_title_contains", "")).strip(),
        process_name=str(raw.get("process_name", "")).strip(),
        right_hold_enabled=right_hold_enabled,
        right_hold_trigger=right_hold_trigger,
        left_click_loop_enabled=left_click_loop_enabled,
        left_click_loop_trigger=left_click_loop_trigger,
        left_click_interval_ms=int(raw.get("left_click_interval_ms", 100)),
        right_click_loop_enabled=right_click_loop_enabled,
        right_click_loop_trigger=right_click_loop_trigger,
        right_click_interval_ms=int(raw.get("right_click_interval_ms", 100)),
        skill_loop_enabled=bool(raw.get("skill_loop_enabled", False)),
        skill_loop_key=str(raw.get("skill_loop_key", "1")),
        skill_loop_interval_ms=int(raw.get("skill_loop_interval_ms", 500)),
        f1_combo_enabled=bool(raw.get("f1_combo_enabled", True)),
        f1_combo_trigger=str(raw.get("f1_combo_trigger", "f1")),
        f1_combo_interval_ms=int(raw.get("f1_combo_interval_ms", 80)),
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
    path.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_config(config: Config) -> None:
    if not config.window_title_contains and not config.process_name:
        raise ValueError("请填写窗口标题或进程名，至少一项。")
    active_triggers = []
    for enabled, trigger_id, label in [
        (config.right_hold_enabled, config.right_hold_trigger, "自动按住右键"),
        (config.left_click_loop_enabled, config.left_click_loop_trigger, "左键自动连点"),
        (config.right_click_loop_enabled, config.right_click_loop_trigger, "右键自动连点"),
        (config.f1_combo_enabled, config.f1_combo_trigger, "2/3快速连按"),
    ]:
        if trigger_id not in TRIGGER_KEYS:
            raise ValueError(f"{label} 的开关键无效。")
        if enabled:
            active_triggers.append((trigger_id, label))
    seen: dict[str, str] = {}
    for trigger_id, label in active_triggers:
        if trigger_id in seen:
            raise ValueError(f"{label} 和 {seen[trigger_id]} 使用了同一个开关键：{trigger_id_to_label(trigger_id)}。")
        seen[trigger_id] = label
    if config.left_click_interval_ms < 50:
        raise ValueError("左键间隔不能小于 50ms。")
    if config.right_click_interval_ms < 50:
        raise ValueError("右键间隔不能小于 50ms。")
    if config.skill_loop_key not in SKILL_KEYS:
        raise ValueError("技能循环按键只能选择 1、2、3、4 或 Space。")
    if config.skill_loop_interval_ms < 250:
        raise ValueError("技能循环间隔不能小于 250ms。")
    if config.f1_combo_interval_ms < 30:
        raise ValueError("F1 2/3连按间隔不能小于 30ms。")
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




