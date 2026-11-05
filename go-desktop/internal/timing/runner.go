// Package timing is the isolated scheduling experiment. Sinks used by the
// prototype only collect timestamps; no implementation sends keyboard input.
package timing

import (
	"context"
	"fmt"
	"runtime"
	"time"
)

// Run schedules one periodic callback using absolute deadlines. Missed ticks
// are skipped rather than emitted as an unbounded catch-up burst, matching the
// legacy C++ scheduler's policy. The callback must avoid blocking or allocating.
func Run(ctx context.Context, interval time.Duration, spin time.Duration, emit func(time.Time)) error {
	if interval <= 0 || spin < 0 || spin > interval {
		return fmt.Errorf("invalid interval or spin window")
	}
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	w, err := newWaiter(ctx)
	if err != nil {
		return err
	}
	defer w.Close()
	due := time.Now()
	for {
		if err := ctx.Err(); err != nil {
			return nil
		}
		if err := w.Until(due.Add(-spin)); err != nil {
			if ctx.Err() != nil {
				return nil
			}
			return err
		}
		for spin > 0 && time.Now().Before(due) {
			if ctx.Err() != nil {
				return nil
			}
		}
		now := time.Now()
		emit(now)
		due = due.Add(interval)
		if !due.After(now) {
			due = now.Add(interval)
		}
	}
}
