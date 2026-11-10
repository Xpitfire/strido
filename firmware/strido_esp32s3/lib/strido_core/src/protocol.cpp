#include "strido/protocol.h"

#include <cmath>
#include <cstring>

namespace strido {
namespace {

void putU16(uint8_t* out, uint16_t value) {
  out[0] = static_cast<uint8_t>(value & 0xFF);
  out[1] = static_cast<uint8_t>(value >> 8);
}

void putU32(uint8_t* out, uint32_t value) {
  for (int i = 0; i < 4; ++i) out[i] = static_cast<uint8_t>((value >> (8 * i)) & 0xFF);
}

void putF32(uint8_t* out, float value) {
  uint32_t bits;
  std::memcpy(&bits, &value, sizeof(bits));
  putU32(out, bits);
}

uint16_t getU16(const uint8_t* in) { return static_cast<uint16_t>(in[0] | (in[1] << 8)); }

uint32_t getU32(const uint8_t* in) {
  return static_cast<uint32_t>(in[0]) | (static_cast<uint32_t>(in[1]) << 8) | (static_cast<uint32_t>(in[2]) << 16) |
         (static_cast<uint32_t>(in[3]) << 24);
}

float getF32(const uint8_t* in) {
  const uint32_t bits = getU32(in);
  float value;
  std::memcpy(&value, &bits, sizeof(value));
  return value;
}

}  // namespace

uint16_t crc16(const uint8_t* data, size_t length) {
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < length; ++i) {
    crc ^= static_cast<uint16_t>(data[i]) << 8;
    for (int bit = 0; bit < 8; ++bit) {
      crc = (crc & 0x8000) ? static_cast<uint16_t>((crc << 1) ^ 0x1021) : static_cast<uint16_t>(crc << 1);
    }
  }
  return crc;
}

size_t cobsEncode(const uint8_t* input, size_t length, uint8_t* output, size_t capacity) {
  if (capacity < length + length / 254 + 1) return 0;
  size_t read = 0;
  size_t write = 1;
  size_t codeIndex = 0;
  uint8_t code = 1;
  while (read < length) {
    if (input[read] == 0) {
      output[codeIndex] = code;
      codeIndex = write++;
      code = 1;
    } else {
      output[write++] = input[read];
      ++code;
      if (code == 0xFF) {
        output[codeIndex] = code;
        codeIndex = write++;
        code = 1;
      }
    }
    ++read;
  }
  output[codeIndex] = code;
  return write;
}

size_t cobsDecode(const uint8_t* input, size_t length, uint8_t* output, size_t capacity) {
  size_t read = 0;
  size_t write = 0;
  while (read < length) {
    const uint8_t code = input[read++];
    if (code == 0) return 0;
    for (uint8_t i = 1; i < code; ++i) {
      if (read >= length || write >= capacity) return 0;
      const uint8_t value = input[read++];
      if (value == 0) return 0;
      output[write++] = value;
    }
    if (code != 0xFF && read < length) {
      if (write >= capacity) return 0;
      output[write++] = 0;
    }
  }
  return write;
}

size_t encodeFrame(uint8_t type, const uint8_t* payload, size_t payloadLength, uint8_t* out, size_t capacity) {
  uint8_t packet[kMaxPacket];
  if (payloadLength + 3 > kMaxPacket) return 0;
  packet[0] = type;
  if (payloadLength > 0) std::memcpy(packet + 1, payload, payloadLength);
  putU16(packet + 1 + payloadLength, crc16(packet, payloadLength + 1));
  const size_t encoded = cobsEncode(packet, payloadLength + 3, out, capacity > 0 ? capacity - 1 : 0);
  if (encoded == 0) return 0;
  out[encoded] = 0;
  return encoded + 1;
}

bool parsePacket(const uint8_t* packet, size_t length, uint8_t* type, const uint8_t** payload, size_t* payloadLength) {
  if (length < 3) return false;
  const uint16_t expected = getU16(packet + length - 2);
  if (crc16(packet, length - 2) != expected) return false;
  *type = packet[0];
  *payload = packet + 1;
  *payloadLength = length - 3;
  return true;
}

size_t serialise(const StateMessage& m, uint8_t* out) {
  size_t offset = 0;
  putU16(out + offset, m.last_command_seq);
  offset += 2;
  putU32(out + offset, m.time_ms);
  offset += 4;
  out[offset++] = m.status;
  for (float value : m.q) {
    putF32(out + offset, value);
    offset += 4;
  }
  for (float value : m.quat) {
    putF32(out + offset, value);
    offset += 4;
  }
  for (float value : m.gyro) {
    putF32(out + offset, value);
    offset += 4;
  }
  for (float value : m.accel) {
    putF32(out + offset, value);
    offset += 4;
  }
  putF32(out + offset, m.bus_voltage);
  offset += 4;
  putF32(out + offset, m.current);
  offset += 4;
  return offset;
}

size_t serialise(const CalibrationMessage& m, uint8_t* out) {
  out[0] = m.joint;
  out[1] = static_cast<uint8_t>(m.direction);
  putU16(out + 2, m.neutral_us);
  putF32(out + 4, m.zero_rad);
  putU16(out + 8, m.min_us);
  putU16(out + 10, m.max_us);
  return kCalibrationPayloadSize;
}

bool deserialise(const uint8_t* data, size_t length, JointCommandMessage* m) {
  if (length != kJointCommandPayloadSize) return false;
  m->seq = getU16(data);
  m->mode = data[2];
  for (int i = 0; i < 12; ++i) {
    m->q[i] = getF32(data + 3 + 4 * i);
    if (!std::isfinite(m->q[i])) return false;  // NaN/Inf would bypass every limit downstream
  }
  return true;
}

bool deserialise(const uint8_t* data, size_t length, ServoPulseMessage* m) {
  if (length != kServoPulsePayloadSize) return false;
  m->seq = getU16(data);
  for (int i = 0; i < 12; ++i) m->pulse_us[i] = getU16(data + 2 + 2 * i);
  return true;
}

bool deserialise(const uint8_t* data, size_t length, CalibrationMessage* m) {
  if (length != kCalibrationPayloadSize) return false;
  m->joint = data[0];
  m->direction = static_cast<int8_t>(data[1]);
  m->neutral_us = getU16(data + 2);
  m->zero_rad = getF32(data + 4);
  if (!std::isfinite(m->zero_rad)) return false;
  m->min_us = getU16(data + 8);
  m->max_us = getU16(data + 10);
  return true;
}

size_t FrameReader::push(uint8_t byte, uint8_t* packet, size_t capacity) {
  if (byte != 0) {
    if (length_ < sizeof(buffer_)) {
      buffer_[length_++] = byte;
    } else {
      overflow_ = true;
    }
    return 0;
  }
  size_t decoded = 0;
  if (!overflow_ && length_ > 0) decoded = cobsDecode(buffer_, length_, packet, capacity);
  if (overflow_ || (length_ > 0 && decoded == 0)) ++dropped_;
  length_ = 0;
  overflow_ = false;
  return decoded;
}

}  // namespace strido
