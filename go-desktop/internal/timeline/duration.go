package timeline

import (
	"encoding/json"
	"fmt"
)

const MaxDurationMS int64 = 3600000

// timing includes muted tracks so switching a track off preserves the timing
// of the remaining tracks. DurationMS is only a derived compatibility field.
func (m Definition) timing() (actionMS, playbackMS int64, err error) {
	for _, track := range m.Tracks {
		for _, b := range track.Blocks {
			if b.AtMS < 0 || b.DurationMS < 0 || b.AtMS > MaxDurationMS || b.DurationMS > MaxDurationMS-b.AtMS {
				return 0, 0, fmt.Errorf("动作时间必须在 0ms–1 小时内")
			}
			actionMS = max(actionMS, b.AtMS+b.DurationMS)
		}
	}
	if m.LoopWaitMS < 0 || m.LoopWaitMS > MaxDurationMS {
		return 0, 0, fmt.Errorf("每轮结束后等待应为 0ms–1 小时")
	}
	playbackMS = actionMS
	if m.Loop {
		if m.LoopWaitMS > MaxDurationMS-actionMS {
			return 0, 0, fmt.Errorf("动作时长与每轮等待之和不能超过 1 小时")
		}
		playbackMS += m.LoopWaitMS
	}
	// A zero-time event and an empty draft still need a positive engine duration.
	return actionMS, max(1, playbackMS), nil
}

// UnmarshalJSON upgrades old schema-3 files without writing them back. Their
// trailing silence becomes a loop wait; single runs finish at the last action.
func (m *Definition) UnmarshalJSON(data []byte) error {
	type plain Definition
	var decoded struct {
		plain
		LoopWaitMS *int64 `json:"loop_wait_ms"`
	}
	if err := json.Unmarshal(data, &decoded); err != nil {
		return err
	}
	*m = Definition(decoded.plain)
	if decoded.LoopWaitMS != nil {
		m.LoopWaitMS = *decoded.LoopWaitMS
	} else if m.Loop {
		actionMS, _, err := m.timing()
		if err != nil {
			return err
		}
		m.LoopWaitMS = max(0, m.DurationMS-actionMS)
	}
	_, duration, err := m.timing()
	if err != nil {
		return err
	}
	m.DurationMS = duration
	return nil
}
