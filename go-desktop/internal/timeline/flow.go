package timeline

import (
	"fmt"
	"sort"

	"github.com/indiefun/d4-helper/go-desktop/internal/sequence"
)

// FlowNode has a single entry and exit. A sequence sums child durations,
// parallel waits for its longest branch, repeat includes only inter-round gaps.
// No authoring structure is interpreted on the runtime input thread.
type FlowNode struct {
	ID        string      `json:"id"`
	Type      string      `json:"type"`
	Items     []*FlowNode `json:"items,omitempty"`
	Branches  []*FlowNode `json:"branches,omitempty"`
	Body      *FlowNode   `json:"body,omitempty"`
	Count     int64       `json:"count,omitempty"`
	GapMS     int64       `json:"gap_ms,omitempty"`
	WaitMS    int64       `json:"wait_ms,omitempty"`
	Action    *Block      `json:"action,omitempty"`
	Disabled  bool        `json:"disabled,omitempty"`
	Collapsed bool        `json:"collapsed,omitempty"`
}

type flowStats struct{ duration, actions, events int64 }

func flowTracks(root *FlowNode) ([]Track, int64, error) {
	if root == nil || root.Type != "sequence" {
		return nil, 0, fmt.Errorf("流程根节点必须是顺序范围")
	}
	stats := map[*FlowNode]flowStats{}
	ids := map[string]bool{}
	var measure func(*FlowNode, int) (flowStats, error)
	measure = func(n *FlowNode, depth int) (flowStats, error) {
		var result flowStats
		if n == nil || n.ID == "" || len(n.ID) > 128 || ids[n.ID] {
			return result, fmt.Errorf("范围或动作 ID 为空、重复")
		}
		if depth > 32 || len(ids) >= MaxGraphNodes {
			return result, fmt.Errorf("流程嵌套过深或超过 4096 个节点")
		}
		ids[n.ID] = true
		children := n.Items
		switch n.Type {
		case "sequence":
		case "parallel":
			if len(n.Branches) < 1 || len(n.Branches) > 64 {
				return result, fmt.Errorf("同时执行范围支持 1–64 条分支")
			}
			children = n.Branches
		case "repeat":
			if n.Count < 1 || n.Count > 100 || n.GapMS < 0 || n.GapMS > MaxDurationMS || n.Body == nil || n.Body.Type != "sequence" {
				return result, fmt.Errorf("重复次数须为 1–100，间隔须在 0ms–1 小时内")
			}
			children = []*FlowNode{n.Body}
		case "wait":
			if n.WaitMS < 0 || n.WaitMS > MaxDurationMS {
				return result, fmt.Errorf("等待时间必须在 0ms–1 小时内")
			}
			result.duration = n.WaitMS
			stats[n] = result
			return result, nil
		case "tap", "hold", "move", "scroll":
			if err := validateFlowAction(n); err != nil {
				return result, err
			}
			b := n.Action
			result.duration = b.DurationMS
			result.actions = 1
			if !n.Disabled {
				switch n.Type {
				case "tap", "hold":
					result.events = 2
				case "scroll":
					result.events = 1
				case "move":
					if len(b.Path) > 0 {
						result.events = int64(len(b.Path))
					} else if b.DurationMS == 0 {
						result.events = 1
					} else {
						result.events = max(1, (b.DurationMS+7)/8) + 1
					}
				}
			}
			if result.events > MaxEvents {
				return result, fmt.Errorf("展开后的事件超过 100000 个")
			}
			stats[n] = result
			return result, nil
		default:
			return result, fmt.Errorf("未知范围或动作 %s", n.Type)
		}
		for _, child := range children {
			if n.Type == "parallel" && (child == nil || child.Type != "sequence") {
				return result, fmt.Errorf("并行分支必须是顺序范围")
			}
			part, err := measure(child, depth+1)
			if err != nil {
				return result, err
			}
			if n.Type == "parallel" {
				result.duration = max(result.duration, part.duration)
			} else {
				result.duration += part.duration
			}
			result.actions += part.actions
			result.events += part.events
			if result.duration > MaxDurationMS || result.actions > MaxEvents || result.events > MaxEvents {
				return result, fmt.Errorf("流程超过 1 小时或展开后的动作/事件超过 100000 个")
			}
		}
		if n.Type == "repeat" {
			// Check bounded products before emitting or allocating repeated actions.
			result.duration = result.duration*n.Count + n.GapMS*(n.Count-1)
			result.actions *= n.Count
			result.events *= n.Count
			if result.duration > MaxDurationMS || result.actions > MaxEvents || result.events > MaxEvents {
				return result, fmt.Errorf("重复展开超过 1 小时或 100000 个动作/事件")
			}
		}
		stats[n] = result
		return result, nil
	}
	result, err := measure(root, 0)
	if err != nil {
		return nil, 0, err
	}
	type scheduled struct {
		b     Block
		muted bool
	}
	blocks := make([]scheduled, 0, int(result.actions))
	var emit func(*FlowNode, int64)
	emit = func(n *FlowNode, at int64) {
		if stats[n].actions == 0 {
			return
		} // Empty/wait-only nested repeats need no expansion.
		switch n.Type {
		case "sequence":
			for _, child := range n.Items {
				emit(child, at)
				at += stats[child].duration
			}
		case "parallel":
			for _, branch := range n.Branches {
				emit(branch, at)
			}
		case "repeat":
			for i := int64(0); i < n.Count; i++ {
				emit(n.Body, at+i*(stats[n.Body].duration+n.GapMS))
			}
		default:
			b := *n.Action
			b.ID = fmt.Sprintf("flow_event_%d", len(blocks))
			b.Type = n.Type
			b.AtMS = at
			blocks = append(blocks, scheduled{b, n.Disabled})
		}
	}
	emit(root, 0)
	sort.SliceStable(blocks, func(i, j int) bool { return blocks[i].b.AtMS < blocks[j].b.AtMS })
	tracks := []Track{}
	ends := []int64{}
	for _, entry := range blocks {
		lane := -1
		for i, end := range ends {
			if end <= entry.b.AtMS && tracks[i].Muted == entry.muted {
				lane = i
				break
			}
		}
		if lane < 0 {
			if len(tracks) >= 64 {
				return nil, 0, fmt.Errorf("同时执行的动作超过 64 路")
			}
			lane = len(tracks)
			tracks = append(tracks, Track{ID: fmt.Sprintf("flow_track_%d", lane), Name: fmt.Sprintf("分支 %d", lane+1), Muted: entry.muted, Blocks: []Block{}})
			ends = append(ends, 0)
		}
		tracks[lane].Blocks = append(tracks[lane].Blocks, entry.b)
		ends[lane] = occupiedEnd(entry.b)
	}
	return tracks, result.duration, nil
}

func validateFlowAction(n *FlowNode) error {
	b := n.Action
	if b == nil || b.Type != n.Type || b.DurationMS < 0 || b.DurationMS > MaxDurationMS {
		return fmt.Errorf("动作参数或时长无效")
	}
	if (b.X == nil) != (b.Y == nil) || (b.FromX == nil) != (b.FromY == nil) {
		return fmt.Errorf("鼠标坐标 X/Y 必须成对")
	}
	for _, p := range []*int{b.X, b.Y, b.FromX, b.FromY} {
		if p != nil && (*p < -100000 || *p > 100000) {
			return fmt.Errorf("坐标超出范围")
		}
	}
	switch n.Type {
	case "tap", "hold":
		if !sequence.ValidKey(b.Key) || b.DurationMS < 1 {
			return fmt.Errorf("按键无效或按住时长少于 1ms")
		}
	case "scroll":
		if b.Delta == 0 || b.Delta > 12000 || b.Delta < -12000 {
			return fmt.Errorf("滚动量须为 ±12000 内的非零整数")
		}
	case "move":
		if b.X == nil || b.DurationMS > 0 && b.FromX == nil {
			return fmt.Errorf("鼠标移动缺少目标或起点")
		}
		previous := int64(-1)
		for _, w := range b.Path {
			if w.AtMS < 0 || w.AtMS > b.DurationMS || w.AtMS < previous || w.X < -100000 || w.X > 100000 || w.Y < -100000 || w.Y > 100000 {
				return fmt.Errorf("录制轨迹无效")
			}
			previous = w.AtMS
		}
	}
	return nil
}

// FlowDefault is the production example. NodeDefault remains a v1 fixture.
func FlowDefault() Config {
	c := Default()
	a := func(id, kind, key string, duration int64) *FlowNode {
		return &FlowNode{ID: id, Type: kind, Action: &Block{Type: kind, Key: key, DurationMS: duration}}
	}
	seq := func(id string, items ...*FlowNode) *FlowNode {
		return &FlowNode{ID: id, Type: "sequence", Items: items}
	}
	wait := func(id string, ms int64) *FlowNode { return &FlowNode{ID: id, Type: "wait", WaitMS: ms} }
	root := seq("root", &FlowNode{ID: "parallel", Type: "parallel", Branches: []*FlowNode{
		seq("branch_a", a("hold", "hold", "right", 800)),
		seq("branch_b", &FlowNode{ID: "repeat", Type: "repeat", Count: 4, Body: seq("repeat_body", a("tap1", "tap", "1", 60), wait("inner_wait", 140))}),
	}}, wait("tail_wait", 120), a("tap2", "tap", "2", 60))
	m := Definition{ID: "starter", Name: "右键蓄力 + 连续施法", Enabled: true, Trigger: "f1", Graph: &Graph{Version: 2, Root: root}}
	_, m.DurationMS, _ = flowTracks(root)
	c.Macros = []Definition{m}
	return c
}
