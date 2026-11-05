//go:build windows

// Package win contains the Windows ABI boundary. All synthetic input is tagged;
// keyboard/mouse hooks ignore injected events and never block the hook thread.
package win

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"time"
	"unsafe"

	"github.com/indiefun/d4-helper/go-desktop/internal/engine"
	"golang.org/x/sys/windows"
)

var user = windows.NewLazySystemDLL("user32.dll")
var kernel = windows.NewLazySystemDLL("kernel32.dll")
var shell = windows.NewLazySystemDLL("shell32.dll")
var gdi = windows.NewLazySystemDLL("gdi32.dll")

func proc(name string) *windows.LazyProc { return user.NewProc(name) }

var getForeground = proc("GetForegroundWindow")
var getAsync = proc("GetAsyncKeyState")
var getRect = proc("GetWindowRect")
var getCursor = proc("GetCursorPos")
var getMetrics = proc("GetSystemMetrics")
var sendInput = proc("SendInput")
var postMessage = proc("PostMessageW")

const inputTag uintptr = 0xD4A41101

type Rect struct{ Left, Top, Right, Bottom int32 }
type Point struct{ X, Y int32 }
type Foreground struct {
	HWND    uintptr `json:"-"`
	Title   string  `json:"title"`
	Process string  `json:"process"`
	Rect    Rect    `json:"rect"`
}

var keyCodes = map[string]uint16{"left": 1, "right": 2, "middle": 4, "xbutton1": 5, "xbutton2": 6, "backspace": 8, "tab": 9, "enter": 13, "shift": 16, "ctrl": 17, "alt": 18, "pause": 19, "capslock": 20, "esc": 27, "space": 32, "pageup": 33, "pagedown": 34, "end": 35, "home": 36, "left_arrow": 37, "up": 38, "right_arrow": 39, "down": 40, "insert": 45, "delete": 46}

func init() {
	for n := 0; n < 10; n++ {
		keyCodes[fmt.Sprint(n)] = uint16(48 + n)
	}
	for n := 'a'; n <= 'z'; n++ {
		keyCodes[string(n)] = uint16(n - 32)
	}
	for n := 1; n <= 12; n++ {
		keyCodes[fmt.Sprintf("f%d", n)] = uint16(111 + n)
	}
}
func KeyFromVK(vk uint32) string {
	if vk == 160 || vk == 161 {
		vk = 16
	}
	if vk == 162 || vk == 163 {
		vk = 17
	}
	if vk == 164 || vk == 165 {
		vk = 18
	}
	for key, code := range keyCodes {
		if uint32(code) == vk {
			return key
		}
	}
	return ""
}
func Held() map[string]bool {
	r := map[string]bool{}
	for key, vk := range keyCodes {
		v, _, _ := getAsync.Call(uintptr(vk))
		if v&0x8000 != 0 {
			r[key] = true
		}
	}
	return r
}
func ForegroundWindow() Foreground {
	hwnd, _, _ := getForeground.Call()
	return Describe(hwnd)
}
func Describe(hwnd uintptr) Foreground {
	f := Foreground{HWND: hwnd}
	if hwnd == 0 {
		return f
	}
	var text [1024]uint16
	proc("GetWindowTextW").Call(hwnd, uintptr(unsafe.Pointer(&text[0])), uintptr(len(text)))
	f.Title = windows.UTF16ToString(text[:])
	getRect.Call(hwnd, uintptr(unsafe.Pointer(&f.Rect)))
	var pid uint32
	proc("GetWindowThreadProcessId").Call(hwnd, uintptr(unsafe.Pointer(&pid)))
	h, err := windows.OpenProcess(windows.PROCESS_QUERY_LIMITED_INFORMATION, false, pid)
	if err == nil {
		defer windows.CloseHandle(h)
		var path [32768]uint16
		n := uint32(len(path))
		if windows.QueryFullProcessImageName(h, 0, &path[0], &n) == nil {
			f.Process = filepath.Base(windows.UTF16ToString(path[:n]))
		}
	}
	return f
}
func Cursor() Point { var p Point; getCursor.Call(uintptr(unsafe.Pointer(&p))); return p }
func Screen() Rect {
	x, _, _ := getMetrics.Call(76)
	y, _, _ := getMetrics.Call(77)
	w, _, _ := getMetrics.Call(78)
	h, _, _ := getMetrics.Call(79)
	return Rect{int32(x), int32(y), int32(x) + int32(w), int32(y) + int32(h)}
}
func currentHWND() uintptr { h, _, _ := getForeground.Call(); return h }

func ForegroundIsSelf(hwnd uintptr) bool {
	var pid uint32
	proc("GetWindowThreadProcessId").Call(hwnd, uintptr(unsafe.Pointer(&pid)))
	return pid == uint32(os.Getpid())
}

type input struct {
	Type    uint32
	Padding uint32
	Data    [32]byte
}
type keyboardInput struct {
	VK, Scan    uint16
	Flags, Time uint32
	Padding     uint32
	Extra       uintptr
}
type mouseInput struct {
	X, Y              int32
	Data, Flags, Time uint32
	Padding           uint32
	Extra             uintptr
}

type Driver struct {
	Target atomic.Uintptr
	Dry    bool
	buffer []input
}

func (d *Driver) Send(events []engine.Input) (int, error) {
	if len(events) == 0 {
		return 0, nil
	}
	if d.Dry {
		return len(events), nil
	}
	foregroundMatches := d.Target.Load() != 0 && currentHWND() == d.Target.Load()
	for _, e := range events {
		if (e.Down || e.Kind == "move" || e.Kind == "scroll") && !foregroundMatches {
			return 0, fmt.Errorf("目标窗口已失焦，已阻止输入")
		}
	}
	if cap(d.buffer) < len(events) {
		d.buffer = make([]input, len(events))
	} else {
		d.buffer = d.buffer[:len(events)]
		clear(d.buffer)
	}
	for i, e := range events {
		if e.Kind == "move" || e.Kind == "scroll" {
			m := (*mouseInput)(unsafe.Pointer(&d.buffer[i].Data[0]))
			m.Extra = inputTag
			if e.Kind == "scroll" {
				m.Flags = 0x800
				m.Data = uint32(int32(e.Delta))
			} else {
				if e.X == nil || e.Y == nil {
					return 0, fmt.Errorf("鼠标移动缺少坐标")
				}
				s := Screen()
				w, h := int64(s.Right-s.Left-1), int64(s.Bottom-s.Top-1)
				if w <= 0 || h <= 0 {
					return 0, fmt.Errorf("桌面尺寸无效")
				}
				m.X = int32(max(0, min(65535, (int64(*e.X)-int64(s.Left))*65535/w)))
				m.Y = int32(max(0, min(65535, (int64(*e.Y)-int64(s.Top))*65535/h)))
				m.Flags = 1 | 0x8000 | 0x4000
			}
			continue
		}
		code, ok := keyCodes[e.Key]
		if !ok {
			return 0, fmt.Errorf("未知输入按键: %s", e.Key)
		}
		if e.Key == "left" || e.Key == "right" || e.Key == "middle" || e.Key == "xbutton1" || e.Key == "xbutton2" {
			m := (*mouseInput)(unsafe.Pointer(&d.buffer[i].Data[0]))
			m.Extra = inputTag
			switch e.Key {
			case "xbutton1", "xbutton2":
				m.Data = 1
				if e.Key == "xbutton2" {
					m.Data = 2
				}
				if e.Down {
					m.Flags = 0x80
				} else {
					m.Flags = 0x100
				}
			case "left":
				if e.Down {
					m.Flags = 2
				} else {
					m.Flags = 4
				}
			case "right":
				if e.Down {
					m.Flags = 8
				} else {
					m.Flags = 16
				}
			case "middle":
				if e.Down {
					m.Flags = 32
				} else {
					m.Flags = 64
				}
			}
			if foregroundMatches && e.X != nil && e.Y != nil {
				s := Screen()
				width, height := int64(s.Right-s.Left-1), int64(s.Bottom-s.Top-1)
				if width <= 0 || height <= 0 {
					return 0, fmt.Errorf("无法读取桌面尺寸")
				}
				m.X = int32(max(0, min(65535, (int64(*e.X)-int64(s.Left))*65535/width)))
				m.Y = int32(max(0, min(65535, (int64(*e.Y)-int64(s.Top))*65535/height)))
				m.Flags |= 1 | 0x8000 | 0x4000
			}
		} else {
			d.buffer[i].Type = 1
			k := (*keyboardInput)(unsafe.Pointer(&d.buffer[i].Data[0]))
			k.VK = code
			k.Extra = inputTag
			if !e.Down {
				k.Flags = 2
			}
			if strings.HasSuffix(e.Key, "_arrow") || e.Key == "up" || e.Key == "down" || e.Key == "insert" || e.Key == "delete" || e.Key == "home" || e.Key == "end" || e.Key == "pageup" || e.Key == "pagedown" {
				k.Flags |= 1
			}
		}
	}
	n, _, err := sendInput.Call(uintptr(len(d.buffer)), uintptr(unsafe.Pointer(&d.buffer[0])), unsafe.Sizeof(input{}))
	if int(n) != len(events) {
		return int(n), fmt.Errorf("SendInput 发送 %d/%d 条失败（检查游戏与工具权限级别）: %v", n, len(events), err)
	}
	return int(n), nil
}

func AcquireInstance() (windows.Handle, error) {
	return AcquireNamedInstance("Global\\D4HelperSingleInstance")
}
func AcquireNamedInstance(label string) (windows.Handle, error) {
	name, _ := windows.UTF16PtrFromString(label)
	h, err := windows.CreateMutex(nil, false, name)
	if err == windows.ERROR_ALREADY_EXISTS {
		windows.CloseHandle(h)
		return 0, fmt.Errorf("D4Helper 已经在运行，请先退出已有版本")
	}
	return h, err
}
func ShowError(message string) {
	text, _ := windows.UTF16PtrFromString(message)
	title, _ := windows.UTF16PtrFromString("D4Helper")
	proc("MessageBoxW").Call(0, uintptr(unsafe.Pointer(text)), uintptr(unsafe.Pointer(title)), 0x10)
}

type keyboardHook struct {
	VK, Scan, Flags, Time uint32
	Extra                 uintptr
}
type mouseHook struct {
	Position          Point
	Data, Flags, Time uint32
	Extra             uintptr
}
type message struct {
	HWND    uintptr
	ID      uint32
	Padding uint32
	WParam  uintptr
	LParam  uintptr
	Time    uint32
	Point   Point
	Private uint32
}
type windowClass struct {
	Size, Style                        uint32
	Callback                           uintptr
	ClassExtra, WindowExtra            int32
	Instance, Icon, Cursor, Background uintptr
	Menu, Name                         *uint16
	SmallIcon                          uintptr
}

func decodeKeyboard(wp uintptr, k *keyboardHook) (engine.PhysicalEvent, bool) {
	if k.Flags&0x10 != 0 || k.Extra == inputTag {
		return engine.PhysicalEvent{}, false
	}
	key := KeyFromVK(k.VK)
	if key == "" {
		return engine.PhysicalEvent{}, false
	}
	if wp != 0x100 && wp != 0x104 && wp != 0x101 && wp != 0x105 {
		return engine.PhysicalEvent{}, false
	}
	return engine.PhysicalEvent{Key: key, Down: wp == 0x100 || wp == 0x104, At: time.Now()}, true
}
func decodeMouse(wp uintptr, m *mouseHook) (engine.PhysicalEvent, bool) {
	if m.Flags&1 != 0 || m.Extra == inputTag {
		return engine.PhysicalEvent{}, false
	}
	e := engine.PhysicalEvent{At: time.Now()}
	switch wp {
	case 0x200:
		e.Kind = "move"
	case 0x20a:
		e.Kind = "scroll"
		e.Delta = int(int16(m.Data >> 16))
	case 0x201:
		e.Key = "left"
		e.Down = true
	case 0x202:
		e.Key = "left"
	case 0x204:
		e.Key = "right"
		e.Down = true
	case 0x205:
		e.Key = "right"
	case 0x207:
		e.Key = "middle"
		e.Down = true
	case 0x208:
		e.Key = "middle"
	case 0x20b, 0x20c:
		e.Key = "xbutton1"
		if m.Data>>16 == 2 {
			e.Key = "xbutton2"
		}
		e.Down = wp == 0x20b
	default:
		return e, false
	}
	x, y := int(m.Position.X), int(m.Position.Y)
	e.X = &x
	e.Y = &y
	return e, true
}
