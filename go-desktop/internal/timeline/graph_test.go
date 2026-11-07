package timeline

import (
	"encoding/json"
	"strings"
	"testing"
	"time"
)

func graphMacro() Definition {
	return Definition{ID: "flow", Name: "节点流程", Enabled: true, Trigger: "f2", Graph: &Graph{Version: 1, Nodes: []Node{
		{ID: "start", Type: "start"}, {ID: "fork", Type: "parallel"},
		{ID: "a", Type: "hold", Action: &Block{Type: "hold", Key: "1", DurationMS: 100}},
		{ID: "wait", Type: "wait", WaitMS: 300},
		{ID: "b", Type: "tap", Action: &Block{Type: "tap", Key: "2", DurationMS: 60}},
		{ID: "join", Type: "join"},
		{ID: "last", Type: "tap", Action: &Block{Type: "tap", Key: "3", DurationMS: 50}},
		{ID: "tail", Type: "wait", WaitMS: 200},
	}, Edges: []Edge{{"start", "fork"}, {"fork", "a"}, {"fork", "wait"}, {"wait", "b"}, {"a", "join"}, {"b", "join"}, {"join", "last"}, {"last", "tail"}}}}
}
func TestGraphParallelJoinAndTrailingWait(t *testing.T) {
	m := graphMacro()
	m.Tracks = []Track{{ID: "stale", Blocks: []Block{{ID: "wrong", Type: "tap", Key: "9", DurationMS: 3000}}}}
	p, err := Compile(m)
	if err != nil {
		t.Fatal(err)
	}
	if p.Duration != 610*time.Millisecond || len(p.Events) != 6 {
		t.Fatalf("wrong plan: %+v", p)
	}
	for i, want := range []int{0, 100, 300, 360, 360, 410} {
		if p.Events[i].Offset != time.Duration(want)*time.Millisecond {
			t.Fatalf("event %d: %+v", i, p.Events[i])
		}
	}
	m.Loop = true
	m.LoopWaitMS = 90
	p, err = Compile(m)
	if err != nil || p.Duration != 700*time.Millisecond || !p.Loop {
		t.Fatal(p, err)
	}
}
func TestGraphSaveReloadKeepsAuthoringAndDiscardsTrackCache(t *testing.T) {
	c := Default()
	m := graphMacro()
	m.Tracks = []Track{{ID: "stale", Blocks: []Block{{ID: "wrong", Type: "tap", Key: "9", DurationMS: 3000}}}}
	m.Graph.Nodes[2].X = 768.5
	c.Macros = []Definition{m}
	raw, _ := json.Marshal(c)
	normalized, cfg, err := Normalize(string(raw))
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(normalized, "wrong") || cfg.Macros[0].Graph.Nodes[2].X != 768.5 || cfg.Macros[0].DurationMS != 610 {
		t.Fatal("lost authoring or trusted stale tracks", normalized)
	}
	_, again, err := Normalize(normalized)
	if err != nil {
		t.Fatal(err)
	}
	p, err := Compile(again.Macros[0])
	if err != nil || p.Duration != 610*time.Millisecond {
		t.Fatal(p, err)
	}
}
func TestGraphRejectsCyclesAndInvalidConnections(t *testing.T) {
	cases := map[string]func(*Graph){
		"cycle":             func(g *Graph) { g.Edges = append(g.Edges, Edge{"tail", "wait"}) },
		"missing endpoint":  func(g *Graph) { g.Edges = append(g.Edges, Edge{"tail", "missing"}) },
		"duplicate edge":    func(g *Graph) { g.Edges = append(g.Edges, g.Edges[0]) },
		"multiple input":    func(g *Graph) { g.Edges = append(g.Edges, Edge{"a", "b"}) },
		"multiple output":   func(g *Graph) { g.Edges = append(g.Edges, Edge{"a", "tail"}) },
		"start input":       func(g *Graph) { g.Edges = append(g.Edges, Edge{"tail", "start"}) },
		"second start":      func(g *Graph) { g.Nodes = append(g.Nodes, Node{ID: "other", Type: "start"}) },
		"bad wait":          func(g *Graph) { g.Nodes[3].WaitMS = -1 },
		"mismatched action": func(g *Graph) { g.Nodes[2].Action.Type = "scroll" },
		"overflow":          func(g *Graph) { g.Nodes[3].WaitMS = MaxDurationMS },
		"unconnected join input": func(g *Graph) {
			g.Edges = append(g.Edges, Edge{"idle", "join"})
			g.Nodes = append(g.Nodes, Node{ID: "idle", Type: "wait", WaitMS: 1})
		},
	}
	for name, change := range cases {
		t.Run(name, func(t *testing.T) {
			m := graphMacro()
			change(m.Graph)
			if _, err := Compile(m); err == nil {
				t.Fatal("accepted invalid graph")
			}
		})
	}
	// Pure disconnected cycles must also be rejected; unused drafts never execute.
	m := graphMacro()
	m.Graph.Nodes = append(m.Graph.Nodes, Node{ID: "x", Type: "wait"}, Node{ID: "y", Type: "wait"})
	m.Graph.Edges = append(m.Graph.Edges, Edge{"x", "y"}, Edge{"y", "x"})
	if _, err := Compile(m); err == nil {
		t.Fatal("accepted disconnected cycle")
	}
}
func TestGraphDisconnectedMutedAndZeroTimeActions(t *testing.T) {
	m := graphMacro()
	m.Graph.Nodes = append(m.Graph.Nodes, Node{ID: "idle", Type: "hold", Action: &Block{Type: "hold", Key: "9", DurationMS: 999}})
	m.Graph.Nodes[2].Muted = true
	p, err := Compile(m)
	if err != nil || p.Duration != 610*time.Millisecond || len(p.Events) != 4 {
		t.Fatal(p, err)
	}
	m.Graph = &Graph{Version: 1, Nodes: []Node{{ID: "s", Type: "start"}, {ID: "a", Type: "scroll", Action: &Block{Type: "scroll", Delta: 120}}, {ID: "b", Type: "scroll", Action: &Block{Type: "scroll", Delta: -120}}}, Edges: []Edge{{"s", "a"}, {"a", "b"}}}
	p, err = Compile(m)
	if err != nil || len(p.Events) != 2 || p.Events[0].Offset != 0 || p.Events[1].Offset != 0 {
		t.Fatal(p, err)
	}
}
