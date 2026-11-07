//go:build ignore

// Cross-check editor-produced workspaces with the production Go compiler.
package main

import (
	"encoding/json"
	"fmt"
	"github.com/indiefun/d4-helper/go-desktop/internal/timeline"
	"os"
	"reflect"
)

type migration struct {
	Name   string          `json:"name"`
	Before json.RawMessage `json:"before"`
	After  json.RawMessage `json:"after"`
}

func main() {
	if len(os.Args) != 3 {
		panic("usage: verify-flow-workspaces.go workspace.json migrations.json")
	}
	data, err := os.ReadFile(os.Args[1])
	must(err)
	_, cfg, err := timeline.Normalize(string(data))
	must(err)
	for _, m := range cfg.Macros {
		p, err := timeline.Compile(m)
		must(err)
		fmt.Printf("Compiled browser macro %q: %d events, %dms\n", m.Name, len(p.Events), p.Duration.Milliseconds())
	}
	data, err = os.ReadFile(os.Args[2])
	must(err)
	var cases []migration
	must(json.Unmarshal(data, &cases))
	for _, c := range cases {
		_, before, err := timeline.Normalize(string(c.Before))
		must(err)
		_, after, err := timeline.Normalize(string(c.After))
		must(err)
		if len(before.Macros) != len(after.Macros) {
			panic("migration lost a macro")
		}
		for i, m := range before.Macros {
			a, err := timeline.Compile(m)
			must(err)
			b, err := timeline.Compile(after.Macros[i])
			must(err)
			if !reflect.DeepEqual(a, b) {
				panic(fmt.Sprintf("%s: compiled event plans differ\nbefore=%+v\nafter=%+v", c.Name, a, b))
			}
		}
		fmt.Printf("Migration %q: identical Go event plans\n", c.Name)
	}
}
func must(err error) {
	if err != nil {
		panic(err)
	}
}
