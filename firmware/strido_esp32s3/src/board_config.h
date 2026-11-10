// Seeed XIAO ESP32S3 pin assignment for Strido (see docs/electronics.md, "Pin maps").
#pragma once

#include <cstdint>

namespace board {

// I2C bus: PCA9685 (0x40), LSM6DSOX (0x6A), INA260 (0x41 - bridge its A0 jumper!)
constexpr int kSda = 5;   // D4
constexpr int kScl = 6;   // D5
constexpr uint32_t kI2cHz = 400000;

// ST7789V 240x320 LCD (Waveshare 2inch) on SPI
constexpr int kLcdSck = 7;   // D8
constexpr int kLcdMosi = 9;  // D10
constexpr int kLcdDc = 8;    // D9
constexpr int kLcdCs = 1;    // D0
constexpr int kLcdRst = 2;   // D1
constexpr int kLcdBacklight = 3;  // D2 (strapping pin: only driven after boot)

// PCA9685 output enable (active low). HIGH = all servo pulses off instantly.
constexpr int kServoOutputEnableN = 4;  // D3

constexpr int kStatusLed = 21;  // on-board user LED (active low)

constexpr uint8_t kPcaAddress = 0x40;
constexpr uint8_t kImuAddress = 0x6A;
constexpr uint8_t kPowerMonitorAddress = 0x41;

// PCA9685 channel of each joint, Go2 order FL, FR, RL, RR x (hip, thigh, calf).
// Kept identical to the upstream Yertle wiring (channels 4..15).
constexpr uint8_t kServoChannel[12] = {15, 11, 7, 14, 10, 6, 13, 9, 5, 12, 8, 4};

constexpr uint16_t kServoFrequencyHz = 200;  // SPT5435LV accepts up to 330 Hz
constexpr uint32_t kControlPeriodUs = 5000;  // 200 Hz control / IMU loop
constexpr uint32_t kStatePeriodMs = 10;      // 100 Hz state stream to the host
constexpr uint32_t kUsbBaud = 2000000;       // ignored by USB CDC, kept for UART fallback

}  // namespace board
