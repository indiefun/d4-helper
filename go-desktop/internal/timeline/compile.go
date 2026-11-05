package timeline

import (
	"fmt"
	"sort"
	"time"

	"github.com/indiefun/d4-helper/go-desktop/internal/sequence"
)

// Compile merges all unmuted tracks on one absolute clock. Overlapping holds
// use reference counts, so an earlier block cannot release a later block's key.
// Explicit down/up blocks are validated together across all tracks.
func Compile(m Definition) (sequence.Plan, error) {
	p := sequence.Plan{Duration: time.Duration(m.DurationMS) * time.Millisecond, Loop: m.Loop}
	if m.DurationMS < 1 || m.DurationMS > 3600000 {
		return p, fmt.Errorf("作品长度应为 1ms–1 小时")
	}
	if len(m.Tracks) > 64 {
		return p, fmt.Errorf("最多支持 64 条轨道")
	}
	type point struct {
		at               int64
		kind, key, token string
		down             bool
		x, y             *int
		delta, order     int
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
			if b.AtMS < 0 || b.DurationMS < 0 || b.AtMS+b.DurationMS > m.DurationMS || b.RepeatMS < 0 {
				return p, fmt.Errorf("动作超出时间轴范围")
			}
			if b.AtMS > m.DurationMS || b.DurationMS > m.DurationMS {
				return p, fmt.Errorf("动作超出时间轴范围")
			}
			if (b.X == nil) != (b.Y == nil) || (b.FromX == nil) != (b.FromY == nil) {
				return p, fmt.Errorf("鼠标坐标 X/Y 必须成对")
			}
			if track.Muted {
				continue
			}
			if b.RepeatMS > 0 && (b.Type != "tap" || b.RepeatMS < max(1, b.DurationMS)) {
				return p, fmt.Errorf("仅点击支持间隔重复，间隔不能短于按住时长")
			}
			switch b.Type {
			case "tap", "hold", "down", "up":
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
			for at := b.AtMS; at+b.DurationMS <= m.DurationMS; at += b.RepeatMS {
				token := fmt.Sprintf("%s:%d", b.ID, at)
				push := func(q point) error { return add(q) }
				switch b.Type {
				case "tap", "hold":
					if b.DurationMS < 1 {
						return p, fmt.Errorf("点击或按住时长至少为 1ms")
					}
					if err := push(point{at: at, kind: "key", key: b.Key, token: token, down: true, x: b.X, y: b.Y}); err != nil {
						return p, err
					}
					if err := push(point{at: at + b.DurationMS, kind: "key", key: b.Key, token: token}); err != nil {
						return p, err
					}
				case "down", "up":
					if err := push(point{at: at, kind: "key", key: b.Key, token: "explicit:" + b.Key, down: b.Type == "down", x: b.X, y: b.Y}); err != nil {
						return p, err
					}
				case "scroll":
					if err := push(point{at: at, kind: "scroll", delta: b.Delta}); err != nil {
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
							if err := push(point{at: at + w.AtMS, kind: "move", x: &x, y: &y}); err != nil {
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
						if err := push(point{at: offset, kind: "move", x: &x, y: &y}); err != nil {
							return p, err
						}
					}
				}
				if b.RepeatMS == 0 {
					break
				}
			}
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
	held := map[string]map[string]bool{}
	for _, e := range points {
		if e.kind != "key" {
			p.Events = append(p.Events, sequence.Event{Offset: time.Duration(e.at) * time.Millisecond, Kind: e.kind, X: e.x, Y: e.y, Delta: e.delta})
			continue
		}
		if held[e.key] == nil {
			held[e.key] = map[string]bool{}
		}
		owners := held[e.key]
		before := len(owners)
		if e.down {
			if owners[e.token] {
				return p, fmt.Errorf("%s 重复按下，请添加抬起动作", e.key)
			}
			owners[e.token] = true
		} else {
			if !owners[e.token] {
				return p, fmt.Errorf("%s 的抬起之前没有对应按下", e.key)
			}
			delete(owners, e.token)
		}
		if (before == 0) != (len(owners) == 0) {
			p.Events = append(p.Events, sequence.Event{Offset: time.Duration(e.at) * time.Millisecond, Kind: "key", Key: e.key, Down: e.down, X: e.x, Y: e.y})
		}
	}
	for key, owners := range held {
		if len(owners) > 0 {
			return p, fmt.Errorf("%s 缺少抬起动作；可以改用带时长的按住块", key)
		}
	}
	return p, nil
}
