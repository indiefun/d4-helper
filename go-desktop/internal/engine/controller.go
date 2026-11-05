package engine

import (
	"fmt"
	"github.com/indiefun/d4-helper/go-desktop/internal/sequence"
	"time"
)

func (c *Core) Arm(on bool, held map[string]bool, now time.Time) error {
	c.Stop(now)
	c.CancelRecording()
	c.CaptureKind = ""
	c.Captured = ""
	c.armed = false
	c.keys = copyKeys(held)
	if on && len(c.physical) > 0 {
		return fmt.Errorf("仍有按键释放失败，请先重试停止")
	}
	c.armed = on
	if on {
		c.fault = ""
	}
	return nil
}
func (c *Core) Focus(active bool, held map[string]bool, now time.Time) {
	if c.target == active {
		return
	}
	c.target = active
	c.Stop(now)
	c.CancelRecording()
	c.keys = copyKeys(held)
}
func (c *Core) Handle(e PhysicalEvent) {
	if e.Kind == "move" || e.Kind == "scroll" {
		if c.target && c.armed && c.recordState == "countdown" && !e.At.Before(c.recordAt) {
			c.recordState = "recording"
			c.recordEnd = c.recordAt.Add(time.Duration(c.Config.MaxSeconds) * time.Second)
			c.recordHeld = map[string]bool{}
		}
		if c.target && c.armed && c.recordState == "recording" {
			if !e.At.Before(c.recordEnd) {
				c.finishRecording(e.At)
				return
			}
			c.capture(e)
		}
		return
	}
	previous := c.keys[e.Key]
	c.keys[e.Key] = e.Down
	if e.Down && previous {
		return
	}
	if e.Down && e.Key == c.Config.EmergencyTrigger {
		c.armed = false
		c.Stop(e.At)
		c.CancelRecording()
		c.CaptureKind = ""
		c.Captured = ""
		return
	}
	if c.CaptureKind != "" {
		if e.Down {
			if e.Key == "esc" {
				c.Captured = "cancelled"
			} else if (c.CaptureKind == "trigger" && sequence.ValidTrigger(e.Key)) || (c.CaptureKind == "key" && sequence.ValidKey(e.Key)) {
				c.Captured = e.Key
			}
			if c.Captured != "" {
				c.CaptureKind = ""
			}
		}
		return
	}
	if !c.target || !c.armed {
		return
	}
	if c.recordState == "countdown" && !e.At.Before(c.recordAt) {
		c.recordState = "recording"
		c.recordEnd = c.recordAt.Add(time.Duration(c.Config.MaxSeconds) * time.Second)
		c.recordHeld = map[string]bool{}
	}
	if c.recordState == "recording" && !e.At.Before(c.recordEnd) {
		c.finishRecording(e.At)
		return
	}
	if e.Key == c.Config.RecordingTrigger {
		if e.Down {
			if c.recordState == "idle" {
				c.StartRecording(e.At)
			} else if c.recordState == "recording" {
				c.finishRecording(e.At)
			} else {
				c.CancelRecording()
			}
		}
		return
	}
	if c.recordState == "recording" {
		c.capture(e)
		return
	}
	if c.recordState != "idle" || !e.Down {
		return
	}
	for _, m := range c.Config.Macros {
		if m.Enabled && m.Trigger == e.Key {
			_ = c.Toggle(m.ID, e.At)
			return
		}
	}
}
func (c *Core) BeginCapture(kind string, now time.Time) error {
	if kind != "trigger" && kind != "key" {
		return fmt.Errorf("无效的录入类型")
	}
	c.Stop(now)
	c.CancelRecording()
	c.Captured = ""
	c.CaptureKind = kind
	return nil
}
func (c *Core) Snapshot(now time.Time) Snapshot {
	s := Snapshot{TargetActive: c.target, Armed: c.armed, Fault: c.fault, PendingReleases: len(c.physical), Recording: c.recordState, RecordingCount: len(c.recording), Capture: c.Captured, Macros: []MacroStatus{}}
	if c.recordState == "countdown" {
		s.Countdown = max(0, int(c.recordAt.Sub(now).Seconds())+1)
	}
	if c.recordState == "recording" {
		s.RecordingElapsedMS = now.Sub(c.recordAt).Milliseconds()
	}
	for _, m := range c.Config.Macros {
		if m.Enabled {
			position := int64(0)
			if run := c.active[m.ID]; run != nil {
				position = max(0, min(run.program.Duration.Milliseconds(), now.Sub(run.start).Milliseconds()))
			}
			s.Macros = append(s.Macros, MacroStatus{ID: m.ID, Name: m.Name, Trigger: m.Trigger, Active: c.active[m.ID] != nil, PositionMS: position, DurationMS: m.Plan.Duration.Milliseconds()})
		}
	}
	return s
}
