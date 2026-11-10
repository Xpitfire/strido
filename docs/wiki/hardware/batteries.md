# Batteries: the 2S LiPo

Strido runs from one 2S lithium-polymer (LiPo) pack: 7.4 V nominal, 5000 mAh, about 37 Wh. LiPo stores a lot of energy for its weight and can deliver large currents, but it is also the one part of the robot that can start a fire. This page explains the numbers on the label and the habits that keep the pack healthy and safe.

::: tip In Strido
- **Part:** LiPo 2S 5000 mAh hardcase with XT60, max 138 × 47 × 25 mm (Gens ace G-Tech class), BOM line `lipo_2s_5000`.
- **Accessories:** balance charger with AC input (B6AC class, `charger`), LiPo safety bag (`lipo_bag`), LiPo cell checker / low-voltage alarm (`lipo_checker`).
- **Data:** `hardware/electronics.yaml` → `power.pack` (7.4 V nominal, 8.4 V full, 6.4 V empty, 5000 mAh) and `rails.pack` (6.0–8.4 V).
- **Firmware:** low-battery warning at 6.8 V, servo cut-off at 6.4 V (`firmware/strido_esp32s3/lib/strido_core/include/strido/safety.h`), measured by the INA260.
- **ROS 2:** `/battery_state` (pack voltage and logic-branch current).
:::

## Cells and the "2S" label

A LiPo **cell** is one lithium-ion pouch. Its voltage depends on its state of charge:

| Cell state | Voltage per cell | 2S pack |
|---|---|---|
| Full (end of charge) | 4.20 V | 8.4 V |
| Nominal (label value) | 3.70 V | 7.4 V |
| Strido warning | 3.40 V | 6.8 V |
| Strido servo cut-off | 3.20 V | 6.4 V |
| Lowest rail value the logic branch is checked for | 3.00 V | 6.0 V |

**2S** means two cells in **s**eries: the voltages add, and the capacity stays that of one cell. (A "2S2P" pack would have two parallel pairs, doubling capacity.) Two cells were chosen because:

- 2S (6.4–8.4 V in use) sits just above the 6.0 V servo rail, so the UBECs only need to step down a little.
- 2S is the common RC-car pack, so packs, chargers and XT60 leads are cheap and easy to find.

## Capacity and energy

**Capacity** (mAh) is charge $Q$: 5000 mAh means the pack can deliver 5 A for one hour, or 1 A for five hours, before it is empty. Charge is current integrated over time, $Q = \int I\,\mathrm{d}t$, so at constant current $Q = I\,t$. **Energy** (Wh) also accounts for voltage. Electrical power is $P = V I$; integrating it over the discharge gives the energy, and if the voltage stays close to its nominal value this reduces to

$$
E = \int V I\,\mathrm{d}t \approx V_\mathrm{nom}\, Q = 7.4\,\mathrm{V} \times 5.0\,\mathrm{Ah} = 37\,\mathrm{Wh}
$$

(1 Wh = 3600 J, so this is about 133 kJ.) The nominal voltage is used because a LiPo's voltage falls gently from 4.2 V to about 3.2 V per cell over most of the discharge; 3.7 V per cell is a good average.

Energy is the number that predicts runtime. `docs/electronics.md` estimates about 60 W drawn from the pack while trotting (12 servos ≈ 50 W, plus Pi, LiDAR and the rest, through 90 %-efficient converters). With a usable fraction $\eta_\mathrm{use} = 0.8$ of the stored energy:

$$
E_\mathrm{usable} \approx 37\,\mathrm{Wh} \times 0.8 = 29.6\,\mathrm{Wh}
$$

$$
t_\mathrm{run} = \frac{E_\mathrm{usable}}{P} \approx \frac{29.6\,\mathrm{Wh}}{60\,\mathrm{W}} \approx 0.5\,\mathrm{h} \approx 30\,\mathrm{min}\ \text{trotting}
$$

Standing draws less, so the doc estimates about 45 min. The 80 % factor is there because the firmware stops the servos well before the cells are truly empty. Both runtimes are marked [ESTIMATE]: measure your own with `/battery_state` and a clamp meter.

37 Wh is also below the 100 Wh limit above which shipping a LiPo needs a surcharge (`docs/bom/sources.md`).

## C-rating: how fast the pack can deliver

The **C-rating** expresses current as a multiple of capacity. With $Q$ in ampere-hours, a rate of $C$ means the current

$$
I = C \cdot \frac{Q}{1\,\mathrm{h}}
$$

so 1C on a 5000 mAh pack is $5\,\mathrm{A}$, and 60C is $60 \times 5\,\mathrm{A} = 300\,\mathrm{A}$ (the Gens ace pack's continuous rating; 100C gives $500\,\mathrm{A}$ burst). Equivalently, a pack discharged at $n$C empties in $1/n$ hours.

`hardware/electronics.yaml` records a `max_discharge_a` of 300 A for this pack (60C continuous, Gens ace GEA502S60X6HGT). The robot's worst-case pack current is about 23.6 A (servo and logic branches, `docs/verification/electronics.md`), so the pack works at under a tenth of its rating.

Why buy far more C than you need? Every cell behaves roughly like an ideal voltage source $V_\mathrm{oc}$ (the open-circuit voltage) in series with an **internal resistance** $R_\mathrm{int}$. By Ohm's law the terminal voltage under load is

$$
V_\mathrm{term} = V_\mathrm{oc} - I\,R_\mathrm{int}
$$

and the pack also turns $P_\mathrm{loss} = I^2 R_\mathrm{int}$ into heat. A pack with a higher genuine C-rating usually has a lower internal resistance, so it **sags** less when twelve servos pull a current peak together. As an illustration (not a measured value), a pack with $R_\mathrm{int} = 10\,\mathrm{m\Omega}$ at the robot's worst-case $23.6\,\mathrm{A}$ would sag by $0.24\,\mathrm{V}$ and dissipate $5.6\,\mathrm{W}$. Less sag means fewer false low-battery readings and more voltage headroom for the UBECs. Cheap packs often overstate their C-rating, which is why `docs/bom/sources.md` lists the LiPo among the parts where the brand matters (hardcase, real C rating).

### Load sag and the cut-off filter

Sag is also why the firmware does **not** cut off on a single low reading. The INA260 is read every 100 ms. The servos only relax after **5 consecutive readings below 6.4 V** (0.5 s), so a short current spike in mid-step does not drop the robot. A pack that really is empty stays low and trips the cut-off.

## Charging: always a balance charger

LiPo cells charge with **constant current, then constant voltage** (CC/CV): the charger pushes a set current until the cell reaches 4.20 V, then holds 4.20 V while the current tapers. Going above 4.20 V per cell damages the cell and can make it unstable.

In a series pack the charger only sees the total voltage, and the two cells are never exactly equal. One cell could reach 4.30 V while the other is still at 4.10 V, and the total would still read 8.4 V. The **balance lead**, the small extra plug with one wire per cell junction, lets a **balance charger** measure each cell and bleed off the higher one. Strido's B6AC-class charger does this.

Rules of thumb (see Battery University in Further reading):

- Charge at **1C or less**: 5 A for this pack.
- Always plug in the balance lead and select the LiPo program with the right cell count (2S).
- Charge **inside the LiPo bag**, on a non-flammable surface, and **never leave it unattended** (`docs/electronics.md`, safety rules).
- Let a warm pack cool down before charging it.

## Storage voltage

A LiPo ages fastest when it sits **full** (4.20 V per cell), and it is damaged if it sits **empty**. For storage longer than a few days, bring each cell to about **3.80–3.85 V** (about 7.6–7.7 V for the pack). Most balance chargers, including the B6AC class, have a *storage* program that charges or discharges to this level automatically.

## The LiPo checker

The cell checker plugs into the balance lead and shows each cell's voltage and the total. Use it:

- **Before a run:** both cells near 4.2 V and within a few hundredths of a volt of each other.
- **After a run:** cells still at or above about 3.2 V and still balanced.
- **Before storage:** cells at storage voltage.

A cell that drifts away from its partner run after run is the first sign of a failing pack. In alarm mode the checker beeps when any cell drops below a threshold. That adds a second, independent warning on top of the firmware's.

## Safe handling

::: danger LiPo fire risk
A damaged, over-charged or over-discharged LiPo can vent and burn violently. A LiPo fire cannot be put out by smothering it.
:::

- **Inspect the pack.** A hardcase helps, but check for swelling ("puffing"), dents, cut wires or a hot pack after use. Retire any puffed pack.
- **Never short the leads.** The pack can deliver hundreds of amps. That is also why the arming loop key must never fit the battery's own XT60. See [Power](power.md) for the contact rule.
- **Fuse close to the pack.** The 25 A main fuse protects the 14 AWG trunk right after the battery input.
- **Unplug after use.** Even with the logic switched off, the robot stays connected to the pack through its wiring. Disconnect the battery when you finish.
- **Transport and store** the pack in the LiPo bag, at storage voltage, away from heat.
- **Dispose properly:** discharge fully with a charger's discharge program, then take it to a battery collection point.

## Check yourself

1. What is the pack voltage of a 2S LiPo at 3.4 V per cell, and what does the firmware do there?
2. How much current is 2C for this pack?
3. Why does a balance charger need the balance lead if it already measures 8.4 V at the main leads?
4. Why does the firmware wait for five consecutive low readings before it cuts off?
5. You will not use the robot for a month. What should you do with the pack?

<details>
<summary>Answers</summary>

1. 6.8 V; the firmware raises the low-battery warning.
2. $2 \times 5\,\mathrm{A} = 10\,\mathrm{A}$.
3. The total can read 8.4 V while one cell is over-charged and the other under-charged; only per-cell measurement shows and corrects that.
4. Current peaks make the voltage sag briefly. Requiring 0.5 s below 6.4 V ignores spikes and reacts only to a truly empty pack.
5. Bring it to storage voltage (about 3.80–3.85 V per cell) with the charger's storage program and keep it in the LiPo bag.

</details>

## Further reading

- [BU-409: Charging Lithium-ion (Battery University)](https://batteryuniversity.com/article/bu-409-charging-lithium-ion)
- [BU-808: How to prolong lithium-based batteries (Battery University)](https://batteryuniversity.com/article/bu-808-how-to-prolong-lithium-based-batteries)
- [TI INA260 datasheet](https://www.ti.com/lit/ds/symlink/ina260.pdf): the sensor that measures the pack voltage
- Related pages: [Power](power.md), [Safety](../making/safety.md), [Electronics, wiring and power](../../electronics.md)
