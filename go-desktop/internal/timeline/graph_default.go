package timeline

// NodeDefault starts with a short, readable sequence. Default remains the
// timeline fixture for older workspace compatibility and migration tests.
func NodeDefault() Config {
	c := Default()
	m := Definition{ID: "starter", Name: "技能连招", Enabled: true, Trigger: "f1", Graph: &Graph{Version: 1, Nodes: []Node{
		{ID: "flow_start", Type: "start", X: 80, Y: 180},
		{ID: "flow_tap", Type: "tap", X: 360, Y: 180, Action: &Block{ID: "flow_tap", Type: "tap", Key: "1", DurationMS: 60}},
		{ID: "flow_wait", Type: "wait", X: 640, Y: 180, WaitMS: 300},
		{ID: "flow_hold", Type: "hold", X: 920, Y: 180, Action: &Block{ID: "flow_hold", Type: "hold", Key: "right", DurationMS: 800}},
	}, Edges: []Edge{{"flow_start", "flow_tap"}, {"flow_tap", "flow_wait"}, {"flow_wait", "flow_hold"}}}}
	m.Tracks, m.DurationMS, _ = graphTracks(m.Graph)
	c.Macros = []Definition{m}
	return c
}
