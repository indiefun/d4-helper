package timeline

import (
	"encoding/json"
	"reflect"
	"strings"
	"testing"

	"github.com/indiefun/d4-helper/go-desktop/internal/sequence"
)

func TestSingleTrackOverlapRules(t *testing.T) {
	point := func(id string, at int64) Block { return Block{ID: id, Type: "scroll", AtMS: at, Delta: 120} }
	hold := Block{ID: "hold", Type: "hold", Key: "f", AtMS: 100, DurationMS: 200}
	for _, tc := range []struct {
		name   string
		blocks []Block
		valid  bool
	}{
		{"adjacent", []Block{hold, {ID: "tap", Type: "tap", Key: "g", AtMS: 300, DurationMS: 10}}, true},
		{"different keys still overlap", []Block{hold, {ID: "tap", Type: "tap", Key: "g", AtMS: 299, DurationMS: 10}}, false},
		{"point at start", []Block{point("p", 100), hold}, false},
		{"point inside duration", []Block{point("p", 200), hold}, false},
		{"point at end", []Block{point("p", 300), hold}, true},
		{"points coincide", []Block{point("p", 400), point("q", 400)}, false},
		{"adjacent points", []Block{point("p", 400), point("q", 401)}, true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			for _, muted := range []bool{false, true} {
				_, err := Compile(one(Track{ID: "track", Name: "测试轨道", Muted: muted, Blocks: tc.blocks}))
				if (err == nil) != tc.valid || (!tc.valid && !strings.Contains(err.Error(), "重叠")) {
					t.Fatalf("muted=%v: %v", muted, err)
				}
			}
		})
	}
}

func overlappingExample() Config {
	c := Default()
	m := &c.Macros[0]
	m.Tracks[0].Blocks = append(m.Tracks[0].Blocks, m.Tracks[1].Blocks...)
	m.Tracks = m.Tracks[:1]
	return c
}

func TestSplitTracksPreservesContentTimesAndSource(t *testing.T) {
	c := overlappingExample()
	c.Macros[0].Tracks[0].Muted = true
	m := c.Macros[0]
	before, _ := json.Marshal(m)
	split, changed, err := SplitTracks(m)
	if err != nil || !changed || len(split.Tracks) != 2 {
		t.Fatalf("split failed: %+v %v", split, err)
	}
	after, _ := json.Marshal(m)
	if string(before) != string(after) {
		t.Fatal("source document changed")
	}
	blocks := map[string]Block{}
	for _, b := range m.Tracks[0].Blocks {
		blocks[b.ID] = b
	}
	for _, track := range split.Tracks {
		if !track.Muted || trackOverlaps(track) {
			t.Fatal("track state or spacing changed")
		}
		for _, b := range track.Blocks {
			if !reflect.DeepEqual(b, blocks[b.ID]) {
				t.Fatal("block content changed")
			}
			delete(blocks, b.ID)
		}
	}
	if len(blocks) != 0 || split.DurationMS != m.DurationMS || split.Trigger != m.Trigger {
		t.Fatal("content lost")
	}
	if _, err := Compile(split); err != nil {
		t.Fatal(err)
	}
	_, changed, err = SplitTracks(split)
	if err != nil || changed {
		t.Fatal("split not idempotent")
	}
}

func TestEditingCanReadOverlapButRuntimeAndSaveRejectIt(t *testing.T) {
	raw, _ := json.Marshal(overlappingExample())
	if _, _, err := Normalize(string(raw)); err == nil {
		t.Fatal("runtime accepted overlap")
	}
	normalized, cfg, err := ReadForEditing(string(raw))
	if err != nil || len(cfg.Macros[0].Tracks) != 1 || !strings.Contains(normalized, "sample_hold") {
		t.Fatal("overlapping file unavailable for repair", err)
	}
	cfg.Macros[0], _, err = SplitTracks(cfg.Macros[0])
	if err != nil {
		t.Fatal(err)
	}
	if _, err := cfg.Runtime(); err != nil {
		t.Fatal(err)
	}
}

func TestRecordingSplitsCoincidentScrollWithoutChangingTimes(t *testing.T) {
	m := FromRecording([]sequence.RecordedEvent{{Type: "scroll", AtMS: 100, Delta: 120}, {Type: "scroll", AtMS: 100, Delta: -120}})
	if len(m.Tracks) != 2 || m.Tracks[0].Blocks[0].AtMS != 100 || m.Tracks[1].Blocks[0].AtMS != 100 {
		t.Fatal("recorded timing changed")
	}
	if _, err := Compile(m); err != nil {
		t.Fatal(err)
	}
}

func TestSplitTrackLimitNeverDropsBlocks(t *testing.T) {
	m := one(Track{ID: "track", Blocks: []Block{}})
	for i := 0; i < 65; i++ {
		m.Tracks[0].Blocks = append(m.Tracks[0].Blocks, Block{ID: NewID("b"), Type: "scroll", Delta: 120})
	}
	result, _, err := SplitTracks(m)
	if err == nil || len(result.Tracks[0].Blocks) != 65 {
		t.Fatal("split silently dropped blocks")
	}
}
