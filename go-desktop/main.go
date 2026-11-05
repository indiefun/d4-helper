package main

import (
	"embed"
	"encoding/json"
	"flag"
	"fmt"
	"github.com/indiefun/d4-helper/go-desktop/internal/timeline"
	"github.com/indiefun/d4-helper/go-desktop/internal/win"
	"golang.org/x/sys/windows"
	"io/fs"
	"os"
	"path/filepath"

	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
	winoptions "github.com/wailsapp/wails/v2/pkg/options/windows"
)

//go:embed all:frontend
var assets embed.FS

func main() {
	config := flag.String("config", "", "configuration file")
	dry := flag.Bool("dry-run", false, "collect execution without sending input")
	selfTest := flag.String("self-test", "", "dry renderer/bridge smoke test; write JSON report and exit")
	flag.Parse()
	var instance windows.Handle
	var err error
	if *selfTest != "" {
		instance, err = win.AcquireNamedInstance("Local\\D4HelperStudioDrySmoke")
	} else {
		instance, err = win.AcquireInstance()
	}
	if err != nil {
		win.ShowError(err.Error())
		return
	}
	defer windows.CloseHandle(instance)
	if *config == "" {
		executable, _ := os.Executable()
		for _, candidate := range []string{filepath.Join(filepath.Dir(executable), "workspace.timeline.json"), "workspace.timeline.json", "../workspace.timeline.json", filepath.Join(filepath.Dir(executable), "..", "..", "workspace.timeline.json")} {
			if _, err := os.Stat(candidate); err == nil {
				*config, _ = filepath.Abs(candidate)
				break
			}
		}
		if *config == "" {
			*config = filepath.Join(filepath.Dir(executable), "workspace.timeline.json")
			data, _ := json.MarshalIndent(timeline.Default(), "", "  ")
			if _, err := writeConfiguration(*config, string(data)); err != nil {
				win.ShowError(err.Error())
				return
			}
		}
	}
	frontend, err := fs.Sub(assets, "frontend")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	app := NewApp(*config)
	app.dry = *dry || *selfTest != ""
	app.selfTest = *selfTest
	err = wails.Run(&options.App{
		Title: "D4Helper Studio · 多轨宏编辑器", Width: 1440, Height: 900, MinWidth: 1200, MinHeight: 760,
		BackgroundColour: &options.RGBA{R: 18, G: 20, B: 24, A: 255},
		AssetServer:      &assetserver.Options{Assets: frontend},
		Windows:          &winoptions.Options{Theme: winoptions.Dark, OnSuspend: func() { _ = app.StopAll() }, OnResume: func() { _ = app.StopAll() }},
		OnStartup:        app.startup, OnShutdown: app.shutdown, OnBeforeClose: app.beforeClose, Bind: []interface{}{app},
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
