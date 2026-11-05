package engine

import (
	"fmt"
	"sort"
	"time"
)

func (c *Core) Stop(now time.Time) {
	clear(c.active)
	clear(c.owners)
	c.retryReleases(now)
}
func (c *Core) Fail(err error, now time.Time) {
	c.fault = err.Error()
	c.armed = false
	c.Stop(now)
	c.CancelRecording()
	c.CaptureKind = ""
	c.Captured = ""
}
func (c *Core) retryReleases(now time.Time) {
	if len(c.physical) == 0 {
		c.retryAt = time.Time{}
		return
	}
	keys := make([]string, 0, len(c.physical))
	for key := range c.physical {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	c.tx = c.tx[:0]
	for _, key := range keys {
		c.tx = append(c.tx, Input{Key: key})
	}
	n, err := c.driver.Send(c.tx)
	if n < 0 {
		n = 0
	}
	if n > len(c.tx) {
		n = len(c.tx)
	}
	for _, e := range c.tx[:n] {
		delete(c.physical, e.Key)
	}
	if len(c.physical) > 0 {
		c.armed = false
		c.retryAt = now.Add(20 * time.Millisecond)
		if err != nil {
			c.fault = fmt.Sprintf("释放输入失败，将重试: %v", err)
		}
	} else {
		c.retryAt = time.Time{}
	}
}
func (c *Core) send(now time.Time) bool {
	if len(c.tx) == 0 {
		return true
	}
	n, err := c.driver.Send(c.tx)
	if n < 0 {
		n = 0
	}
	if n > len(c.tx) {
		n = len(c.tx)
	}
	for _, e := range c.tx[:n] {
		if e.Kind == "move" || e.Kind == "scroll" {
			continue
		}
		if e.Down {
			c.physical[e.Key] = true
		} else {
			delete(c.physical, e.Key)
		}
	}
	if err != nil || n != len(c.tx) {
		if err == nil {
			err = fmt.Errorf("SendInput 仅发送 %d/%d 条输入", n, len(c.tx))
		}
		c.Fail(err, now)
		return false
	}
	return true
}
