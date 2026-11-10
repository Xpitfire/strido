#include "strido/safety.h"

#include <cmath>

namespace strido {

void SafetySupervisor::onCommand(uint32_t now_ms, bool wants_position, bool calibration) {
  last_command_ms_ = now_ms;
  wants_position_ = wants_position;
  watchdog_tripped_ = false;
  if (state_ == DriveState::kEstop) return;
  if (!wants_position || battery_critical_ || (!power_monitor_ && !calibration)) {
    state_ = DriveState::kRelaxed;
    return;
  }
  state_ = DriveState::kActive;
}

void SafetySupervisor::onEstop(bool engaged) {
  estop_ = engaged;
  if (engaged) {
    state_ = DriveState::kEstop;
  } else if (state_ == DriveState::kEstop) {
    state_ = DriveState::kRelaxed;  // must receive a fresh position command to move again
  }
}

void SafetySupervisor::onBattery(float volts) {
  // Ignore implausible readings (sensor absent reports 0 V).
  if (volts < 1.0f) return;
  battery_low_ = volts < config_.battery_warn_v;
  // Debounce: only consecutive low readings trip the cut-off (servo load causes short sags).
  // Hysteresis: once critical, require recovery above the warning level.
  if (volts < config_.battery_cutoff_v) {
    if (low_samples_ < config_.battery_cutoff_samples) ++low_samples_;
    if (low_samples_ >= config_.battery_cutoff_samples) battery_critical_ = true;
  } else {
    low_samples_ = 0;
    if (volts > config_.battery_warn_v) battery_critical_ = false;
  }
  if (battery_critical_ && state_ != DriveState::kEstop) state_ = DriveState::kRelaxed;
}

DriveState SafetySupervisor::update(uint32_t now_ms) {
  if (estop_) {
    state_ = DriveState::kEstop;
    return state_;
  }
  if (state_ == DriveState::kActive && now_ms - last_command_ms_ > config_.command_timeout_ms) {
    state_ = DriveState::kHolding;
    hold_since_ms_ = now_ms;
    watchdog_tripped_ = true;
  }
  if (state_ == DriveState::kHolding && now_ms - hold_since_ms_ > config_.hold_timeout_ms) {
    state_ = DriveState::kRelaxed;
  }
  return state_;
}

bool SafetySupervisor::rateLimit(const float target[12], float previous[12], float dt_s) const {
  const float step = config_.max_joint_speed_rad_s * dt_s;
  bool limited = false;
  for (int i = 0; i < 12; ++i) {
    if (!std::isfinite(target[i])) {  // keep the last good value
      limited = true;
      continue;
    }
    const float delta = target[i] - previous[i];
    if (std::fabs(delta) > step) {
      previous[i] += delta > 0 ? step : -step;
      limited = true;
    } else {
      previous[i] = target[i];
    }
  }
  return limited;
}

}  // namespace strido
