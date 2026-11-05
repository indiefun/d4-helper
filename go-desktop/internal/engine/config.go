package engine

import (
	"fmt"
	"github.com/indiefun/d4-helper/go-desktop/internal/sequence"
	"strings"
)

// Config contains only execution plans and controller settings. The editor's
// track/block schema is compiled outside the runtime.
type Macro struct {
	ID, Name, Trigger string
	Enabled           bool
	Plan              sequence.Plan
}
type Config struct {
	Macros                             []Macro
	WindowTitle, Process               string
	Overlay                            bool
	Opacity                            float64
	AvoidMouse                         bool
	AvoidDistance                      int
	RecordingTrigger, EmergencyTrigger string
	Countdown, MaxSeconds              int
}

func (c Config) Matches(title, process string) bool {
	return (c.WindowTitle != "" || c.Process != "") && (c.WindowTitle == "" || strings.Contains(strings.ToLower(title), strings.ToLower(c.WindowTitle))) && (c.Process == "" || strings.EqualFold(c.Process, process))
}
func (c Config) Validate() error {
	ids, keys := map[string]bool{}, map[string]bool{}
	for _, m := range c.Macros {
		if m.ID == "" || ids[m.ID] {
			return fmt.Errorf("重复的执行计划 ID")
		}
		ids[m.ID] = true
		if m.Enabled && m.Trigger != "none" {
			if !sequence.ValidTrigger(m.Trigger) || keys[m.Trigger] {
				return fmt.Errorf("快捷键无效或重复: %s", m.Trigger)
			}
			keys[m.Trigger] = true
		}
		previous := int64(-1)
		for _, e := range m.Plan.Events {
			if e.Offset.Nanoseconds() < previous || e.Offset < 0 || e.Offset > m.Plan.Duration {
				return fmt.Errorf("执行事件时间无效")
			}
			previous = e.Offset.Nanoseconds()
			switch e.Kind {
			case "key":
				if !sequence.ValidKey(e.Key) {
					return fmt.Errorf("无效的原始按键事件")
				}
			case "move":
				if e.X == nil || e.Y == nil {
					return fmt.Errorf("移动事件缺少坐标")
				}
			case "scroll":
				if e.Delta == 0 {
					return fmt.Errorf("滚动量为零")
				}
			default:
				return fmt.Errorf("不支持的原始事件类型 %s", e.Kind)
			}
		}
		if m.Plan.Duration <= 0 {
			return fmt.Errorf("执行计划时长必须大于零")
		}
	}
	return nil
}
