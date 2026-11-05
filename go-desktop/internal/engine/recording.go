package engine

import (
	"fmt"
	"github.com/indiefun/d4-helper/go-desktop/internal/sequence"
	"sort"
	"time"
)

func (c *Core) StartRecording(now time.Time) error {
	if !c.target || !c.armed {
		return fmt.Errorf("请先启用引擎并切到游戏窗口")
	}
	c.Stop(now)
	if len(c.physical) > 0 {
		return fmt.Errorf("输入尚未完全释放，不能开始录制")
	}
	c.recordState = "countdown"
	c.recordAt = now.Add(time.Duration(c.Config.Countdown) * time.Second)
	c.recording = nil
	c.recordHeld = map[string]bool{}
	c.Tick(now)
	return nil
}
func (c *Core) capture(e PhysicalEvent) {
	if e.Kind == "move" || e.Kind == "scroll" {
		at := e.At.Sub(c.recordAt).Milliseconds()
		if at < 0 {
			return
		}
		if e.Kind == "move" && len(c.recording) > 0 {
			last := c.recording[len(c.recording)-1]
			if last.Type == "move" && at-last.AtMS < 16 {
				return
			}
		}
		c.recording = append(c.recording, sequence.RecordedEvent{Type: e.Kind, AtMS: at, X: e.X, Y: e.Y, Delta: e.Delta})
		if len(c.recording) >= 10000 {
			c.finishRecording(e.At)
		}
		return
	}
	if !sequence.ValidKey(e.Key) || e.Key == c.Config.EmergencyTrigger {
		return
	}
	if e.Down {
		if c.recordHeld[e.Key] {
			return
		}
		c.recordHeld[e.Key] = true
	} else {
		if !c.recordHeld[e.Key] {
			return
		}
		delete(c.recordHeld, e.Key)
	}
	at := e.At.Sub(c.recordAt).Milliseconds()
	if at < 0 {
		return
	}
	kind := "key_up"
	if e.Down {
		kind = "key_down"
	}
	c.recording = append(c.recording, sequence.RecordedEvent{Type: kind, Key: e.Key, AtMS: at, X: e.X, Y: e.Y})
	if len(c.recording) >= 10000 {
		c.finishRecording(e.At)
	}
}
func (c *Core) finishRecording(now time.Time) {
	if len(c.recording) > 0 {
		first := c.recording[0].AtMS
		for i := range c.recording {
			c.recording[i].AtMS -= first
		}
		last := c.recording[len(c.recording)-1].AtMS
		keys := []string{}
		for key := range c.recordHeld {
			keys = append(keys, key)
		}
		sort.Strings(keys)
		for _, key := range keys {
			c.recording = append(c.recording, sequence.RecordedEvent{Type: "key_up", Key: key, AtMS: last + 10})
		}
		if len(c.Recordings) < 32 {
			c.Recordings = append(c.Recordings, c.recording)
		} else {
			c.fault = "未处理的录制过多，请打开配置窗口保存"
			c.armed = false
		}
	}
	c.CancelRecording()
}
func (c *Core) FinishRecording(now time.Time) {
	if c.recordState == "recording" {
		c.finishRecording(now)
	} else {
		c.CancelRecording()
	}
}
func (c *Core) CancelRecording() { c.recordState = "idle"; c.recording = nil; c.recordHeld = nil }
