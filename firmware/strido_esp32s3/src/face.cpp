#include "face.h"

#include <Arduino.h>

#define LGFX_USE_V1
#include <LovyanGFX.hpp>

#include "board_config.h"

namespace face {
namespace {

class Lcd : public lgfx::LGFX_Device {
  lgfx::Panel_ST7789 panel_;
  lgfx::Bus_SPI bus_;
  lgfx::Light_PWM light_;

 public:
  Lcd() {
    {
      auto cfg = bus_.config();
      cfg.spi_host = SPI2_HOST;
      cfg.spi_mode = 0;
      cfg.freq_write = 27000000;  // conservative for ~15 cm jumper wires
      cfg.freq_read = 8000000;
      cfg.spi_3wire = true;
      cfg.use_lock = true;
      cfg.dma_channel = SPI_DMA_CH_AUTO;
      cfg.pin_sclk = board::kLcdSck;
      cfg.pin_mosi = board::kLcdMosi;
      cfg.pin_miso = -1;
      cfg.pin_dc = board::kLcdDc;
      bus_.config(cfg);
      panel_.setBus(&bus_);
    }
    {
      auto cfg = panel_.config();
      cfg.pin_cs = board::kLcdCs;
      cfg.pin_rst = board::kLcdRst;
      cfg.pin_busy = -1;
      cfg.panel_width = 240;
      cfg.panel_height = 320;
      cfg.readable = false;
      cfg.invert = true;  // IPS ST7789V panels need colour inversion
      cfg.rgb_order = false;
      cfg.bus_shared = false;
      panel_.config(cfg);
    }
    {
      auto cfg = light_.config();
      cfg.pin_bl = board::kLcdBacklight;
      cfg.invert = false;
      cfg.freq = 20000;
      cfg.pwm_channel = 7;
      light_.config(cfg);
      panel_.setLight(&light_);
    }
    setPanel(&panel_);
  }
};

Lcd lcd;
LGFX_Sprite frame(&lcd);
Expression expression = kBoot;
char status[40] = "Strido";
bool dirty = true;
uint32_t next_blink_ms = 3000;
uint32_t blink_until_ms = 0;
bool was_blinking = false;
float shown_battery_v = -1.0f;
bool shown_relaxed = false;

uint16_t eyeColour(Expression e) {
  switch (e) {
    case kLowBattery: return lcd.color565(255, 60, 40);
    case kAlert: return lcd.color565(255, 190, 0);
    case kSleep: return lcd.color565(60, 90, 140);
    default: return lcd.color565(80, 230, 255);
  }
}

void drawEye(int cx, int cy, bool left, bool blinking) {
  const uint16_t colour = eyeColour(expression);
  const int w = 78;
  int h = 96;
  if (blinking || expression == kSleep) {
    frame.fillRoundRect(cx - w / 2, cy - 4, w, 8, 4, colour);
    return;
  }
  if (expression == kAlert) h = 112;
  frame.fillRoundRect(cx - w / 2, cy - h / 2, w, h, 22, colour);
  if (expression == kHappy) {  // cut the lower half: smiling arcs
    frame.fillRoundRect(cx - w / 2 - 2, cy - 4, w + 4, h, 22, TFT_BLACK);
  } else if (expression == kSad) {  // droop the outer upper corner
    const int x0 = left ? cx - w / 2 - 2 : cx + w / 2 + 2;
    const int x1 = left ? cx + w / 2 : cx - w / 2;
    frame.fillTriangle(x0, cy - h / 2 - 2, x1, cy - h / 2 - 2, x0, cy - 6, TFT_BLACK);
  }
}

}  // namespace

void begin() {
  lcd.init();
  lcd.setRotation(1);  // landscape, connector on the right when seen from the front
  lcd.setBrightness(200);
  frame.setColorDepth(16);
  frame.setPsram(true);
  frame.createSprite(lcd.width(), lcd.height());
}

void setExpression(Expression e) {
  if (e != expression) {
    expression = e;
    dirty = true;
  }
}

void setStatus(const char* text) {
  if (strncmp(text, status, sizeof(status)) != 0) {
    strncpy(status, text, sizeof(status) - 1);
    status[sizeof(status) - 1] = '\0';
    dirty = true;
  }
}

void update(uint32_t now_ms, float battery_v, bool relaxed) {
  if (now_ms >= next_blink_ms) {
    blink_until_ms = now_ms + 140;
    next_blink_ms = now_ms + 2500 + (esp_random() % 3000);
  }
  const bool blinking = now_ms < blink_until_ms;
  if (fabsf(battery_v - shown_battery_v) > 0.05f || relaxed != shown_relaxed) {
    shown_battery_v = battery_v;
    shown_relaxed = relaxed;
    dirty = true;
  }
  if (!dirty && blinking == was_blinking) return;
  was_blinking = blinking;
  dirty = false;
  frame.fillScreen(TFT_BLACK);
  drawEye(frame.width() / 2 - 70, frame.height() / 2 - 14, true, blinking);
  drawEye(frame.width() / 2 + 70, frame.height() / 2 - 14, false, blinking);
  frame.setTextColor(lcd.color565(160, 160, 160), TFT_BLACK);
  frame.setTextSize(2);
  frame.setCursor(8, frame.height() - 22);
  frame.printf("%s  %.2fV%s", status, battery_v, relaxed ? "  limp" : "");
  frame.pushSprite(0, 0);
}

}  // namespace face
