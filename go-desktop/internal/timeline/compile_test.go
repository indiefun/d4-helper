package timeline

import (
	"github.com/indiefun/d4-helper/go-desktop/internal/sequence"
	"testing"
	"time"
)

func one(tracks ...Track) Definition {
	return Definition{ID: "m", Name: "test", Trigger: "none", Enabled: true, DurationMS: 2000, Tracks: tracks}
}
func TestParallelTracksMergeOnOneClock(t *testing.T) {
	m := one(Track{ID: "a", Blocks: []Block{{ID: "hold", Type: "hold", Key: "right", AtMS: 0, DurationMS: 1500}}}, Track{ID: "b", Blocks: []Block{{ID: "tap", Type: "tap", Key: "2", AtMS: 200, DurationMS: 40}, {ID: "tap2", Type: "tap", Key: "1", AtMS: 800, DurationMS: 40}}})
	p, err := Compile(m)
	if err != nil {
		t.Fatal(err)
	}
	if len(p.Events) != 6 || p.Events[1].Offset != 200*time.Millisecond || p.Events[5].Key != "right" || p.Events[5].Down {
		t.Fatalf("bad merge: %+v", p)
	}
}
func TestOverlappingKeyHoldsHaveIndependentOwners(t *testing.T) {
	m := one(Track{ID: "a", Blocks: []Block{{ID: "a", Type: "hold", Key: "f", DurationMS: 500}}}, Track{ID: "b", Blocks: []Block{{ID: "b", Type: "hold", Key: "f", AtMS: 200, DurationMS: 700}}})
	// Track and block identities must be distinct.
	m.Tracks[0].Blocks[0].ID = "block_a"
	m.Tracks[1].Blocks[0].ID = "block_b"
	p, err := Compile(m)
	if err != nil {
		t.Fatal(err)
	}
	if len(p.Events) != 2 || p.Events[1].Offset != 900*time.Millisecond {
		t.Fatal("early release of overlapping hold")
	}
}
func TestExplicitDownAndUpCanLiveOnDifferentTracks(t *testing.T) {
	m := one(Track{ID: "a", Blocks: []Block{{ID: "down", Type: "down", Key: "f", AtMS: 100}}}, Track{ID: "b", Blocks: []Block{{ID: "up", Type: "up", Key: "f", AtMS: 900}}})
	p, err := Compile(m)
	if err != nil || len(p.Events) != 2 {
		t.Fatal(err)
	}
	m.Tracks[1].Muted = true
	if _, err := Compile(m); err == nil {
		t.Fatal("unmatched down after mute accepted")
	}
}
func TestRepeatedClicksAndMovementExpansion(t *testing.T) {
	x, y, fx, fy := 100, 200, 0, 0
	m := one(Track{ID: "a", Blocks: []Block{{ID: "tap", Type: "tap", Key: "f", AtMS: 0, DurationMS: 20, RepeatMS: 100}}}, Track{ID: "b", Blocks: []Block{{ID: "move", Type: "move", AtMS: 300, DurationMS: 80, X: &x, Y: &y, FromX: &fx, FromY: &fy}}})
	p, err := Compile(m)
	if err != nil {
		t.Fatal(err)
	}
	keyCount, moves := 0, 0
	for _, e := range p.Events {
		if e.Kind == "key" {
			keyCount++
		} else if e.Kind == "move" {
			moves++
		}
	}
	if keyCount != 40 || moves != 11 {
		t.Fatalf("bad expansion: %d %d", keyCount, moves)
	}
}
func TestConflictingMovementAndOutOfBoundsRejected(t *testing.T) {
	x, y := 1, 2
	m := one(Track{ID: "a", Blocks: []Block{{ID: "bad", Type: "tap", Key: "f", AtMS: 1999, DurationMS: 20}}})
	if _, err := Compile(m); err == nil {
		t.Fatal("out of bounds accepted")
	}
	m = one(Track{ID: "a", Blocks: []Block{{ID: "move1", Type: "move", DurationMS: 100, X: &x, Y: &y, FromX: &x, FromY: &y}, {ID: "move2", Type: "move", AtMS: 50, DurationMS: 100, X: &x, Y: &y, FromX: &x, FromY: &y}}})
	if _, err := Compile(m); err == nil {
		t.Fatal("conflicting pointer paths accepted")
	}
}
func TestRecordingBecomesEditableParallelTracks(t *testing.T) {
	m := FromRecording([]sequence.RecordedEvent{{Type: "key_down", Key: "f", AtMS: 0}, {Type: "key_down", Key: "right", AtMS: 10}, {Type: "key_up", Key: "f", AtMS: 40}, {Type: "key_up", Key: "right", AtMS: 500}})
	if len(m.Tracks) != 2 || m.Tracks[0].Blocks[0].DurationMS != 40 {
		t.Fatal("recording not split by key")
	}
	if _, err := Compile(m); err != nil {
		t.Fatal(err)
	}
}

func TestRecordedMouseStrokeStaysOneEditableBlock(t *testing.T) {
	x1, y1, x2, y2, x3, y3 := 0, 0, 10, 20, 50, 80
	m := FromRecording([]sequence.RecordedEvent{{Type: "move", AtMS: 100, X: &x1, Y: &y1}, {Type: "move", AtMS: 120, X: &x2, Y: &y2}, {Type: "move", AtMS: 160, X: &x3, Y: &y3}})
	if len(m.Tracks) != 1 || len(m.Tracks[0].Blocks) != 1 || len(m.Tracks[0].Blocks[0].Path) != 3 {
		t.Fatal("mouse stroke fragmented into blocks")
	}
	p, err := Compile(m)
	if err != nil {
		t.Fatal(err)
	}
	if len(p.Events) != 3 || p.Events[2].Offset != 160*time.Millisecond || *p.Events[2].X != 50 {
		t.Fatal("recorded trajectory changed")
	}
}
