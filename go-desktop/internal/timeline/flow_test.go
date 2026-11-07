package timeline

import (
	"encoding/json"
	"github.com/indiefun/d4-helper/go-desktop/internal/engine"
	"testing"
	"time"
)

type flowDriver struct {
	at   time.Time
	sent []struct {
		at    time.Time
		input engine.Input
	}
}

func (d *flowDriver) Send(inputs []engine.Input) (int, error) {
	for _, input := range inputs {
		d.sent = append(d.sent, struct {
			at    time.Time
			input engine.Input
		}{d.at, input})
	}
	return len(inputs), nil
}

func TestFlowPlanRunsThroughEngineAndStopsOnFocusLoss(t *testing.T) {
	cfg := FlowDefault()
	cfg.Macros[0].Loop = true
	cfg.Macros[0].LoopWaitMS = 100
	runtime, err := cfg.Runtime()
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now()
	driver := &flowDriver{at: now}
	core := engine.New(driver)
	if err := core.Apply(runtime, nil, now); err != nil {
		t.Fatal(err)
	}
	core.Focus(true, nil, now)
	if err := core.Arm(true, nil, now); err != nil {
		t.Fatal(err)
	}
	if err := core.Toggle("starter", now); err != nil {
		t.Fatal(err)
	}
	// Tick every event/round boundary, as the worker does, without wall-clock sleeps.
	for wakes := 0; wakes < 30; wakes++ {
		due := core.Next()
		if due.IsZero() || due.After(now.Add(1100*time.Millisecond)) {
			break
		}
		driver.at = due
		core.Tick(due)
	}
	var taps []int64
	for _, event := range driver.sent {
		if event.input.Key == "1" && event.input.Down {
			taps = append(taps, event.at.Sub(now).Milliseconds())
		}
	}
	for i, want := range []int64{0, 200, 400, 600, 1080} {
		if len(taps) <= i || taps[i] != want {
			t.Fatal("repeat timing did not reach input engine", taps)
		}
	}
	driver.at = now.Add(1100 * time.Millisecond)
	core.Focus(false, nil, driver.at)
	last := driver.sent[len(driver.sent)-1]
	if last.input.Down {
		t.Fatal("focus loss left input pressed", driver.sent)
	}
	s := core.Snapshot(driver.at)
	if s.PendingReleases != 0 || s.Macros[0].Active {
		t.Fatal("flow did not stop on focus loss", s)
	}
}

func TestFlowParallelRepeatAndRoundBoundaries(t *testing.T) {
	m := FlowDefault().Macros[0]
	p, err := Compile(m)
	if err != nil {
		t.Fatal(err)
	}
	if p.Duration != 980*time.Millisecond || len(p.Events) != 12 {
		t.Fatal(p, err)
	}
	var taps []time.Duration
	for _, e := range p.Events {
		if e.Key == "1" && e.Down {
			taps = append(taps, e.Offset)
		}
	}
	for i, want := range []int{0, 200, 400, 600} {
		if taps[i] != time.Duration(want)*time.Millisecond {
			t.Fatal(taps)
		}
	}
	repeated := m.Graph.Root.Items[0].Branches[1].Items[0]
	repeated.GapMS = 100
	p, err = Compile(m)
	if err != nil || p.Duration != 1280*time.Millisecond {
		t.Fatal(p, err)
	}
	for _, e := range p.Events {
		if e.Key == "2" && e.Down && e.Offset != 1220*time.Millisecond {
			t.Fatal("last repeat got an extra gap", e)
		}
	}
	m.Loop = true
	m.LoopWaitMS = 300
	p, err = Compile(m)
	if err != nil || !p.Loop || p.Duration != 1580*time.Millisecond {
		t.Fatal(p, err)
	}
}

func TestFlowNestedParallelRepeatMutedAndCache(t *testing.T) {
	c := FlowDefault()
	m := &c.Macros[0]
	first := m.Graph.Root.Items[0]
	m.Graph.Root.Items[0] = &FlowNode{ID: "outer_repeat", Type: "repeat", Count: 3, GapMS: 20, Body: &FlowNode{ID: "outer_body", Type: "sequence", Items: []*FlowNode{first}}}
	first.Branches[0].Items[0].Disabled = true
	m.Tracks = []Track{{ID: "stale", Blocks: []Block{{ID: "wrong", Type: "tap", Key: "9", DurationMS: 5000}}}}
	first.Collapsed = true
	raw, _ := json.Marshal(c)
	normalized, saved, err := Normalize(string(raw))
	if err != nil {
		t.Fatal(err)
	}
	p, err := Compile(saved.Macros[0])
	if err != nil || p.Duration != 2620*time.Millisecond || len(p.Events) != 26 {
		t.Fatal(p, err, normalized)
	}
	for _, e := range p.Events {
		if e.Key == "right" || e.Key == "9" {
			t.Fatal("muted action/cache was executed", e)
		}
	}
	_, again, err := Normalize(normalized)
	if err != nil || !again.Macros[0].Graph.Root.Items[0].Body.Items[0].Collapsed {
		t.Fatal("lost authoring", err)
	}
}

func TestFlowRejectsBadActionsAndPreflightsExpansion(t *testing.T) {
	cases := map[string]func(*Definition){
		"zero hold":         func(m *Definition) { m.Graph.Root.Items[0].Branches[0].Items[0].Action.DurationMS = 0 },
		"bad count":         func(m *Definition) { m.Graph.Root.Items[0].Branches[1].Items[0].Count = 101 },
		"negative interval": func(m *Definition) { m.Graph.Root.Items[0].Branches[1].Items[0].GapMS = -1 },
		"duplicate id":      func(m *Definition) { m.Graph.Root.Items[1].ID = m.Graph.Root.ID },
		"unknown":           func(m *Definition) { m.Graph.Root.Items[1].Type = "script" },
		"duration":          func(m *Definition) { m.Graph.Root.Items[1].WaitMS = MaxDurationMS },
		"empty parallel":    func(m *Definition) { m.Graph.Root.Items[0].Branches = nil },
		"bad root":          func(m *Definition) { m.Graph.Root.Type = "parallel" },
	}
	for name, mutate := range cases {
		t.Run(name, func(t *testing.T) {
			m := FlowDefault().Macros[0]
			mutate(&m)
			if _, err := Compile(m); err == nil {
				t.Fatal("accepted invalid flow")
			}
		})
	}
	// Nested repeats of instantaneous events must fail before expanding millions.
	n := &FlowNode{ID: "scroll", Type: "scroll", Action: &Block{Type: "scroll", Delta: 120}}
	for i := 0; i < 5; i++ {
		n = &FlowNode{ID: NewID("repeat"), Type: "repeat", Count: 100, Body: &FlowNode{ID: NewID("body"), Type: "sequence", Items: []*FlowNode{n}}}
	}
	if _, _, err := flowTracks(&FlowNode{ID: "root", Type: "sequence", Items: []*FlowNode{n}}); err == nil {
		t.Fatal("unbounded repeat accepted")
	}
	// Empty repeated scopes do not walk 100^5 iterations.
	n = &FlowNode{ID: "empty", Type: "sequence"}
	for i := 0; i < 5; i++ {
		n = &FlowNode{ID: NewID("seq"), Type: "sequence", Items: []*FlowNode{{ID: NewID("repeat"), Type: "repeat", Count: 100, Body: n}}}
	}
	if _, d, err := flowTracks(n); err != nil || d != 0 {
		t.Fatal(d, err)
	}
}

func TestFlowRecordedPathRepeatAndMoveConflict(t *testing.T) {
	x, y, fx, fy := 50, 60, 10, 20
	a := &FlowNode{ID: "move", Type: "move", Action: &Block{Type: "move", DurationMS: 80, X: &x, Y: &y, FromX: &fx, FromY: &fy, Path: []Waypoint{{0, 10, 20}, {40, 30, 40}, {80, 50, 60}}}}
	m := Definition{Graph: &Graph{Version: 2, Root: &FlowNode{ID: "root", Type: "sequence", Items: []*FlowNode{{ID: "repeat", Type: "repeat", Count: 2, GapMS: 20, Body: &FlowNode{ID: "body", Type: "sequence", Items: []*FlowNode{a}}}}}}}
	p, err := Compile(m)
	if err != nil || len(p.Events) != 6 || p.Events[3].Offset != 100*time.Millisecond || p.Duration != 180*time.Millisecond {
		t.Fatal(p, err)
	}
	b := *a
	b.ID = "move2"
	m.Graph.Root.Items = []*FlowNode{{ID: "parallel", Type: "parallel", Branches: []*FlowNode{{ID: "a", Type: "sequence", Items: []*FlowNode{a}}, {ID: "b", Type: "sequence", Items: []*FlowNode{&b}}}}}
	if _, err := Compile(m); err == nil {
		t.Fatal("parallel mouse movement was accepted")
	}
}
