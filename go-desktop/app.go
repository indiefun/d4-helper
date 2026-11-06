package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/indiefun/d4-helper/go-desktop/internal/engine"
	"github.com/indiefun/d4-helper/go-desktop/internal/sequence"
	"github.com/indiefun/d4-helper/go-desktop/internal/timeline"
	"github.com/indiefun/d4-helper/go-desktop/internal/win"
	wruntime "github.com/wailsapp/wails/v2/pkg/runtime"
)

type App struct {
	ctx          context.Context
	mu           sync.Mutex
	configPath   string
	worker       *engine.Worker
	driver       *win.Driver
	service      *win.Service
	cancel       context.CancelFunc
	cfg          timeline.Config
	foreground   win.Foreground
	state        LiveState
	recorded     []timeline.Definition
	startupError string
	dry          bool
	quitting     bool
	selfTest     string
	readyOnce    sync.Once
}

type LiveState struct {
	engine.Snapshot
	Foreground    win.Foreground        `json:"foreground"`
	NewRecordings []timeline.Definition `json:"new_recordings"`
	Dry           bool                  `json:"dry_run"`
	Error         string                `json:"error"`
}

type Workspace struct {
	Path    string `json:"path"`
	Content string `json:"content"`
}
type PreviewEvent struct {
	AtMS float64 `json:"at_ms"`
	Key  string  `json:"key"`
	Type string  `json:"type"`
	X    *int    `json:"x,omitempty"`
	Y    *int    `json:"y,omitempty"`
}
type Preview struct {
	Events     []PreviewEvent `json:"events"`
	Count      int            `json:"count"`
	DurationMS float64        `json:"duration_ms"`
	Loop       bool           `json:"loop"`
}

func NewApp(path string) *App {
	return &App{configPath: path}
}

func (a *App) startup(ctx context.Context) {
	a.ctx = ctx
	background, cancel := context.WithCancel(context.Background())
	a.cancel = cancel
	driver := &win.Driver{Dry: a.dry}
	a.driver = driver
	worker, err := engine.Start(background, driver)
	if err != nil {
		a.startupError = err.Error()
		return
	}
	a.worker = worker
	workspace, err := a.load(a.configPath)
	if err != nil {
		a.startupError = err.Error()
	} else {
		_, a.cfg, err = timeline.Normalize(workspace.Content)
		if err == nil {
			err = worker.Do(func(c *engine.Core) error {
				runtimeConfig, err := a.cfg.Runtime()
				if err != nil {
					return err
				}
				return c.Apply(runtimeConfig, win.Held(), time.Now())
			})
		}
		if err != nil {
			a.startupError = err.Error()
		}
	}
	service := &win.Service{}
	service.WantMovement = worker.IsRecording
	service.OnInput = func(e engine.PhysicalEvent, hwnd uintptr) {
		worker.Post(func(c *engine.Core) error {
			if driver.Target.Load() != hwnd {
				c.Focus(false, win.Held(), e.At)
			}
			c.Handle(e)
			return nil
		})
	}
	service.OnForeground = func(f win.Foreground) {
		a.mu.Lock()
		a.foreground = f
		a.mu.Unlock()
		held := win.Held()
		worker.Post(func(c *engine.Core) error {
			target := !win.ForegroundIsSelf(f.HWND) && c.Config.Matches(f.Title, f.Process)
			hwnd := uintptr(0)
			if target {
				hwnd = f.HWND
			}
			previous := driver.Target.Swap(hwnd)
			if previous != hwnd {
				c.Focus(false, held, time.Now())
			}
			c.Focus(target, held, time.Now())
			return nil
		})
	}
	service.OnShow = func() { wruntime.WindowShow(a.ctx); wruntime.WindowUnminimise(a.ctx) }
	service.OnStop = func() { _ = a.StopAll() }
	service.OnQuit = a.Quit
	if err := service.Start(background); err != nil {
		a.startupError = err.Error()
		worker.Do(func(c *engine.Core) error { c.Fail(err, time.Now()); return nil })
	} else {
		a.service = service
		if a.startupError == "" {
			_ = worker.Do(func(c *engine.Core) error { return c.Arm(true, win.Held(), time.Now()) })
		}
	}
	go a.monitor(background)
	if a.selfTest != "" {
		go func() {
			select {
			case <-background.Done():
				return
			case <-time.After(20 * time.Second):
				a.writeSelfTest(0, "WebView 前端初始化超时")
			}
		}()
	}
}

// FrontendReady also serves as an explicit renderer-to-Go bridge smoke check.
func (a *App) FrontendReady(count int) {
	if a.selfTest != "" {
		a.writeSelfTest(count, "")
	}
}
func (a *App) writeSelfTest(count int, problem string) {
	a.readyOnce.Do(func() {
		report := struct {
			FrontendMacros int             `json:"frontend_macros"`
			BackendMacros  int             `json:"backend_macros"`
			Dry            bool            `json:"dry_run"`
			Error          string          `json:"error"`
			Engine         engine.Snapshot `json:"engine"`
		}{FrontendMacros: count, Dry: a.dry, Error: problem}
		a.mu.Lock()
		report.BackendMacros = len(a.cfg.Macros)
		if a.startupError != "" {
			report.Error = a.startupError
		}
		a.mu.Unlock()
		if a.worker != nil {
			report.Engine, _ = a.worker.Snapshot()
		}
		b, _ := json.MarshalIndent(report, "", "  ")
		_ = os.WriteFile(a.selfTest, b, 0644)
		go a.Quit()
	})
}

func (a *App) monitor(ctx context.Context) {
	ticker := time.NewTicker(100 * time.Millisecond)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}
		var snapshot engine.Snapshot
		var recordings [][]sequence.RecordedEvent
		err := a.worker.Do(func(c *engine.Core) error {
			snapshot = c.Snapshot(time.Now())
			recordings = c.Recordings
			c.Recordings = nil
			return nil
		})
		a.mu.Lock()
		cfg, foreground := a.cfg, a.foreground
		a.state = LiveState{Snapshot: snapshot, Foreground: foreground, Dry: a.dry, Error: a.startupError}
		if err != nil {
			a.state.Error = err.Error()
		}
		for _, recording := range recordings {
			if len(a.recorded) >= 32 {
				a.startupError = "未保存的录制已达到 32 条，请打开配置窗口处理"
				a.worker.Post(func(c *engine.Core) error { c.Fail(fmt.Errorf("未保存录制过多"), time.Now()); return nil })
				break
			}
			recorded := timeline.FromRecording(recording)
			recorded.Name = "录制 " + time.Now().Format("15:04:05")
			a.recorded = append(a.recorded, recorded)
		}
		a.mu.Unlock()
		if a.service != nil {
			a.service.Update(win.View{Snapshot: snapshot, Foreground: foreground, Overlay: cfg.Overlay, Opacity: cfg.Opacity, Avoid: cfg.AvoidMouse, Distance: cfg.AvoidDistance})
		}
	}
}
func (a *App) shutdown(ctx context.Context) {
	if a.cancel != nil {
		a.cancel()
	}
	if a.service != nil {
		a.service.Close()
	}
	if a.worker != nil {
		a.worker.Close()
	}
}
func (a *App) beforeClose(ctx context.Context) bool {
	a.mu.Lock()
	quitting := a.quitting
	a.mu.Unlock()
	if !quitting && a.service != nil && a.service.HasTray() {
		wruntime.WindowHide(ctx)
		return true
	}
	return false
}
func (a *App) Poll() LiveState {
	a.mu.Lock()
	defer a.mu.Unlock()
	s := a.state
	s.NewRecordings = a.recorded
	a.recorded = nil
	return s
}
func (a *App) SetArmed(on bool) error {
	if a.worker == nil || a.service == nil {
		return fmt.Errorf("Windows 输入服务未启动: %s", a.startupError)
	}
	return a.worker.Do(func(c *engine.Core) error { return c.Arm(on, win.Held(), time.Now()) })
}
func (a *App) StopAll() error {
	if a.worker == nil {
		return nil
	}
	return a.worker.Do(func(c *engine.Core) error { return c.Arm(false, win.Held(), time.Now()) })
}
func (a *App) ToggleMacro(id string) error {
	if a.worker == nil {
		return fmt.Errorf("引擎未启动")
	}
	return a.worker.Do(func(c *engine.Core) error { return c.Toggle(id, time.Now()) })
}
func (a *App) CaptureKey(kind string) error {
	if a.worker == nil {
		return fmt.Errorf("引擎未启动")
	}
	return a.worker.Do(func(c *engine.Core) error { return c.BeginCapture(kind, time.Now()) })
}
func (a *App) CancelCapture() error {
	if a.worker == nil {
		return nil
	}
	return a.worker.Do(func(c *engine.Core) error { c.CaptureKind = ""; c.Captured = ""; return nil })
}
func (a *App) FinishRecording() error {
	if a.worker == nil {
		return nil
	}
	return a.worker.Do(func(c *engine.Core) error { c.FinishRecording(time.Now()); return nil })
}
func (a *App) DetectForeground() (win.Foreground, error) {
	time.Sleep(2 * time.Second)
	f := win.ForegroundWindow()
	if f.HWND == 0 {
		return f, fmt.Errorf("未找到前台窗口")
	}
	return f, nil
}
func (a *App) HideToTray() error {
	if a.service == nil || !a.service.HasTray() {
		return fmt.Errorf("托盘不可用，请保持配置窗口打开")
	}
	wruntime.WindowHide(a.ctx)
	return nil
}
func (a *App) Quit() { a.mu.Lock(); a.quitting = true; a.mu.Unlock(); wruntime.Quit(a.ctx) }

func (a *App) ApplyConfiguration(raw string) error {
	_, cfg, err := timeline.Normalize(raw)
	if err != nil {
		return err
	}
	if a.worker == nil {
		return fmt.Errorf("引擎未启动")
	}
	if err := a.worker.Do(func(c *engine.Core) error {
		runtimeConfig, err := cfg.Runtime()
		if err != nil {
			return err
		}
		if err := c.Apply(runtimeConfig, win.Held(), time.Now()); err != nil {
			return err
		}
		f := win.ForegroundWindow()
		target := !win.ForegroundIsSelf(f.HWND) && c.Config.Matches(f.Title, f.Process)
		hwnd := uintptr(0)
		if target {
			hwnd = f.HWND
		}
		a.driver.Target.Store(hwnd)
		c.Focus(target, win.Held(), time.Now())
		return nil
	}); err != nil {
		return err
	}
	f := win.ForegroundWindow()
	a.mu.Lock()
	a.cfg = cfg
	a.foreground = f
	a.startupError = ""
	a.mu.Unlock()
	return nil
}

// SaveAndApply compiles tracks before replacing the running event plans.
func (a *App) SaveAndApply(raw string) (Workspace, error) {
	normalized, _, err := timeline.Normalize(raw)
	if err != nil {
		return Workspace{}, err
	}
	a.mu.Lock()
	path := a.configPath
	a.mu.Unlock()
	if err := a.ApplyConfiguration(normalized); err != nil {
		return Workspace{}, err
	}
	if _, err := writeConfiguration(path, normalized); err != nil {
		_ = a.StopAll()
		return Workspace{}, err
	}
	if err := a.SetArmed(true); err != nil {
		return Workspace{}, err
	}
	a.mu.Lock()
	a.configPath = path
	a.mu.Unlock()
	return Workspace{path, normalized}, nil
}

func (a *App) load(path string) (Workspace, error) {
	info, err := os.Stat(path)
	if err != nil {
		return Workspace{}, fmt.Errorf("读取配置失败: %w", err)
	}
	if info.Size() > 8*1024*1024 {
		return Workspace{}, fmt.Errorf("配置文件不能超过 8MB")
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return Workspace{}, err
	}
	normalized, _, err := timeline.ReadForEditing(string(data))
	if err != nil {
		return Workspace{}, err
	}
	a.mu.Lock()
	a.configPath = path
	a.mu.Unlock()
	return Workspace{path, normalized}, nil
}

func (a *App) LoadConfiguration() (Workspace, error) {
	a.mu.Lock()
	path := a.configPath
	a.mu.Unlock()
	return a.load(path)
}

func (a *App) ImportConfiguration() (Workspace, error) {
	path, err := wruntime.OpenFileDialog(a.ctx, wruntime.OpenDialogOptions{Title: "导入宏配置", Filters: []wruntime.FileFilter{{DisplayName: "JSON 配置", Pattern: "*.json"}}})
	if err != nil {
		return Workspace{}, err
	}
	if path == "" {
		return Workspace{}, nil
	}
	workspace, err := a.load(path)
	if err != nil {
		return Workspace{}, err
	}
	if err := a.ApplyConfiguration(workspace.Content); err != nil {
		// load accepts old overlapping tracks for editing only. They stay
		// disarmed until the user splits the tracks and saves.
		if _, _, validation := timeline.Normalize(workspace.Content); validation != nil {
			_ = a.StopAll()
			return workspace, nil
		}
		return Workspace{}, err
	}
	if err := a.SetArmed(true); err != nil {
		return Workspace{}, err
	}
	return workspace, nil
}

func (a *App) SaveConfiguration(raw string) (string, error) {
	if _, _, err := timeline.Normalize(raw); err != nil {
		return "", err
	}
	path, err := wruntime.SaveFileDialog(a.ctx, wruntime.SaveDialogOptions{Title: "另存为编辑器配置", DefaultFilename: "workspace.timeline.json", Filters: []wruntime.FileFilter{{DisplayName: "JSON 配置", Pattern: "*.json"}}})
	if err != nil || path == "" {
		return "", err
	}
	if !strings.EqualFold(filepath.Ext(path), ".json") {
		path += ".json"
	}
	return writeConfiguration(path, raw)
}

func writeConfiguration(path, raw string) (string, error) {
	normalized, _, err := timeline.Normalize(raw)
	if err != nil {
		return "", err
	}
	var doc map[string]json.RawMessage
	if err := json.Unmarshal([]byte(normalized), &doc); err != nil {
		return "", err
	}
	doc["schema_version"] = json.RawMessage("3")
	data, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return "", err
	}
	// Write to the same directory, then replace atomically through MoveFileEx.
	tmp, err := os.CreateTemp(filepath.Dir(path), ".d4-config-*.tmp")
	if err != nil {
		return "", err
	}
	name := tmp.Name()
	defer os.Remove(name)
	if _, err := tmp.Write(append(data, '\n')); err != nil {
		tmp.Close()
		return "", err
	}
	if err := tmp.Sync(); err != nil {
		tmp.Close()
		return "", err
	}
	if err := tmp.Close(); err != nil {
		return "", err
	}
	if err := replaceFile(name, path); err != nil {
		return "", err
	}
	return path, nil
}

func (a *App) PreviewMacro(raw, id string) (Preview, error) {
	_, cfg, err := timeline.Normalize(raw)
	if err != nil {
		return Preview{}, err
	}
	for _, m := range cfg.Macros {
		if m.ID != id {
			continue
		}
		plan, err := timeline.Compile(m)
		if err != nil {
			return Preview{}, err
		}
		p := Preview{Events: []PreviewEvent{}, Count: len(plan.Events), DurationMS: float64(plan.Duration) / 1e6, Loop: plan.Loop}
		for i, e := range plan.Events {
			if i >= 200 {
				break
			}
			kind := e.Kind
			if kind == "key" {
				kind = "key_up"
				if e.Down {
					kind = "key_down"
				}
			}
			p.Events = append(p.Events, PreviewEvent{AtMS: float64(e.Offset) / 1e6, Key: e.Key, Type: kind, X: e.X, Y: e.Y})
		}
		return p, nil
	}
	return Preview{}, fmt.Errorf("macro not found")
}
func (a *App) StartRecording() error {
	if a.worker == nil {
		return fmt.Errorf("engine unavailable")
	}
	return a.worker.Do(func(c *engine.Core) error { return c.StartRecording(time.Now()) })
}
func (a *App) CursorPosition() win.Point { return win.Cursor() }

func (a *App) CapturePosition() win.Point { time.Sleep(2 * time.Second); return win.Cursor() }
func (a *App) BeginRecordingAfterSwitch() error {
	time.Sleep(2 * time.Second)
	return a.StartRecording()
}
