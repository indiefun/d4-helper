package timing

import (
	"context"
	"testing"
	"time"
)

func TestCancellationInterruptsLongTimer(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	started := make(chan struct{}, 1)
	done := make(chan error, 1)
	go func() {
		done <- Run(ctx, time.Minute, 0, func(time.Time) {
			select {
			case started <- struct{}{}:
			default:
			}
		})
	}()
	select {
	case <-started:
	case err := <-done:
		t.Fatalf("runner failed: %v", err)
	case <-time.After(3 * time.Second):
		t.Fatal("runner did not start")
	}
	cancel()
	select {
	case err := <-done:
		if err != nil {
			t.Fatal(err)
		}
	case <-time.After(time.Second):
		t.Fatal("cancel did not interrupt pending timer")
	}
}

func TestTimestampReportUsesObservedIntervals(t *testing.T) {
	start := time.Now()
	samples := []time.Time{start, start.Add(time.Millisecond), start.Add(3 * time.Millisecond), start.Add(13 * time.Millisecond)}
	r := Summarize("test", time.Millisecond, samples, time.Second, 10*time.Millisecond, 0)
	if r.Samples != 4 || r.P50MS != 2 || r.P99MS != 10 || r.CPUPercentOneCore != 1 {
		t.Fatalf("incorrect report: %+v", r)
	}
}
