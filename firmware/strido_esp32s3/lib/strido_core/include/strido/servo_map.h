// Joint angles <-> servo pulse widths, with per-servo calibration and limits.
// Pure C++ (native-testable). Mirror: packages/strido-core/src/strido/leg.py
#pragma once

#include <cstdint>

#include "strido/kinematics.h"

namespace strido {

// SPT5435LV-180W: 500-2500 us = 180 degrees, neutral 1500 us (datasheet).
constexpr float kPulseMinUs = 500.0f;
constexpr float kPulseMaxUs = 2500.0f;
constexpr float kUsPerRad = (kPulseMaxUs - kPulseMinUs) / 3.14159265358979323846f;

struct ServoCalibration {
  int8_t direction;     // +1 or -1: sign between shaft angle and pulse width
  uint16_t neutral_us;  // pulse that holds the shaft at `zero_rad`
  float zero_rad;       // actuator angle (hip, thigh or crank) at the neutral pulse
  uint16_t min_us;      // hard pulse window (mechanical limits, from the ROM sweep)
  uint16_t max_us;
};

// Actuator angles for one leg: hip q1, thigh q2, knee-drive crank psi.
struct ActuatorAngles {
  float hip;
  float thigh;
  float crank;
};

// Default calibration derived from hardware/joint_limits.yaml (generated).
ServoCalibration defaultCalibration(int joint);

// Joint angles (q1, q2, q3) of a leg -> actuator angles. False if unreachable.
bool jointsToActuators(int leg, const float q[3], ActuatorAngles* out);

// Clamp actuator angles to the generated limits; returns true if clamped.
bool clampActuators(int leg, ActuatorAngles* angles);

// Actuator angle -> pulse width in microseconds (clamped to the calibration window).
uint16_t actuatorToPulse(const ServoCalibration& calibration, float angle);
float pulseToActuator(const ServoCalibration& calibration, uint16_t pulse_us);

}  // namespace strido
