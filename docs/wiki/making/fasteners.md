# Fasteners

Strido is held together by 223 screws in three sizes (M2, M2.5, M3), all with socket heads. This page explains how to read a screw designation, how a screw holds in a printed hole, why the pilot holes are sized as they are, and how tight is tight enough in plastic.

::: tip In Strido
The fastener list is in the BOM ([bom/README.md](../../bom/README.md), sections *Fasteners* and *Fasteners by joint*); each assembly step lists its screws in the parts box ([assembly manual](../../assembly/README.md)). The fit gate (`python -m strido_verify.fits`, report [verification/fits.md](../../verification/fits.md)) checks every screw against the bands in `hardware/verification/tolerances.yaml`. ADR-009 in [decisions.md](../../decisions.md) covers the servo-mount pilots.
:::

## Reading a screw designation

`M3 × 10 DIN 912 A2` means:

| Part | Meaning |
|---|---|
| `M3` | Metric ISO thread, 3 mm nominal (outer) diameter. Coarse pitch unless stated: M2 = 0.4 mm, M2.5 = 0.45 mm, M3 = 0.5 mm per turn |
| `× 10` | Length in mm, measured from under the head to the tip |
| `DIN 912` / `ISO 4762` | Socket head cap screw: cylindrical head with a hex socket. DIN 912 and ISO 4762 are the same shape; the BOM orders DIN 912, the CAD calls them `iso4762_…` |
| `A2` | Stainless steel grade (A2 = 304-type austenitic) |

## The fasteners in this robot

All screws are socket head cap screws. One hex key size per thread:

| Thread | Hex key | Nut (across flats) | Lengths used | Typical use |
|---|---|---|---|---|
| M2 | 1.5 mm | 4.0 mm | 5, 10 mm | LCD bracket, regulator stand-offs, camera PCB |
| M2.5 | 2.0 mm | 5.0 mm | 5, 6 mm | Pi 5 / PCA9685 / INA260 stand-offs, IMU, LiDAR |
| M3 | 2.5 mm | 5.5 mm | 8, 10, 12, 16, 20, 25, 40 mm | everything structural: frames, servos, legs, shells |

The M3 × 10 is by far the most common (86 in the CAD: servo ears, shoulder frames, chassis, knee axles). The longest is the single M3 × 40 camera tilt pivot.

Other fastener types in the BOM:

- **Hex nuts** ISO 4032 / DIN 934 (M2, M2.5, M3): plain nuts, 56 of them M3. Some sit in moulded pockets in the printed part (for example the captive nut in `upper_shoulder_frame`), so you tighten from the screw side only.
- **Nylon-insert lock nuts** DIN 985 M3 (17 in the CAD): a nylon ring grips the thread so the nut does not back off even when it is *not* tight. That is why they are used at moving joints (tibia joints, tibia link pins, camera pivot).
- **Washers** ISO 7089 M3 (16): spread the load under a head or nut at the knee axles, hip pivots and arm pins.
- **Stand-offs**, female-female: brass M2.5 × 6 mm (boards) and M2 × 8 mm (regulator). They lift circuit boards off the deck.

No heat-set inserts are used: every screw ends in a nut, a printed pilot, or a metal thread.

## Three ways a screw ends

The fit report counts how each of the 223 screws terminates:

| Termination | Count | What holds the screw |
|---|---|---|
| Nut | 105 | A hex nut, lock nut or brass stand-off; the printed parts are clamped between head and nut |
| Thread-forming | 78 | The screw cuts its own thread into a printed pilot hole (servo ears, servo brackets, knee axles, crank pins, hip horns, shell bosses) |
| Vendor thread | 40 | A metal thread in a bought part: aluminium horns (femur-to-horn), servo output shafts (centre screws), LCD hex studs, LiDAR body |

A nut joint is the strongest and can be retightened indefinitely. A thread-forming joint is convenient (no nut to hold) but plastic threads wear out if you take the screw out and in many times.

## Thread-forming screws in printed pilots

The BOM's ordinary machine screws are used as thread-forming screws: driven into a hole smaller than the screw, they push plastic aside and form a matching thread. Two numbers decide whether that works.

### Pilot diameter

Guides for thread-forming screws in thermoplastics recommend a pilot of about $0.8\,d$ ($d$ = nominal diameter). Strido grades the **printed** pilot as a ratio of $d$, taking the expected print shrink into account:

$$
\frac{D_\mathrm{printed}}{d} = \frac{D_\mathrm{CAD} - 0.15\,\mathrm{mm}}{d}
$$

| Printed pilot / d | Grade | Why |
|---|---|---|
| < 0.70 | fail | too much material to displace: the boss splits or the screw head strips |
| 0.70 – 0.90 | ok | full grip |
| 0.90 – 0.93 | warn | weak grip: tighten by feel; if a screw spins, harden the pilot with thin CA glue and re-drive |
| > 0.93 | fail | no grip |

For M3 that means a CAD pilot of about 2.25–2.85 mm is ok and 2.85–2.94 mm is a warning. Example: the `femur` M3 pilots are 2.80–2.85 mm in CAD, so they print at about 2.65–2.70 mm, and $2.70\,\mathrm{mm} / 3\,\mathrm{mm} = 0.90$ (range $0.88$–$0.90\,d$): ok.

### Engagement length

Engagement is the length over which the hole is narrower than the screw, i.e. how much thread is formed. Rule: at least $1.5\,d$ is ok ($1.5 \times 3\,\mathrm{mm} = 4.5\,\mathrm{mm}$ for M3), $1.0$–$1.5\,d$ is a warning (do not over-tighten), below $1.0\,d$ fails. The `femur` pilots have 4.0 mm engagement ($4.0 / 3 \approx 1.33\,d$) and the `arming_port_bezel` M2.5 pilots 2.5 mm ($1.0\,d$): both warn, so tighten gently. Why engagement matters (thread shear area grows with engaged length) is worked through in [strength, torque and failure](strength.md).

### ADR-009: the servo-mount pilots

29 screws of the upstream servo-mount family (`left_servo_mount`, `right_servo_mount`, the derived `_fl`/`_fr` variants and `servo_mount_top_bracket`) thread into 2.94–2.97 mm CAD pilots: 0.93–0.94 d after printing, just above the weak-grip band, with 4–12 mm engagement. Upstream Yertle robots are built with exactly these holes, so instead of redesigning them the project records an accepted deviation with a builder action:

1. **Preferred:** print these five parts with **X-Y hole compensation −0.15 mm**, which brings the pilot to about 2.65 mm (see [3D printing](3d-printing.md)).
2. **Otherwise:** before driving each screw, wick a drop of thin CA (cyanoacrylate) glue into the pilot and let it cure; it hardens the hole wall so the screw forms a firmer thread. Check that each screw bites before the joint carries load.

If a mount ever strips a thread, the ADR's fallback is a re-pilot variant with a Ø 2.5 mm hole.

## Threadlocker

Medium-strength (blue) threadlocker is an anaerobic adhesive: it cures in the absence of air between **metal** threads (the metal ions catalyse the cure) and stops vibration from loosening a screw, while still allowing removal with a hand tool. Strido uses it only on **metal-to-metal screws**: the screws into the servo output shafts and the tapped aluminium 25T horns: the horn centre screws, the femur-to-horn M3 × 20, the hip-horn M3 × 8 through the servo mount into the disc horn and the arm-pin M3 × 16 into the knee-drive arm horn. Every step reverses the load on a horn, and metal on metal has no plastic to grip the thread, so these are the screws most likely to work loose.

One drop on the screw thread is enough.

::: warning No threadlocker in printed holes
Henkel's data sheet for Loctite 243 states that it is not normally recommended on plastics, particularly thermoplastics, because stress cracking can result; between a steel screw and plastic it also lacks the metal surfaces it needs to cure. For weak printed pilots use hole compensation or a CA-hardened pilot instead.
:::

## Tightening in plastic

A steel M3 screw can easily produce more clamping force than a printed boss can take. The [strength report](../../verification/strength.md#tightening-torque-into-printed-pilots) gives a torque limit for every printed pilot (0.05–0.35 N·m; the formulas are in [strength, torque and failure](strength.md)). The rules from the assembly manual:

- **Screws into printed pilots (marked self-tapping):** turn until snug, never to full torque. "Snug" means the head has just seated and the parts no longer move; stop there.
- **Through thin parts:** the electronics deck is 3 mm thick in the centre; its screw heads sit in counterbores, so do not over-tighten.
- **Lock nuts at moving joints:** tighten only until the joint has no play; the knee links must swing under their own weight (Step 12). A lock nut holds its position without being tight.
- **Friction joints:** the camera pivot (M3 × 40 with a lock nut) is tightened until the camera holds its angle, 15° down being the reference.
- **Short hex keys:** hold a hex key by its long arm only for loosening; use the short arm (or finger pressure on a screwdriver handle) for tightening into plastic, so you cannot apply much torque by accident.

Signs you went too far: the screw keeps turning without getting tighter (thread stripped), a white stress mark appears around the hole, or a layer line opens up next to the boss.

## Check yourself

1. What do `M2.5 × 6` and `ISO 4762` tell you?
2. An M3 pilot is drawn at 2.80 mm. What will it print at, and what grade does it get?
3. Why do the knee joints use DIN 985 lock nuts rather than plain nuts?
4. Which screws in Strido get thread locker as standard?
5. What is the preferred builder action for the servo-mount pilots under ADR-009?

<details>
<summary>Answers</summary>

1. Metric thread 2.5 mm diameter, 6 mm long under the head; a socket head cap screw.
2. About 2.65 mm (2.80 − 0.15), i.e. 0.88 d: ok, full grip.
3. The joint must turn freely, so the nut cannot be tightened hard; the nylon insert keeps it from backing off anyway.
4. Only the metal-to-metal screws into the servo horns; printed pilots never get anaerobic thread locker.
5. Print those parts with X-Y hole compensation −0.15 mm, giving a pilot of about 2.65 mm.

</details>

## Further reading

- [Henkel: LOCTITE 243 technical data sheet](https://datasheets.tdx.henkel.com/LOCTITE-243-en_GL.pdf)
- [Fit report: verification/fits.md](../../verification/fits.md) and [decisions (ADR-009)](../../decisions.md)
- [Prusa Knowledge Base: PETG](https://help.prusa3d.com/article/petg_2059) (material the pilots are printed in)
- Related in this wiki: [3D printing](3d-printing.md), [mechanics](../hardware/mechanics.md), [tools and workshop](tools-and-workshop.md)
