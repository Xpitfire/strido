#include "strido/servo_map.h"

#include <cmath>

namespace strido {
namespace {

// NaN maps to `low` (comparisons with NaN are false, so the naive form would pass it through).
float clampf(float value, float low, float high) { return !(value >= low) ? low : (value > high ? high : value); }

}  // namespace

ServoCalibration defaultCalibration(int joint) {
  const LegGeometry& g = kLegs[joint / 3];
  ServoCalibration calibration{};
  calibration.neutral_us = 1500;
  switch (joint % 3) {
    case kHip:
      calibration.direction = static_cast<int8_t>(g.dir_hip);
      calibration.zero_rad = g.neutral_hip;
      break;
    case kThigh:
      calibration.direction = static_cast<int8_t>(g.dir_thigh);
      calibration.zero_rad = g.neutral_thigh;
      break;
    default:
      calibration.direction = static_cast<int8_t>(g.dir_crank);
      calibration.zero_rad = g.neutral_crank;
      break;
  }
  calibration.min_us = static_cast<uint16_t>(kPulseMinUs);
  calibration.max_us = static_cast<uint16_t>(kPulseMaxUs);
  return calibration;
}

bool jointsToActuators(int leg, const float q[3], ActuatorAngles* out) {
  float crank;
  if (!crankFromCalf(leg, q[1], q[2], &crank)) return false;
  out->hip = q[0];
  out->thigh = q[1];
  out->crank = crank;
  return true;
}

bool clampActuators(int leg, ActuatorAngles* angles) {
  const LegGeometry& g = kLegs[leg];
  const ActuatorAngles before = *angles;
  angles->hip = clampf(angles->hip, g.hip_min, g.hip_max);
  angles->thigh = clampf(angles->thigh, g.thigh_min, g.thigh_max);
  angles->crank = clampf(angles->crank, g.crank_min, g.crank_max);
  // The knee angle that results from (thigh, crank) must stay inside its own window too.
  float calf;
  if (calfFromCrank(leg, angles->thigh, angles->crank, &calf)) {
    const float limited = clampf(calf, g.calf_min, g.calf_max);
    if (limited != calf) {
      float crank;
      if (crankFromCalf(leg, angles->thigh, limited, &crank)) angles->crank = clampf(crank, g.crank_min, g.crank_max);
    }
  }
  return before.hip != angles->hip || before.thigh != angles->thigh || before.crank != angles->crank;
}

uint16_t actuatorToPulse(const ServoCalibration& c, float angle) {
  const float pulse = static_cast<float>(c.neutral_us) + static_cast<float>(c.direction) * kUsPerRad * (angle - c.zero_rad);
  return static_cast<uint16_t>(std::lround(clampf(pulse, static_cast<float>(c.min_us), static_cast<float>(c.max_us))));
}

float pulseToActuator(const ServoCalibration& c, uint16_t pulse_us) {
  return c.zero_rad + (static_cast<float>(pulse_us) - static_cast<float>(c.neutral_us)) / (static_cast<float>(c.direction) * kUsPerRad);
}

}  // namespace strido
