# Tools and workshop

Building Strido needs a small set of hand tools, a soldering iron, a Dupont crimp tool and a multimeter, plus a 3D printer. This page lists them, explains the electrical techniques the harness uses (soldering, crimping, lever clamps, heat-shrinking) and the multimeter checks that catch wiring mistakes before they cost a board.

::: tip In Strido
The tools are listed in the BOM under [Tools (not in the totals)](../../bom/README.md#tools-not-in-the-totals) and in section E (*Tools and consumables*) of the catalogue and assembly book ([catalogue](../../catalog.md)). The harness steps and voltage checks are in [electronics.md](../../electronics.md#wiring-harness); assembly Step 0 lists the tools per task ([assembly manual](../../assembly/README.md)).
:::

## The tool list

From the catalogue's section E (what each tool is for) and the BOM's tool table (example products):

| Tool | Used for in Strido | Example in the BOM |
|---|---|---|
| Hex keys 1.5 / 2.0 / 2.5 mm | M2 / M2.5 / M3 socket heads | Wera 950/9 Hex-Plus set |
| Nut drivers 4.0 / 5.0 / 5.5 mm | holding M2 / M2.5 / M3 nuts | not priced |
| Drills 2.2 / 2.7 / 3.2 mm (hand or pin vice) | chasing the tight holes listed in the [fit report](../../verification/fits.md) | — |
| Flush cutters, deburring tool | removing supports and brims | Wiha 26812 |
| Soldering iron, solder, heat-shrink | power entry, XT60 connectors, splices, XIAO pins, PCA9685 OE pull-up | Miniware TS101; solder (`solder`) and the heat-shrink assortment are in the BOM |
| Wire stripper | stripping 14–22 AWG silicone wire | Jokari Super 4 plus |
| Dupont crimp tool, contacts + housings | Pi 5 V feed (W12), W17/W20 at the PCA9685, the 12 re-crimped servo signal wires | DxCRIMP set; contacts and housings: `dupont_crimp_contacts` (610-piece kit) in the BOM |
| Spiral wrap, cable ties, adhesive tie mounts | dressing the harness: wrap on every bundle of three or more cables, ties at the marked points, two 13 × 13 mm mounts on the deck side strips | in the BOM (`spiral_wrap`, `cable_ties` bag of 100, `cable_tie_mounts`) |
| Multimeter | 6.0 V UBEC check, 5 V rail, OE voltage | Kaiweets |
| Calipers | measuring printed holes, bearings, screw lengths | — |
| Medium thread locker | screws into metal horns only (never into printed holes) | in the BOM (fasteners) |
| Thin CA glue (liquid) | hardening weak printed pilots (ADR-009 fallback) | any liquid superglue |
| LiPo balance charger + LiPo bag | battery care | in the BOM (power) |
| USB-C cable | flashing the XIAO ESP32-S3 | — |
| 3D printer, ≥ 220 × 220 mm bed | all printed parts (shells are 114 × 208 mm) | e.g. Bambu Lab A1 Combo |

Why a pin vice and not a power drill for chasing holes? You only want to remove the 0.1–0.2 mm of plastic that printing added; a power drill heats PETG, grabs and can crack a thin boss.

## Workspace set-up

- **A flat, non-flammable surface** for soldering and charging, with nothing flammable within reach of the iron or the LiPo bag.
- **Good light and a magnifier** for the 2.54 mm Dupont pins and the small Adafruit boards.
- **Parts trays** per assembly step: the manual's parts boxes list exactly which screws each step uses, so sort them first.
- **Ventilation** while soldering (flux fumes) and while printing.
- **An anti-static habit**: touch a grounded metal object before handling the Pi, XIAO, IMU or PCA9685, and hold boards by their edges (see [safety](safety.md)).
- **A bench supply option**: the BOM's recommended Raspberry Pi 27 W USB-C supply powers the Pi alone for software work, so the LiPo is not needed at the desk.

## Soldering

Soldering joins two metals with a lower-melting alloy. A good joint is made by heating **both parts** with the iron and feeding solder into the joint, not onto the iron tip.

Where you solder on this robot:

| Joint | Wire | Notes |
|---|---|---|
| Battery input XT60H: W01 (+) and W04 (−) | 14 AWG | Large contacts need a hot, broad tip; pre-tin both cup and wire |
| Arming jack XT60H: W02/arming on contact 1, W03 on contact 2; the loop key's bridge | 14 AWG | the loop key bridges the jack's two contacts; check its contact type first (multimeter table below) |
| Main fuse holder leads: W01 in, W02 out | 14 AWG | heat-shrink each joint |
| Back-shell splice: W02, W02/arming and the logic fuse holder's own lead | 14 AWG | heat-shrunk splice; the holder's 14 AWG lead is the logic tap (no thinner wire behind the 25 A fuse) |
| Splice under the deck: W03 → both UBEC IN+ | 14 AWG | heat-shrunk splice |
| Ground star W04 beside the battery input | 14 AWG to both UBEC IN−, 18 AWG to the switch GND | one star point; heat-shrink it |
| UBEC outputs W05 / W06 | 18 AWG pair | extends each UBEC's output lead |
| Logic fuse out (W09), regulator in and out (W11, W24 ground, W12) | 18 / 22 AWG | the switch and INA260 ends of W09–W11 and W24 are screw terminals |
| Button pair W13 | 22 AWG | heat-shrink each joint |
| XIAO pins: W17 (3V3, GND, SDA, SCL), W20 (D3), W21 (display cable's Dupont ends) | 22 AWG / display cable | no room for Dupont housings 9 mm under the upper shoulder frame. Two wires share the XIAO 3V3 pin and two the GND pin (W17 and W21): solder both to the pin |
| 2.2 kΩ OE pull-up | resistor leads | on the PCA9685 header, from OE to VCC; solder it before the board is mounted (Step 7) |

Technique, in order:

1. Cut the wire to its length from the cut list in the [wiring check](../../verification/wiring.md), strip just enough to fill the cup or joint (the cut list allows 6 mm per soldered end), twist the strands.
2. **Slide the heat-shrink onto the wire first.** It cannot go on after the connector is soldered.
3. Tin the wire and the contact separately, then join them and reheat until the solder flows into both.
4. Hold still until the solder sets: a moved joint looks dull and grainy and is weak ("cold joint").
5. Inspect: a good joint is smooth and shiny (lead-free solder is slightly duller) with the strands visible under the solder.

Adafruit's guide suggests roughly 370 °C for leaded and 400 °C for lead-free solder on a temperature-controlled iron; heavy XT60 contacts on 14 AWG need the heat but not a long dwell, or the connector's plastic softens. Mating the XT60 to its counterpart while soldering keeps the contacts aligned.

## Crimping Dupont connectors

A crimp joins a wire to a contact by deforming metal around it, cold. The Dupont crimp tool shapes two pairs of wings: the front pair bites the bare conductor, the rear pair grips the insulation for strain relief. The finished contact clicks into a plastic housing that plugs onto a 2.54 mm header pin.

Crimps in Strido:

- **W12:** the 5 V feed from the D36V50F5 regulator to Raspberry Pi header pins 2 and 4 (5 V) and 6 and 14 (GND), 22 AWG, one wire per pin, because each pin carries about 1.6 A. Thick silicone insulation may not fit the insulation wings; trim it or use thin-wall wire.
- **W17 and W20 at the PCA9685:** the I²C wires (3V3, GND, SDA, SCL) and the OE wire, soldered at the XIAO end, crimped onto the PCA9685's left header.
- **The 12 servo signal wires:** each servo's own lead runs to a tie, where the red and brown wires are peeled off for the WAGO bus. The orange signal wire is **cut to length** and **re-crimped** with a female Dupont contact in a **1-pin housing**, which plugs onto the PWM pin of its PCA9685 channel. There are no servo extensions: every plug-and-socket pair you leave out is one less contact to work loose in a walking robot ([cable management](cable-management.md)). Cut the orange wire so it reaches its channel without strain; the front knee leads have only 12 mm to spare.

Crimp rather than solder at these ends: a crimp leaves the strands flexible right up to the contact, and its insulation grip relieves strain.

Checks for every crimp:

- Pull test: a firm tug must not pull the wire out.
- No strands outside the contact.
- The contact latches in the housing (it should not push out from the front).

## Lever clamps (WAGO)

The servo power bus is made of WAGO 221-415 lever connectors: no tool, but the strip length matters. Strip **11 mm** (WAGO's data sheet), open the lever, push the conductor in until the insulation meets the housing, close the lever and tug. Through the transparent housing you can see the copper reach the end. Each servo's red wire goes into the leg's upper (V+) connector, the brown into the lower (GND), ports hip 1, thigh 2, knee 3; one wire per entry. Wire each WAGO before sliding it into its holder: there is no room to open the levers in place.

## Heat shrink

Heat-shrink tubing shrinks to about half its diameter (a common ratio; check your assortment) when heated, insulating and strain-relieving a joint. Choose a size that slides over the joint before shrinking and fits tightly after. Cover every exposed soldered joint in the power path. Use a hot-air tool or the side of the iron shaft rather than a flame near a LiPo.

## Multimeter checks

A multimeter is the cheapest insurance in the build. The harness steps prescribe these measurements:

| When | Where | Expected | If not |
|---|---|---|---|
| Before connecting any servo | each UBEC output, no load | **5.8–6.0 V** | the servo is rated up to 6.0 V: return a unit that reads higher; check the jumper is open (no 7.4 V setting) |
| Before plugging into the Pi | Dupont ends of W12, fuses in, button pressed | **4.8–5.2 V** (D36V50F5: 5 V ± 4 %) | do not plug in; check polarity and the regulator |
| Smoke test | PCA9685 OE while the XIAO is in its bootloader (hold BOOT, press RESET) | **≥ 2.4 V** (outputs off) | the 2.2 kΩ pull-up is missing or not on VCC |
| Before first power-up (good practice) | resistance between + and − at the battery input, no pack connected | not near 0 Ω | a short: find it before connecting the battery |
| Before bridging the loop key | try the *unbridged* key housing on the pack connector | must **not** fit | wrong contact type: see the XT60 rule in [electronics.md](../../electronics.md#xt60-contact-rule-the-loop-key-must-never-fit-the-battery) |

Measure voltage with the black probe on ground (COM) and the red probe on the point; set the meter to DC volts in a range above 8.4 V (the full 2S pack). Continuity mode (beep) is handy for checking that a wire goes where the wiring list says.

## Check yourself

1. Why must heat-shrink go onto the wire before soldering the XT60?
2. Which three hex key sizes do you need, and why exactly these?
3. What does the rear pair of wings on a Dupont crimp do?
4. What voltage must a UBEC show before any servo is connected, and why does a higher reading disqualify it?
5. Why chase tight holes with a pin vice rather than a power drill?
6. Why is each servo's orange signal wire cut and re-crimped instead of plugged in with an extension lead?

<details>
<summary>Answers</summary>

1. Once the connector is soldered on, the tubing cannot be slid over it.
2. 1.5, 2.0 and 2.5 mm: the socket sizes of the M2, M2.5 and M3 socket head screws.
3. It grips the insulation for strain relief; the front pair grips the conductor.
4. 5.8–6.0 V unloaded. The SPT5435LV is rated for 4.8–6.0 V only, so anything above 6.0 V over-stresses the servos.
5. Only 0.1–0.2 mm needs removing; a power drill heats and grabs the plastic and can crack thin bosses.
6. An extension adds a plug-and-socket pair per servo that vibration can work loose, plus extra wire to stow. Cut to length, the lead goes straight to its PCA9685 channel with one contact.

</details>

## Further reading

- [Adafruit Guide to Excellent Soldering](https://learn.adafruit.com/adafruit-guide-excellent-soldering)
- [Pololu D36V50F5 step-down regulator](https://www.pololu.com/product/4091)
- [Electronics, wiring and power](../../electronics.md) and the [assembly manual](../../assembly/README.md)
- [WAGO 221-415 data sheet](https://wago.priintcloud.com/datasheets/221-415/en)
- [Molex Quality Crimping Handbook](https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/commercialcrimpbookpdf/638/63800/TM-638000029-001.pdf)
- Related in this wiki: [cable management](cable-management.md), [safety](safety.md), [power](../hardware/power.md), [fasteners](fasteners.md)
