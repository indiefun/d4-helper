package timeline

import (
	"fmt"
	"sort"
	"time"

	"github.com/indiefun/d4-helper/go-desktop/internal/sequence"
)

// Compile merges all unmuted tracks on one absolute clock. Overlapping holds
// use reference counts, so an earlier block cannot release a later block's key.
// Every key block generates its own press and release events.
func Compile(m Definition) (sequence.Plan, error) {
	_, duration, err := m.timing()
	p := sequence.Plan{Duration: time.Duration(duration) * time.Millisecond, Loop: m.Loop}
	if err != nil {
		return p, err
	}
	if len(m.Tracks) > 64 {
		return p, fmt.Errorf("最多支持 64 条轨道")
	}
	type point struct {
		at           int64
		kind, key    string
		down         bool
		x, y         *int
		delta, order int
	}
	points := []point{}
	ids := map[string]bool{}
	moves := [][2]int64{}
	add := func(e point) error {
		if len(points) >= MaxEvents {
			return fmt.Errorf("展开后的事件过多")
		}
		e.order = len(points)
		points = append(points, e)
		return nil
	}
	for _, track := range m.Tracks {
		if track.ID == "" || ids[track.ID] {
			return p, fmt.Errorf("轨道 ID 重复或为空")
		}
		ids[track.ID] = true
		for _, b := range track.Blocks {
			if b.ID == "" || ids[b.ID] {
				return p, fmt.Errorf("动作 ID 重复或为空")
			}
			ids[b.ID] = true
			if (b.X == nil) != (b.Y == nil) || (b.FromX == nil) != (b.FromY == nil) {
				return p, fmt.Errorf("鼠标坐标 X/Y 必须成对")
			}
			switch b.Type {
			case "tap", "hold":
				if !sequence.ValidKey(b.Key) {
					return p, fmt.Errorf("未知按键 %s", b.Key)
				}
			case "move":
				if b.X == nil {
					return p, fmt.Errorf("鼠标移动需要目标坐标")
				}
				if b.DurationMS > 0 && b.FromX == nil {
					return p, fmt.Errorf("平滑移动需要起点坐标")
				}
			case "scroll":
				if b.Delta == 0 || b.Delta > 12000 || b.Delta < -12000 {
					return p, fmt.Errorf("滚轮步数超出范围")
				}
			default:
				return p, fmt.Errorf("未知动作 %s", b.Type)
			}
			if track.Muted {
				continue
			}
			at := b.AtMS
			switch b.Type {
			case "tap", "hold":
				if b.DurationMS < 1 {
					return p, fmt.Errorf("点击或按住时长至少为 1ms")
				}
				if err := add(point{at: at, kind: "key", key: b.Key, down: true, x: b.X, y: b.Y}); err != nil {
					return p, err
				}
				if err := add(point{at: at + b.DurationMS, kind: "key", key: b.Key}); err != nil {
					return p, err
				}
			case "scroll":
				if err := add(point{at: at, kind: "scroll", delta: b.Delta}); err != nil {
					return p, err
				}
			case "move":
				end := max(at+1, at+b.DurationMS)
				for _, span := range moves {
					if at < span[1] && end > span[0] {
						return p, fmt.Errorf("鼠标移动动作重叠，请移动到不同时间")
					}
				}
				moves = append(moves, [2]int64{at, max(at+1, end)})
				if len(b.Path) > 0 {
					previous := int64(-1)
					for _, w := range b.Path {
						if w.AtMS < 0 || w.AtMS > b.DurationMS || w.AtMS < previous {
							return p, fmt.Errorf("录制轨迹时间无效")
						}
						previous = w.AtMS
						x, y := w.X, w.Y
						if err := add(point{at: at + w.AtMS, kind: "move", x: &x, y: &y}); err != nil {
							return p, err
						}
					}
					break
				}
				samples := max(1, (b.DurationMS+7)/8)
				for n := int64(0); n <= samples; n++ {
					if b.DurationMS == 0 && n == 0 {
						continue
					}
					x, y := *b.X, *b.Y
					if b.DurationMS > 0 {
						x = *b.FromX + int(int64(*b.X-*b.FromX)*n/samples)
						y = *b.FromY + int(int64(*b.Y-*b.FromY)*n/samples)
					}
					offset := at + b.DurationMS*n/samples
					if err := add(point{at: offset, kind: "move", x: &x, y: &y}); err != nil {
						return p, err
					}
				}
			}
		}
		if trackOverlaps(track) {
			return p, fmt.Errorf("轨道“%s”中有重叠动作，请拆分到不同轨道", track.Name)
		}
	}
	sort.SliceStable(points, func(i, j int) bool {
		if points[i].at != points[j].at {
			return points[i].at < points[j].at
		}
		priority := func(e point) int {
			if e.kind == "key" && !e.down {
				return 0
			}
			if e.kind == "move" {
				return 1
			}
			if e.kind == "key" {
				return 2
			}
			return 3
		}
		if priority(points[i]) != priority(points[j]) {
			return priority(points[i]) < priority(points[j])
		}
		return points[i].order < points[j].order
	})
	held := map[string]int{}
	for _, e := range points {
		if e.kind != "key" {
			p.Events = append(p.Events, sequence.Event{Offset: time.Duration(e.at) * time.Millisecond, Kind: e.kind, X: e.x, Y: e.y, Delta: e.delta})
			continue
		}
		before := held[e.key]
		if e.down {
			held[e.key]++
		} else {
			held[e.key]--
		}
		if (before == 0) != (held[e.key] == 0) {
			p.Events = append(p.Events, sequence.Event{Offset: time.Duration(e.at) * time.Millisecond, Kind: "key", Key: e.key, Down: e.down, X: e.x, Y: e.y})
		}
	}
	return p, nil
}
