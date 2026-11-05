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
	if err != nil || cfg.Version != 3 || len(cfg.Macros[0].Tracks) != 3 {
		t.Fatal("timeline save lost tracks", err)
	}
	p, err := a.PreviewMacro(raw, cfg.Macros[0].ID)
	if err != nil || p.Count != 6 {
		t.Fatal("timeline preview mismatch", err)
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
