// Front LCD "eyes" + status line (LovyanGFX, ST7789V 240x320 in landscape).
#pragma once

#include <cstdint>

namespace face {

enum Expression : uint8_t { kNeutral = 0, kHappy = 1, kSad = 2, kSleep = 3, kAlert = 4, kLowBattery = 5, kBoot = 6 };

void begin();
void setExpression(Expression expression);
void setStatus(const char* text);
// Call ~20 Hz: animates blinking and redraws only what changed.
void update(uint32_t now_ms, float battery_v, bool relaxed);

}  // namespace face
