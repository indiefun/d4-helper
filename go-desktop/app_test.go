package main

import (
	"context"
	"encoding/json"
	"github.com/indiefun/d4-helper/go-desktop/internal/timeline"
	"os"
	"path/filepath"
	"testing"
)

func testDocument(t *testing.T) string {
	t.Helper()
	b, err := json.Marshal(timeline.Default())
	if err != nil {
		t.Fatal(err)
	}
	return string(b)
}
func TestTimelineSaveReloadAndRuntime(t *testing.T) {
	path := filepath.Join(t.TempDir(), "workspace.timeline.json")
	raw := testDocument(t)
	if _, err := writeConfiguration(path, raw); err != nil {
		t.Fatal(err)
	}
	a := NewApp(path)
	a.dry = true
	a.startup(context.Background())
	defer a.shutdown(context.Background())
	if a.startupError != "" {
		t.Fatal(a.startupError)
	}
	// Editing disarms execution; saving must make the macro shortcut usable again.
	if err := a.StopAll(); err != nil {
		t.Fatal(err)
	}
	w, err := a.SaveAndApply(raw)
	if err != nil {
		t.Fatal(err)
	}
	snapshot, err := a.worker.Snapshot()
	if err != nil || !snapshot.Armed {
		t.Fatal("saving did not rearm macro shortcuts", err)
	}
	_, cfg, err := timeline.Normalize(w.Content)
	if err != nil || cfg.Version != 3 || len(cfg.Macros[0].Tracks) != 2 {
		t.Fatal("timeline save lost tracks", err)
	}
	p, err := a.PreviewMacro(raw, cfg.Macros[0].ID)
	if err != nil || p.Count != 6 {
		t.Fatal("timeline preview mismatch", err)
	}
}

func TestNodeWorkspaceSaveReloadAndPreview(t *testing.T) {
	cfg := timeline.NodeDefault()
	raw, err := json.Marshal(cfg)
	if err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(t.TempDir(), "workspace.timeline.json")
	if _, err := writeConfiguration(path, string(raw)); err != nil {
		t.Fatal(err)
	}
	a := NewApp(path)
	a.dry = true
	a.startup(context.Background())
	defer a.shutdown(context.Background())
	if a.startupError != "" {
		t.Fatal(a.startupError)
	}
	w, err := a.SaveAndApply(string(raw))
	if err != nil {
		t.Fatal(err)
	}
	_, saved, err := timeline.Normalize(w.Content)
	if err != nil || saved.Macros[0].Graph == nil || len(saved.Macros[0].Graph.Edges) != 3 {
		t.Fatal("node authoring lost during save", err)
	}
	p, err := a.PreviewMacro(w.Content, "starter")
	if err != nil || p.Count != 4 || p.DurationMS != 1160 {
		t.Fatal("node plan did not reach execution bridge", p, err)
	}
	loaded, err := a.LoadConfiguration()
	if err != nil {
		t.Fatal(err)
	}
	_, reloaded, err := timeline.Normalize(loaded.Content)
	if err != nil || reloaded.Macros[0].Graph.Nodes[3].X != 920 {
		t.Fatal("node layout lost on reload", err)
	}
}
func TestLegacyFileIsExplicitlyRejectedWithoutModification(t *testing.T) {
	path := filepath.Join(t.TempDir(), "config.json")
	raw := `{"macros":[],"toggle_profiles":[]}`
	os.WriteFile(path, []byte(raw), 0644)
	a := NewApp(path)
	if _, err := a.LoadConfiguration(); err == nil {
		t.Fatal("legacy model silently imported")
	}
	after, _ := os.ReadFile(path)
	if string(after) != raw {
		t.Fatal("legacy file changed")
	}
}

func TestOverlappingWorkspaceLoadsDisarmedAndOnlyChangesOnSave(t *testing.T) {
	cfg := timeline.Default()
	cfg.Macros[0].Tracks[0].Blocks = append(cfg.Macros[0].Tracks[0].Blocks, cfg.Macros[0].Tracks[1].Blocks...)
	cfg.Macros[0].Tracks = cfg.Macros[0].Tracks[:1]
	raw, _ := json.Marshal(cfg)
	path := filepath.Join(t.TempDir(), "workspace.timeline.json")
	if err := os.WriteFile(path, raw, 0644); err != nil {
		t.Fatal(err)
	}
	a := NewApp(path)
	a.dry = true
	a.startup(context.Background())
	defer a.shutdown(context.Background())
	if _, err := a.LoadConfiguration(); err != nil {
		t.Fatal(err)
	}
	snapshot, err := a.worker.Snapshot()
	if err != nil || snapshot.Armed {
		t.Fatal("overlapping workspace was armed", err)
	}
	after, _ := os.ReadFile(path)
	if string(after) != string(raw) {
		t.Fatal("loading rewrote workspace")
	}
	if _, err := a.SaveAndApply(string(raw)); err == nil {
		t.Fatal("saved overlaps")
	}
	cfg.Macros[0], _, err = timeline.SplitTracks(cfg.Macros[0])
	if err != nil {
		t.Fatal(err)
	}
	repaired, _ := json.Marshal(cfg)
	if _, err := a.SaveAndApply(string(repaired)); err != nil {
		t.Fatal(err)
	}
	snapshot, err = a.worker.Snapshot()
	if err != nil || !snapshot.Armed {
		t.Fatal("repaired workspace was not armed", err)
	}
}
