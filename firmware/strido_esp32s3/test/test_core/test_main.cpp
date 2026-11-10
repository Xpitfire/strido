// Native unit tests of the firmware core: pio test -e native
// Golden values come from the Python mirror (packages/strido-core), so these tests
// also prove that host and MCU agree on the linkage model and the wire format.
#include <unity.h>

#include <cmath>
#include <cstdio>
#include <cstring>

#include "strido/kinematics.h"
#include "strido/protocol.h"
#include "strido/safety.h"
#include "strido/servo_map.h"

using namespace strido;

namespace {
constexpr float kDeg = 3.14159265358979323846f / 180.0f;
}

void setUp() { initKinematics(); }
void tearDown() {}

void test_linkage_matches_python_model() {
  float calf;
  TEST_ASSERT_TRUE(calfFromCrank(0, 45.0f * kDeg, 35.0f * kDeg, &calf));
  TEST_ASSERT_FLOAT_WITHIN(0.01f, -90.01659f, calf / kDeg);  // python: leg.calf_from_crank('FL', 45, 35)
  float crank;
  TEST_ASSERT_TRUE(crankFromCalf(3, 60.0f * kDeg, -110.0f * kDeg, &crank));
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 37.81137f, crank / kDeg);  // python: leg.crank_from_calf('RR', 60, -110)
}

void test_linkage_round_trip_over_the_workspace() {
  for (int leg = 0; leg < kLegCount; ++leg) {
    for (float thigh = -30.0f; thigh <= 120.0f; thigh += 10.0f) {
      for (float calf = -145.0f; calf <= -50.0f; calf += 5.0f) {
        float crank, back;
        TEST_ASSERT_TRUE(crankFromCalf(leg, thigh * kDeg, calf * kDeg, &crank));
        TEST_ASSERT_TRUE(calfFromCrank(leg, thigh * kDeg, crank, &back));
        TEST_ASSERT_FLOAT_WITHIN(1e-3f, calf * kDeg, back);
      }
    }
  }
}

void test_linkage_rejects_unreachable_crank() {
  float calf;
  // Crank pin pointing at the knee: the long link (131 mm) cannot span the 103 mm gap.
  TEST_ASSERT_FALSE(calfFromCrank(0, 0.0f, -180.0f * kDeg, &calf));
}

void test_crc_matches_ccitt_false_check_value() {
  const char* text = "123456789";
  TEST_ASSERT_EQUAL_HEX16(0x29B1, crc16(reinterpret_cast<const uint8_t*>(text), 9));
}

void test_joint_command_frame_matches_python_bytes() {
  // python: protocol.joint_command(7, 1, [0.1*i for i in range(12)]).hex()
  const char* golden =
      "030107020101010111cdcccc3dcdcc4c3e9a99993ecdcccc3e0101123f9a99193f3333333fcdcc4c3f6666663f0109803fcdcc8c3fc24200";
  uint8_t payload[kJointCommandPayloadSize];
  payload[0] = 7;
  payload[1] = 0;
  payload[2] = 1;
  for (int i = 0; i < 12; ++i) {
    const float value = static_cast<float>(0.1 * i);  // same rounding as Python's struct.pack('<f')
    memcpy(payload + 3 + 4 * i, &value, 4);
  }
  uint8_t frame[kMaxEncoded];
  const size_t length = encodeFrame(kJointCommand, payload, sizeof(payload), frame, sizeof(frame));
  char hex[2 * kMaxEncoded + 1] = {0};
  for (size_t i = 0; i < length; ++i) snprintf(hex + 2 * i, 3, "%02x", frame[i]);
  TEST_ASSERT_EQUAL_STRING(golden, hex);
}

void test_frame_reader_decodes_a_stream_and_drops_corruption() {
  uint8_t payload[kJointCommandPayloadSize] = {0};
  payload[0] = 42;
  uint8_t frame[kMaxEncoded];
  const size_t length = encodeFrame(kJointCommand, payload, sizeof(payload), frame, sizeof(frame));
  FrameReader reader;
  uint8_t packet[kMaxPacket];
  size_t decoded = 0;
  for (size_t i = 0; i < length; ++i) decoded = reader.push(frame[i], packet, sizeof(packet));
  uint8_t type;
  const uint8_t* body;
  size_t body_length;
  TEST_ASSERT_TRUE(parsePacket(packet, decoded, &type, &body, &body_length));
  TEST_ASSERT_EQUAL_UINT8(kJointCommand, type);
  TEST_ASSERT_EQUAL_UINT8(42, body[0]);
  frame[3] ^= 0x5A;  // corrupt one byte: CRC must reject it
  for (size_t i = 0; i < length; ++i) decoded = reader.push(frame[i], packet, sizeof(packet));
  TEST_ASSERT_FALSE(decoded > 0 && parsePacket(packet, decoded, &type, &body, &body_length));
}

void test_pulse_mapping_and_window() {
  ServoCalibration c{-1, 1500, 0.5f, 900, 2100};
  TEST_ASSERT_EQUAL_UINT16(1500, actuatorToPulse(c, 0.5f));
  TEST_ASSERT_EQUAL_UINT16(static_cast<uint16_t>(std::lround(1500 - kUsPerRad * 0.2f)), actuatorToPulse(c, 0.7f));
  TEST_ASSERT_EQUAL_UINT16(900, actuatorToPulse(c, 3.0f));   // clamped to the window
  TEST_ASSERT_EQUAL_UINT16(2100, actuatorToPulse(c, -3.0f));
  TEST_ASSERT_FLOAT_WITHIN(1e-3f, 0.7f, pulseToActuator(c, actuatorToPulse(c, 0.7f)));
}

void test_actuator_clamp_respects_generated_limits() {
  ActuatorAngles a{3.0f, -3.0f, 3.0f};
  TEST_ASSERT_TRUE(clampActuators(0, &a));
  TEST_ASSERT_FLOAT_WITHIN(1e-6f, kLegs[0].hip_max, a.hip);
  TEST_ASSERT_FLOAT_WITHIN(1e-6f, kLegs[0].thigh_min, a.thigh);
  TEST_ASSERT_TRUE(a.crank <= kLegs[0].crank_max + 1e-6f);
}

void test_watchdog_holds_then_relaxes() {
  SafetySupervisor safety;
  safety.setPowerMonitor(true);
  safety.onCommand(1000, true);
  TEST_ASSERT_EQUAL(DriveState::kActive, safety.update(1100));
  TEST_ASSERT_EQUAL(DriveState::kHolding, safety.update(1201));
  TEST_ASSERT_TRUE(safety.watchdogTripped());
  TEST_ASSERT_EQUAL(DriveState::kHolding, safety.update(3000));
  TEST_ASSERT_EQUAL(DriveState::kRelaxed, safety.update(3202));
  safety.onCommand(4000, true);
  TEST_ASSERT_EQUAL(DriveState::kActive, safety.update(4010));
}

void test_estop_latches_until_released_and_new_command() {
  SafetySupervisor safety;
  safety.setPowerMonitor(true);
  safety.onCommand(0, true);
  safety.onEstop(true);
  safety.onCommand(10, true);
  TEST_ASSERT_EQUAL(DriveState::kEstop, safety.update(20));
  safety.onEstop(false);
  TEST_ASSERT_EQUAL(DriveState::kRelaxed, safety.update(30));
  safety.onCommand(40, true);
  TEST_ASSERT_EQUAL(DriveState::kActive, safety.update(50));
}

void test_battery_cutoff_with_hysteresis() {
  SafetySupervisor safety;
  safety.setPowerMonitor(true);
  safety.onCommand(0, true);
  safety.onBattery(6.3f);  // one sagging sample (servo load) does not trip the cut-off
  safety.onBattery(7.2f);
  TEST_ASSERT_FALSE(safety.batteryCritical());
  for (int i = 0; i < 5; ++i) safety.onBattery(6.3f);
  TEST_ASSERT_TRUE(safety.batteryCritical());
  TEST_ASSERT_EQUAL(DriveState::kRelaxed, safety.update(1));
  safety.onBattery(6.6f);  // between cut-off and warning: stays critical
  safety.onCommand(2, true);
  TEST_ASSERT_EQUAL(DriveState::kRelaxed, safety.update(3));
  safety.onBattery(7.4f);
  safety.onCommand(4, true);
  TEST_ASSERT_EQUAL(DriveState::kActive, safety.update(5));
}

void test_no_power_monitor_refuses_to_drive() {
  SafetySupervisor safety;  // INA260 missing: no low-battery cut-off available
  safety.onCommand(0, true);
  TEST_ASSERT_EQUAL(DriveState::kRelaxed, safety.update(1));
}

void test_calibration_pulses_allowed_without_power_monitor() {
  SafetySupervisor safety;  // bench servo centring before the INA260 is wired
  safety.onCommand(0, true, /*calibration=*/true);
  TEST_ASSERT_EQUAL(DriveState::kActive, safety.update(1));
  safety.onCommand(2, true);  // a normal position command still needs the power monitor
  TEST_ASSERT_EQUAL(DriveState::kRelaxed, safety.update(3));
}

void test_non_finite_joint_command_is_rejected() {
  uint8_t payload[kJointCommandPayloadSize] = {0};
  payload[2] = kModePosition;
  const float nan = std::nanf("");
  memcpy(payload + 3 + 4 * 5, &nan, sizeof(nan));
  JointCommandMessage message;
  TEST_ASSERT_FALSE(deserialise(payload, sizeof(payload), &message));
  ActuatorAngles a{nan, nan, nan};
  clampActuators(0, &a);
  TEST_ASSERT_FLOAT_WITHIN(1e-6f, kLegs[0].hip_min, a.hip);  // NaN never reaches a pulse
}

void test_rate_limit_caps_step() {
  SafetySupervisor safety;
  float target[12] = {0};
  float previous[12] = {0};
  target[0] = 1.0f;
  TEST_ASSERT_TRUE(safety.rateLimit(target, previous, 0.005f));
  TEST_ASSERT_FLOAT_WITHIN(1e-6f, 6.0f * 0.005f, previous[0]);
}

int main() {
  UNITY_BEGIN();
  RUN_TEST(test_linkage_matches_python_model);
  RUN_TEST(test_linkage_round_trip_over_the_workspace);
  RUN_TEST(test_linkage_rejects_unreachable_crank);
  RUN_TEST(test_crc_matches_ccitt_false_check_value);
  RUN_TEST(test_joint_command_frame_matches_python_bytes);
  RUN_TEST(test_frame_reader_decodes_a_stream_and_drops_corruption);
  RUN_TEST(test_pulse_mapping_and_window);
  RUN_TEST(test_actuator_clamp_respects_generated_limits);
  RUN_TEST(test_watchdog_holds_then_relaxes);
  RUN_TEST(test_estop_latches_until_released_and_new_command);
  RUN_TEST(test_battery_cutoff_with_hysteresis);
  RUN_TEST(test_no_power_monitor_refuses_to_drive);
  RUN_TEST(test_calibration_pulses_allowed_without_power_monitor);
  RUN_TEST(test_non_finite_joint_command_is_rejected);
  RUN_TEST(test_rate_limit_caps_step);
  return UNITY_END();
}
