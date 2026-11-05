package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"
	"time"

	wruntime "github.com/wailsapp/wails/v2/pkg/runtime"
)

var appVersion = "2.0.0-dev"

const releasesURL = "https://github.com/indiefun/d4-helper/releases/latest"

type UpdateResult struct {
	Newer   bool   `json:"newer"`
	Message string `json:"message"`
}

func (a *App) Version() string { return "D4Helper v" + appVersion + " · Go" }
func newerVersion(candidate, current string) bool {
	parse := func(s string) []int {
		s = strings.TrimPrefix(s, "v")
		s = strings.SplitN(s, "-", 2)[0]
		parts := strings.Split(s, ".")
		n := make([]int, len(parts))
		for i, p := range parts {
			v, err := strconv.Atoi(p)
			if err != nil {
				return nil
			}
			n[i] = v
		}
		return n
	}
	next, now := parse(candidate), parse(current)
	if next == nil || now == nil {
		return false
	}
	for i := 0; i < max(len(next), len(now)); i++ {
		x, y := 0, 0
		if i < len(next) {
			x = next[i]
		}
		if i < len(now) {
			y = now[i]
		}
		if x != y {
			return x > y
		}
	}
	return false
}
func (a *App) CheckUpdate() (UpdateResult, error) {
	client := http.Client{Timeout: 10 * time.Second}
	request, err := http.NewRequestWithContext(a.ctx, "GET", "https://api.github.com/repos/indiefun/d4-helper/releases/latest", nil)
	if err != nil {
		return UpdateResult{}, err
	}
	request.Header.Set("User-Agent", "D4Helper-Go/"+appVersion)
	response, err := client.Do(request)
	if err != nil {
		return UpdateResult{}, err
	}
	defer response.Body.Close()
	if response.StatusCode != 200 {
		return UpdateResult{}, fmt.Errorf("检查更新失败: HTTP %d", response.StatusCode)
	}
	var release struct {
		Tag string `json:"tag_name"`
	}
	if err := json.NewDecoder(io.LimitReader(response.Body, 1024*1024)).Decode(&release); err != nil {
		return UpdateResult{}, err
	}
	newer := newerVersion(release.Tag, appVersion)
	text := "没有可用更新（最新发布 " + release.Tag + "）"
	if newer {
		text = "发现新版本 " + release.Tag
	}
	return UpdateResult{newer, text}, nil
}
func (a *App) OpenReleases()            { wruntime.BrowserOpenURL(a.ctx, releasesURL) }
func (a *App) TryMacro(id string) error { time.Sleep(2 * time.Second); return a.ToggleMacro(id) }
