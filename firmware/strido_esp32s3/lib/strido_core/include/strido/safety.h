// Command watchdog, rate limiting and power supervision (pure C++).
#pragma once

#include <cstdint>

namespace strido {

enum class DriveState : uint8_t {
  kRelaxed = 0,  // PCA9685 outputs disabled (OE high), servos limp
  kActive = 1,   // following host commands
  kHolding = 2,  // command stream lost: hold last pose, then relax
  kEstop = 3,    // latched emergency stop: outputs disabled until released
};

struct SafetyConfig {
  uint32_t command_timeout_ms = 200;   // no command for this long -> hold
  uint32_t hold_timeout_ms = 2000;     // holding this long -> relax
  float max_joint_speed_rad_s = 6.0f;  // SPT5435LV: 0.14 s/60 deg @ 6 V = 7.5 rad/s
  float battery_warn_v = 6.8f;         // 3.4 V/cell
  float battery_cutoff_v = 6.4f;       // 3.2 V/cell -> relax and refuse to drive
  uint8_t battery_cutoff_samples = 5;  // consecutive low readings (10 Hz) before cut-off: ignores load sag spikes
};

class SafetySupervisor {
 public:
  explicit SafetySupervisor(SafetyConfig config = SafetyConfig()) : config_(config) {}

  // `calibration`: raw-pulse bench mode (servo centring), allowed without the power monitor.
  void onCommand(uint32_t now_ms, bool wants_position, bool calibration = false);
  void onEstop(bool engaged);
  void onBattery(float volts);
  // Without a working power monitor there is no low-battery cut-off, so driving is refused.
  void setPowerMonitor(bool present) { power_monitor_ = present; }
  // Advance timers; returns the state the outputs must follow.
  DriveState update(uint32_t now_ms);

  DriveState state() const { return state_; }
  bool batteryLow() const { return battery_low_; }
  bool batteryCritical() const { return battery_critical_; }
  bool watchdogTripped() const { return watchdog_tripped_; }

  // Limit the change of each target so the servo never gets a step larger than
  // max speed * dt. `previous` is updated in place. Returns true if limited.
  bool rateLimit(const float target[12], float previous[12], float dt_s) const;

 private:
  SafetyConfig config_;
  DriveState state_ = DriveState::kRelaxed;
  uint32_t last_command_ms_ = 0;
  uint32_t hold_since_ms_ = 0;
  bool estop_ = false;
  bool battery_low_ = false;
  bool battery_critical_ = false;
  bool watchdog_tripped_ = false;
  bool wants_position_ = false;
  bool power_monitor_ = false;
  uint8_t low_samples_ = 0;
};

}  // namespace strido
