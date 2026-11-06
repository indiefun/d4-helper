package timeline

import (
	"encoding/json"
	"strings"
	"testing"
	"time"

	"github.com/indiefun/d4-helper/go-desktop/internal/engine"
	"github.com/indiefun/d4-helper/go-desktop/internal/sequence"
)

func TestDurationFollowsActionsAndLoopWait(t *testing.T) {
	m := one(Track{ID: "track", Blocks: []Block{{ID: "hold", Type: "hold", Key: "f", AtMS: 200, DurationMS: 800}}})
	m.DurationMS = 3000 // Old editor canvas length is no longer authoritative.
	m.LoopWaitMS = 500
	for _, tc := range []struct {
		loop bool
		want time.Duration
	}{{false, time.Second}, {true, 1500 * time.Millisecond}} {
		m.Loop = tc.loop
		p, err := Compile(m)
		if err != nil || p.Duration != tc.want {
			t.Fatalf("loop=%t: duration=%v, err=%v", tc.loop, p.Duration, err)
		}
	}
	m.Tracks[0].Blocks[0].DurationMS = 300
	p, err := Compile(m)
	if err != nil || p.Duration != time.Second || p.Events[1].Offset != 500*time.Millisecond {
		t.Fatal("shortening an action did not shorten the cycle while preserving its wait", p, err)
	}
	m.Tracks[0].Muted = true
	p, err = Compile(m)
	if err != nil || p.Duration != time.Second || len(p.Events) != 0 {
		t.Fatal("muting a track changed the shared timeline timing", p, err)
	}
}

func TestOldDurationBecomesLoopWaitAndMigrationIsStable(t *testing.T) {
	for _, loop := range []bool{false, true} {
		raw := `{"schema_version":3,"macros":[{"id":"m","name":"test","enabled":true,"trigger":"none","duration_ms":2000,"loop":LOOP,"tracks":[{"id":"track","blocks":[{"id":"tap","type":"tap","key":"f","at_ms":200,"duration_ms":60}]}]}]}`
		raw = strings.Replace(raw, "LOOP", map[bool]string{false: "false", true: "true"}[loop], 1)
		normalized, cfg, err := Normalize(raw)
		if err != nil {
			t.Fatal(err)
		}
		wantDuration, wantWait := int64(260), int64(0)
		if loop {
			wantDuration, wantWait = 2000, 1740
		}
		m := cfg.Macros[0]
		if m.DurationMS != wantDuration || m.LoopWaitMS != wantWait {
			t.Fatalf("loop=%t: wrong migration: %+v", loop, m)
		}
		second, _, err := Normalize(normalized)
		if err != nil || second != normalized {
			t.Fatal("reloading changed migrated timing", err)
		}
	}
}

func TestExplicitZeroWaitOverridesLegacyDuration(t *testing.T) {
	m := one(Track{ID: "track", Blocks: []Block{{ID: "tap", Type: "tap", Key: "f", DurationMS: 60}}})
	m.Loop = true
	data, _ := json.Marshal(m)
	var decoded Definition
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatal(err)
	}
	if decoded.DurationMS != 60 || decoded.LoopWaitMS != 0 {
		t.Fatal("explicit zero wait was replaced by old duration", decoded)
	}
	for _, wait := range []int64{-1, MaxDurationMS, int64(^uint64(0) >> 1)} {
		m.LoopWaitMS = wait
		if _, err := Compile(m); err == nil {
			t.Fatalf("invalid wait accepted: %d", wait)
		}
	}
}

func TestEmptyAndInstantaneousTimelinesHavePositiveEngineDuration(t *testing.T) {
	for _, tracks := range [][]Track{nil, {{ID: "track", Blocks: []Block{{ID: "scroll", Type: "scroll", Delta: 120}}}}} {
		p, err := Compile(one(tracks...))
		if err != nil || p.Duration != time.Millisecond {
			t.Fatal("zero-time timeline did not compile", p, err)
		}
	}
	m := FromRecording(nil)
	if m.DurationMS != 1 {
		t.Fatal("empty recording had a fixed trailing duration")
	}
	m = FromRecording([]sequence.RecordedEvent{{Type: "key_down", Key: "f", AtMS: 0}, {Type: "key_up", Key: "f", AtMS: 40}})
	if m.DurationMS != 40 {
		t.Fatal("recording still has padding after the last action")
	}
}

type timingDriver struct{ sent []engine.Input }

func (d *timingDriver) Send(inputs []engine.Input) (int, error) {
	d.sent = append(d.sent, inputs...)
	return len(inputs), nil
}

func TestEngineReleasesBeforeLoopWaitAndRestartsAfterIt(t *testing.T) {
	m := one(Track{ID: "track", Blocks: []Block{{ID: "hold", Type: "hold", Key: "f", DurationMS: 100}}})
	m.Loop, m.LoopWaitMS = true, 50
	p, err := Compile(m)
	if err != nil {
		t.Fatal(err)
	}
	driver := &timingDriver{}
	core := engine.New(driver)
	now := time.Now()
	config := engine.Config{RecordingTrigger: "f12", EmergencyTrigger: "pause", Macros: []engine.Macro{{ID: "m", Enabled: true, Trigger: "f1", Plan: p}}}
	if err := core.Apply(config, nil, now); err != nil {
		t.Fatal(err)
	}
	core.Focus(true, nil, now)
	if err := core.Arm(true, nil, now); err != nil {
		t.Fatal(err)
	}
	if err := core.Toggle("m", now); err != nil {
		t.Fatal(err)
	}
	core.Tick(now.Add(100 * time.Millisecond))
	core.Tick(now.Add(149 * time.Millisecond))
	if len(driver.sent) != 2 || driver.sent[1].Down || core.Snapshot(now).PendingReleases != 0 {
		t.Fatal("input stayed pressed or restarted during loop wait", driver.sent)
	}
	core.Tick(now.Add(150 * time.Millisecond))
	core.Tick(now.Add(150 * time.Millisecond))
	if len(driver.sent) != 3 || !driver.sent[2].Down {
		t.Fatal("next cycle did not start after its wait", driver.sent)
	}
	core.Tick(now.Add(250 * time.Millisecond))
	core.Handle(engine.PhysicalEvent{Key: "pause", Down: true, At: now.Add(275 * time.Millisecond)})
	core.Tick(now.Add(300 * time.Millisecond))
	if len(driver.sent) != 4 || core.Snapshot(now).Armed {
		t.Fatal("emergency stop during wait did not prevent restart", driver.sent)
	}
}
