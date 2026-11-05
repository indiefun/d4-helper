//go:build windows

package timing

import (
	"context"
	"fmt"
	"sync"
	"syscall"
	"time"
	"unsafe"
)

var (
	kernel32     = syscall.NewLazyDLL("kernel32.dll")
	createTimer  = kernel32.NewProc("CreateWaitableTimerExW")
	setTimer     = kernel32.NewProc("SetWaitableTimer")
	createEvent  = kernel32.NewProc("CreateEventW")
	setEvent     = kernel32.NewProc("SetEvent")
	waitMultiple = kernel32.NewProc("WaitForMultipleObjects")
	closeHandle  = kernel32.NewProc("CloseHandle")
	getThread    = kernel32.NewProc("GetCurrentThread")
	getPriority  = kernel32.NewProc("GetThreadPriority")
	setPriority  = kernel32.NewProc("SetThreadPriority")
	getProcess   = kernel32.NewProc("GetCurrentProcess")
	getTimes     = kernel32.NewProc("GetProcessTimes")
)

type waiter struct {
	timer    uintptr
	cancel   uintptr
	wake     uintptr
	stop     func() bool
	callback sync.WaitGroup
	thread   uintptr
	priority uintptr
}

func newWaiter(ctx context.Context) (*waiter, error) {
	// CREATE_WAITABLE_TIMER_HIGH_RESOLUTION, TIMER_ALL_ACCESS.
	timer, _, err := createTimer.Call(0, 0, 2, 0x1F0003)
	if timer == 0 {
		return nil, fmt.Errorf("high-resolution timer unavailable: %w", err)
	}
	cancel, _, err := createEvent.Call(0, 1, 0, 0)
	if cancel == 0 {
		closeHandle.Call(timer)
		return nil, fmt.Errorf("create cancellation event: %w", err)
	}
	w := &waiter{timer: timer, cancel: cancel}
	wake, _, wakeErr := createEvent.Call(0, 0, 0, 0)
	if wake == 0 {
		closeHandle.Call(timer)
		closeHandle.Call(cancel)
		return nil, fmt.Errorf("create command wake event: %w", wakeErr)
	}
	w.wake = wake
	w.thread, _, _ = getThread.Call()
	w.priority, _, _ = getPriority.Call(w.thread)
	// Same priority class as the current C++ worker; restored before unpinning.
	setPriority.Call(w.thread, 2)
	w.callback.Add(1)
	w.stop = context.AfterFunc(ctx, func() { defer w.callback.Done(); setEvent.Call(cancel) })
	return w, nil
}

func (w *waiter) Until(deadline time.Time) error {
	_, err := w.Wait(deadline)
	return err
}

// NewWaiter must be created/closed on the same locked OS thread.
func NewWaiter(ctx context.Context) (*waiter, error) { return newWaiter(ctx) }
func (w *waiter) Wake()                              { setEvent.Call(w.wake) }
func (w *waiter) Wait(deadline time.Time) (bool, error) {
	if deadline.IsZero() {
		handles := [2]uintptr{w.cancel, w.wake}
		r, _, err := waitMultiple.Call(2, uintptr(unsafe.Pointer(&handles[0])), 0, 0xFFFFFFFF)
		if r == 0 {
			return false, context.Canceled
		}
		if r == 1 {
			return true, nil
		}
		return false, err
	}
	remaining := time.Until(deadline)
	if remaining <= 0 {
		return false, nil
	}
	// Negative FILETIME means relative time in 100ns units; round up.
	ticks := -int64((remaining + 99*time.Nanosecond) / (100 * time.Nanosecond))
	r, _, err := setTimer.Call(w.timer, uintptr(unsafe.Pointer(&ticks)), 0, 0, 0, 0)
	if r == 0 {
		return false, fmt.Errorf("set waitable timer: %w", err)
	}
	handles := [3]uintptr{w.cancel, w.wake, w.timer}
	r, _, err = waitMultiple.Call(3, uintptr(unsafe.Pointer(&handles[0])), 0, 0xFFFFFFFF)
	if r == 0 {
		return false, context.Canceled
	}
	if r == 1 {
		return true, nil
	}
	if r == 2 {
		return false, nil
	}
	return false, fmt.Errorf("waitable timer wait failed (%d): %w", r, err)
}

func (w *waiter) Close() {
	if w.stop() {
		w.callback.Done()
	}
	w.callback.Wait()
	closeHandle.Call(w.cancel)
	closeHandle.Call(w.timer)
	closeHandle.Call(w.wake)
	setPriority.Call(w.thread, w.priority)
}

type filetime struct{ Low, High uint32 }

func CPUTime() (time.Duration, error) {
	handle, _, _ := getProcess.Call()
	var creation, exit, kernel, user filetime
	r, _, err := getTimes.Call(handle, uintptr(unsafe.Pointer(&creation)), uintptr(unsafe.Pointer(&exit)), uintptr(unsafe.Pointer(&kernel)), uintptr(unsafe.Pointer(&user)))
	if r == 0 {
		return 0, err
	}
	ticks := (uint64(kernel.High)<<32 | uint64(kernel.Low)) + (uint64(user.High)<<32 | uint64(user.Low))
	return time.Duration(ticks*100) * time.Nanosecond, nil
}
