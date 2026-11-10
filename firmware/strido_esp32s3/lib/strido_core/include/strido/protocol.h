// Host (Raspberry Pi) <-> MCU (ESP32-S3) binary protocol over USB CDC.
// Mirror: packages/strido-core/src/strido/protocol.py. Spec: docs/software.md ("Protocol")
//
// Wire format: COBS(packet) followed by a 0x00 delimiter, where
//   packet = type:u8 | payload | crc16:u16 (little endian)
//   crc16  = CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF) over type|payload.
// All multi-byte fields are little endian; floats are IEEE-754 binary32.
#pragma once

#include <cstddef>
#include <cstdint>

namespace strido {

constexpr size_t kMaxPacket = 160;               // decoded bytes incl. type and CRC
constexpr size_t kMaxEncoded = kMaxPacket + kMaxPacket / 254 + 2;

enum MessageType : uint8_t {
  kJointCommand = 0x01,      // u16 seq, u8 mode, f32 q[12]
  kServoPulseCommand = 0x02, // u16 seq, u16 pulse_us[12] (0 = no pulse)
  kSetCalibration = 0x03,    // u8 joint, i8 direction, u16 neutral_us, f32 zero_rad, u16 min_us, u16 max_us
  kSaveCalibration = 0x04,   // (empty)
  kRequestCalibration = 0x05,// (empty) -> 12x kCalibration
  kEstop = 0x06,             // u8 engaged
  kDisplay = 0x07,           // u8 expression, u8 length, char text[length<=32]
  kState = 0x81,             // see StateMessage
  kCalibration = 0x82,       // same layout as kSetCalibration
  kLog = 0x83,               // char text[]
};

enum CommandMode : uint8_t { kModeRelax = 0, kModePosition = 1 };

enum StatusFlag : uint8_t {
  kFlagEstop = 1 << 0,
  kFlagRelaxed = 1 << 1,
  kFlagWatchdog = 1 << 2,
  kFlagImuOk = 1 << 3,
  kFlagPowerOk = 1 << 4,
  kFlagPwmOk = 1 << 5,
  kFlagClamped = 1 << 6,
  kFlagCalibrationMode = 1 << 7,
};

struct JointCommandMessage {
  uint16_t seq;
  uint8_t mode;
  float q[12];
};

struct ServoPulseMessage {
  uint16_t seq;
  uint16_t pulse_us[12];
};

struct CalibrationMessage {
  uint8_t joint;
  int8_t direction;
  uint16_t neutral_us;
  float zero_rad;
  uint16_t min_us;
  uint16_t max_us;
};

struct StateMessage {
  uint16_t last_command_seq;
  uint32_t time_ms;
  uint8_t status;
  float q[12];        // commanded joint angles actually applied (after limits)
  float quat[4];      // w, x, y, z (body orientation, Mahony filter)
  float gyro[3];      // rad/s, IMU frame = base frame
  float accel[3];     // m/s^2
  float bus_voltage;  // V
  float current;      // A
};

uint16_t crc16(const uint8_t* data, size_t length);

// COBS; returns encoded length (without delimiter) or 0 on overflow.
size_t cobsEncode(const uint8_t* input, size_t length, uint8_t* output, size_t capacity);
// Returns decoded length or 0 on malformed input/overflow.
size_t cobsDecode(const uint8_t* input, size_t length, uint8_t* output, size_t capacity);

// Builds type|payload|crc and COBS-encodes it; appends the 0x00 delimiter.
size_t encodeFrame(uint8_t type, const uint8_t* payload, size_t payloadLength, uint8_t* out, size_t capacity);

// Validates CRC of a decoded packet; on success sets *type, *payload, *payloadLength.
bool parsePacket(const uint8_t* packet, size_t length, uint8_t* type, const uint8_t** payload, size_t* payloadLength);

// Little-endian field (de)serialisation.
size_t serialise(const StateMessage& message, uint8_t* out);
size_t serialise(const CalibrationMessage& message, uint8_t* out);
bool deserialise(const uint8_t* data, size_t length, JointCommandMessage* message);
bool deserialise(const uint8_t* data, size_t length, ServoPulseMessage* message);
bool deserialise(const uint8_t* data, size_t length, CalibrationMessage* message);

constexpr size_t kStatePayloadSize = 2 + 4 + 1 + 12 * 4 + 4 * 4 + 3 * 4 + 3 * 4 + 4 + 4;
constexpr size_t kJointCommandPayloadSize = 2 + 1 + 12 * 4;
constexpr size_t kServoPulsePayloadSize = 2 + 12 * 2;
constexpr size_t kCalibrationPayloadSize = 1 + 1 + 2 + 4 + 2 + 2;

// Incremental frame splitter: feed bytes, get complete decoded packets.
class FrameReader {
 public:
  // Returns decoded length when a full valid frame completed, else 0.
  size_t push(uint8_t byte, uint8_t* packet, size_t capacity);
  uint32_t droppedFrames() const { return dropped_; }

 private:
  uint8_t buffer_[kMaxEncoded];
  size_t length_ = 0;
  bool overflow_ = false;
  uint32_t dropped_ = 0;
};

}  // namespace strido
