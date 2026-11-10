# Servos

A hobby servo is a small gearmotor with its own position controller: you send it a pulse width, it turns its output shaft to the matching angle and holds it there. Strido uses twelve of them, one per joint, and everything about how the robot moves starts with how these servos are driven.

::: tip In Strido
- **Part:** SPT5435LV-180W digital servo, 13 bought (12 + 1 spare), BOM line `servo_spt5435lv` in `hardware/bom.yaml`.
- **Joints:** hip (abduction), thigh and knee crank on each leg, FL, FR, RL, RR. PCA9685 channels 4–15 (`hardware/electronics.yaml`, `servos.channels`).
- **Signal:** PCA9685 PWM driver at 200 Hz, 500–2500 µs, 3.3 V logic level, enabled through the XIAO D3 → PCA9685 OE line.
- **Power:** the 6.0 V servo rail from two Hobbywing UBEC-10A, six servos each, through the WAGO buses in the front and rear cavities.
- **Horns:** 25T aluminium disc horns (8) for hip and thigh, 25T aluminium clamping arm horns (4) for the knee crank.
- **Code:** `firmware/strido_esp32s3/lib/strido_core/src/servo_map.cpp` (angle → pulse), `strido-cli center` / `calibrate`.
:::

## What is inside a hobby servo

A servo packs four things into a 40.5 × 20 × 40.5 mm case (72 g for the SPT5435LV):

1. **DC motor.** The SPT5435LV uses a cored (iron-armature) motor.
2. **Gearbox.** All-metal gears trade speed for torque. The output shaft carries a 25-tooth spline (Futaba 25T) and runs in two ball bearings (2BB).
3. **Potentiometer.** It sits on the output shaft and turns shaft angle into a voltage, so the servo always knows where its output is.
4. **Control board.** It compares the commanded angle (from the pulse width) with the measured angle (from the potentiometer) and drives the motor to close the gap. This is a closed position loop *inside* the servo.

The control loop never leaves the servo. The robot only *commands* angles and cannot read them back, so `/joint_states` reports the angles the firmware commanded after clamping, not measured ones (`docs/software.md`).

### Analogue vs digital

An analogue servo updates its motor drive at the rate the pulses arrive. A digital servo has a microcontroller that samples the pulse and re-drives the motor at a much higher internal rate. The result is a stiffer hold, a smaller dead band and faster response. The cost is a higher idle current: the SPT page lists 100 mA quiescent. For a walking robot, the stiff hold is what keeps a leg from sagging under load.

## The pulse-width signal (PWM)

The servo reads the **width** of a repeating logic pulse, not its frequency or duty cycle:

| Pulse width | SPT5435LV-180W shaft |
|---|---|
| 500 µs | one end (−90° from neutral) |
| 1500 µs | neutral point (centre) |
| 2500 µs | other end (+90°) |

Inside that window the mapping is linear: the angle $\theta$ away from neutral is proportional to how far the pulse width $t_\mathrm{p}$ is from $1500\,\mu\mathrm{s}$,

$$
\theta = \frac{t_\mathrm{p} - 1500\,\mu\mathrm{s}}{k}, \qquad k = \frac{2500\,\mu\mathrm{s} - 500\,\mu\mathrm{s}}{180^\circ} \approx 11.1\,\mu\mathrm{s}/^\circ = \frac{2000\,\mu\mathrm{s}}{\pi\,\mathrm{rad}} \approx 636.6\,\mu\mathrm{s/rad}
$$

The radian form of $k$ is the constant `kUsPerRad` in `servo_map.h`.

The pulse repeats at a fixed rate. Classic RC gear sends one pulse every 20 ms (50 Hz). The SPT5435LV accepts up to 330 Hz, and Strido runs at **200 Hz** (`kServoFrequencyHz`), one new pulse every $T = 1/f = 5\,\mathrm{ms}$. That matches the firmware's 200 Hz control loop, so every new joint target reaches the servo in the next frame.

In general PWM terms, a pulse of width $t_\mathrm{p}$ repeated every $T$ has a **duty cycle** $D = t_\mathrm{p}/T$. The neutral pulse at 200 Hz is $D = 1500\,\mu\mathrm{s} / 5000\,\mu\mathrm{s} = 30\,\%$, the extremes 10 % and 50 %. The servo ignores $D$ and times only $t_\mathrm{p}$, which is why changing the frame rate from 50 Hz to 200 Hz does not move the shaft, as long as the gap between pulses stays long enough for the servo to see each one separately.

::: warning Buy the right angle variant
The same pulse range means different angles on different variants. On a 270° servo, 500–2500 µs would cover 270°, and every joint mapping would be wrong. The BOM requires the **-180W** variant; confirm the angle with any non-SPT seller (`hardware/bom.yaml`, note on `servo_spt5435lv`).
:::

### Resolution and dead band

The **dead band** is the smallest change in pulse width the servo reacts to. The SPT page gives 4 µs, about 0.36°.

The PCA9685 that generates the pulses divides each period into 4096 steps (12-bit):

$$
\Delta t_\mathrm{step} = \frac{T}{2^{12}} = \frac{T}{4096}
$$

$$
200\,\mathrm{Hz}:\ \frac{5000\,\mu\mathrm{s}}{4096} \approx 1.22\,\mu\mathrm{s}, \qquad 50\,\mathrm{Hz}:\ \frac{20\,000\,\mu\mathrm{s}}{4096} \approx 4.88\,\mu\mathrm{s}
$$

At 200 Hz one step is $1.22\,\mu\mathrm{s} / 636.6\,\mu\mathrm{s/rad} \approx 1.9\,\mathrm{mrad} \approx 0.11^\circ$ of shaft travel.

At 50 Hz one step would already be wider than the dead band; at 200 Hz the driver resolves about three steps inside it. The higher frame rate buys both faster updates and finer positioning.

### Signal level

The SPT page specifies a PWM signal level of 3.3–5.0 V. The PCA9685 runs from the XIAO's 3.3 V regulator, so its pulses are exactly 3.3 V high: in spec, but with no margin. `docs/verification/electronics.md` flags this check as "pass, no margin". If a servo jitters, measure the XIAO 3V3 rail first.

## Torque, speed and current

| Specification (SPT spec page) | 4.8 V | 6.0 V |
|---|---|---|
| Stall torque | 29 kg·cm | 35 kg·cm |
| Speed (no load) | 0.16 s / 60° | 0.14 s / 60° |
| Rated current | | 1.4 A |
| Stall (blocking) current | | 3.5 A |

### Stall torque in SI units

Hobby servos quote torque in kg·cm: the weight of a mass in kilograms hanging from an arm in centimetres. Torque is force times lever arm, $\tau = F r$, and the force of 1 kg is its weight $m g$, so

$$
1\,\mathrm{kg\,cm} = 1\,\mathrm{kg} \times 9.81\,\mathrm{m/s^2} \times 0.01\,\mathrm{m} = 0.0981\,\mathrm{N\,m}
$$

$$
35\,\mathrm{kg\,cm} \times 0.0981\,\frac{\mathrm{N\,m}}{\mathrm{kg\,cm}} = 3.43\,\mathrm{N\,m}
$$

**Stall torque** is the most the servo can push when it is not moving at all. It is a limit, not a working point. In MuJoCo the standing knee needs about **0.7 N·m**, roughly a fifth of stall (`docs/electronics.md`). That margin is what lets the robot trot, recover from a stumble and carry its 3.07 kg (`docs/design.md`).

### Current follows torque

A DC motor's torque is proportional to its current, $\tau_\mathrm{m} = k_\mathrm{t}\, I$, with the motor's torque constant $k_\mathrm{t}$; the gearbox multiplies the motor torque by its ratio. So the current rises roughly in proportion to the torque the servo delivers, and at full stall torque the SPT5435LV draws its **stall current**, 3.5 A. This is why the power design counts stalls:

$$
6 \times 3.5\,\mathrm{A} = 21\,\mathrm{A} > 15\,\mathrm{A}\ \text{(UBEC peak rating)}, \qquad 12 \times 3.5\,\mathrm{A} = 42\,\mathrm{A}\ \text{total}
$$

A servo pushing into a hard stop, or fighting another leg, sits at stall current and heats up fast. Two rules in the docs follow from this:

- **Never** insert the arming key while position commands are running: all twelve servos would jump at once.
- **Never** command all legs into hard stops.

The firmware also limits joint speed to **6 rad/s** (`max_joint_speed_rad_s` in `safety.h`), below the servo's no-load speed at 6 V, $\omega_0 = 60^\circ / 0.14\,\mathrm{s} = (\pi/3)\,\mathrm{rad} / 0.14\,\mathrm{s} \approx 7.5\,\mathrm{rad/s}$. Sudden steps would otherwise pull bursts of near-stall current. A DC motor's torque falls roughly linearly from stall at zero speed to zero at $\omega_0$, $\tau(\omega) \approx \tau_\mathrm{stall}(1 - \omega/\omega_0)$; see [statics and dynamics](../theory/statics-and-dynamics.md).

## The 6 V servo rail

The SPT5435LV is rated **4.8–6.0 V only**. The 2S LiPo swings from 8.4 V (full) to 6.4 V (cut-off), which is always above that range. A connection straight to the pack would over-volt every servo. Two Hobbywing UBEC-10A regulators therefore step the pack down to 6.0 V:

- The UBEC's **output jumper stays open**: that selects 6.0 V. The 7.4 V setting would destroy the servos.
- Measure every UBEC unloaded before connecting servos and accept only **5.8–6.0 V** ([electronics › wiring harness](../../electronics.md#wiring-harness), step 2).
- Under load near an empty pack, the rail is expected to sag to about **5.4 V** (estimate in `hardware/electronics.yaml`). The servo is still in range but weaker: torque falls roughly with voltage (29 kg·cm at 4.8 V vs 35 kg·cm at 6 V).

The PCA9685 carries **only the signal**. Servo current flows UBEC → WAGO bus → the servo's red/brown wires, and never through a logic board. The V+ pin on the PCA9685 header stays unused. More detail is in [Power](power.md).

## Horns and the 25T spline

The **horn** couples the servo's output spline to the robot's structure. Strido uses aluminium horns because printed parts bolted to a plastic horn would strip the spline or flex.

| Horn | Qty | Joint | Fixed with |
|---|---|---|---|
| 25T aluminium disc horn | 4 | thigh: femur and femur servo connector, 4 × M3 × 20 | M3 × 8 centre screw |
| 25T aluminium disc horn | 4 | hip: leg module, 2 × M3 × 8 | M3 × 8 centre screw |
| 25T aluminium clamping arm horn | 4 | knee drive crank | M3 × 8 centre screw |

**25T** means 25 teeth on the spline. Each tooth is $360^\circ / 25 = 14.4^\circ$, so the horn can only sit in 14.4° steps. A horn pushed on "one tooth off" is 14.4° wrong, about $14.4^\circ \times 11.1\,\mu\mathrm{s}/^\circ \approx 160\,\mu\mathrm{s}$ of pulse. Horns from another spline standard (for example 24T or 23T) do not fit properly and will strip.

Screws that go from steel into the aluminium horn get one drop of **medium thread locker**: metal-to-metal joints vibrate loose otherwise (`docs/assembly/README.md`).

## Centring and calibration

### Step 1: centre before you fit a horn

Before any horn goes on, every servo is driven to **1500 µs**, its neutral:

```bash
strido-cli --port <usb port> center   # 1500 µs on every channel
```

With the shaft at neutral, each horn goes on at the **assembly reference pose**:

| Joint | Reference at 1500 µs |
|---|---|
| Hip | leg vertical |
| Thigh | femur 45° backwards |
| Knee crank | 35° |

These are the `neutral_hip`, `neutral_thigh` and `neutral_crank` values in the generated geometry (0, 0.785 and 0.611 rad). Because the spline only allows 14.4° steps, pick the tooth that comes closest; the remainder is fixed in software.

### Step 2: trim in firmware

Each joint has a `ServoCalibration` record stored in the ESP32 flash (`Preferences`):

| Field | Meaning |
|---|---|
| `direction` | +1 or −1: mirrored servos on the left and right turn the opposite way for the same joint motion |
| `neutral_us` | pulse that puts the joint at its reference angle (default 1500) |
| `zero_rad` | the reference angle itself |
| `min_us`, `max_us` | hard pulse window |

The firmware converts an actuator angle to a pulse with:

$$
t_\mathrm{p} = t_\mathrm{neutral} + s\, k\, (\theta - \theta_0)
$$

with $t_\mathrm{neutral}$ = `neutral_us`, the sign $s$ = `direction`, $k = 636.6\,\mu\mathrm{s/rad}$ and the reference angle $\theta_0$ = `zero_rad`; the result is clamped to `[min_us, max_us]`.

Worked example: to move a thigh with `direction = +1` from its 45° reference to 60°:

$$
\theta - \theta_0 = 60^\circ - 45^\circ = 15^\circ = 0.262\,\mathrm{rad}
$$

$$
t_\mathrm{p} \approx 1500\,\mu\mathrm{s} + 0.262 \times 636.6\,\mu\mathrm{s} \approx 1500\,\mu\mathrm{s} + 167\,\mu\mathrm{s} = 1667\,\mu\mathrm{s}
$$

`strido-cli calibrate` lets you nudge each `neutral_us` in ±5 µs or ±25 µs steps until the joint sits exactly at its reference, then saves to flash. The robot should be on a stand with its legs free. A half-tooth error (7.2°) is about 80 µs, well within the trim range. Calibration also absorbs small per-chip differences in the PCA9685 clock, which scale every pulse.

::: danger Raw pulses bypass joint limits
`strido-cli center` and `pulse` send raw pulse widths. They skip the joint and knee-crank limits from the CAD range-of-motion sweep. Use them only while horns are off or the legs are free to move.
:::

## Check yourself

1. Why can the robot not report the true angle of a joint?
2. What pulse width does the firmware send for a joint 10° past its reference, with `direction = −1` and `neutral_us = 1500`?
3. Why is the servo rail regulated to 6.0 V instead of taken straight from the 7.4 V pack?
4. A horn ends up visibly crooked even after centring. How big can the error be before you should move it one tooth?
5. Why does each UBEC carry a stall warning in `docs/verification/electronics.md`?

<details>
<summary>Answers</summary>

1. The position feedback (potentiometer) is used only inside the servo. Nothing reads it back, so the firmware reports the angles it commanded.
2. $10^\circ = 0.1745\,\mathrm{rad}$; $0.1745 \times 636.6\,\mu\mathrm{s} \approx 111\,\mu\mathrm{s}$; with direction $-1$ the pulse is $1500 - 111 \approx 1389\,\mu\mathrm{s}$.
3. The SPT5435LV is rated 4.8–6.0 V only; the pack is 6.4–8.4 V in use and would over-volt it.
4. Up to half a tooth, 7.2° (≈ 80 µs), is a job for `strido-cli calibrate`. Beyond that, move the horn one tooth (14.4°).
5. Six stalled servos draw $6 \times 3.5\,\mathrm{A} = 21\,\mathrm{A}$, above the UBEC's 15 A peak rating.

</details>

## Further reading

- [SPT5435LV-180W specification (SPT Servo)](http://www.spt-servo.com/Product/015234339.html)
- [PCA9685 datasheet (NXP, Adafruit mirror)](https://cdn-shop.adafruit.com/datasheets/PCA9685.pdf)
- [Adafruit 16-channel PWM/servo driver guide](https://learn.adafruit.com/16-channel-pwm-servo-driver)
- [Servo spline reference (ServoCity)](https://www.servocity.com/servo-spline-info/)
- Related pages: [Power](power.md), [Microcontrollers](microcontrollers.md), [Mechanics](mechanics.md), [Electronics, wiring and power](../../electronics.md)
- Theory: [Control](../theory/control.md) (the PD loop inside the servo), [Statics and dynamics](../theory/statics-and-dynamics.md) (joint torques)
