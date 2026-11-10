# Control

Control theory is about making a system do what you command, despite loads, noise and modelling errors, by measuring what it actually does and correcting for the difference. This page covers open and closed loop, PID and PD control, transfer functions and step responses, sampling rates, the hobby servo's internal loop, and compliance, using the Strido servos and its MuJoCo model as examples.

::: tip In Strido
- **Rates:** the firmware runs a $200\,\mathrm{Hz}$ control and IMU loop (`kControlPeriodUs = 5000`) and refreshes the servos at $200\,\mathrm{Hz}$ (`kServoFrequencyHz`; the SPT5435LV accepts up to $330\,\mathrm{Hz}$). It streams state to the host at $100\,\mathrm{Hz}$ (all in `firmware/strido_esp32s3/src/board_config.h`). The joint command stream is $100\,\mathrm{Hz}$ (`strido_sim/walk.py`) and the learned policy runs at $50\,\mathrm{Hz}$ (`strido/policy.py`).
- **Servo model in simulation:** MuJoCo position actuators with `kp="25" kv="0.4" forcerange="-3.432 3.432"`, plus joint `damping="0.25" armature="0.012" frictionloss="0.05"` (`models/mujoco/strido.xml`).
- **Hardware:** 12 SPT5435LV-180W position servos driven by a PCA9685 PWM board ([servos](../hardware/servos.md), [firmware](../software/firmware.md)).
:::

## Open loop and closed loop

**Open loop** applies a precomputed input and never checks the result. A trot gait that replays foot trajectories through inverse kinematics is open loop with respect to the body: if the robot slips, the gait does not notice.

**Closed loop** (feedback) measures the output $y$, compares it with the reference $r$, and acts on the error $e = r - y$. Feedback rejects disturbances and hides modelling errors. The price is stability problems if the gain is too high or the delay too long.

Strido stacks several loops, each faster than the one above it:

```mermaid
graph LR
  P[policy / gait<br/>50–100 Hz] -->|joint targets| F[ESP32 loop<br/>200 Hz, slew limit, linkage]
  F -->|PWM pulse, 200 Hz frames| S[servo's internal<br/>position loop]
  S --> J[joint]
  IMU[IMU 200 Hz] -->|gravity, gyro| P
```

The servos give no position feedback to the host (`strido_sim/rl/env.py`). So the only joint-level loop closes *inside* each servo. The policy closes the body-level loop through the IMU.

## PID control

The classic controller combines three terms:

$$
u(t) = K_p\,e(t) + K_i \int_0^t e(\tau)\,\mathrm{d}\tau + K_d\,\dot e(t)
$$

- **P** pushes in proportion to the error, like a spring.
- **I** accumulates past error and removes steady-state offsets, at the cost of overshoot and wind-up.
- **D** opposes the rate of change, like a damper. In practice it acts on $-\dot y$ instead of $\dot e$, which avoids a kick when the reference jumps.

For joints, the usual choice is **PD** with the target velocity set to zero:

$$
\tau = k_p\,(q^\ast - q) - k_v\,\dot q
$$

This is exactly MuJoCo's `<position kp kv>` actuator. It is then clipped to the force range, $\lvert\tau\rvert \le 3.432\,\mathrm{N\,m}$, the servo's stall torque.

## Transfer functions and the step response

Model one joint as an inertia $I$ with viscous damping $b$. In the Laplace domain, $I s^2 Q = T - b s Q$. With PD control the closed loop from target to angle is:

$$
\frac{Q(s)}{Q^\ast(s)} = \frac{k_p}{I s^2 + (b + k_v)s + k_p}
= \frac{\omega_n^2}{s^2 + 2\zeta\omega_n s + \omega_n^2},
\qquad
\omega_n = \sqrt{\frac{k_p}{I}},\quad
\zeta = \frac{b + k_v}{2\sqrt{k_p I}}
$$

This standard second-order system explains most of what you see in a step response:

- $\omega_n$ sets the speed. Rise time $\approx 1.8/\omega_n$, and bandwidth $\approx \omega_n$ for $\zeta$ near $0.7$.
- $\zeta$ sets the shape. Below 1 the response overshoots and rings. The overshoot is $\exp(-\pi\zeta/\sqrt{1-\zeta^2})$. Above 1 it is sluggish but monotone.
- Raising $k_p$ speeds the response up but lowers $\zeta$, so you raise $k_v$ with it.
- The static stiffness is $k_p$: a constant load $\tau_L$ leaves an error of $\tau_L/k_p$. Only an integral term removes it.

### Worked example: the MuJoCo knee

From `models/mujoco/strido.xml`: $k_p = 25\,\mathrm{N\,m/rad}$, $k_v = 0.4\,\mathrm{N\,m\,s/rad}$, joint damping $b = 0.25$, armature $0.012\,\mathrm{kg\,m^2}$. The calf adds $m r_c^2 \approx 0.0521 \cdot 0.048^2 = 1.2\times10^{-4}\,\mathrm{kg\,m^2}$ plus its own $1.5\times10^{-4}\,\mathrm{kg\,m^2}$ about its centre of mass (`mass_report.yaml`), so $I \approx 0.0123\,\mathrm{kg\,m^2}$ for a swinging calf (the armature dominates). Then:

$$
\omega_n = \sqrt{\frac{25}{0.0121}} = 45\,\mathrm{rad/s}\ (7.2\,\mathrm{Hz}),
\qquad
\zeta = \frac{0.25 + 0.4}{2\sqrt{25 \cdot 0.0121}} = 0.59
$$

That predicts a rise time of about $40\,\mathrm{ms}$ and roughly $10\,\%$ overshoot. These are estimates: they ignore friction loss, the torque clamp and the other links.

In the stand the knee carries $0.70\,\mathrm{N\,m}$ (see [statics and dynamics](statics-and-dynamics.md)), so the model sags by:

$$
\Delta q = \frac{0.70}{25} = 0.028\,\mathrm{rad} \approx 1.6^\circ
$$

The policy can learn to command slightly past the target to cancel this. Because the RL environment randomises the servo stiffness each episode (`env.py`), the policy cannot rely on one exact value.

## Sampling, delay and bandwidth

Digital controllers sample. The Nyquist limit says you need more than two samples per period of the fastest signal you care about. For good control, the rule of thumb is a loop **10–20 times faster** than the closed-loop bandwidth. Delay matters just as much: a pure delay $T_d$ adds phase lag $\varphi = \omega T_d$, which eats the phase margin and eventually destabilises a high-gain loop.

For Strido:

| Loop | Rate | Period / worst-case added delay |
|---|---|---|
| Policy | $50\,\mathrm{Hz}$ | $20\,\mathrm{ms}$ |
| Joint command stream | $100\,\mathrm{Hz}$ | $10\,\mathrm{ms}$ |
| ESP32 control + IMU | $200\,\mathrm{Hz}$ | $5\,\mathrm{ms}$ |
| Servo PWM frame | $200\,\mathrm{Hz}$ (max $330\,\mathrm{Hz}$) | $5\,\mathrm{ms}$ ($3.0\,\mathrm{ms}$) |
| MuJoCo physics | $500\,\mathrm{Hz}$ | $2\,\mathrm{ms}$ |

A classic analogue servo takes a new pulse only every $20\,\mathrm{ms}$ ($50\,\mathrm{Hz}$). At the $7.2\,\mathrm{Hz}$ joint bandwidth estimated above, that much delay alone costs $\omega T_d = 45 \cdot 0.02 = 0.9\,\mathrm{rad} \approx 52^\circ$ of phase. At $200\,\mathrm{Hz}$ it is $13^\circ$. That is presumably why the firmware runs the PCA9685 at $200\,\mathrm{Hz}$. The $50\,\mathrm{Hz}$ policy is fine because it only shapes the gait, whose cycle is $0.4\,\mathrm{s}$ ($2.5\,\mathrm{Hz}$, `GAIT_PERIOD_S` in `strido/policy.py`). That gives 20 policy steps per cycle, while the fast loops below it do the stiff work.

## The hobby servo's internal loop

A hobby servo is a small closed-loop system in a box: a DC motor, a gearbox, a potentiometer on the output and a controller chip. The pulse width encodes the target angle. The chip compares it with the pot reading and drives the motor with roughly proportional (often PD-like) control, saturating at the stall torque. You can neither read its position nor tune its gains. Externally it behaves like a stiff PD joint with a torque limit, a speed limit (no-load $0.14\,\mathrm{s}/60^\circ$ at $6\,\mathrm{V}$, about $7.5\,\mathrm{rad/s}$) and some deadband. That is the abstraction MuJoCo's position actuator models. The firmware adds a $6\,\mathrm{rad/s}$ slew limit on top (`MAX_JOINT_SPEED_RAD_S`), so that sudden steps do not pull near-stall current.

## Impedance and compliance

A position controller with gains $k_p$ and $k_v$ makes the joint behave like a **spring and damper** towards the target:

$$
\tau_{\text{ext}} = k_p\,\Delta q + k_v\,\dot q
$$

Mapped to the foot through $\boldsymbol{\tau} = \mathbf{J}^\top\mathbf{F}$ and $\delta\mathbf{p} = \mathbf{J}\,\delta\mathbf{q}$, the foot's Cartesian stiffness is:

$$
\mathbf{K}_x = \mathbf{J}^{-\top}\,\mathbf{K}_q\,\mathbf{J}^{-1}
$$

**Impedance control** chooses this stiffness on purpose. A legged robot wants its feet *compliant* when they touch down, so impacts are absorbed and small terrain errors do not jolt the body, and stiff during stance. Robots with torque-controlled motors (the MIT Cheetah, for example) set $\mathbf{K}_x$ in software. A hobby servo is stiff and fixed, so on Strido compliance comes from lower commanded speed, the slew limit, the foot pads, and a policy trained with randomised stiffness.

## Check yourself

1. Why does a PD-controlled joint carrying a constant load not reach its target exactly?
2. If you double $k_p$ and keep $k_v$, what happens to $\omega_n$ and $\zeta$?
3. Why would a $50\,\mathrm{Hz}$ servo frame hurt more than a $50\,\mathrm{Hz}$ policy?
4. Where is the only joint-position feedback loop on the real robot?

<details><summary>Answers</summary>

1. At steady state the P term must supply the load torque, so $e = \tau_L/k_p \neq 0$. Only an integral term removes it.
2. $\omega_n$ grows by $\sqrt{2}$. $\zeta$ shrinks by $\sqrt{2}$, so there is more overshoot.
3. The frame delay sits inside the fast, stiff joint loop, whose bandwidth is several hertz. The policy shapes slower body motion (the $2.5\,\mathrm{Hz}$ gait cycle) and relies on the joint loops beneath it.
4. Inside each servo, between its potentiometer and its controller chip. The host and the ESP32 never see the joint angle.

</details>

## Further reading

- K. J. Åström and R. M. Murray, *Feedback Systems: An Introduction for Scientists and Engineers*, 2nd ed., Princeton University Press, 2021. [Free online](https://fbswiki.org)
- K. M. Lynch and F. C. Park, *Modern Robotics*, Cambridge University Press, 2017, ch. 11 (robot control, including impedance control).
- N. Hogan, "Impedance Control: An Approach to Manipulation", *ASME J. Dynamic Systems, Measurement, and Control*, 107(1), 1985.
- [MuJoCo documentation: actuators](https://mujoco.readthedocs.io/en/stable/XMLreference.html#actuator).
- [Servos](../hardware/servos.md) and [firmware](../software/firmware.md) in this wiki.
