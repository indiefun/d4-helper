package timeline

import (
	"fmt"
	"math"
	"sort"
)

// Graph describes finish-to-start dependencies. Parallel starts every output;
// join waits for every input. Loops belong to the macro, never to graph cycles.
type Graph struct {
	Version int    `json:"version"`
	Nodes   []Node `json:"nodes"`
	Edges   []Edge `json:"edges"`
}
type Node struct {
	ID     string  `json:"id"`
	Type   string  `json:"type"`
	X      float64 `json:"x"`
	Y      float64 `json:"y"`
	WaitMS int64   `json:"wait_ms,omitempty"`
	Muted  bool    `json:"muted,omitempty"`
	Action *Block  `json:"action,omitempty"`
}
type Edge struct {
	From string `json:"from"`
	To   string `json:"to"`
}

const MaxGraphNodes = 4096

func graphTracks(g *Graph) ([]Track, int64, error) {
	if g.Version != 1 || len(g.Nodes) == 0 || len(g.Nodes) > MaxGraphNodes || len(g.Edges) > MaxGraphNodes*2 {
		return nil, 0, fmt.Errorf("节点图格式无效或超过 4096 个节点")
	}
	nodes := map[string]Node{}
	in, out := map[string][]string{}, map[string][]string{}
	start := ""
	for _, n := range g.Nodes {
		if n.ID == "" || len(n.ID) > 128 || nodes[n.ID].ID != "" || math.IsNaN(n.X) || math.IsNaN(n.Y) || math.IsInf(n.X, 0) || math.IsInf(n.Y, 0) || math.Abs(n.X) > 1000000 || math.Abs(n.Y) > 1000000 {
			return nil, 0, fmt.Errorf("节点 ID 或位置无效")
		}
		switch n.Type {
		case "start":
			if start != "" {
				return nil, 0, fmt.Errorf("只能有一个开始节点")
			}
			start = n.ID
		case "wait":
			if n.WaitMS < 0 || n.WaitMS > MaxDurationMS {
				return nil, 0, fmt.Errorf("等待时间必须在 0ms–1 小时内")
			}
		case "parallel", "join":
		case "tap", "hold", "move", "scroll":
			if n.Action == nil || n.Action.Type != n.Type || n.Action.DurationMS < 0 || n.Action.DurationMS > MaxDurationMS {
				return nil, 0, fmt.Errorf("动作节点参数无效")
			}
		default:
			return nil, 0, fmt.Errorf("未知节点类型 %s", n.Type)
		}
		nodes[n.ID] = n
	}
	if start == "" {
		return nil, 0, fmt.Errorf("缺少开始节点")
	}
	seen := map[Edge]bool{}
	for _, e := range g.Edges {
		if nodes[e.From].ID == "" || nodes[e.To].ID == "" || e.From == e.To || seen[e] {
			return nil, 0, fmt.Errorf("连线无效或重复")
		}
		seen[e] = true
		in[e.To] = append(in[e.To], e.From)
		out[e.From] = append(out[e.From], e.To)
	}
	degrees := map[string]int{}
	queue := []string{}
	for _, n := range g.Nodes {
		if n.Type == "start" && len(in[n.ID]) != 0 || n.Type != "join" && len(in[n.ID]) > 1 || n.Type != "parallel" && len(out[n.ID]) > 1 || len(in[n.ID]) > 64 || len(out[n.ID]) > 64 {
			return nil, 0, fmt.Errorf("多路输出请使用并行节点，多路输入请使用汇合节点")
		}
		degrees[n.ID] = len(in[n.ID])
		if degrees[n.ID] == 0 {
			queue = append(queue, n.ID)
		}
	}
	active := map[string]bool{start: true}
	ends := map[string]int64{}
	blocks := []struct {
		block Block
		muted bool
	}{}
	var duration int64
	visited := 0
	for len(queue) > 0 {
		id := queue[0]
		queue = queue[1:]
		visited++
		n := nodes[id]
		var at int64
		for _, parent := range in[id] {
			if active[parent] {
				active[id] = true
			}
			at = max(at, ends[parent])
		}
		if active[id] {
			for _, parent := range in[id] {
				if !active[parent] {
					return nil, 0, fmt.Errorf("汇合分支尚未连接开始节点")
				}
			}
			span := int64(0)
			if n.Type == "wait" {
				span = n.WaitMS
			}
			if n.Action != nil && n.Type != "start" && n.Type != "wait" && n.Type != "parallel" && n.Type != "join" {
				b := *n.Action
				b.ID = id
				b.Type = n.Type
				b.AtMS = at
				span = b.DurationMS
				blocks = append(blocks, struct {
					block Block
					muted bool
				}{b, n.Muted})
			}
			if span > MaxDurationMS-at {
				return nil, 0, fmt.Errorf("流程总时长不能超过 1 小时")
			}
			ends[id] = at + span
			duration = max(duration, ends[id])
		}
		for _, child := range out[id] {
			degrees[child]--
			if degrees[child] == 0 {
				queue = append(queue, child)
			}
		}
	}
	if visited != len(g.Nodes) {
		return nil, 0, fmt.Errorf("不能连接成环；重复执行请开启宏循环")
	}
	// Pack independent actions into nonoverlapping lanes for the existing engine.
	sort.SliceStable(blocks, func(i, j int) bool { return blocks[i].block.AtMS < blocks[j].block.AtMS })
	tracks := []Track{}
	laneEnds := []int64{}
	for _, item := range blocks {
		lane := -1
		for i, end := range laneEnds {
			if end <= item.block.AtMS && tracks[i].Muted == item.muted {
				lane = i
				break
			}
		}
		if lane < 0 {
			if len(tracks) >= 64 {
				return nil, 0, fmt.Errorf("同时执行的动作超过 64 路")
			}
			lane = len(tracks)
			tracks = append(tracks, Track{ID: fmt.Sprintf("graph_track_%d", lane), Name: fmt.Sprintf("流程 %d", lane+1), Muted: item.muted, Blocks: []Block{}})
			laneEnds = append(laneEnds, 0)
		}
		tracks[lane].Blocks = append(tracks[lane].Blocks, item.block)
		laneEnds[lane] = occupiedEnd(item.block)
	}
	return tracks, duration, nil
}
