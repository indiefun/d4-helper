//go:build windows

package win

import (
	"context"
	"fmt"
	"runtime"
	"sync"
	"syscall"
	"time"
	"unsafe"

	"github.com/indiefun/d4-helper/go-desktop/internal/engine"
	"golang.org/x/sys/windows"
)

type View struct {
	Snapshot   engine.Snapshot
	Foreground Foreground
	Overlay    bool
	Opacity    float64
	Avoid      bool
	Distance   int
}
type Service struct {
	OnInput                func(engine.PhysicalEvent, uintptr)
	WantMovement           func() bool
	OnForeground           func(Foreground)
	OnShow, OnQuit, OnStop func()
	OnError                func(error)
	mu                     sync.Mutex
	view                   View
	hwnd                   uintptr
	overlay                uintptr
	done                   chan struct{}
	cancel                 context.CancelFunc
	lastForeground         uintptr
	metadataAt             time.Time
	overlayRect            Rect
	lastAvoid              time.Time
	lastBounds             Rect
	trayOK                 bool
}
type notifyIcon struct {
	Size                uint32
	Window              uintptr
	ID, Flags, Callback uint32
	Icon                uintptr
	Tip                 [128]uint16
	State, StateMask    uint32
	Info                [256]uint16
	Timeout             uint32
	InfoTitle           [64]uint16
	InfoFlags           uint32
	GUID                [16]byte
	BalloonIcon         uintptr
}

func (s *Service) Update(v View) { s.mu.Lock(); s.view = v; s.mu.Unlock() }
func (s *Service) HasTray() bool { s.mu.Lock(); defer s.mu.Unlock(); return s.trayOK }
func (s *Service) Start(parent context.Context) error {
	ctx, cancel := context.WithCancel(parent)
	s.cancel = cancel
	s.done = make(chan struct{})
	ready := make(chan error, 1)
	go s.run(ctx, ready)
	return <-ready
}
func (s *Service) Close() {
	if s.cancel != nil {
		s.cancel()
		s.mu.Lock()
		hwnd := s.hwnd
		s.mu.Unlock()
		if hwnd != 0 {
			postMessage.Call(hwnd, 0x10, 0, 0)
		}
		<-s.done
	}
}

func (s *Service) run(ctx context.Context, ready chan<- error) {
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	defer close(s.done)
	instance, _, _ := kernel.NewProc("GetModuleHandleW").Call(0)
	name, _ := windows.UTF16PtrFromString("D4HelperGoNativeService")
	callback := syscall.NewCallback(func(hwnd uintptr, msg uint32, wp, lp uintptr) uintptr {
		switch msg {
		case 0x10:
			proc("DestroyWindow").Call(hwnd)
			return 0
		case 2:
			proc("PostQuitMessage").Call(0)
			return 0
		case 0x113:
			s.refreshForeground(false)
			s.refreshOverlay()
			return 0
		case 0x8001:
			if lp == 0x203 || lp == 0x202 {
				if s.OnShow != nil {
					go s.OnShow()
				}
			}
			if lp == 0x205 {
				s.popup(hwnd)
			}
			return 0
		}
		r, _, _ := proc("DefWindowProcW").Call(hwnd, uintptr(msg), wp, lp)
		return r
	})
	wc := windowClass{Size: uint32(unsafe.Sizeof(windowClass{})), Callback: callback, Instance: instance, Name: name}
	atom, _, err := proc("RegisterClassExW").Call(uintptr(unsafe.Pointer(&wc)))
	if atom == 0 {
		ready <- fmt.Errorf("注册原生服务窗口失败: %w", err)
		return
	}
	defer proc("UnregisterClassW").Call(uintptr(unsafe.Pointer(name)), instance)
	hwnd, _, err := proc("CreateWindowExW").Call(0, uintptr(unsafe.Pointer(name)), uintptr(unsafe.Pointer(name)), 0, 0, 0, 0, 0, 0, 0, instance, 0)
	if hwnd == 0 {
		ready <- fmt.Errorf("创建原生服务窗口失败: %w", err)
		return
	}
	s.mu.Lock()
	s.hwnd = hwnd
	s.mu.Unlock()
	defer func() { s.mu.Lock(); s.hwnd = 0; s.trayOK = false; s.mu.Unlock() }()
	next := proc("CallNextHookEx")
	keyboardCB := syscall.NewCallback(func(code int32, wp uintptr, lp *keyboardHook) uintptr {
		if code >= 0 {
			if e, ok := decodeKeyboard(wp, lp); ok && s.OnInput != nil {
				s.OnInput(e, currentHWND())
			}
		}
		r, _, _ := next.Call(0, uintptr(code), wp, uintptr(unsafe.Pointer(lp)))
		return r
	})
	mouseCB := syscall.NewCallback(func(code int32, wp uintptr, lp *mouseHook) uintptr {
		if code >= 0 {
			if e, ok := decodeMouse(wp, lp); ok && s.OnInput != nil {
				if e.Kind == "move" {
					recording := false
					if s.WantMovement != nil {
						recording = s.WantMovement()
					}
					if recording {
						s.OnInput(e, currentHWND())
					}
				} else {
					s.OnInput(e, currentHWND())
				}
			}
		}
		r, _, _ := next.Call(0, uintptr(code), wp, uintptr(unsafe.Pointer(lp)))
		return r
	})
	keyboard, _, err := proc("SetWindowsHookExW").Call(13, keyboardCB, instance, 0)
	if keyboard == 0 {
		proc("DestroyWindow").Call(hwnd)
		ready <- fmt.Errorf("安装键盘事件钩子失败: %w", err)
		return
	}
	defer proc("UnhookWindowsHookEx").Call(keyboard)
	mouse, _, err := proc("SetWindowsHookExW").Call(14, mouseCB, instance, 0)
	if mouse == 0 {
		proc("DestroyWindow").Call(hwnd)
		ready <- fmt.Errorf("安装鼠标事件钩子失败: %w", err)
		return
	}
	defer proc("UnhookWindowsHookEx").Call(mouse)
	foregroundCB := syscall.NewCallback(func(hook uintptr, event uint32, window uintptr, object, child int32, thread, timestamp uint32) uintptr {
		s.refreshForeground(true)
		return 0
	})
	foregroundHook, _, _ := proc("SetWinEventHook").Call(3, 3, 0, foregroundCB, 0, 0, 0)
	if foregroundHook != 0 {
		defer proc("UnhookWinEvent").Call(foregroundHook)
	}
	s.createOverlay(instance)
	defer func() {
		if s.overlay != 0 {
			proc("DestroyWindow").Call(s.overlay)
		}
		overlayName, _ := windows.UTF16PtrFromString("D4HelperGoStatusOverlay")
		proc("UnregisterClassW").Call(uintptr(unsafe.Pointer(overlayName)), instance)
	}()
	icon, _, _ := proc("LoadIconW").Call(instance, 1)
	if icon == 0 {
		icon, _, _ = proc("LoadIconW").Call(0, 32512)
	}
	tray := notifyIcon{Size: uint32(unsafe.Sizeof(notifyIcon{})), Window: hwnd, ID: 1, Flags: 1 | 2 | 4, Callback: 0x8001, Icon: icon}
	copy(tray.Tip[:], windows.StringToUTF16("D4Helper · 双击打开 / 右键菜单"))
	trayResult, _, _ := shell.NewProc("Shell_NotifyIconW").Call(0, uintptr(unsafe.Pointer(&tray)))
	s.mu.Lock()
	s.trayOK = trayResult != 0
	s.mu.Unlock()
	if trayResult != 0 {
		defer shell.NewProc("Shell_NotifyIconW").Call(2, uintptr(unsafe.Pointer(&tray)))
	}
	proc("SetTimer").Call(hwnd, 1, 100, 0)
	defer proc("KillTimer").Call(hwnd, 1)
	s.refreshForeground(true)
	ready <- nil
	var m message
	for ctx.Err() == nil {
		r, _, _ := proc("GetMessageW").Call(uintptr(unsafe.Pointer(&m)), 0, 0, 0)
		if r == 0 || int32(r) == -1 {
			break
		}
		proc("TranslateMessage").Call(uintptr(unsafe.Pointer(&m)))
		proc("DispatchMessageW").Call(uintptr(unsafe.Pointer(&m)))
	}
}

func (s *Service) refreshForeground(force bool) {
	hwnd := currentHWND()
	now := time.Now()
	if !force && hwnd == s.lastForeground && now.Sub(s.metadataAt) < time.Second {
		return
	}
	s.lastForeground = hwnd
	s.metadataAt = now
	if s.OnForeground != nil {
		s.OnForeground(Describe(hwnd))
	}
}
func (s *Service) popup(hwnd uintptr) {
	menu, _, _ := proc("CreatePopupMenu").Call()
	if menu == 0 {
		return
	}
	defer proc("DestroyMenu").Call(menu)
	for _, item := range []struct {
		id    uintptr
		label string
	}{{1, "打开配置"}, {2, "停止全部宏"}, {3, "退出"}} {
		text, _ := windows.UTF16PtrFromString(item.label)
		proc("AppendMenuW").Call(menu, 0, item.id, uintptr(unsafe.Pointer(text)))
	}
	p := Cursor()
	proc("SetForegroundWindow").Call(hwnd)
	choice, _, _ := proc("TrackPopupMenu").Call(menu, 0x100|2, uintptr(p.X), uintptr(p.Y), 0, hwnd, 0)
	postMessage.Call(hwnd, 0, 0, 0)
	switch choice {
	case 1:
		if s.OnShow != nil {
			go s.OnShow()
		}
	case 2:
		if s.OnStop != nil {
			go s.OnStop()
		}
	case 3:
		if s.OnQuit != nil {
			go s.OnQuit()
		}
	}
}

type paintStruct struct {
	DC              uintptr
	Erase           int32
	Rect            Rect
	Restore, Update int32
	Reserved        [32]byte
}

func (s *Service) createOverlay(instance uintptr) {
	name, _ := windows.UTF16PtrFromString("D4HelperGoStatusOverlay")
	callback := syscall.NewCallback(func(hwnd uintptr, msg uint32, wp, lp uintptr) uintptr {
		switch msg {
		case 0x84:
			return ^uintptr(0) // HTTRANSPARENT
		case 0x21:
			return 3 // MA_NOACTIVATE
		case 0x0f:
			s.paint(hwnd)
			return 0
		case 0x14:
			return 1
		}
		r, _, _ := proc("DefWindowProcW").Call(hwnd, uintptr(msg), wp, lp)
		return r
	})
	wc := windowClass{Size: uint32(unsafe.Sizeof(windowClass{})), Callback: callback, Instance: instance, Name: name}
	atom, _, _ := proc("RegisterClassExW").Call(uintptr(unsafe.Pointer(&wc)))
	if atom == 0 {
		return
	}
	hwnd, _, _ := proc("CreateWindowExW").Call(0x80000|0x20|0x80|0x8000000, uintptr(unsafe.Pointer(name)), uintptr(unsafe.Pointer(name)), 0x80000000, 0, 0, 280, 80, 0, 0, instance, 0)
	s.overlay = hwnd
}
func (s *Service) refreshOverlay() {
	if s.overlay == 0 {
		return
	}
	s.mu.Lock()
	v := s.view
	s.mu.Unlock()
	if !v.Overlay || !v.Snapshot.TargetActive || (!v.Snapshot.Armed && v.Snapshot.Fault == "") {
		proc("ShowWindow").Call(s.overlay, 0)
		return
	}
	rows := min(len(v.Snapshot.Macros), 8)
	height := int32(42 + rows*25)
	if v.Snapshot.Recording != "idle" || v.Snapshot.Fault != "" {
		height = 88
	}
	screen := Screen()
	bounds := v.Foreground.Rect
	if bounds.Right <= bounds.Left || bounds.Bottom <= bounds.Top {
		bounds = screen
	}
	bounds.Left = max(bounds.Left, screen.Left)
	bounds.Top = max(bounds.Top, screen.Top)
	bounds.Right = min(bounds.Right, screen.Right)
	bounds.Bottom = min(bounds.Bottom, screen.Bottom)
	const width int32 = 280
	clamp := func(x, y int32) (int32, int32) {
		return max(screen.Left, min(x, screen.Right-width)), max(screen.Top, min(y, screen.Bottom-height))
	}
	x, y := clamp(bounds.Left+20, bounds.Top+20)
	if s.lastBounds == bounds && s.overlayRect.Right-s.overlayRect.Left == width && s.overlayRect.Bottom-s.overlayRect.Top == height && v.Avoid {
		x, y = clamp(s.overlayRect.Left, s.overlayRect.Top)
	}
	p := Cursor()
	distance := func(x, y int32) int64 {
		dx := max(x-p.X, max(0, p.X-(x+width)))
		dy := max(y-p.Y, max(0, p.Y-(y+height)))
		return int64(dx)*int64(dx) + int64(dy)*int64(dy)
	}
	if v.Avoid && time.Since(s.lastAvoid) > 350*time.Millisecond && distance(x, y) < int64(v.Distance*v.Distance) {
		best := distance(x, y)
		for _, candidate := range [][2]int32{{bounds.Left + 20, bounds.Top + 20}, {bounds.Right - width - 20, bounds.Top + 20}, {bounds.Left + 20, bounds.Bottom - height - 20}, {bounds.Right - width - 20, bounds.Bottom - height - 20}} {
			cx, cy := clamp(candidate[0], candidate[1])
			if d := distance(cx, cy); d > best {
				best = d
				x, y = cx, cy
			}
		}
		s.lastAvoid = time.Now()
	}
	s.overlayRect = Rect{x, y, x + width, y + height}
	s.lastBounds = bounds
	proc("SetLayeredWindowAttributes").Call(s.overlay, 0, uintptr(max(25, min(255, int(v.Opacity*255)))), 2)
	proc("SetWindowPos").Call(s.overlay, ^uintptr(0), uintptr(x), uintptr(y), uintptr(width), uintptr(height), 0x10|0x40)
	proc("InvalidateRect").Call(s.overlay, 0, 0)
}
func (s *Service) paint(hwnd uintptr) {
	var p paintStruct
	dc, _, _ := proc("BeginPaint").Call(hwnd, uintptr(unsafe.Pointer(&p)))
	if dc == 0 {
		return
	}
	defer proc("EndPaint").Call(hwnd, uintptr(unsafe.Pointer(&p)))
	s.mu.Lock()
	v := s.view
	s.mu.Unlock()
	var rect Rect
	getRect.Call(hwnd, uintptr(unsafe.Pointer(&rect)))
	rect = Rect{Right: rect.Right - rect.Left, Bottom: rect.Bottom - rect.Top}
	brush, _, _ := gdi.NewProc("CreateSolidBrush").Call(0x181412)
	proc("FillRect").Call(dc, uintptr(unsafe.Pointer(&rect)), brush)
	gdi.NewProc("DeleteObject").Call(brush)
	face, _ := windows.UTF16PtrFromString("Microsoft YaHei UI")
	font, _, _ := gdi.NewProc("CreateFontW").Call(^uintptr(12), 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 5, 0, uintptr(unsafe.Pointer(face)))
	old, _, _ := gdi.NewProc("SelectObject").Call(dc, font)
	defer func() { gdi.NewProc("SelectObject").Call(dc, old); gdi.NewProc("DeleteObject").Call(font) }()
	gdi.NewProc("SetBkMode").Call(dc, 1)
	draw := func(text string, y int32, color uintptr) {
		gdi.NewProc("SetTextColor").Call(dc, color)
		t, _ := windows.UTF16PtrFromString(text)
		r := Rect{12, y, 268, y + 22}
		proc("DrawTextW").Call(dc, uintptr(unsafe.Pointer(t)), ^uintptr(0), uintptr(unsafe.Pointer(&r)), 0x20|0x8000)
	}
	active := 0
	for _, m := range v.Snapshot.Macros {
		if m.Active {
			active++
		}
	}
	draw(fmt.Sprintf("D4Helper   %d/%d", active, len(v.Snapshot.Macros)), 9, 0xb8d6e9)
	if v.Snapshot.Fault != "" {
		draw("引擎已停止 · 请打开配置查看", 38, 0x8888ef)
		return
	}
	if v.Snapshot.Recording == "countdown" {
		draw(fmt.Sprintf("录制准备：%d 秒", v.Snapshot.Countdown), 38, 0x80d6f2)
		return
	}
	if v.Snapshot.Recording == "recording" {
		draw(fmt.Sprintf("● 录制中 %.1fs / %d 个动作", float64(v.Snapshot.RecordingElapsedMS)/1000, v.Snapshot.RecordingCount), 38, 0x8888ef)
		return
	}
	for i, m := range v.Snapshot.Macros {
		if i >= 8 {
			break
		}
		state := "○"
		color := uintptr(0x999999)
		if m.Active {
			state = "●"
			color = 0x85d9a1
		}
		draw(fmt.Sprintf("%-6s  %s  %s", m.Trigger, state, m.Name), int32(36+i*25), color)
	}
}
