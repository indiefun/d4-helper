// Package sequence is the execution contract. A plan is an ordered list of
// primitive input events and a duration. It knows nothing about tracks, JSON,
// editing, hotkeys, windows, or legacy macro modes.
package sequence

import "time"

type Event struct {
	Offset time.Duration
	Kind   string // key, move, scroll
	Key    string
	Down   bool
	X, Y   *int
	Delta  int
}
type Plan struct {
	Events   []Event
	Duration time.Duration
	Loop     bool
}
type RecordedEvent struct {
	Type  string `json:"type"`
	Key   string `json:"key"`
	AtMS  int64  `json:"at_ms"`
	X     *int   `json:"x,omitempty"`
	Y     *int   `json:"y,omitempty"`
	Delta int    `json:"delta,omitempty"`
}

func ValidKey(key string) bool {
	if len(key) == 1 && ((key[0] >= 'a' && key[0] <= 'z') || (key[0] >= '0' && key[0] <= '9')) {
		return true
	}
	for _, k := range []string{"left", "right", "middle", "xbutton1", "xbutton2", "space", "tab", "enter", "backspace", "shift", "ctrl", "alt", "capslock", "insert", "delete", "home", "end", "pageup", "pagedown", "up", "down", "left_arrow", "right_arrow", "pause", "esc", "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12"} {
		if key == k {
			return true
		}
	}
	return false
}
func ValidTrigger(key string) bool { return ValidKey(key) && key != "left" && key != "right" }
