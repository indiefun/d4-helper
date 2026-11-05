// timingbench never injects input. Both implementations collect timestamps.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strconv"
	"strings"
	"time"

	"github.com/indiefun/d4-helper/go-desktop/internal/timing"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
func run() error {
	engine := flag.String("engine", "go", "go, native or both")
	intervals := flag.String("intervals", "1,2,5,10", "comma-separated positive millisecond intervals")
	seconds := flag.Float64("seconds", 2, "duration per measurement (0.1 to 60 seconds)")
	spinUS := flag.Int64("spin-us", 0, "optional final busy-wait window, microseconds")
	native := flag.String("native", "build/native-timingbench.exe", "path to safe native benchmark")
	output := flag.String("output", "", "optional JSON output path")
	idle := flag.Bool("idle", true, "include an idle CPU measurement")
	flag.Parse()
	if *engine != "go" && *engine != "native" && *engine != "both" {
		return fmt.Errorf("invalid engine")
	}
	if *seconds < .1 || *seconds > 60 || *spinUS < 0 {
		return fmt.Errorf("invalid duration or spin window")
	}
	values := []int{}
	if *idle {
		values = append(values, 0)
	}
	for _, text := range strings.Split(*intervals, ",") {
		n, err := strconv.Atoi(text)
		if err != nil || n < 1 || n > 1000 {
			return fmt.Errorf("invalid interval: %q", text)
		}
		values = append(values, n)
	}
	reports := []timing.Report{}
	for _, ms := range values {
		if *engine == "native" || *engine == "both" {
			data, err := exec.Command(*native, strconv.Itoa(ms), strconv.FormatFloat(*seconds, 'f', 3, 64)).Output()
			if err != nil {
				return fmt.Errorf("native benchmark: %w", err)
			}
			var report timing.Report
			if err := json.Unmarshal(data, &report); err != nil {
				return fmt.Errorf("native result: %w (%s)", err, data)
			}
			reports = append(reports, report)
		}
		if *engine == "go" || *engine == "both" {
			interval, spin := time.Duration(ms)*time.Millisecond, time.Duration(*spinUS)*time.Microsecond
			if ms > 0 && spin > interval {
				return fmt.Errorf("spin window must not exceed interval; equal means busy-wait")
			}
			samples := make([]time.Time, 0, int(*seconds*2000)+100)
			runtime.GC()
			cpuStart, err := timing.CPUTime()
			if err != nil {
				return err
			}
			start := time.Now()
			ctx, cancel := context.WithTimeout(context.Background(), time.Duration(*seconds*float64(time.Second)))
			if ms == 0 {
				<-ctx.Done()
			} else {
				err = timing.Run(ctx, interval, spin, func(at time.Time) { samples = append(samples, at) })
			}
			cancel()
			elapsed := time.Since(start)
			cpuEnd, cpuErr := timing.CPUTime()
			if err != nil {
				return err
			}
			if cpuErr != nil {
				return cpuErr
			}
			reports = append(reports, timing.Summarize("go-waitable-timer", interval, samples, elapsed, cpuEnd-cpuStart, spin))
		}
	}
	result := struct {
		MeasuredAt string          `json:"measured_at"`
		Platform   string          `json:"platform"`
		Runtime    string          `json:"runtime"`
		Notes      string          `json:"notes"`
		Reports    []timing.Report `json:"reports"`
	}{time.Now().UTC().Format(time.RFC3339), runtime.GOOS + "/" + runtime.GOARCH, runtime.Version(), "No SendInput calls. Native timestamps are captured at a stubbed SendInput; Go timestamps at a scheduler callback. This isolates scheduler timing, not game delivery. CPU percentage is relative to one logical core. Sequential, short samples are exploratory, not real-time guarantees.", reports}
	data, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		return err
	}
	if *output != "" {
		if err := os.WriteFile(*output, append(data, '\n'), 0644); err != nil {
			return err
		}
	}
	fmt.Println(string(data))
	return nil
}
