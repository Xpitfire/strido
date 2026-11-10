# Buses and signals

A bus is an agreed way of moving bits between chips: which wires carry what, how fast, and who may talk when. Strido uses five: I²C for the sensors and the servo driver, USB serial between the Pi and the ESP32 (and to the LiDAR), PWM to the servos, SPI to the face display and CSI to the camera. Each was picked for a reason you can work out from the numbers.

::: tip In Strido
- **I²C** (400 kHz) on XIAO D4 = SDA, D5 = SCL: PCA9685 0x40 (all-call 0x70), LSM6DSOX 0x6A, INA260 0x41. Wires W17 (22 AWG, soldered at the XIAO, crimped at the PCA9685) and W18, W19 (STEMMA QT cables, `stemma_qt_female` × 2).
- **USB serial:** Pi → XIAO USB CDC (W14, `/dev/strido_mcu`) and Pi → RPLIDAR C1 USB adapter (W15, `/dev/rplidar`).
- **PWM:** PCA9685 → 12 servos, 200 Hz, 500–2500 µs; LCD backlight on D2.
- **SPI:** XIAO → Waveshare 2" ST7789 LCD (D8 SCK, D10 MOSI, D9 DC, D0 CS, D1 RST), W21.
- **CSI:** Pi 5 CAM/DISP 0 → Camera Module 3 Wide, 22→15-pin FFC, 300 mm (W16).
- **Source of truth:** `hardware/electronics.yaml`, `firmware/strido_esp32s3/src/board_config.h`, `hardware/wiring.yaml` (cables and routes; cut list in the [wiring check](../../verification/wiring.md)), `docs/electronics.md` (pin maps, wiring list).
:::

## Overview

| Bus | Wires | Speed in Strido | Topology | Used for |
|---|---|---|---|---|
| I²C | SDA, SCL (+ 3.3 V, GND) | 400 kHz | shared, addressed | servo driver, IMU, power monitor |
| USB (CDC serial) | D+, D−, 5 V, GND | USB full speed | point to point | Pi ⇄ XIAO commands and state |
| UART (behind USB adapter) | TX, RX, GND | 460 800 baud | point to point | RPLIDAR C1 scan data |
| Servo PWM | one signal per servo | 200 Hz frame, µs pulse | one wire per servo | joint position commands |
| SPI | SCK, MOSI, CS, DC | 27 MHz write clock | one device here | LCD pixels |
| MIPI CSI-2 | differential lanes in a ribbon | Gbit/s class | point to point | camera images |

## I²C: one pair of wires, many devices

**I²C** (Inter-Integrated Circuit) uses two wires: **SCL** (clock, driven by the controller) and **SDA** (data, both directions). Every device has a 7-bit **address**. The XIAO starts each transaction by sending an address, and only the device with that address answers.

### Addresses in this robot

| Address | Device | Note |
|---|---|---|
| 0x40 | PCA9685 servo driver | firmware `kPcaAddress` |
| 0x70 | PCA9685 all-call | the PCA9685 also answers here; nothing else may use it |
| 0x6A | LSM6DSOX IMU | `kImuAddress` |
| 0x41 | INA260 power monitor | `kPowerMonitorAddress`; **bridge the A0 jumper** |

The INA260 ships at **0x40**, the same as the PCA9685. Two devices on one address both answer at once and corrupt each other's replies. Bridging the solder jumper A0 moves the INA260 to 0x41. `strido_verify.electronics` checks that all addresses are unique and that the firmware constants match the YAML.

### Open drain and pull-ups

I²C devices never drive a line high. They can only pull it **low** (open-drain), and **pull-up resistors** return it to the supply voltage when nobody pulls. That is how several devices share one wire without short-circuiting each other.

Two consequences:

- **The pull-up voltage sets the logic level.** On Strido the bus is pulled up to the XIAO's **3.3 V**, and every device on it is powered from that 3.3 V rail. The check confirms 3.3 V sits inside every device's range: PCA9685 2.3–5.5 V, LSM6DSOX breakout 3–5 V, INA260 2.7–5.5 V.
- **The resistors and the wiring set the speed.** Each pull-up charges the bus capacitance (wires plus pins) back to high. Too much capacitance, or pull-ups that are too weak, makes the rising edges slow, and fast-mode I²C at 400 kHz has a strict rise-time limit. Breakout boards usually carry their own pull-ups, and on a shared bus they act in parallel. Short wires keep the capacitance low. W17 is the longest hop, routed 272 mm and cut 300 mm; W18 and W19 are 150 mm STEMMA QT cables (routed 86 mm and 125 mm).

The pull-up resistor $R_\mathrm{p}$ and the bus capacitance $C_\mathrm{b}$ form an RC circuit. When the last device releases the line, the voltage rises exponentially towards the supply $V_\mathrm{DD}$:

$$
V(t) = V_\mathrm{DD}\left(1 - e^{-t/(R_\mathrm{p} C_\mathrm{b})}\right)
$$

I²C measures the **rise time** $t_\mathrm{r}$ between 30 % and 70 % of $V_\mathrm{DD}$. Solving $V(t)$ for those two levels gives $t_\mathrm{r} = R_\mathrm{p} C_\mathrm{b} \ln(0.7/0.3) \approx 0.847\,R_\mathrm{p} C_\mathrm{b}$. The I²C specification (NXP UM10204) allows at most $300\,\mathrm{ns}$ in fast mode and $400\,\mathrm{pF}$ of bus capacitance, so the largest allowed pull-up is

$$
R_\mathrm{p,max} = \frac{t_\mathrm{r}}{0.847\, C_\mathrm{b}}
$$

For an assumed $C_\mathrm{b} = 100\,\mathrm{pF}$ (an illustration, not a measurement of this harness) that is $R_\mathrm{p,max} \approx 3.5\,\mathrm{k\Omega}$. The lower bound comes from the $3\,\mathrm{mA}$ a device must be able to sink while holding the line below $0.4\,\mathrm{V}$: $R_\mathrm{p,min} = (V_\mathrm{DD} - 0.4\,\mathrm{V}) / 3\,\mathrm{mA} \approx 0.97\,\mathrm{k\Omega}$ at $3.3\,\mathrm{V}$. Pull-ups on several breakouts combine like parallel resistors, $1/R_\mathrm{p} = \sum_i 1/R_i$, which is why too many boards can push $R_\mathrm{p}$ below that minimum.

### Why 400 kHz

The clock period, and so the time for one bit, is $T_\mathrm{bit} = 1/f_\mathrm{SCL}$; at $400\,\mathrm{kHz}$ that is $2.5\,\mu\mathrm{s}$. Each I²C byte takes 9 clock cycles (8 data bits plus an acknowledge). Setting one PCA9685 channel means sending the address, a register number and four data bytes:

$$
t_\mathrm{ch} = 6 \times 9 \times T_\mathrm{bit} = 54 \times 2.5\,\mu\mathrm{s} \approx 135\,\mu\mathrm{s}
$$

$$
t_{12} = 12\, t_\mathrm{ch} \approx 1.6\,\mathrm{ms}\quad\text{(plus small overheads)}
$$

The IMU read and, every 100 ms, the INA260 read share the same 5 ms control period. At the 100 kHz standard mode the servo writes alone would take about 6.5 ms and miss the deadline. That is why the bus runs in **fast mode, 400 kHz** (`kI2cHz`). These figures are rough estimates; the exact count depends on the library.

### STEMMA QT

Both hops to and from the IMU use a **STEMMA QT** cable: Adafruit's 4-pin JST SH (1 mm pitch) connector carrying 3.3 V, GND, SDA and SCL. It is pin-compatible with SparkFun's Qwiic. The IMU breakout has two STEMMA QT sockets so the bus can continue; each BOM cable ends in female sockets for a 2.54 mm header. The IMU sits 2.5 mm under the Pi's circuit board, so Dupont housings on its header cannot fit; the low STEMMA QT plug does.

The first hop has the opposite problem. The XIAO's pins point up 9 mm below the upper shoulder frame, too little for a 14 mm Dupont housing, so W17 (3V3, GND, SDA, SCL, 22 AWG) is **soldered to the XIAO pins** and **crimped** with Dupont contacts at the PCA9685 (see [cable management](../making/cable-management.md#connectors-and-terminations)). The full chain is:

```
XIAO ──W17 22 AWG (soldered / Dupont)──▶ PCA9685 (left header) ──W18 STEMMA QT──▶ LSM6DSOX ──W19 STEMMA QT──▶ INA260
```

## USB serial and UART

### UART basics

A **UART** sends bytes one bit at a time on a TX wire and receives on an RX wire. There is no clock wire: both sides agree on a **baud rate** in advance. Each byte is framed by a start bit and a stop bit, so 8N1 framing costs 10 bit-times per byte.

The RPLIDAR C1 speaks 3.3 V TTL UART at **460 800 baud, 8N1**:

$$
\frac{460\,800\,\mathrm{bit/s}}{10\,\mathrm{bit/byte}} \approx 46\,\mathrm{kB/s}
$$

That is plenty for 5000 samples per second. A small CP210x USB adapter (in the LiDAR pedestal) turns that UART into a USB serial port on the Pi. The udev rule names it `/dev/rplidar`, so the port name never changes between boots.

### USB CDC to the XIAO

The ESP32-S3 has native USB. The firmware presents itself as a **CDC** (Communications Device Class) serial port, which Linux shows as a tty and udev names `/dev/strido_mcu`. Over USB the "baud rate" is meaningless: data moves in USB packets. The firmware's `kUsbBaud = 2000000` is ignored and only kept for a possible UART fallback.

### Framing: COBS and CRC16

A serial link is just a stream of bytes, so the receiver needs to know where a message starts and whether it arrived intact:

- **COBS** (Consistent Overhead Byte Stuffing) rewrites each frame so it contains no `0x00` byte, then appends one `0x00` as the end marker. After a glitch, the receiver resynchronises at the next zero.
- **CRC16-CCITT-FALSE** is a 16-bit checksum over the frame. A frame with a wrong CRC is dropped instead of moving a leg to a garbage angle.

The traffic is small: a `STATE` payload is 103 bytes at 100 Hz, $103\,\mathrm{B} \times 100\,\mathrm{Hz} \approx 10\,\mathrm{kB/s}$, and a `JOINT_COMMAND` carries 12 × float32 per gait step.

## PWM to the servos

The servo signal is a pulse-width-modulated wire: a 3.3 V pulse every 5 ms (200 Hz) whose **width**, 500–2500 µs, encodes the angle. Each servo has its own signal wire from a PCA9685 channel; ground is shared through the servo power bus. Details and the numbers are in [Servos](servos.md).

The LCD backlight is a second use of PWM, on XIAO D2. Here the **duty cycle** $D = t_\mathrm{on}/T$, the fraction of time the line is high, sets brightness: the average voltage the LED sees is $\bar{V} = D\,V_\mathrm{high}$. It runs at a 20 kHz frequency ($T = 50\,\mu\mathrm{s}$), far above what the eye can see flicker in. D2 is GPIO 3, an ESP32-S3 **strapping pin** that is read at boot to select the boot mode. The firmware therefore drives it only after boot.

## SPI to the face display

**SPI** (Serial Peripheral Interface) has a clock (SCK), a data line from controller to device (MOSI) and a chip-select (CS) per device. There are no addresses: pulling CS low selects the device. SPI is push-pull rather than open-drain, so it runs far faster than I²C.

The Waveshare 2" LCD uses an ST7789 controller, 240 × 320 pixels. One full frame at 16 bits per pixel is:

$$
N = 240 \times 320 \times 16\,\mathrm{bit} = 1\,228\,800\,\mathrm{bit}
$$

$$
t_\mathrm{frame} = \frac{N}{f_\mathrm{SCK}} = \frac{1\,228\,800\,\mathrm{bit}}{27 \times 10^{6}\,\mathrm{bit/s}} \approx 45\,\mathrm{ms}
$$

On I²C at 400 kHz, with 9 clocks per 8-bit byte, the same frame would take $N \cdot \tfrac{9}{8} / 400\,\mathrm{kHz} \approx 3.5\,\mathrm{s}$. The firmware writes at **27 MHz**, noted as "conservative for ~15 cm jumper wires" in `face.cpp`: longer, unshielded wires blur fast edges. The display needs only one direction, so MISO is unused. The extra **DC** (data/command) line tells the controller whether a byte is a command or pixel data. **RST** resets the panel.

## CSI to the camera

The camera produces far more data than any of the buses above: 12 megapixels, 1080p50 video. It uses **MIPI CSI-2**, a high-speed serial interface with differential data lanes, carried on a flat flexible cable (FFC) straight into the Pi's image signal processor.

- The **Pi 5** has 22-pin, 0.5 mm-pitch camera connectors; **Camera Module 3** has a 15-pin, 1 mm-pitch connector. Hence the **22 → 15 pin** adapter cable, 300 mm long, routed through the front-shell ribbon slot.
- FFCs are fragile: the ribbon goes in with the camera, just before the front shell (assembly Step 18). Avoid sharp folds, fold its 124 mm of spare length flat, and insert it with the metal contacts facing the connector's contacts.

The camera also has its own small control bus for focus and settings. That runs inside the CSI cable to the Pi, not on the robot's I²C bus.

## Check yourself

1. What would go wrong if you forgot to bridge the INA260's A0 jumper?
2. Why do I²C lines need pull-up resistors, while SPI lines do not?
3. Roughly how long does it take to write all 12 servo channels at 100 kHz, and why does that matter?
4. What does the `0x00` byte at the end of each USB frame do?
5. Why does the camera use CSI instead of USB or SPI?

<details>
<summary>Answers</summary>

1. The INA260 would sit at 0x40 together with the PCA9685, and both would answer the same transactions, corrupting the bus. The firmware would then refuse to drive without a working power monitor.
2. I²C outputs are open-drain and only pull low, so something must pull the line high. SPI outputs actively drive both levels.
3. About 6.5 ms (four times the 1.6 ms at 400 kHz), longer than the 5 ms control period.
4. It marks the end of a COBS-encoded frame. COBS guarantees no other zero appears inside, so the receiver can always resynchronise.
5. Its data rate (12 MP stills, 1080p50 video) needs a high-speed differential link straight into the Pi's image processor; SPI is far too slow, and CSI is the Pi's native camera interface.

</details>

## Further reading

- [I²C bus pull-up resistor calculation (TI SLVA689)](https://www.ti.com/lit/an/slva689/slva689.pdf)
- [Introducing Adafruit STEMMA QT](https://learn.adafruit.com/introducing-adafruit-stemma-qt)
- [Consistent Overhead Byte Stuffing (overview)](https://en.wikipedia.org/wiki/Consistent_Overhead_Byte_Stuffing)
- [RPLIDAR C1 datasheet (Slamtec)](https://wiki.slamtec.com/download/attachments/83066883/SLAMTEC_rplidar_datasheet_C1_v1.0_en.pdf?api=v2&modificationDate=1700531479533&version=1)
- Related pages: [Microcontrollers](microcontrollers.md), [Sensors](sensors.md), [Firmware](../software/firmware.md), [Cable management](../making/cable-management.md), [Electronics, wiring and power](../../electronics.md)
