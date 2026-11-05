//go:build windows

package win

import (
	"context"
	"testing"
	"time"
	"unsafe"

	"github.com/indiefun/d4-helper/go-desktop/internal/engine"
)

func TestWindowsABILayouts(t *testing.T) {
	for name, pair := range map[string][2]uintptr{"INPUT": {unsafe.Sizeof(input{}), 40}, "KEYBDINPUT": {unsafe.Sizeof(keyboardInput{}), 24}, "MOUSEINPUT": {unsafe.Sizeof(mouseInput{}), 32}, "WNDCLASSEXW": {unsafe.Sizeof(windowClass{}), 80}, "MSG": {unsafe.Sizeof(message{}), 48}, "NOTIFYICONDATAW": {unsafe.Sizeof(notifyIcon{}), 976}, "PAINTSTRUCT": {unsafe.Sizeof(paintStruct{}), 72}} {
		if pair[0] != pair[1] {
			t.Fatalf("%s layout: %d != %d", name, pair[0], pair[1])
		}
	}
}
func TestInjectedEventsNeverReachRecorder(t *testing.T) {
	k := keyboardHook{VK: 'F', Flags: 0x10}
	if _, ok := decodeKeyboard(0x100, &k); ok {
		t.Fatal("injected keyboard event was captured")
	}
	k.Flags = 0
	k.Extra = inputTag
	if _, ok := decodeKeyboard(0x100, &k); ok {
		t.Fatal("own keyboard event was captured")
	}
	k.Extra = 0
	e, ok := decodeKeyboard(0x100, &k)
	if !ok || e.Key != "f" || !e.Down {
		t.Fatal("physical keyboard event lost")
	}
	m := mouseHook{Flags: 1}
	if _, ok := decodeMouse(0x201, &m); ok {
		t.Fatal("injected mouse event was captured")
	}
}
func TestForegroundGuardNeverSendsDownWithoutTarget(t *testing.T) {
	driver := &Driver{}
	n, err := driver.Send([]engine.Input{{Key: "f", Down: true}})
	if err == nil || n != 0 {
		t.Fatal("unguarded input accepted")
	}
}
func TestNativeServiceStartsAndStopsWithoutInput(t *testing.T) {
	if testing.Short() {
		t.Skip("native message loop smoke test")
	}
	seen := make(chan Foreground, 1)
	s := &Service{OnForeground: func(f Foreground) {
		select {
		case seen <- f:
		default:
		}
	}}
	if err := s.Start(context.Background()); err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	select {
	case <-seen:
	case <-time.After(2 * time.Second):
		t.Fatal("foreground initialization missing")
	}
	if s.hwnd == 0 || s.overlay == 0 {
		t.Fatal("native service/overlay window not created")
	}
}
