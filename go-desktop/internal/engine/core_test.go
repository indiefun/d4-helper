package engine

import (
	"context"
	"fmt"
	"github.com/indiefun/d4-helper/go-desktop/internal/sequence"
	"testing"
	"time"
)

type fakeDriver struct {
	sent   [][]Input
	counts []int
}

func (d *fakeDriver) Send(events []Input) (int, error) {
	d.sent = append(d.sent, append([]Input(nil), events...))
	if len(d.counts) > 0 {
		n := d.counts[0]
		d.counts = d.counts[1:]
		if n != len(events) {
			return n, fmt.Errorf("partial send")
		}
	}
	return len(events), nil
}
func plan(key string, duration time.Duration) sequence.Plan {
	return sequence.Plan{Duration: duration, Events: []sequence.Event{{Kind: "key", Key: key, Down: true}, {Kind: "key", Key: key, Offset: duration}}}
}
func config(plans ...sequence.Plan) Config {
	c := Config{RecordingTrigger: "f12", EmergencyTrigger: "pause", MaxSeconds: 60}
	for i, p := range plans {
		c.Macros = append(c.Macros, Macro{ID: fmt.Sprint(i), Name: fmt.Sprint(i), Enabled: true, Trigger: fmt.Sprintf("f%d", i+1), Plan: p})
	}
	return c
}
func setup(t *testing.T, plans ...sequence.Plan) (*Core, *fakeDriver, time.Time) {
	t.Helper()
	d := &fakeDriver{}
	c := New(d)
	now := time.Now()
	if err := c.Apply(config(plans...), nil, now); err != nil {
		t.Fatal(err)
	}
	c.Focus(true, nil, now)
	c.Arm(true, nil, now)
	return c, d, now
}
func TestPlansAreIndependentOfEditorAndSharedKeysReleaseLast(t *testing.T) {
	c, d, now := setup(t, plan("right", time.Second), plan("right", 2*time.Second))
	c.Toggle("0", now)
	c.Toggle("1", now)
	if len(d.sent) != 1 {
		t.Fatal("duplicate shared down")
	}
	c.Tick(now.Add(time.Second))
	if len(d.sent) != 1 {
		t.Fatal("earlier plan released later owner")
	}
	c.Tick(now.Add(2 * time.Second))
	if len(d.sent) != 2 || d.sent[1][0].Down {
		t.Fatal("last owner did not release")
	}
}
func TestPartialSendStopsAndRetriesOnlyInsertedKeys(t *testing.T) {
	p := sequence.Plan{Duration: time.Second, Events: []sequence.Event{{Kind: "key", Key: "f", Down: true}, {Kind: "key", Key: "g", Down: true}, {Kind: "key", Key: "f", Offset: time.Second}, {Kind: "key", Key: "g", Offset: time.Second}}}
	c, d, now := setup(t, p)
	d.counts = []int{1, 0, 1}
	c.Toggle("0", now)
	if c.armed || len(c.physical) != 1 || !c.physical["f"] {
		t.Fatal("partial send not tracked")
	}
	c.Tick(now.Add(30 * time.Millisecond))
	if len(c.physical) != 0 || d.sent[2][0].Key != "f" {
		t.Fatal("release compensation wrong")
	}
}
func TestZeroInsertedDoesNotGenerateUnrelatedRelease(t *testing.T) {
	c, d, now := setup(t, plan("f", time.Second))
	d.counts = []int{0}
	c.Toggle("0", now)
	if len(d.sent) != 1 || len(c.physical) != 0 {
		t.Fatal("unpaired release")
	}
}
func TestFocusSwitchRequiresFreshPhysicalPress(t *testing.T) {
	c, d, now := setup(t, plan("right", time.Second))
	c.Handle(PhysicalEvent{Key: "f1", Down: true, At: now})
	c.Focus(false, map[string]bool{"f1": true}, now)
	if len(c.physical) != 0 || len(d.sent) != 2 {
		t.Fatal("focus cleanup failed")
	}
	c.Focus(true, map[string]bool{"f1": true}, now)
	c.Handle(PhysicalEvent{Key: "f1", Down: true, At: now})
	if len(c.active) != 0 {
		t.Fatal("held trigger restarted plan")
	}
	c.Handle(PhysicalEvent{Key: "f1", At: now})
	c.Handle(PhysicalEvent{Key: "f1", Down: true, At: now})
	if len(c.active) != 1 {
		t.Fatal("fresh trigger lost")
	}
}
func TestMovementDoesNotEnterKeyOwnershipAndEmergencyStops(t *testing.T) {
	x, y := 5, 10
	p := sequence.Plan{Duration: time.Second, Events: []sequence.Event{{Kind: "move", X: &x, Y: &y}, {Kind: "scroll", Delta: 120}}}
	c, d, now := setup(t, p)
	c.Toggle("0", now)
	if len(d.sent) != 1 || len(c.physical) != 0 || len(d.sent[0]) != 2 {
		t.Fatal("move treated as key")
	}
	c.Handle(PhysicalEvent{Key: "pause", Down: true, At: now})
	if c.armed || len(c.active) != 0 {
		t.Fatal("emergency stop failed")
	}
}
func TestRecordingRetainsShortClickAndMovement(t *testing.T) {
	c, _, now := setup(t)
	c.StartRecording(now)
	x, y := 10, 20
	c.Handle(PhysicalEvent{Key: "f", Down: true, At: now.Add(time.Millisecond)})
	c.Handle(PhysicalEvent{Key: "f", At: now.Add(2 * time.Millisecond)})
	c.Handle(PhysicalEvent{Kind: "move", X: &x, Y: &y, At: now.Add(3 * time.Millisecond)})
	c.FinishRecording(now.Add(time.Second))
	if len(c.Recordings) != 1 || len(c.Recordings[0]) != 3 || c.Recordings[0][1].AtMS != 1 || c.Recordings[0][2].Type != "move" {
		t.Fatal("recording dropped primitive events")
	}
}
func TestWorkerIdleWakeAndShutdownRelease(t *testing.T) {
	d := &fakeDriver{}
	w, err := Start(context.Background(), d)
	if err != nil {
		t.Fatal(err)
	}
	err = w.Do(func(c *Core) error {
		now := time.Now()
		if err := c.Apply(config(plan("right", time.Minute)), nil, now); err != nil {
			return err
		}
		c.Focus(true, nil, now)
		c.Arm(true, nil, now)
		return c.Toggle("0", now)
	})
	if err != nil {
		t.Fatal(err)
	}
	start := time.Now()
	w.Close()
	if time.Since(start) > time.Second || len(d.sent) != 2 || d.sent[1][0].Down {
		t.Fatal("shutdown did not interrupt long wait and release")
	}
}
