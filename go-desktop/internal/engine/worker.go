package engine

import (
	"context"
	"fmt"
	"runtime"
	"sync"
	"sync/atomic"
	"time"

	"github.com/indiefun/d4-helper/go-desktop/internal/timing"
)

type waker interface{ Wake() }
type request struct {
	apply func(*Core) error
	reply chan error
}
type Worker struct {
	ctx       context.Context
	cancel    context.CancelFunc
	commands  chan request
	done      chan struct{}
	overflow  atomic.Bool
	recording atomic.Bool
	mu        sync.Mutex
	wake      waker
	core      *Core
}

func Start(parent context.Context, driver Driver) (*Worker, error) {
	ctx, cancel := context.WithCancel(parent)
	w := &Worker{ctx: ctx, cancel: cancel, commands: make(chan request, 2048), done: make(chan struct{}), core: New(driver)}
	ready := make(chan error, 1)
	go w.run(ready)
	if err := <-ready; err != nil {
		cancel()
		return nil, err
	}
	return w, nil
}
func (w *Worker) run(ready chan<- error) {
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	defer close(w.done)
	wait, err := timing.NewWaiter(w.ctx)
	if err != nil {
		ready <- err
		return
	}
	defer wait.Close()
	w.mu.Lock()
	w.wake = wait
	w.mu.Unlock()
	ready <- nil
	defer func() {
		if failure := recover(); failure != nil {
			w.core.fault = fmt.Sprintf("执行引擎异常: %v", failure)
		}
		w.mu.Lock()
		w.wake = nil
		w.mu.Unlock()
		w.core.armed = false
		w.core.Stop(time.Now())
		for i := 0; i < 4 && len(w.core.physical) > 0; i++ {
			time.Sleep(20 * time.Millisecond)
			w.core.retryReleases(time.Now())
		}
	}()
	for {
		if w.ctx.Err() != nil {
			return
		}
		if w.overflow.Swap(false) {
			w.core.Fail(fmt.Errorf("输入事件队列溢出，已停止引擎，请重新启用"), time.Now())
		}
		for n := 0; n < 2048; n++ {
			select {
			case cmd := <-w.commands:
				err := cmd.apply(w.core)
				if cmd.reply != nil {
					cmd.reply <- err
				}
			default:
				n = 2048
			}
		}
		w.core.Tick(time.Now())
		w.recording.Store(w.core.recordState == "recording")
		if _, err := wait.Wait(w.core.Next()); err != nil {
			if w.ctx.Err() == nil {
				w.core.Fail(err, time.Now())
			}
			return
		}
	}
}
func (w *Worker) signal() {
	w.mu.Lock()
	if w.wake != nil {
		w.wake.Wake()
	}
	w.mu.Unlock()
}
func (w *Worker) Do(fn func(*Core) error) error {
	cmd := request{fn, make(chan error, 1)}
	select {
	case <-w.done:
		return fmt.Errorf("引擎已停止")
	case w.commands <- cmd:
	case <-time.After(3 * time.Second):
		return fmt.Errorf("引擎命令超时")
	}
	w.signal()
	select {
	case err := <-cmd.reply:
		return err
	case <-w.done:
		return fmt.Errorf("引擎已停止")
	}
}

// Post is nonblocking so a low-level Windows hook never waits for execution.
// Overflow fails closed instead of dropping a key-up and leaving a key held.
func (w *Worker) Post(fn func(*Core) error) {
	select {
	case <-w.done:
		return
	default:
	}
	select {
	case w.commands <- request{apply: fn}:
	default:
		w.overflow.Store(true)
	}
	w.signal()
}
func (w *Worker) Snapshot() (Snapshot, error) {
	var s Snapshot
	err := w.Do(func(c *Core) error { s = c.Snapshot(time.Now()); return nil })
	return s, err
}
func (w *Worker) Close()            { w.cancel(); w.signal(); <-w.done }
func (w *Worker) IsRecording() bool { return w.recording.Load() }
