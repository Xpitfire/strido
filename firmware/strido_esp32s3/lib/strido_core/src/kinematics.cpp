#include "strido/kinematics.h"

#include <cmath>

namespace strido {
namespace {

constexpr float kPi = 3.14159265358979323846f;

float forwardSide[kLegCount];
float inverseSide[kLegCount];
bool initialised = false;

float wrap(float angle) { return std::remainder(angle, 2.0f * kPi); }

Vec2 polar(float radius, float angle) { return {radius * std::cos(angle), radius * std::sin(angle)}; }

Vec2 add(Vec2 a, Vec2 b) { return {a.u + b.u, a.v + b.v}; }

Vec2 sub(Vec2 a, Vec2 b) { return {a.u - b.u, a.v - b.v}; }

float cross(Vec2 a, Vec2 b) { return a.u * b.v - a.v * b.u; }

float angleOf(Vec2 a) { return std::atan2(a.v, a.u); }

float sign(float x) { return x > 0.0f ? 1.0f : (x < 0.0f ? -1.0f : 0.0f); }

Vec2 kneePoint(const LegGeometry& leg, float thigh) {
  return {-leg.thigh_length * std::sin(thigh), -leg.thigh_length * std::cos(thigh)};
}

// Direction (atan2 in the u-v plane) of the knee->foot vector.
float calfDirection(float thigh, float calf) { return -kPi / 2.0f - (thigh + calf); }

// Circle-circle intersection; picks the solution on `side` of c0->c1.
bool intersect(Vec2 c0, float r0, Vec2 c1, float r1, float side, Vec2* out) {
  const Vec2 delta = sub(c1, c0);
  const float distance = std::sqrt(delta.u * delta.u + delta.v * delta.v);
  if (distance < 1e-9f || distance > r0 + r1 || distance < std::fabs(r0 - r1)) return false;
  const float along = (r0 * r0 - r1 * r1 + distance * distance) / (2.0f * distance);
  const float height = std::sqrt(std::fmax(r0 * r0 - along * along, 0.0f));
  const Vec2 base = {c0.u + along * delta.u / distance, c0.v + along * delta.v / distance};
  const Vec2 normal = {-delta.v / distance, delta.u / distance};
  const Vec2 candidate = {base.u + height * normal.u, base.v + height * normal.v};
  if (sign(cross(delta, sub(candidate, c0))) == side || height == 0.0f) {
    *out = candidate;
  } else {
    *out = {base.u - height * normal.u, base.v - height * normal.v};
  }
  return true;
}

}  // namespace

void initKinematics() {
  for (int leg = 0; leg < kLegCount; ++leg) {
    const LegGeometry& g = kLegs[leg];
    const Vec2 knee = kneePoint(g, g.cad_thigh_angle);
    const Vec2 crankB = polar(g.crank_radius_b, g.cad_crank_angle + g.crank_offset);
    const Vec2 tibiaPin = add(knee, polar(g.tibia_radius, calfDirection(g.cad_thigh_angle, g.cad_calf_angle) + g.tibia_offset));
    forwardSide[leg] = sign(cross(sub(crankB, knee), sub(tibiaPin, knee)));
    inverseSide[leg] = sign(cross(tibiaPin, crankB));
  }
  initialised = true;
}

bool crankFromCalf(int leg, float thigh, float calf, float* crank) {
  if (!initialised || leg < 0 || leg >= kLegCount) return false;
  const LegGeometry& g = kLegs[leg];
  const Vec2 knee = kneePoint(g, thigh);
  const Vec2 tibiaPin = add(knee, polar(g.tibia_radius, calfDirection(thigh, calf) + g.tibia_offset));
  Vec2 crankB;
  if (!intersect({0.0f, 0.0f}, g.crank_radius_b, tibiaPin, g.long_link, inverseSide[leg], &crankB)) return false;
  *crank = wrap(angleOf(crankB) - g.crank_offset);
  return true;
}

bool calfFromCrank(int leg, float thigh, float crank, float* calf) {
  if (!initialised || leg < 0 || leg >= kLegCount) return false;
  const LegGeometry& g = kLegs[leg];
  const Vec2 knee = kneePoint(g, thigh);
  const Vec2 crankB = polar(g.crank_radius_b, crank + g.crank_offset);
  Vec2 tibiaPin;
  if (!intersect(knee, g.tibia_radius, crankB, g.long_link, forwardSide[leg], &tibiaPin)) return false;
  const float direction = angleOf(sub(tibiaPin, knee)) - g.tibia_offset;
  *calf = wrap(-kPi / 2.0f - direction - thigh);
  return true;
}

bool minTransmissionAngle(int leg, float thigh, float calf, float* angle) {
  float crank;
  if (!crankFromCalf(leg, thigh, calf, &crank)) return false;
  const LegGeometry& g = kLegs[leg];
  const Vec2 knee = kneePoint(g, thigh);
  const Vec2 crankB = polar(g.crank_radius_b, crank + g.crank_offset);
  const Vec2 tibiaPin = add(knee, polar(g.tibia_radius, calfDirection(thigh, calf) + g.tibia_offset));
  const Vec2 link = sub(tibiaPin, crankB);
  const float atCrank = std::fabs(std::remainder(angleOf(link) - angleOf(crankB), kPi));
  const float atTibia = std::fabs(std::remainder(angleOf(link) - angleOf(sub(tibiaPin, knee)), kPi));
  *angle = std::fmin(atCrank, atTibia);
  return true;
}

}  // namespace strido
