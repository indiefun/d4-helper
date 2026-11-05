//go:build !windows

package timing

import (
	"context"
	"time"
)

type waiter struct {
	ctx   context.Context
	timer *time.Timer
	wake  chan struct{}
}

func newWaiter(ctx context.Context) (*waiter, error) {
	return &waiter{ctx: ctx, timer: time.NewTimer(time.Hour), wake: make(chan struct{}, 1)}, nil
}
func (w *waiter) Until(deadline time.Time) error {
	_, err := w.Wait(deadline)
	return err
}
func NewWaiter(ctx context.Context) (*waiter, error) { return newWaiter(ctx) }
func (w *waiter) Wake() {
	select {
	case w.wake <- struct{}{}:
	default:
	}
}
func (w *waiter) Wait(deadline time.Time) (bool, error) {
	if deadline.IsZero() {
		select {
		case <-w.ctx.Done():
			return false, w.ctx.Err()
		case <-w.wake:
			return true, nil
		}
	}
	d := time.Until(deadline)
	if d <= 0 {
		return false, nil
	}
	if !w.timer.Stop() {
		select {
		case <-w.timer.C:
		default:
		}
	}
	w.timer.Reset(d)
	select {
	case <-w.ctx.Done():
		return false, w.ctx.Err()
	case <-w.timer.C:
		return false, nil
	case <-w.wake:
		return true, nil
	}
}
func (w *waiter) Close()              { w.timer.Stop() }
func CPUTime() (time.Duration, error) { return 0, nil }
