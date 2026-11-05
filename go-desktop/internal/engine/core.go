// Package engine owns all macro state on a single scheduler thread. Core is
// independent of Windows and accepts explicit times for deterministic tests.
package engine

import (
	"fmt"
	"time"

	"github.com/indiefun/d4-helper/go-desktop/internal/sequence"
)

type Input struct {
	Kind  string
	Delta int
	Key   string
	Down  bool
	X, Y  *int
}
type PhysicalEvent struct {
	Kind  string
	Delta int
	Key   string
	Down  bool
	At    time.Time
	X, Y  *int
}
type Driver interface{ Send([]Input) (int, error) }
type group struct {
	at     time.Duration
	events []sequence.Event
}
type running struct {
	id      string
	program sequence.Plan
	groups  []group
	index   int
	start   time.Time
	end     time.Time
}
type MacroStatus struct {
	ID         string `json:"id"`
	Name       string `json:"name"`
	Trigger    string `json:"trigger"`
	Active     bool   `json:"active"`
	PositionMS int64  `json:"position_ms"`
	DurationMS int64  `json:"duration_ms"`
}
type Snapshot struct {
	TargetActive       bool          `json:"target_active"`
	Armed              bool          `json:"armed"`
	Fault              string        `json:"fault"`
	PendingReleases    int           `json:"pending_releases"`
	Macros             []MacroStatus `json:"macros"`
	Recording          string        `json:"recording"`
	RecordingElapsedMS int64         `json:"recording_elapsed_ms"`
	RecordingCount     int           `json:"recording_count"`
	Countdown          int           `json:"countdown"`
	Capture            string        `json:"capture"`
}

type Core struct {
	Config              Config
	driver              Driver
	programs            map[string]sequence.Plan
	groups              map[string][]group
	active              map[string]*running
	owners              map[string]map[string]bool
	physical            map[string]bool
	keys                map[string]bool
	target, armed       bool
	fault               string
	retryAt             time.Time
	tx                  []Input
	recordState         string
	recordAt, recordEnd time.Time
	recording           []sequence.RecordedEvent
	recordHeld          map[string]bool
	Recordings          [][]sequence.RecordedEvent
	CaptureKind         string
	Captured            string
}

func New(driver Driver) *Core {
	return &Core{driver: driver, programs: map[string]sequence.Plan{}, groups: map[string][]group{}, active: map[string]*running{}, owners: map[string]map[string]bool{}, physical: map[string]bool{}, keys: map[string]bool{}, recordState: "idle", tx: make([]Input, 0, 128)}
}

func (c *Core) Apply(config Config, held map[string]bool, now time.Time) error {
	if err := config.Validate(); err != nil {
		return err
	}
	programs := map[string]sequence.Plan{}
	groups := map[string][]group{}
	for _, m := range config.Macros {
		if !m.Enabled {
			continue
		}
		p := m.Plan
		programs[m.ID] = p
		for _, e := range p.Events {
			g := groups[m.ID]
			if len(g) == 0 || g[len(g)-1].at != e.Offset {
				g = append(g, group{at: e.Offset})
			}
			g[len(g)-1].events = append(g[len(g)-1].events, e)
			groups[m.ID] = g
		}
	}
	c.Stop(now)
	c.CancelRecording()
	c.CaptureKind = ""
	c.Captured = ""
	c.Config = config
	c.programs = programs
	c.groups = groups
	c.keys = copyKeys(held)
	if len(c.physical) > 0 {
		c.armed = false
		return fmt.Errorf("部分按键尚未释放，无法应用配置")
	}
	c.fault = ""
	return nil
}
func copyKeys(keys map[string]bool) map[string]bool {
	r := map[string]bool{}
	for k, v := range keys {
		r[k] = v
	}
	return r
}
