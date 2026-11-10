// Strido MCU firmware (Seeed XIAO ESP32S3).
//
// Responsibilities (everything else lives on the Raspberry Pi / ROS 2):
//   * 200 Hz control loop: joint commands -> knee linkage -> calibrated pulses -> PCA9685
//   * IMU (LSM6DSOX) + Mahony orientation, power monitor (INA260)
//   * safety: command watchdog, hold-then-relax, latched e-stop, battery cut-off,
//     hard servo kill through the PCA9685 OE pin
//   * front LCD face/status
//   * binary protocol over USB CDC (docs/software.md, "Protocol")
#include <Adafruit_AHRS.h>
#include <Adafruit_INA260.h>
#include <Adafruit_LSM6DSOX.h>
#include <Adafruit_PWMServoDriver.h>
#include <Arduino.h>
#include <Preferences.h>
#include <Wire.h>

#include <cstring>

#include "board_config.h"
#include "face.h"
#include "strido/kinematics.h"
#include "strido/protocol.h"
#include "strido/safety.h"
#include "strido/servo_map.h"

using namespace strido;

namespace {

Adafruit_PWMServoDriver pwm(board::kPcaAddress, Wire);
Adafruit_LSM6DSOX imu;
Adafruit_INA260 power;
Adafruit_Mahony orientation;
Preferences preferences;
SafetySupervisor safety;

ServoCalibration calibration[kJointCount];
portMUX_TYPE command_lock = portMUX_INITIALIZER_UNLOCKED;  // guards `command` and `safety`

// Shared between the comms task (writer) and the control task (reader).
struct Command {
  float q[kJointCount];
  uint16_t pulse_us[kJointCount];
  bool raw_pulses = false;
  bool position = false;
  uint16_t seq = 0;
} command;

// Written by the control task, read by the comms task.
StateMessage state{};
portMUX_TYPE state_lock = portMUX_INITIALIZER_UNLOCKED;

bool pwm_ok = false;
bool imu_ok = false;
bool power_ok = false;
bool outputs_enabled = false;
float applied_q[kJointCount];
float battery_v = 0.0f;

void setOutputs(bool enabled) {
  if (enabled == outputs_enabled) return;
  digitalWrite(board::kServoOutputEnableN, enabled ? LOW : HIGH);
  if (!enabled) {
    for (int joint = 0; joint < kJointCount; ++joint) pwm.setPWM(board::kServoChannel[joint], 0, 0);
  }
  outputs_enabled = enabled;
}

void loadCalibration() {
  preferences.begin("strido", true);
  for (int joint = 0; joint < kJointCount; ++joint) {
    calibration[joint] = defaultCalibration(joint);
    char key[8];
    snprintf(key, sizeof(key), "cal%d", joint);
    if (preferences.getBytesLength(key) == sizeof(ServoCalibration)) {
      preferences.getBytes(key, &calibration[joint], sizeof(ServoCalibration));
    }
  }
  preferences.end();
}

void saveCalibration() {
  preferences.begin("strido", false);
  for (int joint = 0; joint < kJointCount; ++joint) {
    char key[8];
    snprintf(key, sizeof(key), "cal%d", joint);
    preferences.putBytes(key, &calibration[joint], sizeof(ServoCalibration));
  }
  preferences.end();
}

void sendFrame(uint8_t type, const uint8_t* payload, size_t length) {
  uint8_t encoded[kMaxEncoded];
  const size_t size = encodeFrame(type, payload, length, encoded, sizeof(encoded));
  if (size > 0 && Serial.availableForWrite() >= static_cast<int>(size)) Serial.write(encoded, size);
}

void sendCalibration() {
  for (int joint = 0; joint < kJointCount; ++joint) {
    CalibrationMessage message{static_cast<uint8_t>(joint), calibration[joint].direction, calibration[joint].neutral_us,
                               calibration[joint].zero_rad, calibration[joint].min_us, calibration[joint].max_us};
    uint8_t payload[kCalibrationPayloadSize];
    serialise(message, payload);
    sendFrame(kCalibration, payload, sizeof(payload));
  }
}

void handlePacket(uint8_t type, const uint8_t* payload, size_t length) {
  const uint32_t now = millis();
  switch (type) {
    case kJointCommand: {
      JointCommandMessage message;
      if (!deserialise(payload, length, &message)) return;
      portENTER_CRITICAL(&command_lock);
      memcpy(command.q, message.q, sizeof(command.q));
      command.position = message.mode == kModePosition;
      command.raw_pulses = false;
      command.seq = message.seq;
      safety.onCommand(now, message.mode == kModePosition);
      portEXIT_CRITICAL(&command_lock);
      break;
    }
    case kServoPulseCommand: {
      ServoPulseMessage message;
      if (!deserialise(payload, length, &message)) return;
      portENTER_CRITICAL(&command_lock);
      memcpy(command.pulse_us, message.pulse_us, sizeof(command.pulse_us));
      command.raw_pulses = true;
      command.position = true;
      command.seq = message.seq;
      safety.onCommand(now, true, /*calibration=*/true);
      portEXIT_CRITICAL(&command_lock);
      break;
    }
    case kSetCalibration: {
      CalibrationMessage message;
      if (!deserialise(payload, length, &message) || message.joint >= kJointCount) return;
      if (message.direction != 1 && message.direction != -1) return;
      if (message.min_us < kPulseMinUs || message.max_us > kPulseMaxUs || message.min_us >= message.max_us) return;
      calibration[message.joint] = {message.direction, message.neutral_us, message.zero_rad, message.min_us, message.max_us};
      break;
    }
    case kSaveCalibration:
      saveCalibration();
      break;
    case kRequestCalibration:
      sendCalibration();
      break;
    case kEstop:
      if (length == 1) {
        portENTER_CRITICAL(&command_lock);
        safety.onEstop(payload[0] != 0);
        portEXIT_CRITICAL(&command_lock);
      }
      break;
    case kDisplay:
      if (length >= 2 && payload[1] <= length - 2) {
        char text[33];
        const size_t n = payload[1] < 32 ? payload[1] : 32;
        memcpy(text, payload + 2, n);
        text[n] = '\0';
        face::setExpression(static_cast<face::Expression>(payload[0]));
        if (n > 0) face::setStatus(text);
      }
      break;
    default:
      break;
  }
}

// ------------------------------------------------------------------ control (core 1)
void applyServos(const Command& snapshot, float dt_s, bool* clamped) {
  if (snapshot.raw_pulses) {
    for (int joint = 0; joint < kJointCount; ++joint) {
      const ServoCalibration& c = calibration[joint];
      uint16_t us = snapshot.pulse_us[joint];
      if (us != 0) us = us < c.min_us ? c.min_us : (us > c.max_us ? c.max_us : us);
      pwm.writeMicroseconds(board::kServoChannel[joint], us);
    }
    return;
  }
  float previous_q[kJointCount];
  memcpy(previous_q, applied_q, sizeof(previous_q));
  safety.rateLimit(snapshot.q, applied_q, dt_s);  // const method: no shared state touched
  for (int leg = 0; leg < kLegCount; ++leg) {
    ActuatorAngles actuators;
    if (!jointsToActuators(leg, &applied_q[leg * 3], &actuators)) {
      *clamped = true;
      // Unreachable request: keep the previous pulses and report the angles they produce.
      memcpy(&applied_q[leg * 3], &previous_q[leg * 3], 3 * sizeof(float));
      continue;
    }
    *clamped |= clampActuators(leg, &actuators);
    const float angles[3] = {actuators.hip, actuators.thigh, actuators.crank};
    for (int slot = 0; slot < 3; ++slot) {
      const int joint = leg * 3 + slot;
      pwm.writeMicroseconds(board::kServoChannel[joint], actuatorToPulse(calibration[joint], angles[slot]));
    }
    // Report the knee angle that the clamped actuators actually produce.
    float calf;
    applied_q[leg * 3 + 0] = actuators.hip;
    applied_q[leg * 3 + 1] = actuators.thigh;
    if (calfFromCrank(leg, actuators.thigh, actuators.crank, &calf)) applied_q[leg * 3 + 2] = calf;
  }
}

void controlTask(void*) {
  uint32_t last_us = micros();
  uint32_t last_power_ms = 0;
  for (;;) {
    const uint32_t now_us = micros();
    const float dt = (now_us - last_us) * 1e-6f;
    last_us = now_us;
    const uint32_t now_ms = millis();

    if (imu_ok) {
      sensors_event_t accel, gyro, temperature;
      imu.getEvent(&accel, &gyro, &temperature);
      // Board axes -> base frame: the IMU is mounted with its x to robot left, y to robot rear.
      const float gx = -gyro.gyro.y, gy = gyro.gyro.x, gz = gyro.gyro.z;
      const float ax = -accel.acceleration.y, ay = accel.acceleration.x, az = accel.acceleration.z;
      orientation.updateIMU(gx * RAD_TO_DEG, gy * RAD_TO_DEG, gz * RAD_TO_DEG, ax, ay, az);
      float qw, qx, qy, qz;
      orientation.getQuaternion(&qw, &qx, &qy, &qz);
      portENTER_CRITICAL(&state_lock);
      state.quat[0] = qw; state.quat[1] = qx; state.quat[2] = qy; state.quat[3] = qz;
      state.gyro[0] = gx; state.gyro[1] = gy; state.gyro[2] = gz;
      state.accel[0] = ax; state.accel[1] = ay; state.accel[2] = az;
      portEXIT_CRITICAL(&state_lock);
    }
    if (power_ok && now_ms - last_power_ms >= 100) {
      last_power_ms = now_ms;
      // I2C reads block: never inside a critical section.
      battery_v = power.readBusVoltage() / 1000.0f;
      const float current_a = power.readCurrent() / 1000.0f;
      portENTER_CRITICAL(&command_lock);
      safety.onBattery(battery_v);
      portEXIT_CRITICAL(&command_lock);
      portENTER_CRITICAL(&state_lock);
      state.bus_voltage = battery_v;
      state.current = current_a;
      portEXIT_CRITICAL(&state_lock);
    }

    Command snapshot;
    portENTER_CRITICAL(&command_lock);
    const DriveState drive = safety.update(now_ms);
    const bool watchdog = safety.watchdogTripped();
    const bool battery_low = safety.batteryLow();
    snapshot = command;
    portEXIT_CRITICAL(&command_lock);

    bool clamped = false;
    if (pwm_ok && (drive == DriveState::kActive || drive == DriveState::kHolding)) {
      // Outputs were off: the servo positions are unknown, so start from the commanded pose
      // instead of slewing from a stale one (the host ramps from the rest pose it commands first).
      if (!outputs_enabled && !snapshot.raw_pulses) memcpy(applied_q, snapshot.q, sizeof(applied_q));
      setOutputs(true);
      if (drive == DriveState::kActive) applyServos(snapshot, dt, &clamped);
    } else {
      setOutputs(false);
    }

    uint8_t flags = 0;
    if (drive == DriveState::kEstop) flags |= kFlagEstop;
    if (!outputs_enabled) flags |= kFlagRelaxed;
    if (watchdog) flags |= kFlagWatchdog;
    if (imu_ok) flags |= kFlagImuOk;
    if (power_ok && !battery_low) flags |= kFlagPowerOk;
    if (pwm_ok) flags |= kFlagPwmOk;
    if (clamped) flags |= kFlagClamped;
    if (snapshot.raw_pulses) flags |= kFlagCalibrationMode;
    portENTER_CRITICAL(&state_lock);
    memcpy(state.q, applied_q, sizeof(state.q));
    state.status = flags;
    state.last_command_seq = snapshot.seq;
    state.time_ms = now_ms;
    portEXIT_CRITICAL(&state_lock);

    const uint32_t elapsed = micros() - now_us;
    if (elapsed < board::kControlPeriodUs) delayMicroseconds(board::kControlPeriodUs - elapsed);
    else vTaskDelay(1);
  }
}

// ------------------------------------------------------------------ comms + face (core 0)
void commsTask(void*) {
  FrameReader reader;
  uint8_t packet[kMaxPacket];
  uint32_t last_state_ms = 0;
  uint32_t last_face_ms = 0;
  for (;;) {
    while (Serial.available() > 0) {
      const size_t length = reader.push(static_cast<uint8_t>(Serial.read()), packet, sizeof(packet));
      if (length == 0) continue;
      uint8_t type;
      const uint8_t* payload;
      size_t payload_length;
      if (parsePacket(packet, length, &type, &payload, &payload_length)) handlePacket(type, payload, payload_length);
    }
    const uint32_t now = millis();
    if (now - last_state_ms >= board::kStatePeriodMs) {
      last_state_ms = now;
      StateMessage snapshot;
      portENTER_CRITICAL(&state_lock);
      snapshot = state;
      portEXIT_CRITICAL(&state_lock);
      uint8_t payload[kStatePayloadSize];
      serialise(snapshot, payload);
      sendFrame(kState, payload, sizeof(payload));
    }
    if (now - last_face_ms >= 50) {
      last_face_ms = now;
      portENTER_CRITICAL(&command_lock);
      const bool critical = safety.batteryCritical();
      portEXIT_CRITICAL(&command_lock);
      if (critical) face::setExpression(face::kLowBattery);
      face::update(now, battery_v, !outputs_enabled);
      digitalWrite(board::kStatusLed, (now / (outputs_enabled ? 125 : 500)) % 2 ? HIGH : LOW);
    }
    vTaskDelay(1);
  }
}

}  // namespace

void setup() {
  pinMode(board::kServoOutputEnableN, OUTPUT);
  digitalWrite(board::kServoOutputEnableN, HIGH);  // servos limp until the host commands a pose
  pinMode(board::kStatusLed, OUTPUT);
  Serial.begin(board::kUsbBaud);
  Wire.begin(board::kSda, board::kScl, board::kI2cHz);

  initKinematics();
  loadCalibration();
  for (int leg = 0; leg < kLegCount; ++leg) {  // start from the assembly reference pose
    const LegGeometry& g = kLegs[leg];
    float calf = g.cad_calf_angle;
    calfFromCrank(leg, g.neutral_thigh, g.neutral_crank, &calf);
    applied_q[leg * 3 + 0] = g.neutral_hip;
    applied_q[leg * 3 + 1] = g.neutral_thigh;
    applied_q[leg * 3 + 2] = calf;
  }
  memcpy(command.q, applied_q, sizeof(applied_q));

  pwm_ok = pwm.begin();
  if (pwm_ok) {
    pwm.setOscillatorFrequency(25000000);
    pwm.setPWMFreq(board::kServoFrequencyHz);
    for (int joint = 0; joint < kJointCount; ++joint) pwm.setPWM(board::kServoChannel[joint], 0, 0);
  }
  imu_ok = imu.begin_I2C(board::kImuAddress, &Wire);
  if (imu_ok) {
    imu.setAccelRange(LSM6DS_ACCEL_RANGE_8_G);
    imu.setGyroRange(LSM6DS_GYRO_RANGE_1000_DPS);
    imu.setAccelDataRate(LSM6DS_RATE_416_HZ);
    imu.setGyroDataRate(LSM6DS_RATE_416_HZ);
    orientation.begin(1e6f / board::kControlPeriodUs);
  }
  power_ok = power.begin(board::kPowerMonitorAddress, &Wire);
  safety.setPowerMonitor(power_ok);

  face::begin();
  face::setExpression(face::kNeutral);
  face::setStatus(pwm_ok ? "ready" : "NO PCA9685");

  xTaskCreatePinnedToCore(controlTask, "control", 6144, nullptr, 3, nullptr, 1);
  xTaskCreatePinnedToCore(commsTask, "comms", 8192, nullptr, 2, nullptr, 0);
}

void loop() { vTaskDelay(portMAX_DELAY); }
