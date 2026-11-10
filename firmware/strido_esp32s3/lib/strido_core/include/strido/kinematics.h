// Knee linkage and joint/actuator mapping for Strido (mirror of
// packages/strido-core/src/strido/leg.py). Pure C++, no Arduino dependency, so it
// runs in the native unit tests too.
#pragma once

#include <cstdint>

#include "strido/geometry_generated.h"

namespace strido {

constexpr int kLegCount = 4;
constexpr int kJointCount = 12;

// Joint index = leg * 3 + {0 hip, 1 thigh, 2 calf}; legs FL, FR, RL, RR.
enum JointSlot : uint8_t { kHip = 0, kThigh = 1, kCalf = 2 };

struct Vec2 {
  float u;
  float v;
};

// Call once at boot: resolves the linkage assembly branch from the CAD pose.
void initKinematics();

// Crank angle psi (rad) the knee-drive servo must hold for thigh/calf joint
// angles. Returns false when the four-bar cannot close (out of reach).
bool crankFromCalf(int leg, float thigh, float calf, float* crank);

// Knee joint angle for a thigh angle and crank angle (forward linkage).
bool calfFromCrank(int leg, float thigh, float crank, float* calf);

// Smallest knee four-bar transmission angle (rad); near 0 = singular.
bool minTransmissionAngle(int leg, float thigh, float calf, float* angle);

}  // namespace strido
