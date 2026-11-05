// Package timeline is the authoring model and compiler. Tracks are visual
// containers sharing one clock; only compiled primitive events enter engine.
package timeline

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"strings"

	"github.com/indiefun/d4-helper/go-desktop/internal/engine"
	"github.com/indiefun/d4-helper/go-desktop/internal/sequence"
)

const SchemaVersion = 3
const MaxEvents = 100000

type Block struct {
	ID         string     `json:"id"`
	Type       string     `json:"type"`
	AtMS       int64      `json:"at_ms"`
	DurationMS int64      `json:"duration_ms"`
	Key        string     `json:"key,omitempty"`
	X          *int       `json:"x,omitempty"`
	Y          *int       `json:"y,omitempty"`
	FromX      *int       `json:"from_x,omitempty"`
	FromY      *int       `json:"from_y,omitempty"`
	Delta      int        `json:"delta,omitempty"`
	RepeatMS   int64      `json:"repeat_ms,omitempty"`
	Path       []Waypoint `json:"path,omitempty"`
}
type Waypoint struct {
	AtMS int64 `json:"at_ms"`
	X    int   `json:"x"`
	Y    int   `json:"y"`
}
type Track struct {
	ID     string  `json:"id"`
	Name   string  `json:"name"`
	Muted  bool    `json:"muted"`
	Blocks []Block `json:"blocks"`
}
type Definition struct {
	ID         string  `json:"id"`
	Name       string  `json:"name"`
	Enabled    bool    `json:"enabled"`
	Trigger    string  `json:"trigger"`
	DurationMS int64   `json:"duration_ms"`
	Loop       bool    `json:"loop"`
	Tracks     []Track `json:"tracks"`
}
type Config struct {
	Version          int          `json:"schema_version"`
	Macros           []Definition `json:"macros"`
	WindowTitle      string       `json:"window_title_contains"`
	Process          string       `json:"process_name"`
	Overlay          bool         `json:"overlay_enabled"`
	Opacity          float64      `json:"overlay_opacity"`
	AvoidMouse       bool         `json:"overlay_avoid_mouse"`
	AvoidDistance    int          `json:"overlay_avoid_distance"`
	RecordingTrigger string       `json:"recording_trigger"`
	Countdown        int          `json:"recording_countdown_sec"`
	MaxSeconds       int          `json:"recording_max_seconds"`
	EmergencyTrigger string       `json:"emergency_trigger"`
}

func NewID(prefix string) string {
	var b [8]byte
	if _, err := rand.Read(b[:]); err != nil {
		panic(err)
	}
	return prefix + "_" + hex.EncodeToString(b[:])
}
func Default() Config {
	return Config{Version: 3, WindowTitle: "暗黑破坏神IV", Process: "Diablo IV.exe", Overlay: true, Opacity: .6, AvoidMouse: true, AvoidDistance: 72, RecordingTrigger: "f12", Countdown: 3, MaxSeconds: 60, EmergencyTrigger: "pause", Macros: []Definition{
		{ID: "starter", Name: "我的第一个宏", Enabled: true, Trigger: "f1", DurationMS: 2000, Tracks: []Track{
			{ID: "track_keys", Name: "键盘", Blocks: []Block{{ID: "sample_click", Type: "tap", Key: "2", AtMS: 200, DurationMS: 60}, {ID: "sample_click2", Type: "tap", Key: "1", AtMS: 800, DurationMS: 60}}},
			{ID: "track_mouse", Name: "鼠标", Blocks: []Block{{ID: "sample_hold", Type: "hold", Key: "right", AtMS: 200, DurationMS: 1200}}},
			{ID: "track_extra", Name: "更多动作", Blocks: []Block{}},
		}},
	}}
}
func Normalize(raw string) (string, Config, error) {
	var header struct {
		Version int `json:"schema_version"`
	}
	raw = strings.TrimPrefix(raw, "\ufeff")
	if err := json.Unmarshal([]byte(raw), &header); err != nil {
		return "", Config{}, fmt.Errorf("配置 JSON 无效: %w", err)
	}
	if header.Version != 3 {
		return "", Config{}, fmt.Errorf("这是旧版配置。新工作台使用独立的多轨时间轴文件，请创建新作品；旧文件保持不变")
	}
	c := Default()
	c.Macros = nil
	if err := json.Unmarshal([]byte(raw), &c); err != nil {
		return "", c, err
	}
	if c.Macros == nil {
		return "", c, fmt.Errorf("作品列表必须是数组")
	}
	if _, err := c.Runtime(); err != nil {
		return "", c, err
	}
	b, err := json.Marshal(c)
	return string(b), c, err
}
func (c Config) Runtime() (engine.Config, error) {
	r := engine.Config{WindowTitle: c.WindowTitle, Process: c.Process, Overlay: c.Overlay, Opacity: c.Opacity, AvoidMouse: c.AvoidMouse, AvoidDistance: c.AvoidDistance, RecordingTrigger: c.RecordingTrigger, EmergencyTrigger: c.EmergencyTrigger, Countdown: c.Countdown, MaxSeconds: c.MaxSeconds}
	if strings.TrimSpace(c.WindowTitle) == "" && strings.TrimSpace(c.Process) == "" {
		return r, fmt.Errorf("请指定要使用宏的窗口标题或进程")
	}
	if c.Opacity < .1 || c.Opacity > 1 || c.AvoidDistance < 16 || c.AvoidDistance > 400 || c.Countdown < 0 || c.Countdown > 30 || c.MaxSeconds < 1 || c.MaxSeconds > 3600 {
		return r, fmt.Errorf("窗口或录制设置超出范围")
	}
	ids, names, triggers := map[string]bool{}, map[string]bool{}, map[string]bool{}
	if len(c.Macros) > 128 {
		return r, fmt.Errorf("最多支持 128 个作品")
	}
	total := 0
	for _, m := range c.Macros {
		if m.ID == "" || ids[m.ID] || strings.TrimSpace(m.Name) == "" || names[m.Name] {
			return r, fmt.Errorf("作品名称或 ID 为空、重复")
		}
		ids[m.ID] = true
		names[m.Name] = true
		if m.Trigger != "none" && !sequence.ValidTrigger(m.Trigger) {
			return r, fmt.Errorf("%s 的快捷键无效", m.Name)
		}
		if m.Enabled && m.Trigger != "none" {
			if triggers[m.Trigger] {
				return r, fmt.Errorf("快捷键 %s 被多个作品使用", m.Trigger)
			}
			triggers[m.Trigger] = true
		}
		p, err := Compile(m)
		if err != nil {
			return r, fmt.Errorf("%s：%w", m.Name, err)
		}
		total += len(p.Events)
		if total > MaxEvents {
			return r, fmt.Errorf("动作总数过多")
		}
		r.Macros = append(r.Macros, engine.Macro{ID: m.ID, Name: m.Name, Enabled: m.Enabled, Trigger: m.Trigger, Plan: p})
	}
	for _, key := range []string{c.RecordingTrigger, c.EmergencyTrigger} {
		if key == "none" {
			continue
		}
		if !sequence.ValidTrigger(key) || triggers[key] {
			return r, fmt.Errorf("录制 / 停止快捷键无效或重复: %s", key)
		}
		triggers[key] = true
	}
	if c.EmergencyTrigger == "none" {
		return r, fmt.Errorf("请设置停止快捷键")
	}
	return r, r.Validate()
}
func FromRecording(events []sequence.RecordedEvent) Definition {
	m := Definition{ID: NewID("macro"), Name: "新录制", Enabled: true, Trigger: "none", DurationMS: 2000, Tracks: []Track{}}
	lanes := map[string]int{}
	down := map[string]sequence.RecordedEvent{}
	add := func(key string, b Block) {
		index, ok := lanes[key]
		if !ok {
			index = len(m.Tracks)
			lanes[key] = index
			m.Tracks = append(m.Tracks, Track{ID: NewID("track"), Name: key, Blocks: []Block{}})
		}
		m.Tracks[index].Blocks = append(m.Tracks[index].Blocks, b)
		end := b.AtMS + b.DurationMS
		if end+200 > m.DurationMS {
			m.DurationMS = end + 200
		}
	}
	var stroke []sequence.RecordedEvent
	flushStroke := func() {
		if len(stroke) == 0 {
			return
		}
		first, last := stroke[0], stroke[len(stroke)-1]
		b := Block{ID: NewID("block"), Type: "move", AtMS: first.AtMS, DurationMS: last.AtMS - first.AtMS, X: last.X, Y: last.Y, FromX: first.X, FromY: first.Y}
		for _, e := range stroke {
			b.Path = append(b.Path, Waypoint{AtMS: e.AtMS - first.AtMS, X: *e.X, Y: *e.Y})
		}
		add("鼠标移动", b)
		stroke = nil
	}
	for _, e := range events {
		if e.Type == "move" {
			if e.X == nil || e.Y == nil {
				continue
			}
			if len(stroke) > 0 && e.AtMS-stroke[len(stroke)-1].AtMS > 120 {
				flushStroke()
			}
			stroke = append(stroke, e)
			continue
		}
		if e.Type == "scroll" {
			add("滚轮", Block{ID: NewID("block"), Type: "scroll", AtMS: e.AtMS, Delta: e.Delta})
			continue
		}
		if e.Type == "key_down" {
			down[e.Key] = e
			continue
		}
		if start, ok := down[e.Key]; ok {
			delete(down, e.Key)
			add(e.Key, Block{ID: NewID("block"), Type: "hold", Key: e.Key, AtMS: start.AtMS, DurationMS: max(1, e.AtMS-start.AtMS), X: start.X, Y: start.Y})
		}
	}
	flushStroke()
	return m
}
