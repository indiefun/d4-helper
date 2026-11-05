package timing

import (
	"math"
	"sort"
	"time"
)

type Report struct {
	Engine            string  `json:"engine"`
	IntervalMS        float64 `json:"interval_ms"`
	Samples           int     `json:"samples"`
	MeanMS            float64 `json:"mean_ms"`
	P50MS             float64 `json:"p50_ms"`
	P95MS             float64 `json:"p95_ms"`
	P99MS             float64 `json:"p99_ms"`
	MaxMS             float64 `json:"max_ms"`
	CPUPercentOneCore float64 `json:"cpu_percent_one_core"`
	ElapsedSeconds    float64 `json:"elapsed_seconds"`
	SpinUS            int64   `json:"spin_us"`
}

func Summarize(engine string, interval time.Duration, samples []time.Time, elapsed, cpu time.Duration, spin time.Duration) Report {
	r := Report{Engine: engine, IntervalMS: float64(interval) / float64(time.Millisecond), Samples: len(samples), CPUPercentOneCore: 100 * float64(cpu) / float64(elapsed), ElapsedSeconds: elapsed.Seconds(), SpinUS: spin.Microseconds()}
	if len(samples) < 2 {
		return r
	}
	gaps := make([]float64, 0, len(samples)-1)
	for i := 1; i < len(samples); i++ {
		gap := float64(samples[i].Sub(samples[i-1])) / float64(time.Millisecond)
		gaps = append(gaps, gap)
		r.MeanMS += gap
	}
	r.MeanMS /= float64(len(gaps))
	sort.Float64s(gaps)
	percentile := func(p float64) float64 { return gaps[int(math.Ceil(p*float64(len(gaps))))-1] }
	r.P50MS, r.P95MS, r.P99MS, r.MaxMS = percentile(.5), percentile(.95), percentile(.99), gaps[len(gaps)-1]
	return r
}
