#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <mmsystem.h>

#include <algorithm>
#include <atomic>
#include <cstdint>
#include <mutex>
#include <thread>
#include <vector>

#pragma comment(lib, "winmm.lib")
#pragma comment(lib, "user32.lib")

namespace {

constexpr int kActionNone = 0;
constexpr int kActionHold = 1;
constexpr int kActionCycle = 2;
constexpr int kActionRecorded = 3;
constexpr int kPlaybackLoop = 1;

constexpr int kMouseLeft = 1;
constexpr int kMouseRight = 2;
constexpr int kMouseMiddle = 3;
constexpr int kKeyboardBase = 0x100;

struct FastEvent {
    int type;       // 1 = key down, 2 = key up
    int key;
    int at_ms;
    int x;
    int y;
    int has_pos;
};

struct FastMacro {
    bool enabled = false;
    int action = kActionNone;
    int interval_ms = 100;
    bool playback_loop = false;
    bool active = false;
    std::vector<int> sequence;
    std::vector<int> hold_items;
    std::vector<FastEvent> events;
    size_t sequence_index = 0;
    size_t event_index = 0;
    int64_t next_cycle_qpc = 0;
    int64_t playback_start_qpc = 0;
    int64_t loop_ready_qpc = 0;
    std::vector<int> playback_held_items;
};

class FastEngine {
public:
    FastEngine() {
        LARGE_INTEGER frequency{};
        QueryPerformanceFrequency(&frequency);
        qpc_frequency_ = frequency.QuadPart > 0 ? frequency.QuadPart : 10000000;
        macros_.resize(64);
    }

    ~FastEngine() { stop(); }

    void start() {
        bool expected = false;
        if (!running_.compare_exchange_strong(expected, true)) {
            return;
        }
        timeBeginPeriod(1);
        worker_ = std::thread(&FastEngine::run, this);
    }

    void stop() {
        bool expected = true;
        if (!running_.compare_exchange_strong(expected, false)) {
            return;
        }
        if (worker_.joinable()) {
            worker_.join();
        }
        std::lock_guard<std::mutex> guard(lock_);
        release_all_locked();
        for (auto& macro : macros_) {
            macro.active = false;
            macro.playback_held_items.clear();
        }
        timeEndPeriod(1);
    }

    void configure(
        int slot,
        bool enabled,
        int action,
        int interval_ms,
        bool playback_loop,
        const int* sequence,
        int sequence_count,
        const int* hold_items,
        int hold_count,
        const FastEvent* events,
        int event_count) {
        if (slot < 0 || slot >= static_cast<int>(macros_.size())) {
            return;
        }
        std::lock_guard<std::mutex> guard(lock_);
        FastMacro& macro = macros_[slot];
        release_macro_locked(slot);
        macro.enabled = enabled;
        macro.action = action;
        macro.interval_ms = std::max(interval_ms, 1);
        macro.playback_loop = playback_loop;
        macro.sequence.clear();
        macro.hold_items.clear();
        macro.events.clear();
        if (sequence && sequence_count > 0) {
            macro.sequence.assign(sequence, sequence + sequence_count);
        }
        if (hold_items && hold_count > 0) {
            macro.hold_items.assign(hold_items, hold_items + hold_count);
        }
        if (events && event_count > 0) {
            macro.events.assign(events, events + event_count);
        }
        macro.active = false;
        reset_timing_locked(macro);
    }

    void clear_config() {
        std::lock_guard<std::mutex> guard(lock_);
        release_all_locked();
        for (auto& macro : macros_) {
            macro = FastMacro{};
        }
    }

    void set_active(int slot, bool active) {
        if (slot < 0 || slot >= static_cast<int>(macros_.size())) {
            return;
        }
        std::lock_guard<std::mutex> guard(lock_);
        FastMacro& macro = macros_[slot];
        if (!macro.enabled || macro.action == kActionNone) {
            macro.active = false;
            return;
        }
        if (active == macro.active) {
            return;
        }
        if (active) {
            macro.active = true;
            reset_timing_locked(macro);
            if (macro.action == kActionHold) {
                for (int key : macro.hold_items) {
                    if (!is_owned_locked(key, slot)) {
                        send_input(key, true);
                    }
                }
            }
        } else {
            release_macro_locked(slot);
        }
    }

    bool is_active(int slot) {
        if (slot < 0 || slot >= static_cast<int>(macros_.size())) {
            return false;
        }
        std::lock_guard<std::mutex> guard(lock_);
        return macros_[slot].active;
    }

    void set_target_active(bool active) {
        std::lock_guard<std::mutex> guard(lock_);
        if (target_active_ == active) {
            return;
        }
        target_active_ = active;
        if (!active) {
            release_all_locked();
            for (auto& macro : macros_) {
                macro.active = false;
                macro.playback_held_items.clear();
            }
        }
    }

    void reset_active() {
        std::lock_guard<std::mutex> guard(lock_);
        release_all_locked();
        for (auto& macro : macros_) {
            macro.active = false;
            macro.playback_held_items.clear();
            reset_timing_locked(macro);
        }
    }

private:
    int64_t now_qpc() const {
        LARGE_INTEGER value{};
        QueryPerformanceCounter(&value);
        return value.QuadPart;
    }

    int64_t ms_to_qpc(int ms) const {
        return (qpc_frequency_ * static_cast<int64_t>(std::max(ms, 0))) / 1000;
    }

    void reset_timing_locked(FastMacro& macro) {
        const int64_t now = now_qpc();
        macro.sequence_index = 0;
        macro.event_index = 0;
        macro.next_cycle_qpc = now;
        macro.playback_start_qpc = now;
        macro.loop_ready_qpc = 0;
        macro.playback_held_items.clear();
    }

    static bool is_mouse_key(int key) {
        return key >= kMouseLeft && key <= kMouseMiddle;
    }

    static WORD virtual_key(int key) {
        return static_cast<WORD>(key - kKeyboardBase);
    }

    static DWORD mouse_down_flag(int key) {
        switch (key) {
        case kMouseLeft: return MOUSEEVENTF_LEFTDOWN;
        case kMouseRight: return MOUSEEVENTF_RIGHTDOWN;
        case kMouseMiddle: return MOUSEEVENTF_MIDDLEDOWN;
        default: return 0;
        }
    }

    static DWORD mouse_up_flag(int key) {
        switch (key) {
        case kMouseLeft: return MOUSEEVENTF_LEFTUP;
        case kMouseRight: return MOUSEEVENTF_RIGHTUP;
        case kMouseMiddle: return MOUSEEVENTF_MIDDLEUP;
        default: return 0;
        }
    }

    void send_input(int key, bool down) {
        INPUT input{};
        if (is_mouse_key(key)) {
            input.type = INPUT_MOUSE;
            input.mi.dwFlags = down ? mouse_down_flag(key) : mouse_up_flag(key);
        } else if (key >= kKeyboardBase) {
            input.type = INPUT_KEYBOARD;
            input.ki.wVk = virtual_key(key);
            input.ki.dwFlags = down ? 0 : KEYEVENTF_KEYUP;
        } else {
            return;
        }
        SendInput(1, &input, sizeof(INPUT));
    }

    void send_tap(int key) {
        INPUT inputs[2]{};
        if (is_mouse_key(key)) {
            inputs[0].type = INPUT_MOUSE;
            inputs[0].mi.dwFlags = mouse_down_flag(key);
            inputs[1].type = INPUT_MOUSE;
            inputs[1].mi.dwFlags = mouse_up_flag(key);
        } else if (key >= kKeyboardBase) {
            inputs[0].type = INPUT_KEYBOARD;
            inputs[0].ki.wVk = virtual_key(key);
            inputs[1].type = INPUT_KEYBOARD;
            inputs[1].ki.wVk = virtual_key(key);
            inputs[1].ki.dwFlags = KEYEVENTF_KEYUP;
        } else {
            return;
        }
        SendInput(2, inputs, sizeof(INPUT));
    }

    bool contains(const std::vector<int>& values, int key) const {
        return std::find(values.begin(), values.end(), key) != values.end();
    }

    bool is_owned_locked(int key, int excluding_slot = -1) const {
        for (int index = 0; index < static_cast<int>(macros_.size()); ++index) {
            if (index == excluding_slot) {
                continue;
            }
            const FastMacro& macro = macros_[index];
            if (!macro.active) {
                continue;
            }
            if (macro.action == kActionHold && contains(macro.hold_items, key)) {
                return true;
            }
            if (macro.action == kActionRecorded && contains(macro.playback_held_items, key)) {
                return true;
            }
        }
        return false;
    }

    void release_recorded_items_locked(int slot) {
        FastMacro& macro = macros_[slot];
        for (int key : macro.playback_held_items) {
            if (!is_owned_locked(key, slot)) {
                send_input(key, false);
            }
        }
        macro.playback_held_items.clear();
    }

    void release_macro_locked(int slot) {
        FastMacro& macro = macros_[slot];
        if (!macro.active) {
            return;
        }
        if (macro.action == kActionHold) {
            for (int key : macro.hold_items) {
                if (!is_owned_locked(key, slot)) {
                    send_input(key, false);
                }
            }
        } else if (macro.action == kActionRecorded) {
            release_recorded_items_locked(slot);
        }
        macro.active = false;
        reset_timing_locked(macro);
    }

    void release_all_locked() {
        for (int index = 0; index < static_cast<int>(macros_.size()); ++index) {
            release_macro_locked(index);
        }
    }

    int64_t process_macro_locked(int slot, int64_t now, int64_t next_due) {
        FastMacro& macro = macros_[slot];
        if (!macro.active || !macro.enabled) {
            return next_due;
        }
        if (macro.action == kActionCycle) {
            if (macro.sequence.empty()) {
                return next_due;
            }
            while (now >= macro.next_cycle_qpc) {
                int key = macro.sequence[macro.sequence_index % macro.sequence.size()];
                ++macro.sequence_index;
                send_tap(key);
                if (is_owned_locked(key, slot)) {
                    send_input(key, true);
                }
                macro.next_cycle_qpc += ms_to_qpc(macro.interval_ms);
                if (macro.next_cycle_qpc <= now) {
                    macro.next_cycle_qpc = now + ms_to_qpc(macro.interval_ms);
                }
            }
            return std::min(next_due, macro.next_cycle_qpc);
        }
        if (macro.action != kActionRecorded || macro.events.empty()) {
            return next_due;
        }

        if (macro.loop_ready_qpc != 0) {
            if (now < macro.loop_ready_qpc) {
                return std::min(next_due, macro.loop_ready_qpc);
            }
            macro.loop_ready_qpc = 0;
            macro.event_index = 0;
            macro.playback_start_qpc = now;
        }

        const int elapsed_ms = static_cast<int>(
            ((now - macro.playback_start_qpc) * 1000) / qpc_frequency_);
        while (macro.event_index < macro.events.size() &&
               macro.events[macro.event_index].at_ms <= elapsed_ms) {
            const FastEvent& event = macro.events[macro.event_index++];
            if (event.has_pos) {
                SetCursorPos(event.x, event.y);
            }
            if (event.type == 1) {
                if (!contains(macro.playback_held_items, event.key)) {
                    if (!is_owned_locked(event.key, slot)) {
                        send_input(event.key, true);
                    }
                    macro.playback_held_items.push_back(event.key);
                }
            } else if (event.type == 2 && contains(macro.playback_held_items, event.key)) {
                macro.playback_held_items.erase(
                    std::remove(macro.playback_held_items.begin(), macro.playback_held_items.end(), event.key),
                    macro.playback_held_items.end());
                if (!is_owned_locked(event.key, slot)) {
                    send_input(event.key, false);
                }
            }
        }

        if (macro.event_index >= macro.events.size()) {
            release_recorded_items_locked(slot);
            if (macro.playback_loop) {
                macro.loop_ready_qpc = now + ms_to_qpc(macro.interval_ms);
                return std::min(next_due, macro.loop_ready_qpc);
            }
            macro.active = false;
            return next_due;
        }
        return std::min(next_due, macro.playback_start_qpc + ms_to_qpc(macro.events[macro.event_index].at_ms));
    }

    void run() {
        SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_HIGHEST);
        while (running_.load(std::memory_order_relaxed)) {
            int64_t next_due = now_qpc() + ms_to_qpc(1);
            {
                std::lock_guard<std::mutex> guard(lock_);
                if (target_active_) {
                    const int64_t now = now_qpc();
                    for (int slot = 0; slot < static_cast<int>(macros_.size()); ++slot) {
                        next_due = process_macro_locked(slot, now, next_due);
                    }
                }
            }
            const int64_t remaining = next_due - now_qpc();
            if (remaining > qpc_frequency_ / 1000) {
                Sleep(1);
            } else {
                SwitchToThread();
            }
        }
    }

    std::mutex lock_;
    std::vector<FastMacro> macros_;
    std::thread worker_;
    std::atomic<bool> running_{false};
    bool target_active_ = false;
    int64_t qpc_frequency_ = 10000000;
};

} // namespace

extern "C" {

__declspec(dllexport) void* rhk_create() {
    return new FastEngine();
}

__declspec(dllexport) void rhk_destroy(void* handle) {
    delete static_cast<FastEngine*>(handle);
}

__declspec(dllexport) void rhk_start(void* handle) {
    if (handle) static_cast<FastEngine*>(handle)->start();
}

__declspec(dllexport) void rhk_stop(void* handle) {
    if (handle) static_cast<FastEngine*>(handle)->stop();
}

__declspec(dllexport) void rhk_clear_config(void* handle) {
    if (handle) static_cast<FastEngine*>(handle)->clear_config();
}

__declspec(dllexport) void rhk_set_target_active(void* handle, int active) {
    if (handle) static_cast<FastEngine*>(handle)->set_target_active(active != 0);
}

__declspec(dllexport) void rhk_set_active(void* handle, int slot, int active) {
    if (handle) static_cast<FastEngine*>(handle)->set_active(slot, active != 0);
}

__declspec(dllexport) int rhk_is_active(void* handle, int slot) {
    return handle && static_cast<FastEngine*>(handle)->is_active(slot) ? 1 : 0;
}

__declspec(dllexport) void rhk_configure_macro(
    void* handle,
    int slot,
    int enabled,
    int action,
    int interval_ms,
    int playback_loop,
    const int* sequence,
    int sequence_count,
    const int* hold_items,
    int hold_count,
    const FastEvent* events,
    int event_count) {
    if (handle) {
        static_cast<FastEngine*>(handle)->configure(
            slot, enabled != 0, action, interval_ms, playback_loop != 0,
            sequence, sequence_count, hold_items, hold_count, events, event_count);
    }
}

}
