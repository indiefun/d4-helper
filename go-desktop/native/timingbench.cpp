// Compile the actual legacy scheduler with all input injection replaced by
// local timestamp collectors. This program must NEVER call real SendInput.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <vector>

static std::vector<LONGLONG> samples;
static UINT WINAPI collect_input(UINT count, LPINPUT, int) {
    if (count == 2) {
        LARGE_INTEGER now{};
        QueryPerformanceCounter(&now);
        samples.push_back(now.QuadPart);
    }
    return count;
}
static BOOL WINAPI ignore_cursor(int, int) { return TRUE; }
#define SendInput collect_input
#define SetCursorPos ignore_cursor
#include "../../native/fast_input_kernel.cpp"
#undef SendInput
#undef SetCursorPos

static ULONGLONG cpu_ticks() {
    FILETIME creation{}, exit{}, kernel{}, user{};
    if (!GetProcessTimes(GetCurrentProcess(), &creation, &exit, &kernel, &user)) return 0;
    ULARGE_INTEGER k{}, u{};
    k.LowPart = kernel.dwLowDateTime; k.HighPart = kernel.dwHighDateTime;
    u.LowPart = user.dwLowDateTime; u.HighPart = user.dwHighDateTime;
    return k.QuadPart + u.QuadPart;
}

int main(int argc, char** argv) {
    if (argc != 3) return 2;
    const int interval = std::atoi(argv[1]);
    const double seconds = std::atof(argv[2]);
    if (interval < 0 || interval > 1000 || seconds < .1 || seconds > 60) return 2;
    samples.reserve(static_cast<size_t>(seconds * 2000 + 100));
    LARGE_INTEGER frequency{}, start{}, end{};
    QueryPerformanceFrequency(&frequency);
    FastEngine engine;
    const int key = 0x100 + 'F';
    if (interval > 0) {
        engine.configure(0, true, 2, interval, false, &key, 1, nullptr, 0, nullptr, 0);
        engine.set_target_active(true);
        engine.set_active(0, true);
    }
    const auto cpu_start = cpu_ticks();
    QueryPerformanceCounter(&start);
    engine.start();
    Sleep(static_cast<DWORD>(seconds * 1000));
    engine.stop();
    QueryPerformanceCounter(&end);
    const auto cpu_end = cpu_ticks();
    const double elapsed = static_cast<double>(end.QuadPart - start.QuadPart) / frequency.QuadPart;
    std::vector<double> gaps;
    double mean = 0;
    for (size_t i = 1; i < samples.size(); ++i) {
        const double ms = 1000.0 * (samples[i] - samples[i - 1]) / frequency.QuadPart;
        gaps.push_back(ms); mean += ms;
    }
    if (!gaps.empty()) mean /= gaps.size();
    std::sort(gaps.begin(), gaps.end());
    const auto percentile = [&gaps](double p) {
        return gaps.empty() ? 0.0 : gaps[static_cast<size_t>(std::ceil(p * gaps.size())) - 1];
    };
    std::printf("{\"engine\":\"cpp-legacy-stubbed\",\"interval_ms\":%d,\"samples\":%zu,\"mean_ms\":%.6f,\"p50_ms\":%.6f,\"p95_ms\":%.6f,\"p99_ms\":%.6f,\"max_ms\":%.6f,\"cpu_percent_one_core\":%.3f,\"elapsed_seconds\":%.6f,\"spin_us\":0}\n",
        interval, samples.size(), mean, percentile(.5), percentile(.95), percentile(.99), percentile(1),
        100.0 * (cpu_end - cpu_start) / 10000000.0 / elapsed, elapsed);
    return 0;
}
