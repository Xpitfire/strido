---
search: false
---

# Price research sources

> **What this page is:** research notes — every offer that was found per item, including alternatives that are dearer, out of stock or superseded. It is **not** a list to order from. To buy the robot, use the [shopping list](shopping_list.md): it turns these offers into four complete alternative plans with their totals.

Two research passes (2026-10-30) priced the BOM for delivery to Austria. They are reproduced here with their URLs, stock notes and caveats; `hardware/bom.yaml` holds the selected offers. Prices change: re-check before ordering.

Pass 1 priced an earlier draft of the design (ESP32-S3 DevKitC, one 20 A BEC, heat-set inserts, 4 servo extensions); its strategy totals are superseded by the [shopping list](shopping_list.md). Corrections that apply to both passes: the Bambu A1 mini (180 mm bed) is too small for the 114 × 208 mm shells (use a ≥ 220 mm bed); the Pololu #2813 is rated 6 A continuous at 55 °C (16 A only at 150 °C) and #2808 3 A at 55 °C (Pololu product pages). Pass 2 priced the items that the final design added or changed (XIAO ESP32-S3, two Hobbywing UBEC-10A, Pololu switch, pushbutton, 30 cm extensions, M2/M2.5 hardware).

---

## Strido EU shopping list for an Austrian builder: prices, vendors and bundle strategies (2026-10-30)

**Answer:** Three shops (DigiKey.at, Amazon.de and AliExpress) cover the whole robot BOM for **€969.59** delivered. Spreading the order over six shops gets it down to **€908.31**. An EU-stock-only build costs about **€1,149** plus Eckstein's shipping, which I couldn't see. All three totals use the Pi 5 4 GB and exclude tools and the 3D printer.

**Sources:**
- **Sub-agents:** most prices come from pages four research sub-agents fetched today.
- **Amazon.de:** I re-fetched every ASIN used in the strategy totals today with `curl` (buy-box price and stock).
- **DigiKey.at:** prices were read in a browser and include 20% Austrian VAT.
- **Conrad.at:** prices are shown without VAT. The gross figures here are net × 1.2, so they are **calculated, not displayed**.
- **DE shops (Welectron, Eckstein, kugellager-*, ruthex, MYBOTSHOP):** they show 19% German VAT. Whether checkout switches to Austria's 20% is UNVERIFIED.

## 1. Offers per item

### 1a. Compute, camera and boards
| Item (qty) | Vendor | Product / SKU | € incl. VAT | Stock | URL |
|---|---|---|---|---|---|
| Pi 5 4 GB (1) | **DigiKey.at** | SC1431 (newer revision of SC1111), 2648-SC1431-ND | **117.18** | 203 | digikey.at (search 2648-SC1431-ND) |
| | Berrybase.at | RPI5-4GB | 123.90 | Limited | https://www.berrybase.at/raspberry-pi-5-4gb-ram |
| | Welectron | RP1-151400-P | 118.00 (DE VAT) | Out of stock | https://www.welectron.com/Raspberry-Pi-5-4-GB-RAM |
| | Reichelt.at | RASP PI 5 B 4GB | 137.55 | Pre-order | https://www.reichelt.at/at/de/shop/produkt/raspberry_pi_5_b_4x_2_4_ghz_4_gb_ram_wlan_bt-359842 |
| Pi 5 8 GB (option) | DigiKey.at | SC1432 | **186.42** | 19,766 | digikey.at |
| | Welectron | RP1-151800-P | 189.00 | In stock | https://www.welectron.com/Raspberry-Pi-5-8-GB-RAM_1 |
| | Reichelt.at / Berrybase.at | – | 191.59 / 189.00 | In stock / Limited | reichelt …-359846 / https://www.berrybase.at/raspberry-pi-5-8gb-ram |
| Active Cooler (1) | DigiKey / Welectron / Reichelt / Berrybase | SC1148 | 5.33 / 4.90 / 5.60 / 5.90 | All in stock (Berrybase limited) | https://www.welectron.com/Offizieller-Raspberry-Pi-Active-Cooler |
| 64 GB A2 microSD (1) | **Amazon.de** | SanDisk Extreme 64GB, B09X7CXWQQ | **26.21** | In stock | https://www.amazon.de/dp/B09X7CXWQQ |
| | Berrybase.at | SanDisk Extreme A2 64GB | 25.90 | Limited | https://www.berrybase.at/sandisk-extreme-microsdxc-a2-uhs-i-u3-v30-170mb-s-speicherkarte-adapter-64gb |
| | Reichelt.at | Official Raspberry Pi A2 64GB | 44.62 | In stock | https://www.reichelt.at/at/de/shop/produkt/raspberry_pi_-_microsd-karte_a2-class_64_gb-383381 |
| Cam Module 3 **Wide** (1) | DigiKey.at | SC1224, 2648-SC1224-ND | 37.28 | 6,881 | digikey.at |
| | Welectron | Official CM3 Wide | **35.90** | In stock | https://www.welectron.com/Official-Raspberry-Pi-Camera-Module-3-Wide |
| | Berrybase / Reichelt | – | 39.90 / 38.32 | Sold out / Out of stock | https://www.berrybase.at/raspberry-pi-camera-module-3-wide-12mp |
| Cam Module 3 standard (option) | Welectron / Berrybase / Reichelt | – | 25.90 / 28.90 / 30.15 | In stock / Limited / In stock | https://www.welectron.com/Official-Raspberry-Pi-Camera-Module-3 |
| Pi 5 camera cable, 200 mm (1) | DigiKey / Berrybase / Welectron | SC1892 / RPI-CC-SM-20 / – | 1.07 / 1.20 / 1.90 | In stock | https://www.berrybase.at/raspberry-pi-camera-cable-standard-mini-200mm |
| 27 W USB-C PSU, EU plug | DigiKey (SC1407) / Welectron / Berrybase | – | 12.78 / 11.90 / 12.40 | In stock | DigiKey also lists SC1153, which is the **US-plug** version; don't order it |
| ESP32-S3-DevKitC-1-**N16R8**, genuine | Reichelt.at | 444792 | 17.75 | **Out of stock** | https://www.reichelt.at/at/de/shop/produkt/entwicklungsboard_esp32-s3-wroom-1-n16r8-444792 |
| | soyter.pl | genuine Espressif | 20.87 (VAT basis unclear) | **Out of stock** | https://soyter.pl/en/products/espressif-esp32-s3-devkitc-1-n16r8-development-board-4875.html |
| | DigiKey.at / Mouser.at | – | not listed / UNVERIFIED (bot block) | – | – |
| ↳ genuine alternative | DigiKey.at | ESP32-S3-DevKitC-1-**N32R16V** | 17.42 | 53 | digikey.at. Uses octal 1.8 V PSRAM, so GPIO35–37 are not usable |
| ↳ clone N16R8 | Amazon.de | B0FYFF8CB2 | **10.07** | In stock | https://www.amazon.de/dp/B0FYFF8CB2 |
| | makeroo.de | ESP32-S3 N16R8 DevKit (made in China; small business, no VAT charged) | 7.99 | – | https://makeroo.de/products/esp32-s3-n16r8-dev-kit-dual-usb-c-16mb-flash-8mb-psram-ai-optimiert-wifi-bluetooth-microcontroller (shipping to AT UNVERIFIED) |
| PCA9685 (1) | DigiKey.at | Adafruit 815, 1528-815-ND | 15.92 | 366 | digikey.at |
| | Amazon.de | JZK clone, B06XSFFXQY | **6.95** | – | https://www.amazon.de/dp/B06XSFFXQY |
| | Amazon.de | DollaTek clone, B0BKZC1XWR | 7.04 | 10 left | https://www.amazon.de/dp/B0BKZC1XWR |
| | Eckstein | QITA clone | 10.50 | In stock | https://eckstein-shop.de/16CH-Servomotor-Treiber-Modul-PCA9685-PWM-fuer-Arduino-Raspberry-Pi |
| LSM6DSOX IMU (1) | DigiKey.at | Adafruit 4438 | **12.73** | 270 | digikey.at |
| | Amazon.de | B085F3F19D | 20.16 | 3 left | https://www.amazon.de/dp/B085F3F19D |
| | Berrybase.at | ADA4438 | 11.90 | Sold out | https://www.berrybase.at/adafruit-lsm6dsox-6-dof-beschleugnigunssensor-und-gyroskop |
| INA260 (1) | DigiKey.at | Adafruit 4226 | **10.60** | 1,375 | digikey.at |
| | Eckstein | 4226 | 11.84 | In stock | https://eckstein-shop.de/AdafruitINA260HighorLowSideVoltage2FCurrent2FPowerSensor |
| | Berrybase | ADA4226 | 10.95 | Sold out | https://www.berrybase.at/adafruit-ina260-high-oder-low-side-spannungs-strom-und-leistungs-sensor |
| Waveshare 2" LCD, ST7789 (1) | Welectron | 17344 | **10.90** | In stock | https://www.welectron.com/Waveshare-17344-2inch-LCD-Module_1 |
| | Amazon.de | B081NBBRWS | 20.16 | In stock | https://www.amazon.de/dp/B081NBBRWS |
| | Eckstein | – | 14.27 | In stock | https://eckstein-shop.de/WaveShare-240320-General-2inch-IPS-LCD-Display-Module |
| Pololu D36V50F5 (1) | DigiKey.at | Pololu 4091, 2183-4091-ND (DigiKey Marketplace) | 48.24 | 215 | digikey.at |
| | Eckstein | – | **41.59** | In stock | https://eckstein-shop.de/Pololu-5V-55A-Step-Down-Voltage-Regulator-D36V50F5-EN |
| | Berrybase | – | 34.95 | Sold out | https://www.berrybase.at/pololu-d36v50f5-5v-5-5a-step-down-spannungsregler |
| STEMMA QT cable, 100 mm (3) | DigiKey.at | Adafruit 4210 | **1.01 each** | 17,267 | digikey.at |
| | Amazon.de | 12-pc JST-SH 4-pin set, B0HB5F48YD | 9.06 | In stock | https://www.amazon.de/dp/B0HB5F48YD |
| | Eckstein / Berrybase | – | 2.25 / 1.90–2.30 | Out of stock | – |

### 1b. LiDAR, servos, horns
| Item (qty) | Vendor | Product / SKU | € incl. VAT | Stock | URL |
|---|---|---|---|---|---|
| RPLIDAR C1 (1) | Amazon.de (WayPonDEV) | B0CP8YRY44 | **70.58** | Ships in 4–5 days | https://www.amazon.de/dp/B0CP8YRY44 |
| | Amazon.de (Waveshare) | B0CT31PH8S | 103.86 | In stock | https://www.amazon.de/dp/B0CT31PH8S |
| | Génération Robots | A-000000-06970 | 81.12 (net 67.60 × 1.2, calculated) | Not shown | https://www.generationrobots.com/de/404200-telemetre-laser-360-rplidar-c1-slamtec.html |
| | MYBOTSHOP.DE | – | 99.95 (DE VAT) | In stock | https://www.mybotshop.de/SLAMTEC-RPLIDAR-C1-360-Laser-Scanner-12-m |
| SPT5435LV-180W (13) | AliExpress "DigitalServo Store" | 4000135787995, variant "35kg-180 Waterproof" | **13.46** (with alu Arm/Disc horn: 14.21); shipping €5.90 | 8,515 | https://de.aliexpress.com/item/4000135787995.html |
| | Amazon.de | "SPT5435LV", B0H17Y4KS2 — **rotation angle not stated** | 23.99 | In stock | https://www.amazon.de/dp/B0H17Y4KS2 |
| | Amazon.de | B0G39ZHL4B | 22.48 | 3 left | https://www.amazon.de/dp/B0G39ZHL4B |
| | Banggood | -180 (not waterproof), p-1577509 | US\$27.99 (≈25.05) | UNVERIFIED | banggood.com |
| 25T alu disc horn (4) | Amazon.de (DollaTek) | 5-pack, B07F71J1Q2 | 5.03 | In stock | https://www.amazon.de/dp/B07F71J1Q2 |
| 25T alu clamping arm (4) | Amazon.de | 5-pack, B0F5QG8HQS | 9.06 | 17 left | https://www.amazon.de/dp/B0F5QG8HQS |
| | Lindinger | SAVÖX 25T single | 7.90 each | Pre-order | https://www.lindinger.at/de/RC-Elektronik/RC-Produkte/Servos-Zubehoer/SAVOEX-Servo-Horn-Single-Alu-High-Torque-25T-Servohebel-Alu/9798687 |
| Horns, cheapest route | AliExpress | Servo bought as "WP Arm" or "WP Disc" variant | +0.75 per servo | – | Same item page as the servos |

### 1c. Power
| Item (qty) | Vendor | Product / SKU | € incl. VAT | Stock | URL |
|---|---|---|---|---|---|
| Servo BEC | Lindinger | **Hobbywing UBEC-10A V2-Car (P/N 30603003)**: 2–6S in, 6.0/7.4/8.4 V out, 10 A continuous / 15 A peak ([manual](https://oss.hobbywing.com/pdf/pdfen/UBEC10ACar.pdf)); the aircraft UBEC-10A (P/N 30603000, 20 A peak) is a different unit | 26.99 each (sale) | Few left | https://www.lindinger.at/de/RC-Elektronik/Stromversorgung-Bus-Systeme/Akkuweichen-Spannungsregler-BEC/HOBBYWING-BEC-10A-V2-Car-UBEC-Regler-fuer-2-6s/9787110 |
| | Amazon.de | SPARKHOBBY 10A UBEC clone, B0DK31PYFZ | 26.63 each | 3 left | https://www.amazon.de/dp/B0DK31PYFZ |
| | Amazon.de | Suoumwa "20A SBEC", B0D4YCJWR3 (continuous rating and minimum input UNVERIFIED) | 37.75 | In stock | https://www.amazon.de/dp/B0D4YCJWR3 |
| | Motion RC EU | Castle CC BEC Pro 20A, 010-0004-01 (15 A continuous at 2S, per sub-agent) | 56.99 | Not shown | https://motionrc.com/eu/products/castle-creations-20a-bec-pro-010-0004-01 |
| LiPo 2S 5000 mAh, XT60 (1) | Amazon.de | Gens ace G-Tech 60C, 138×47×25 mm, B0GKP683YF | **22.18** | In stock | https://www.amazon.de/dp/B0GKP683YF |
| | Amazon.de | Zeee 5200 80C, 2-pack, B08X4GF9DK | 41.34 per 2 | In stock | https://www.amazon.de/dp/B08X4GF9DK |
| | Lindinger | Robbe RO-POWER 5000 2S 35C, 139×46.8×25.9 mm (0.9 mm over the height limit) | 32.99 | Few left | https://www.lindinger.at/de/RC-Elektronik/Antriebe/Akkus/Robbe-Modellsport-RO-POWER-ULTRA-MAXAMP-CAR-5000MAH-7-4-VOLT-2S-35-70-C-LIPO-AKKU-T-XT-60-Stecker/9767786 |
| | Stefansliposhop | SLS XTRON 5000 2S 50C hardcase (4 mm bullets) | 42.50 | 1–3 days | https://www.stefansliposhop.de/en/batteries/sls-xtron/sls-xtron-car/sls-xtron-5000mah-2s1p-7-4v-50c-100c-hardcase-steckkontakte::1105.html |
| Charger, AC input | Amazon.de | HTRC B6AC 80 W, B0F3CYZ6L8 | **46.38** | In stock | https://www.amazon.de/dp/B0F3CYZ6L8 |
| | Robitronic (AT) | SkyRC B6AC V2, genuine | 61.90 | In stock | https://shop.robitronic.com/de/skyrc-b6ac-v2-ladegeraet-sk100008 |
| | Lindinger | SkyRC B6AC Neo / ISDT 608AC | 64.99 / 63.99 | Few left | lindinger.at (9798342 / 9771152) |
| LiPo bag | Lindinger / Amazon | Robbe 23×30 cm / FLASLD, B09C31KVK1 | 6.49 / 14.11 | – | lindinger.at 9787514 / https://www.amazon.de/dp/B09C31KVK1 |
| LiPo checker | Lindinger / Amazon | Absima / ARCELI, B077Z1N9CS | 5.95 / 6.04 | – | lindinger.at 9771616 / https://www.amazon.de/dp/B077Z1N9CS |
| XT60 pairs | Amazon.de | Genuine Amass XT60H, 3 pairs, B07C3KH1VT | 6.44 | In stock | https://www.amazon.de/dp/B07C3KH1VT |
| | Lindinger / Reichelt | Robbe, 3 pairs / Jamara, 1 pair | 4.99 / 2.01 | – | lindinger.at 9750234 / reichelt.at 207648 |
| ATO fuse holder + 25 A fuse | Reichelt.at | Holder 325426 + fuse 7786 | 3.02 + 0.36 each | In stock | reichelt.at (325426, 7786) |
| | Amazon.de | Holder 5-pack (with 20 A fuses), B0B4MWDFD8 + 25 A fuses ×10, B09ZXRZLV8 | 8.05 + 4.02 | In stock | https://www.amazon.de/dp/B0B4MWDFD8 · https://www.amazon.de/dp/B09ZXRZLV8 |
| Main switch ≥30 A | Amazon.de | XT60 inline switch 30 A, B0FG2NTYXF | 11.09 | 7 left | https://www.amazon.de/dp/B0FG2NTYXF |
| Silicone wire 14 / 18 / 22 AWG | Amazon.de | B0C53D343Y (5 m) / B0D12R349S (5+5 m) / B0C7T9KYND (6×4 m) | 12.10 / 9.06 / 12.10 | In stock | amazon.de/dp/… |
| | Lindinger | 2.5 mm² / 0.75 mm², 1 m red + 1 m black each | 4.99 / 2.99 | – | lindinger.at 20479 / 44422 |
| Wago 221-415 (4) | Reichelt.at | 149800 | 0.81 each | In stock | reichelt.at 149800 |
| | Amazon.de | 25-pack, B0107SYYGU | 14.11 | In stock | https://www.amazon.de/dp/B0107SYYGU |
| Servo extension 15 cm (6) | Amazon.de | 5-pack, B081NVPRNG (buy 2) | 6.54 per pack | 20 left | https://www.amazon.de/dp/B081NVPRNG |
| | Lindinger | Multiplex | 3.90 each | – | lindinger.at 67983 |
| Dupont F-F / heat-shrink / cable ties / spiral wrap | Reichelt.at | 282699 / 152924 / 280182 (velcro) / 332584 | 1.11 / 5.39 / 5.14 / 2.50 | In stock | reichelt.at |
| | Amazon.de | B01EV70C78 / B071D7LJ31 / B0BFVRQVFP / B093SQP3PZ | 7.04 / 8.56 / 7.04 / 6.16 | In stock | amazon.de/dp/… |

### 1d. Mechanical
| Item (qty) | Vendor | Product / SKU | € incl. VAT | Stock | URL |
|---|---|---|---|---|---|
| 625ZZ (4) | 3DJake.at | 10-pack | **4.99** | In stock | https://www.3djake.at/3djake/kugellager?sai=33676 |
| | Amazon.de | QUARKZMAN 15-pack, B0CM8TYDR6 | 7.36 | In stock | https://www.amazon.de/dp/B0CM8TYDR6 |
| | kugellager-express.de | 625-ZZ | 0.88 each from 4 (DE VAT) | Available | https://www.kugellager-express.de/miniatur-kugellager-625-ZZ-5x16x5-mm |
| | 123kugellager.at | 625-ZZ | 1.60 each | 50+ | 123kugellager.at |
| 6805-2RS (4) | Amazon.de | QUARKZMAN 2-pack, B0CL4Z679J (buy 2) | 6.74 per pack | In stock | https://www.amazon.de/dp/B0CL4Z679J |
| | kugellager-express.de | 6805/61805-2RS | **1.70 each** from 4 | Available | https://www.kugellager-express.de/rillenkugellager-6805-61805-2rs-25x37x7-mm |
| | kugellager-shop.net / 123kugellager.at | – | 1.90 / 4.36 each | In stock | – |
| 633ZZ (8) | Amazon.de | QUARKZMAN 8-pack ABEC5, B0GGT3GW69 | **10.27** | **3 left** | https://www.amazon.de/dp/B0GGT3GW69 |
| | 123kugellager.at | 633-ZZ | 2.04 each (16.32 for 8) | 50+ | 123kugellager.at |
| Plain bearing 3×5×5 (32) | Amazon.de | QUARKZMAN sintered bronze, 50-pack, B0G15L264D | **10.27** | **4 left** | https://www.amazon.de/dp/B0G15L264D |
| | Amazon.de | Wrapped bushing 10-pack, B0CWRXCWF9 | 5.44 per pack | In stock | – |
| | igus.at | iglidur G **GSM-0304-05 (3×4.5×5)**; prices shown excl. VAT | 50 pcs = 18.50 net (22.20 gross, calculated) | 24–48 h | https://www.igus.at/iglidur-ibh/zylindrische-gleitlager/product-details/iglidur-g-m?artnr=GSM-0304-05 |
| M3 SHCS assortment | Amazon.de | WZHUIDA 1080 pcs, stainless (40 each of 6/8 mm; 30 each of 10/12/14/16/18/20; 20 each of 25/30/35/40/50; plus 360 nuts, 360 washers), B0D2VST57H | **17.14** | 17 left | https://www.amazon.de/dp/B0D2VST57H |
| | Schraubenking.at | DIN 912 A2, loose packs: 6–16 mm in 100s at €2.04–2.35; 18–35 mm in 10s at €0.83–0.97 (cheaper per pack from 3 packs) | see left | In stock | https://www.schraubenking.at/Zylinderschrauben__M3__Edelstahl-A2-/-V2A |
| M3 nyloc DIN 985 (100) | Schraubenking / Amazon | P000454 / B0GXYB1TWK | 2.30 / 7.04 | In stock | schraubenking.at / https://www.amazon.de/dp/B0GXYB1TWK |
| M3 heat-set inserts (30) | Amazon.de | ORTAVA M3×5.7, 100-pack, B0CNGHVWHC | **7.04** | In stock | https://www.amazon.de/dp/B0CNGHVWHC |
| | 3DJake.at / ruthex.de | ruthex RX-M3x5.7, 100-pack (no 50-pack exists) | 8.99 | In stock | https://www.3djake.at/ruthex/gewindeeinsatz-m3-100-stueck |
| M2.5 standoff kit | Amazon.de | GeeekPi 220 pcs brass, B07PHBTTGV | 12.10 | In stock | https://www.amazon.de/dp/B07PHBTTGV |
| M2 screws (20) | Schraubenking.at | M2×6 DIN 912 A2, 10-pack | 0.88 per pack | In stock | https://www.schraubenking.at/M2-x-6mm-Zylinderschrauben-DIN912-Edelstahl-A2-P003960 |
| | Amazon.de | 660-pc M2 kit (button head), B0DJ948G7K | 8.05 | In stock | https://www.amazon.de/dp/B0DJ948G7K |
| Filament, 2 × 1 kg | 3DJake.at | Elegoo PLA black / yellow | **10.39 / kg** | In stock | https://www.3djake.at/elegoo/pla-schwarz-5 |
| | Extrudr (Austria) | PLA NX2 Matt (−40% sale) | 15.59 / kg | In stock | https://extrudr.com/de/at/products/pla-nx2-matt |
| | Amazon.de | Sunlu PLA black, B0BTHSX6S3 / light yellow, B0FLWKNF2G | 13.10 / 15.12 | In stock | amazon.de/dp/… |
| | Bambu EU / Polymaker (3DJake) / Prusament | PLA Basic / PolyTerra / Prusament PLA | 16.99 refill · 19.99 with spool / 14.99 / 26.39 | In stock | eu.store.bambulab.com/products/pla-basic-filament |

### 1e. Tools (optional; prices from the tools sub-agent)
| Tool | Pick (vendor, price €) | Alternatives |
|---|---|---|
| Printer | Bambu A1 mini, 180³ bed: **179** + €10 shipping (eu.store.bambulab.com/products/a1-mini) | A1 Combo 339 (A1 without AMS lite: UNVERIFIED); Prusa MK4S kit 719 / assembled 999; CORE One+ 1,049 kit / 1,349 assembled (prusa3d.com). Black Friday prices |
| Hex keys | Wera 950/9 Hex-Plus, Amazon 28.22 (B009ODV0OE) | Conrad Wera 950 SPKL ≈31.99 (calculated) |
| Soldering + insert tips | Miniware TS101 74.62 (B0CPDRQZYB) + ruthex tip set 17.04 (B0DP51DDF7) + adapter 13.10 (B0CTQV11YC) | Pinecil 82.14; budget Beizkna 22.16 + Preciva tips 25.61 (tip fit UNVERIFIED) |
| Stripper / crimper | Jokari Super 4 plus 14.06 / DxCRIMP set with plugs 30.22 | iCrimp SN-2549 26.21; Knipex 12 62 180 at Conrad ≈34.50 |
| Multimeter / calipers / flush cutters | Kaiweets 46.28 / Kynup 18.94 / Wiha 26812 16.09 | Voltcraft VC131 at Conrad ≈29.99; Knipex 78 61 125 ≈20.99 |
| Drills, tap, files | Bosch 3 mm ×10: 6.04; Bosch 5 mm: 1.91 (B078W5CF3D); tap set with wrench: 9.95; KS files: 6.85; deburrer: 9.06 | RS M3 tap at Conrad ≈3.34 |
| Thread locker / CA glue | Loctite 243, 5 ml: 8.11 / Pattex Ultra Gel: 5.80 | – |
| **Tools subtotal, all Amazon** | **€306.29** (budget iron variant €249.30); free shipping if added to the robot's Amazon order | Printer extra: €189 (A1 mini + shipping) |

## 2. Shipping to Austria
| Vendor | Shipping to AT | Free from | Source |
|---|---|---|---|
| DigiKey.at | €25 | **€75** | Banner on the digikey.at product page. Whether Marketplace items (the Pololu) count toward it is UNVERIFIED |
| Amazon.de | €3.99 home / €1.99 pickup point (Amazon-shipped items) | **€39** | https://www.amazon.de/gp/help/customer/display.html?nodeId=GESTJTJG49FEM5SV |
| Amazon.de parcel tax | **+€2.40 per order** (Austrian Paketsteuer, charged at checkout) | – | https://www.amazon.de/gp/help/customer/display.html?nodeId=TjkNaI0ZNMEFZXbP1q · BMF: https://www.bmf.gv.at/en/topics/taxation/parcel_delivery_tax_overview_and_faq.html |
| Berrybase.at | DHL €5.95 | €200 on the shipping page; €150 on the banner (conflicting) | https://www.berrybase.at/footer-at/informationen/versand-und-zahlungsbedingungen |
| Reichelt.at | DPD €6.95 | UNVERIFIED | https://www.reichelt.at/at/de/shop/service/-12_28 |
| Welectron | UPS €9.90 (≤2 kg) / DHL €14.90 | €200 (DHL) | https://www.welectron.com/Zahlung-und-Versand |
| Eckstein | UNVERIFIED (only shown in the cart) | UNVERIFIED | https://eckstein-shop.de/Informationen-zum-Versand |
| Lindinger.at | €5.99 | €89 (not for dangerous goods or bulky items) | https://www.lindinger.at/de/Modellbau-Lindinger/Versandkosten/ |
| 3DJake.at | €5.49 | €49.90 | https://www.3djake.at/info/versand-und-lieferung |
| Schraubenking.at | €5.90 | €99 | https://www.schraubenking.at/Versandinformationen |
| kugellager-express.de / kugellager-shop.net | €8.90 / €8.50 | None for AT | https://www.kugellager-express.de/Zahlungsarten-Versand |
| ruthex.de | €9.90 | €80 | https://www.ruthex.de/policies/shipping-policy |
| Extrudr | from €6.90 | 5 items | https://extrudr.com/de/at/page/shipping/ |
| Bambu EU | Printer €10; filament €10 | Filament from €55; printers never free | https://eu.store.bambulab.com/policies/shipping-policy |
| Robitronic / Motion RC EU | €5.90 / €6.99 | – / €99 | shop.robitronic.com/de/versandkosten · https://www.motionrc.eu/pages/shipping-policy |
| Stefansliposhop | UPS €16.61 | None seen | https://www.stefansliposhop.de/en/shipping-costs:_:1.html |
| Conrad.at | €6.99 | €69 | https://www.conrad.at/de/service/versandkosten.html |
| AliExpress DigitalServo / Fidurobot | €5.90 / free from €10 | – | Item pages |
| igus, 123kugellager, Génération Robots, MYBOTSHOP, Banggood, DFRobot, HobbyKing (blocked) | UNVERIFIED | UNVERIFIED | – |

## 3. Bundle strategies
These cover the full robot BOM with the Pi 5 4 GB, one Camera Module 3 Wide, 13 servos (12 + 1 spare), 4 disc + 4 arm horns and 2 kg of PLA. Tools and printer are excluded. Prices are per section 1.

| Shop | (a) Fewest shops: subtotal + shipping = total | (b) Lowest total | (c) Fastest, EU stock only |
|---|---|---|---|
| DigiKey.at | Pi, cooler, CM3W, cable, PSU, genuine ESP32 N32R16V, Ada 815, 4438, 4226, 4210 ×3, Pololu: 281.57 + 0 = **281.57** | Same without ESP32 and 815: 248.23 + 0 = **248.23** | – (ships from the US) |
| Amazon.de | Everything else in the EU: LiDAR (WayPonDEV), LCD, SD, LiPo, HTRC charger, 2× SPARKHOBBY BEC, all wiring, bearings, bushings, screws, inserts, standoffs, Sunlu PLA ×2: 498.74 + 0 + 2.40 = **501.14** | LiDAR, LCD, SD, LiPo, charger, switch, 6805, 633, bushings, M3 kit, nyloc, inserts, standoffs, M2, extensions, ties, 22 AWG, clone ESP32 + PCA9685: 331.23 + 2.40 = **333.63** | Items from (a) plus Waveshare C1 (103.86, in stock), Ada 4438, JST-SH set, clone ESP32, 13× Amazon "SPT5435LV" (311.87), horn packs: 850.90 + 2.40 = **853.30** |
| AliExpress (DigitalServo) | 4× WP Arm + 4× WP Disc + 5× WP: 180.98 + 5.90 = **186.88** | Same: **186.88** | – |
| Reichelt.at | – | Wago ×4, ATO holder, 2× 25 A fuse, Dupont, heat-shrink, spiral wrap: 15.98 + 6.95 = **22.93** | – |
| Lindinger.at | – | 2× Hobbywing UBEC 10A V2, bag, checker, 2.5 mm² + 0.75 mm² wire, XT60 ×3 pairs: 79.39 + 5.99 = **85.38** | – |
| 3DJake.at | – | Elegoo PLA black + yellow, 625ZZ 10-pack: 25.77 + 5.49 = **31.26** | – |
| Berrybase.at | – | – | Pi 4 GB, cooler, SD, cable, PSU: 169.30 + 5.95 = **175.25** |
| Welectron | – | – | CM3 Wide, LCD: 46.80 + 9.90 = **56.70** |
| Eckstein | – | – | Pololu, INA260, PCA9685 clone: 63.93 + UNVERIFIED shipping |
| **Grand total** | **€969.59** (3 shops) | **€908.31** (6 shops) | **€1,149.18 + Eckstein shipping** (4 shops) |

**Trade-offs in the totals:**
- **Dropping shops from (b):** removing 3DJake costs +€4.32, Lindinger +€15.63 and Reichelt +€25.01.
- **Genuine boards in (b):** using the genuine ESP32 (N32R16V) and the Adafruit 815 instead of clones adds €16.32, for €924.63.
- **Pi 5 8 GB:** adds €69.24 at DigiKey.
- **Strategy (c) caveats:**
  - The Amazon SPT listing doesn't state the rotation angle; a 90° or 270° unit would break the joint mapping. Confirm with the seller before buying 13.
  - "In stock" at Berrybase means LimitedAvailability.
  - No EU shop had the genuine N16R8 ESP32 or the Adafruit LSM6DSOX in quantity; Amazon has 3 of the IMU left.
- **Stock that could change a total:** Amazon's 633ZZ (3 left), bronze bushings (4 left), SPARKHOBBY BEC (3 left) and Lindinger's Hobbywing (few left). Order these first.

## 4. AliExpress and other non-EU options
| Item | Offer | € | Note |
|---|---|---|---|
| SPT5435LV-180W ×13 | DigitalServo Store, item 4000135787995 | 13.46 each (14.21 with horn) + 5.90 | Most-sold listing with the full SPT range. A search summary says it is SPT's exclusive distributor (UNVERIFIED). The 10-pack (155.16) costs more than 10 singles (134.60) |
| RPLIDAR C1 | Hefei Fidurobot, 1005006190309082 / FD Robot, 1005008790608977 | 66.29 / 65.01, free shipping | Neither is an official Slamtec store; only €4–5 cheaper than Amazon.de |
| RPLIDAR C1 | DFRobot DFR1138 | US\$69 (≈61.76 net) | Shipping and import VAT UNVERIFIED |
| ESP32-S3 N16R8 clone | item 1005006240070551 | US\$4.49 (search snippet only, UNVERIFIED) | – |

**Rules for non-EU orders:**
- **€3 duty per item:** since 1 Jul 2026 the EU charges a flat €3 per item (counted per tariff line, not per unit) on consignments up to €150. The seller pays it ([EU Commission](https://taxation-customs.ec.europa.eu/news/guidance-and-legal-text-temporary-flat-fee-low-value-imports-which-will-apply-until-1-july-2028-2026-06-08_en)).
- **€2 handling fee:** from 1 Nov 2026 there is an extra €2 per item ([vienna.at](https://www.vienna.at/temu-und-shein-neue-2-euro-gebuehr-ab-november/10583882)). It can be passed on in prices.
- **The servo order is over €150.** IOSS (VAT collected at checkout) only applies to consignments up to €150 ([Revenue.ie](https://www.revenue.ie/en/vat/vat-ecommerce/import-oss/index.aspx)). Above that, the normal import procedure applies, so expect possible carrier VAT and clearance fees. Splitting into two orders of 7 + 6 servos (about €90 each) stays under the limit for +€5.90 shipping. How AliExpress handles this is UNVERIFIED.
- **Delivery and quality:** delivery is slow; quality risk is acceptable for horns, bearings, the PCA9685 and the ESP32. **Don't buy LiPo, charger or LiDAR there.**

## 5. Clone fine vs genuine matters
| Clone or generic is fine | Genuine or brand matters |
|---|---|
| PCA9685; bearings (625, 633); bronze bushings; M2/M3 screws, nuts and inserts (stainless A2); standoffs; 25T horns (check the spline); camera cable; LCD (generic ST7789 works); JST-SH cables; Dupont, heat-shrink, ties, spiral wrap, Wago-style connectors; LiPo bag and checker; filament brand | **Servos** (genuine SPT, the -180W variant); **LiPo** (Gens ace, SLS or Robbe class, hardcase, real C rating); **LiDAR** (real Slamtec C1, for the ROS driver); **Pi 5, cameras, PSU** (official only); **microSD** (fakes are common, so buy from Amazon-shipped or retailer stock); **Pololu regulator** (cheap buck converters overstate current); **XT60** (genuine Amass); **BEC** (Hobbywing or Castle over clones, since it feeds all 13 servos); **charger** (SkyRC or ISDT preferred; HTRC is clone-tier); **6805-2RS main-joint bearings** (play shows up directly at the joint); Loctite 243 |

## 6. Caveats that affect the BOM
1. **No real "20 A, 6/7.4 V, 2S-input" BEC turned up.** A buck regulator can't put out 7.4 V from a 2S pack (6.4–8.4 V), so run the servos at **6.0 V**. The sensible options are 2× Hobbywing UBEC-10A V2-Car (10 A continuous / 15 A peak each), each feeding two legs, or a Castle BEC Pro 20A (15 A continuous at 2S per sub-agent).
2. **Genuine ESP32-S3-DevKitC-1-N16R8 is out of stock everywhere checked in the EU** (Reichelt, soyter.pl; DigiKey doesn't list it; Mouser was blocked). Pick one:
   - the genuine N32R16V (DigiKey €17.42), giving up GPIO35–37;
   - an N16R8 clone (Amazon €10.07).
3. **igus has no 3×5×5 part.** Its 3 mm bore part is 3×4.5×5 (GSM-/JSM-0304-05). Either change the printed bore to 4.5 mm or use bronze 3×5×5.
4. **Shops that changed status:**
   - Botland now sells to businesses only (VAT ID required).
   - AZ-Delivery's shop is closed.
   - Mouser, Antratek, RobotShop EU and HobbyKing blocked automated access, so they are not priced.
5. **Austrian parcel tax:** €2.40 per order, charged at Amazon checkout. It only applies to distance sellers with more than €100 M in sales, so it doesn't apply to most small EU shops.
6. **LiPo shipping:** a 2S 5000 mAh pack is about 37 Wh, under 100 Wh, so it ships at normal rates. Lindinger and SLS add surcharges only above 100 Wh.
7. **DE-VAT shops:** Welectron, Eckstein and kugellager-* prices may rise about 0.8% if checkout applies Austria's 20% VAT.
8. **Conrad tool prices** are net × 1.2 (calculated). Bambu and Prusa prices are time-limited Black Friday prices.

---

## EU pricing for the 15 extra quadruped BOM items (Austria, 2026-10-30)

Every item has at least one offer that I read on the shop's page. Prices are € incl. VAT as shown on 2026-10-30, cheapest first.

**Three corrections to the brief:**
- **Item 1:** Seeed SKU 102010635 is the XIAO ESP32S3 **Sense** pre-soldered (it has a camera). The plain pre-soldered board is **102010634**, and 113991114 is the plain board without headers.
- **Item 2:** Pololu #2813 is the **Big** Pushbutton Power Switch HP (4.5–40 V, about 16 A), not a Mini. No "Mini HP 6 A" exists. #2812 is the Big MP (4.5–40 V, 8 A). The 6 A part is the Mini LV **#2808** (2.2–20 V).
- **Item 11:** The GeeekPi kit B07PHBTTGV has **no** M2.5×6 F-F standoffs. You need to buy those separately.

**How to read the price columns:**
- Eckstein and Botland show German VAT (19%). The Austrian price may be about 1% higher.
- Amazon.de prices were fetched without a delivery address, so they likely include German VAT. The Austrian price may differ slightly.
- "(listing)" means I saw the price only on the Amazon search results page, not the product page. Treat it as UNVERIFIED.
- DigiKey prices are the "incl. VAT" figure on DigiKey.at.

## 1. Seeed XIAO ESP32S3 (qty 1)
| Vendor | Product / SKU | € | Pack | Stock | URL |
|---|---|---|---|---|---|
| DigiKey.at | 113991114 plain, no headers (genuine) | 7.98 | 1 | 9,565 | https://www.digikey.at/de/products/result?keywords=113991114 |
| DigiKey.at | 102010634 pre-soldered (genuine) | 9.05 | 1 | 159 | https://www.digikey.at/de/products/detail/seeed-technology-co-ltd/102010634/26553885 |
| Berrybase.at | SE-102010634 "Mit Header" (genuine) | 9.90 | 1 | 100+ | https://www.berrybase.at/en/seeed-studio-xiao-esp32-s3-wifi-bluetooth-5.0-mesh-8mb-psram-dual-core-240-mhz-6-mb-flash-5v-019de2c9775872f985e5ef385c70decc |
| Amazon.de | B0BYSB66S5, Seeed XIAO ESP32-S3 | 16.08 | 1 | Auf Lager | https://www.amazon.de/dp/B0BYSB66S5 |

- The Berrybase "Ohne Header" variant is in stock, but I did not see its own price. The page says "From €9.90".
- Berrybase's €9.50 "XIAO ESP32-S3 **Plus**" is a different board.

## 2. Pololu pushbutton power switch (qty 1)
| Vendor | Product | € | Stock | URL |
|---|---|---|---|---|
| Botland.de | #2808 Mini LV, 2.2–20 V / 6 A | 4.50 | InStock | https://botland.de/elektronische-und-digitale-schalter/29436-mini-push-mosfet-schalter-lv-2-2-20v-6a-mit-rueckstromschutz-pololu-2808.html |
| Botland.de | #2812 Big MP, 4.5–40 V / 8 A | 4.90 | InStock | https://botland.de/elektronische-und-digitale-schalter/5118-grosser-push-mosfet-mp-schalter-45-40-v-8-a-mit-ruckstromschutz-pololu-2812-5903351244879.html |
| Botland.de | #2813 Big HP, 4.5–40 V / 16 A | 7.90 | InStock | https://botland.de/elektronische-und-digitale-schalter/5117-grosser-push-mosfet-schalter-hp-45-40v-16a-mit-ruckstromschutz-pololu-2813-5903351244862.html |
| Eckstein (DE) | #2808 (PO2808) | 5.89 | Available, 1–3 days | https://eckstein-shop.de/PololuMiniPushbuttonPowerSwitchwithReverseVoltageProtection2CLVEN |
| DigiKey.at Marketplace | #2808 / #2812 / #2813 | 5.98 / 7.18 / 10.80 | 382 / 241 / 156 | https://www.digikey.at/de/products/result?keywords=pololu%202813 |

- **Fit for 2S (6.0–8.4 V):** all three variants cover that range. #2808 is limited to 20 V, so it would not work at 3S or higher.
- **Which one to pick depends on what the switch carries:**
  - If it switches only the logic/Pi branch, #2808 (6 A) is enough.
  - If it switches the whole pack feeding two 10 A UBECs, the battery side can draw about 18 A at full servo load (my estimate). That is beyond #2813's rated ~16 A continuous. In that case keep it out of the servo path and use the XT60 arming loop.
- **DigiKey Marketplace** items ship from Pololu in the USA, and the page says a separate shipping fee may apply.
- **Not recommended:** Amazon B079NSQ1ML (#2813) at €56.34 (listing). Berrybase POL2812 at €4.90 is not available.

## 3. 12 mm momentary metal pushbutton, normally open (qty 1)
| Vendor | Product | € | Stock | URL |
|---|---|---|---|---|
| Reichelt.at | ONPOW VS GQ12B-10S, stainless, screw terminals, momentary NO | 5.66 (was 7.05) | ab Lager | https://www.reichelt.at/at/de/shop/produkt/drucktaster_17_5_12_mm_2a-36_vdc_edelstahl-318555 |
| Reichelt.at | ONPOW VS GQ12B-10JS, stainless, solder lugs | 7.46 | ab Lager | https://www.reichelt.at/at/de/shop/produkt/drucktaster_17_5_12_mm_2a-36_vdc_edelstahl-318547 |
| Amazon.de | Metzler 12 mm stainless, B0FH2TX1LN | 5.53 | Auf Lager | https://www.amazon.de/dp/B0FH2TX1LN |

- **Do not buy the Metzler:** its page states a 40 mm installation depth, which is over your 30 mm limit.
- **GQ12B depth is UNVERIFIED.** The datasheet I fetched had no readable body length. ONPOW describes the series as "short body".
- GQ12B-10/J/N is the nickel-plated brass version. Reichelt stocks the stainless (S) version.

## 4. Hobbywing UBEC 10A V2-Car, 2–6S (qty 2)
| Vendor | Product | € each | Stock | URL |
|---|---|---|---|---|
| Lindinger.at | HW30603003 BEC 10A V2-Car (genuine) | **26.99** (was 31.98), confirmed | "Only a few left in stock", 1–3 days | https://www.lindinger.at/en/RC-Electronics/Power-Supply-Bus-System/Battery-Switches-BEC/HOBBYWING-BEC-10A-V2-Car-UBEC-controller-for-2-6S/9787110 |
| Amazon.de | SPARKHOBBY UBEC 10A 2–6S, B0DK31PYFZ (**clone**) | 26.63 | 3 left | https://www.amazon.de/dp/B0DK31PYFZ |
| Amazon.de | Hobbywing B0BCWYQYKW (genuine) | 29.90 from 3 sellers (listing) | no Buy Box | https://www.amazon.de/dp/B0BCWYQYKW |

- Two units at Lindinger cost €53.98, plus €5.99 shipping (free from €89).
- Lindinger's Austrian free-shipping threshold of €89 is confirmed on its site.

## 5. ATO/ATC inline fuse holder with ≥14 AWG leads, plus 20 A fuses
| Vendor | Product | € | Pack | Stock | URL |
|---|---|---|---|---|---|
| Amazon.de | Nilight NI-FH01, 14 AWG, 12-inch loop, B07426WCLM | 8.56 | 10 holders | Auf Lager | https://www.amazon.de/dp/B07426WCLM |
| Amazon.de | Bst4U, 14 AWG, waterproof cap, plus 100 assorted fuses incl. 20 A, B087BT1PH3 | 10.07 | 6 holders + 100 fuses | Auf Lager | https://www.amazon.de/dp/B087BT1PH3 |
| Reichelt.at | FKS 20A ATO fuse | 0.36 each (0.236 from 10) | 1 | ab Lager | https://www.reichelt.at/at/de/shop/produkt/kfz-flachsicherung_20a_gelb-7785 |
| Amazon.de | JatilEr 20 A standard blade fuses, B09ZXQ8F3J | 4.02 | 10 | Auf Lager | https://www.amazon.de/dp/B09ZXQ8F3J |

- Reichelt has no wired **ATO** inline holder. Its nearest option is the IMAXX HLP7335 for **mini** blade fuses (2.5 mm² leads, 30 A, IP55) at €2.62. It would need FK1 20A mini fuses at €0.41 each. Link: https://www.reichelt.at/at/de/shop/produkt/kfz-sicherungshalter_minioto_30_a_58_v_low_profile_ip55-229125

## 6. Servo extension cables, 30 cm JR (qty 12)
| Vendor | Product | € | Pack | Stock | URL |
|---|---|---|---|---|---|
| Amazon.de | 30 cm male–female JR, B07FYF76Y1 (gauge not stated) | 10.07 | 10 | 12 left | https://www.amazon.de/dp/B07FYF76Y1 |
| Amazon.de | VUNIVERSUM 30 cm **22 AWG** (0.32 mm²), B078VSNC9D | 11.08 | 10 | 11 left | https://www.amazon.de/dp/B078VSNC9D |
| Amazon.de | GTIWUNG 30 pcs JR, B082WYFWSY (length mix not checked) | 12.10 (listing) | 30 | ? | https://www.amazon.de/dp/B082WYFWSY |

- You need 12, so buy two packs of 10: 2 × €11.08 = €22.16 for the 22 AWG version.
- I found nothing suitable at Berrybase or Reichelt. Lindinger was not checked.

## 7. Pi 5 camera cable, 22-pin to 15-pin, 300 mm (qty 1)
| Vendor | Product | € | Stock | URL |
|---|---|---|---|---|
| DigiKey.at | Raspberry Pi SC1129 (official) | 2.14 | 1 | https://www.digikey.at/de/products/detail/raspberry-pi/SC1129/21658260 |
| Berrybase.at | RPI-CC-SM-30, official Standard–Mini 300 mm | 2.30 | 100+ | https://www.berrybase.at/raspberry-pi-camera-cable-standard-mini-300mm |
| Amazon.de | B0CMZPKZFT, sold as "offizielles" (unconfirmed) | 5.20 | Auf Lager | https://www.amazon.de/dp/B0CMZPKZFT |
| Amazon.de | Waveshare 22-to-15 pin 300 mm, B0CX1SFD44 | 9.67 | Auf Lager | https://www.amazon.de/dp/B0CX1SFD44 |

- Reichelt's "RASP CAM FPC 30" at €2.27 is the older orange camera cable, probably 15-to-15 pin. It is not the Pi 5 22-pin type.

## 8. Short USB-A to USB-C cable, 90° (qty 2)
| Vendor | Product | € | Pack | Stock | URL |
|---|---|---|---|---|---|
| Amazon.de | deleyCON 0.15 m USB-A to C 90°, B0FVXP8LXJ | 4.99 | 1 | Auf Lager | https://www.amazon.de/dp/B0FVXP8LXJ |
| Amazon.de | deleyCON 0.15 m USB-A to C 90°, 480 Mbps, B0DGTR2X97 | 5.84 | 1 | Auf Lager | https://www.amazon.de/dp/B0DGTR2X97 |
| Amazon.de | aceyoon 20 cm USB-A to C 90°, B09ZDV7S44 | 7.64 | 3 | Auf Lager | https://www.amazon.de/dp/B09ZDV7S44 |

- I found no short USB-A to C cable at Berrybase.

## 9. Adafruit STEMMA QT cable (qty 1)
| Vendor | Product | € | Stock | URL |
|---|---|---|---|---|
| DigiKey.at | Adafruit 4397, JST SH to female sockets, 150 mm | 1.01 | 8 | https://www.digikey.at/de/products/result?keywords=adafruit%204397 |
| DigiKey.at | Adafruit 4209, JST SH to male header | 1.01 | 5 | https://www.digikey.at/de/products/result?keywords=adafruit%204209 |
| Berrybase.at | Seeed SE-114992154, Grove & Qwiic/STEMMA QT to male/female jumpers (alternative) | 2.50 | 3 | search "stemma qt kabel" |

- Berrybase's Adafruit ADA-JSTSH4 and the SparkFun CAB-14988 / CAB-17261 cables are all "nicht lieferbar".
- DigiKey's shipping is €25 below €75, so only order 4397 there as part of a bigger DigiKey order.

## 10. Dupont jumper wires, female–female (1 pack)
| Vendor | Product | € | Stock | URL |
|---|---|---|---|---|
| Berrybase.at | DUPK-SET-10: 40-pin F-F + M-M + F-M, 10 cm | 4.40 | 100+ | https://www.berrybase.at/40pin-jumper-dupont-kabel-set-je-1x-f-f-m-m-f-m-10cm |
| Berrybase.at | DUPK-SET-20: same set, 20 cm | 4.90 | 100+ | https://www.berrybase.at/40pin-jumper-dupont-kabel-set-je-1x-f-f-m-m-f-m-20cm |
| Amazon.de | 120 × F-F 10 cm, B072JT6BCN | 7.04 | Auf Lager | https://www.amazon.de/dp/B072JT6BCN |
| Amazon.de | 160 × F-F, 10/20/30/40 cm, B0F98KBV61 | 8.05 | stock field empty | https://www.amazon.de/dp/B0F98KBV61 |

## 11. M2 and M2.5 hardware
**GeeekPi B07PHBTTGV**, €12.10, in stock. Contents as listed on the page:

| Part | Qty |
|---|---|
| M2.5 × 20+6 male–female | 16 |
| M2.5 × 5+6 male–female | 16 |
| M2.5 × 11+6 male–female | 16 |
| M2.5 × 11 (probably F-F; my inference) | 16 |
| M2.5 × 12+6 | 4 |
| M2.5 screws | 50 |
| M2.5 nuts | 50 |
| Acrylic washers | 50 |

There are **no 6 mm F-F standoffs** in the kit.

| Need | Vendor | Product | € | Pack | Stock | URL |
|---|---|---|---|---|---|---|
| M2.5 × 6 F-F (≥10) | DigiKey.at | Würth 970060151, steel hex, female–female | 0.552 each, so ≈5.52 for 10 | 1 | 3,699 | https://www.digikey.at/de/products/result?keywords=970060151 |
| M2.5 × 6 F-F | Amazon.de | B0GK7QTZ7B, multi-size F-F brass listing (variant not confirmed) | 11.29 | 2–50 | Auf Lager | https://www.amazon.de/dp/B0GK7QTZ7B |
| M2 × 8 F-F (≥3) | Amazon.de | B0DR67YGQL, M2×8 brass, female both ends | 7.73 | 40 | 2 left | https://www.amazon.de/dp/B0DR67YGQL |
| M2 × 5 DIN 912 | Schraubenking.at | A2 stainless | 0.86 | 10 | 2–3 days | https://www.schraubenking.at/M2-x-5mm-Zylinderschrauben-DIN912-Edelstahl-A2-P003957 |
| M2 × 10 DIN 912 | Schraubenking.at | A2 stainless | 0.78 | 10 | 2–3 days | https://www.schraubenking.at/M2-x-10mm-Zylinderschrauben-DIN912-Edelstahl-A2-P002803 |
| M2 nuts DIN 934 | Schraubenking.at | A2 stainless | 1.87 | 100 | 1 day | https://www.schraubenking.at/M2-Sechskantmuttern-DIN934-Edelstahl-A2-P002807 |
| M2.5 × 5 / × 6 DIN 912 | Schraubenking.at | A2 stainless | 0.83 each size | 10 | 2–3 days | …-P004986 / https://www.schraubenking.at/M25-x-6mm-Zylinderschrauben-DIN912-Edelstahl-A2-P005010 |
| M2.5 nuts DIN 934 | Schraubenking.at | A2 stainless | price not seen | 100 | ? | https://www.schraubenking.at/M25-Sechskantmuttern-DIN934-Edelstahl-A2-P004196 |

- No brass M2 × 8 F-F standoff turned up in a quick DigiKey search.

## 12. M3 × 40 DIN 912 and M3 DIN 985 nylock nuts
**WZHUIDA kit B0D2VST57H**, €17.14, "Nur noch 17 auf Lager". The listing confirms it **does contain M3 × 40**:

| Length | Qty |
|---|---|
| M3 × 6, M3 × 8 | 40 each |
| M3 × 10, 12, 14, 16, 18, 20 | 30 each |
| M3 × 25, 30, 35, **40**, 50 | 20 each |
| M3 nuts (plain, **not** nylock) | 360 |
| M3 washers | 360 |

The screws are 304 stainless with a socket cap ("Zylinderkopf" variant).

| Need | Vendor | Product | € | Pack | Stock | URL |
|---|---|---|---|---|---|---|
| M3 × 40 DIN 912 | Schraubenking.at | A2 stainless | 1.01 | 10 | Sofort verfügbar | https://www.schraubenking.at/M3-x-40mm-Zylinderschrauben-DIN912-Edelstahl-A2-P004987 |
| M3 × 40 DIN 912 | Schraubenking.at | 8.8 zinc-plated | 1.16 | 10 | 1 day | https://www.schraubenking.at/M3-x-40mm-Zylinderschrauben-DIN912-Stahl-verzinkt-FKL-88-P005519 |
| M3 DIN 985 nylock | Schraubenking.at | zinc-plated steel | 1.39 | 100 | 1 day | https://www.schraubenking.at/M3-Sicherungsmuttern-DIN985-Stahl-verzinkt-FKL6/8-P000461 |
| M3 DIN 985 nylock | Schraubenking.at | A2 stainless | 2.30 | 100 | 1 day | https://www.schraubenking.at/M3-Sicherungsmuttern-DIN985-Edelstahl-A2-P000454 |
| M3 DIN 985 nylock | Reichelt.at | SKSM M3-100 | 3.48 | 100 | ab Lager | https://www.reichelt.at/at/de/shop/produkt/sicherungsmuttern_m3_100_stueck-65808 |
| M3 DIN 985 nylock | Amazon.de | A2 stainless, B0BJYRLG6G | 5.53 | 50 | Auf Lager | https://www.amazon.de/dp/B0BJYRLG6G |

## 13. Foam mounting tape (19 mm) and 2.5 mm cable ties (100 pcs)
| Vendor | Product | € | Pack | Stock | URL |
|---|---|---|---|---|---|
| Reichelt.at | tesa PRO Universal 19 mm × 5 m (not VHB) | 9.98 | 1 roll | ab Lager | https://www.reichelt.at/at/de/shop/produkt/montageband_tesa_pro_universal_5_m_x_19_mm_weiss-338987 |
| Amazon.de | 3M VHB 5952F, 19 mm × 3 m × 1.1 mm, B00EDLPG7Y | 14.11 | 1 roll | Auf Lager | https://www.amazon.de/dp/B00EDLPG7Y |
| Amazon.de | 3M VHB 4991, 19 mm × 5.5 m × 2.3 mm, B0779B5LBZ | 20.59 | 1 roll | Auf Lager | https://www.amazon.de/dp/B0779B5LBZ |
| Berrybase.at | Cable ties 100 × 2.5 mm, white (E-E510) | 0.90 | 100 | 9 | https://www.berrybase.at/kabelbinder-100-mm-x-2-5-mm-weiss-100-stueck |
| Reichelt.at | Delock 19186, 100 × 2.5 mm, black, cold-resistant | 1.16 | 100 | ab Lager | https://www.reichelt.at/at/de/shop/produkt/kabelbinder_kaelteresistent_l_100_x_b_2_5_mm_schwarz_100_stueck-316436 |
| Berrybase.at | Cable ties 100 × 2.5 mm, transparent (D18605) | 1.90 | 100 | 3 | https://www.berrybase.at/kabelbinder-100-x-2-5mm-transparent-100-stueck |

## 14. XT60 arming-loop plug
**Confirmed.** B07C3KH1VT is "3 Paar (6 Stück) Original Amass Premium XT60H … Stecker Buchse Male Female inkl. Schutzkappen". That is 3 male and 3 female connectors, €6.44, in stock: https://www.amazon.de/dp/B07C3KH1VT

## 15. Medium-strength thread locker
| Vendor | Product | € | Stock | URL |
|---|---|---|---|---|
| Schraubenking.at | Förch thread locker, medium, blue, 10 ml (not Loctite) | 5.71 | 1 day | https://www.schraubenking.at/Schraubensicherung-mittelfest-blau-10ml-P002471 |
| Amazon.de | Loctite 243, 5 ml, B00745GNPK | 8.11 | 4 left | https://www.amazon.de/dp/B00745GNPK |
| Amazon.de | Loctite 243, 10 ml, B00Y8DOMCC | 13.07 | Auf Lager | https://www.amazon.de/dp/B00Y8DOMCC |
| Reichelt.at | Loctite 243, 10 ml | 15.12 | ab Lager | https://www.reichelt.at/at/de/shop/produkt/schraubensicherung_lack_mitttelfest_blau_10_ml-94948 |

## Shipping for shops outside your list
- **Botland (ships from Poland):** I only saw German terms: from €4.99, free above €100. Rates to Austria are UNVERIFIED.
- **Eckstein (DE):** this shop is on your preferred list but you gave no shipping cost for it. The rate to Austria is UNVERIFIED; the shipping-info pages I fetched did not show it.
- **DigiKey Marketplace (Pololu items):** shipped by Pololu from the USA, and a separate shipping fee may apply on top of DigiKey's €25 / free from €75.

## Not reached
- **TME** and **metzler-electronics.com** both block automated access, so I have no prices from them.
- I did not check **Conrad.at** or **AliExpress**.