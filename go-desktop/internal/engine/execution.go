package engine

import (
	"fmt"
	"time"
)

func (c *Core) hasOwner(key string) bool { return len(c.owners[key]) > 0 }
func (c *Core) own(id, key string, on bool) {
	if on {
		if c.owners[key] == nil {
			c.owners[key] = map[string]bool{}
		}
		c.owners[key][id] = true
	} else {
		delete(c.owners[key], id)
		if len(c.owners[key]) == 0 {
			delete(c.owners, key)
		}
	}
}
func (c *Core) execute(id string, g group, now time.Time) bool {
	c.tx = c.tx[:0]
	for i := 0; i < len(g.events); i++ {
		e := g.events[i]
		if e.Kind == "move" || e.Kind == "scroll" {
			c.tx = append(c.tx, Input{Kind: e.Kind, X: e.X, Y: e.Y, Delta: e.Delta})
			continue
		}
		// A zero-duration tap must remain an atomic pair, even if another macro
		// holds this key. Restore that other owner's down state after the pair.
		if e.Down && i+1 < len(g.events) && !g.events[i+1].Down && g.events[i+1].Key == e.Key {
			c.tx = append(c.tx, Input{Key: e.Key, Down: true, X: e.X, Y: e.Y}, Input{Key: e.Key, X: g.events[i+1].X, Y: g.events[i+1].Y})
			i++
			if c.hasOwner(e.Key) {
				c.tx = append(c.tx, Input{Key: e.Key, Down: true})
			}
			continue
		}
		before := c.hasOwner(e.Key)
		c.own(id, e.Key, e.Down)
		after := c.hasOwner(e.Key)
		if before != after {
			c.tx = append(c.tx, Input{Key: e.Key, Down: e.Down, X: e.X, Y: e.Y})
		}
	}
	return c.send(now)
}
func (c *Core) deactivate(id string, now time.Time) {
	delete(c.active, id)
	c.tx = c.tx[:0]
	for key, owners := range c.owners {
		if owners[id] {
			c.own(id, key, false)
			if !c.hasOwner(key) && c.physical[key] {
				c.tx = append(c.tx, Input{Key: key})
			}
		}
	}
	c.send(now)
}
func (c *Core) Toggle(id string, now time.Time) error {
	if !c.armed || !c.target || c.recordState != "idle" || c.CaptureKind != "" {
		return fmt.Errorf("请先启用引擎并切到目标窗口；录制和按键录入时不能运行宏")
	}
	if c.active[id] != nil {
		c.deactivate(id, now)
		return nil
	}
	p, ok := c.programs[id]
	if !ok {
		return fmt.Errorf("宏未启用或没有有效动作")
	}
	if len(p.Events) == 0 {
		return fmt.Errorf("先把动作拖到时间轴，再运行这个宏")
	}
	c.active[id] = &running{id: id, program: p, groups: c.groups[id], start: now, end: now.Add(p.Duration)}
	c.Tick(now)
	return nil
}
func (c *Core) Tick(now time.Time) {
	if !c.retryAt.IsZero() && !now.Before(c.retryAt) {
		c.retryReleases(now)
	}
	if c.recordState == "countdown" && !now.Before(c.recordAt) {
		c.recordState = "recording"
		c.recordEnd = c.recordAt.Add(time.Duration(c.Config.MaxSeconds) * time.Second)
		c.recordHeld = map[string]bool{}
	}
	if c.recordState == "recording" && !now.Before(c.recordEnd) {
		c.finishRecording(now)
	}
	if !c.armed || !c.target {
		return
	}
	// Stable configuration order makes simultaneous macros deterministic.
	for _, m := range c.Config.Macros {
		run := c.active[m.ID]
		if run == nil {
			continue
		}
		// Preserve recorded waits after a stall rather than emitting a burst.
		if run.index < len(run.groups) {
			scheduled := run.start.Add(run.groups[run.index].at)
			if late := now.Sub(scheduled); late > time.Millisecond {
				run.start = run.start.Add(late)
				run.end = run.end.Add(late)
			}
		}
		for run.index < len(run.groups) && !now.Before(run.start.Add(run.groups[run.index].at)) {
			if !c.execute(run.id, run.groups[run.index], now) {
				return
			}
			run.index++
		}
		if run.index < len(run.groups) || now.Before(run.end) {
			continue
		}
		if !run.program.Loop {
			c.deactivate(run.id, now)
			continue
		}
		// Skip expired cycles, never produce an unbounded catch-up burst.
		start := run.end
		if !start.Add(run.program.Duration).After(now) {
			start = now
		}
		run.start = start
		run.end = start.Add(run.program.Duration)
		run.index = 0
		// First event in the new cycle can be due now; process on next wake.
	}
}
func (c *Core) Next() time.Time {
	due := c.retryAt
	add := func(t time.Time) {
		if !t.IsZero() && (due.IsZero() || t.Before(due)) {
			due = t
		}
	}
	if c.recordState == "countdown" {
		add(c.recordAt)
	}
	if c.recordState == "recording" {
		add(c.recordEnd)
	}
	if c.armed && c.target {
		for _, run := range c.active {
			if run.index < len(run.groups) {
				add(run.start.Add(run.groups[run.index].at))
			} else {
				add(run.end)
			}
		}
	}
	return due
}
