# Cable management and the wiring harness

A walking robot shakes, flexes and bends its own wiring thousands of times an hour. Most failures in hobby robots are not broken parts but a lead that chafed through, a contact that worked loose or a wire that snapped inside its insulation next to a joint. This page explains how a **wiring harness** is designed against those failures: how thick each wire must be, what a fuse really protects, how much slack a cable needs to cross a moving joint, how to bend, bundle and terminate wires, and what the CAD check can and cannot prove. Every rule is worked through with Strido's own cut list.

::: tip In Strido
**Source of truth:** `hardware/wiring.yaml` names every cable W00–W23 and the twelve servo leads (S-*leg*-*joint*), the connector each end sits on, the tie points it passes and the wire stock. `strido_cad.wiring` routes them through the CAD; `python -m strido_verify.wiring` checks them and writes the [wiring check](../../verification/wiring.md) with the **cut list**. Ratings and fuses are in `hardware/electronics.yaml`. The build order is in [electronics, wiring and power](../../electronics.md#wiring-harness) and assembly Steps 14–17 (and the shell Steps 18–22) of the [assembly manual](../../assembly/README.md). Decision: [ADR-011](../../decisions.md#adr-011-wiring-harness-routed-and-checked-in-the-cad).
:::

## Why design a harness at all?

The robot's earlier wiring was a list with estimated lengths. As soon as every cable was modelled in the CAD, the list turned out to hide real defects (ADR-011): the main fuse holder left 4 mm for a 14 AWG lead that cannot bend that tightly; Dupont housings fitted neither on the IMU (2.5 mm under the Pi) nor on the XIAO pins (9 mm under the upper shoulder frame); the XIAO-to-PCA9685 wires needed about 0.3 m instead of 0.1 m; and a 60 mm 18 AWG tap sat behind the 25 A fuse alone. None of these shows up on paper. All of them show up in a real build, usually as a late surprise.

A harness is designed against the ways wiring fails in a walking machine:

| Failure | What happens | Design answer |
|---|---|---|
| **Chafing** | a cable rubs on a moving horn, link or shell edge until the insulation wears through and the conductor shorts | route along structure, clear of everything that moves; spiral wrap on bundles; check clearance over the joint ranges |
| **Connector fretting** | vibration makes two mated contacts slide by micrometres; the plating wears, oxide builds up and the contact becomes intermittent | fewer connectors; latching or clamping contacts; tie the cable so its weight does not hang on the contact |
| **Flex fatigue** | a wire bent back and forth at one point breaks strand by strand inside intact insulation | cross joints near their axis with a free loop; avoid stiff points (solder wicking) next to a flexing section |
| **Pinch** | a cable is caught between two parts that close, such as a leg folding against the body | keep every cable out of the volume the legs sweep |
| **Heat** | an undersized wire heats with $P = I^2 R$; insulation softens; in a short circuit it can burn | size every wire for its current; fuse it below what it can carry |

The rest of the page goes through these one by one.

## Conductor sizing

### Ampacity

A wire's **ampacity** is the current it can carry continuously without its insulation getting too hot. It depends on the copper cross-section, the insulation's temperature rating, the surrounding temperature and how well the wire can shed heat: a wire alone in free air carries more than the same wire in a tight bundle (general; published tables derate bundles). Strido uses deliberately conservative values for short chassis runs (`wire_ampacity_a` in `hardware/electronics.yaml`):

| Gauge | Copper area (approx.) | Resistance (approx.) | Ampacity used | Used for in Strido |
|---|---|---|---|---|
| 14 AWG | $2.1\,\mathrm{mm^2}$ | $8.3\,\mathrm{m\Omega/m}$ | 32 A | battery trunk W01–W04 |
| 18 AWG | $0.82\,\mathrm{mm^2}$ | $21\,\mathrm{m\Omega/m}$ | 16 A | UBEC outputs W05/W06, bus jumpers W07/W08, logic branch W09–W11, logic grounds W24, W04/logic |
| 22 AWG | $0.33\,\mathrm{mm^2}$ | $53\,\mathrm{m\Omega/m}$ | 7 A | Pi 5 V feed W12, servo leads, I²C and OE wires W17/W20, button W13 |

The `python -m strido_verify.electronics` gate reads the power cables from `hardware/wiring.yaml` and checks each one's worst-case current against this table: for example W05 carries the UBEC's 10 A continuous on 18 AWG ($10 \le 16$), and W12 carries 1.6 A per 22 AWG wire ($1.6 \le 7$).

### Resistance and voltage drop

A conductor's resistance grows with its length $L$ and shrinks with its cross-section $A$:

$$
R = \frac{\rho\,L}{A}, \qquad \rho_\mathrm{Cu} \approx 1.72 \times 10^{-8}\,\Omega\,\mathrm{m}
$$

The current flows out on one conductor and back on the other, so a supply pair loses

$$
\Delta V = I \cdot 2R, \qquad P = I^2 \cdot 2R
$$

**W05**, front UBEC to the front WAGO bus: 18 AWG pair, routed 190 mm, cut 222 mm. Taking the full cut length as the copper in circuit (an upper bound) at the UBEC's 10 A continuous rating:

$$
R = 0.222\,\mathrm{m} \times 21\,\mathrm{m\Omega/m} \approx 4.7\,\mathrm{m\Omega}\ \text{per conductor}
$$

$$
\Delta V \approx 10\,\mathrm{A} \times 2 \times 4.7\,\mathrm{m\Omega} \approx 93\,\mathrm{mV}, \qquad P \approx (10\,\mathrm{A})^2 \times 9.3\,\mathrm{m\Omega} \approx 0.93\,\mathrm{W}
$$

That is about 1.6 % of the 6.0 V rail: acceptable.

**W12**, regulator to the Pi: 22 AWG, routed 104 mm, cut 123 mm, two wires per rail with 1.6 A each:

$$
R = 0.123\,\mathrm{m} \times 53\,\mathrm{m\Omega/m} \approx 6.5\,\mathrm{m\Omega}, \qquad \Delta V \approx 1.6\,\mathrm{A} \times 2 \times 6.5\,\mathrm{m\Omega} \approx 21\,\mathrm{mV}
$$

Small, but the Pi's margin is small too: the regulator may deliver as little as 4.8 V and the Pi flags under-voltage below 4.63 V ([power](../hardware/power.md)). That is why W12 uses two wires per rail, and why it is kept short.

## Fusing: a fuse protects the wire

A fuse does not protect the robot's boards. It protects **the wire behind it** from overheating in a fault. It must therefore blow before the weakest wire it covers overheats, and must not blow at normal load:

$$
I_\mathrm{load} \le I_\mathrm{fuse} \le I_\mathrm{wire,min}
$$

where $I_\mathrm{wire,min}$ is the ampacity of the *thinnest* wire anywhere behind that fuse. Strido's two fuses (`fuses` in `hardware/electronics.yaml`):

| Fuse | Rating | Protects | Thinnest wire behind it | Worst-case load |
|---|---|---|---|---|
| Main (ATO) | 25 A | W02, W03, W04/front, W04/rear | 14 AWG, 32 A | 23.6 A (servo branch ≈ 21 A at an empty pack + logic) |
| Logic (ATO) | 7.5 A | W09, W10, W11, W24, W04/logic | 18 AWG, 16 A | 2.74 A |

W04/logic and W24 are the logic branch's *ground* returns. In normal operation they carry the same current as the logic feed, so the logic fuse limits it and they may be 18 AWG. The limit is one of normal current, not of every fault: a short from the servo branch (behind only the 25 A fuse) onto a logic ground would return through them. That is why the servo-branch wires run apart from the logic grounds except at the inner frame opening, inside their insulation and wrap.

**Why the old tap was wrong.** The old design fed the logic fuse holder through a 60 mm piece of 18 AWG taken off the trunk *behind the 25 A fuse*. Nothing but the 25 A fuse covered that piece, and 25 A is above 18 AWG's 16 A. A fault drawing, say, 20 A through the tap would never blow the fuse but would heat the tap with

$$
P' = I^2 \frac{\rho}{A} = (20\,\mathrm{A})^2 \times 21\,\mathrm{m\Omega/m} \approx 8.4\,\mathrm{W/m}
$$

indefinitely (an illustration of the principle, not a measured fault). "Keep it short" lowers the chance of a fault but does not change the rule. The fix: the tap is now the logic fuse holder's **own 14 AWG lead**, spliced to W02 in the back shell. No wire thinner than 14 AWG sits behind the 25 A fuse alone, and everything after the 7.5 A fuse is at least 18 AWG.

**Why W01 is unfused and kept short.** W01 runs from the battery input to the main fuse. Nothing can protect it except the pack's own limits: the pack is rated for 300 A (`hardware/electronics.yaml`), so a short on W01 is a battery short. The fuse sits where there was room for its holder and its 14 AWG leads to bend: on the rear WAGO bus, about 0.15 m from the battery input. W01 is therefore treated like the pack's own lead: 14 AWG, cut 151 mm, in spiral wrap, routed clear of everything that moves. ADR-011 says to move the fuse closer only if a compact fused battery input fits under the deck.

## Crossing a joint: service loops

A cable that crosses a joint must change length as the joint turns. If it cannot, the joint pulls on the cable, and the pull ends up at the weakest point: a solder joint, a crimp or a connector. A **service loop** is a deliberate piece of free cable between two fixed ties that absorbs this change.

On Strido the thigh and knee servos ride on the hip body, so their leads cross only the **hip** joint. Each lead is tied at the servo mount plate near the hip axis (on the moving side) and again at the shoulder frame or bus holder (on the body). Between the ties hangs the loop. The hip servos sit on the body and need no loop. The other joints need none either, because no lead crosses them: placing the motors decides which joints the wiring has to cross.

### How far apart do the ties move?

Put the origin on the hip axis. Let $\mathbf{p}$ be the tie on the moving hip body (in the hip's reference pose) and $\mathbf{q}$ the tie on the body. When the hip turns by $\theta$, the moving tie goes to $R(\theta)\,\mathbf{p}$, with $R(\theta)$ the rotation about the hip axis (see [frames and rotations](../theory/frames-and-rotations.md)). The tie-to-tie distance is

$$
d(\theta) = \lVert R(\theta)\,\mathbf{p} - \mathbf{q} \rVert
$$

To see what drives it, split each point into a part along the unit axis $\hat{\mathbf{a}}$ and a part perpendicular to it: $\mathbf{p} = p_a\,\hat{\mathbf{a}} + \mathbf{p}_\perp$, $\mathbf{q} = q_a\,\hat{\mathbf{a}} + \mathbf{q}_\perp$, with radii $r_p = \lVert \mathbf{p}_\perp \rVert$ and $r_q = \lVert \mathbf{q}_\perp \rVert$. The rotation leaves the axial parts alone and turns $\mathbf{p}_\perp$ by $\theta$, so the law of cosines gives

$$
d(\theta)^2 = (p_a - q_a)^2 + r_p^2 + r_q^2 - 2\,r_p\,r_q \cos(\theta - \theta_0)
$$

where $\theta_0$ is the hip angle at which the two perpendicular parts point the same way. Over a full turn $d$ would swing between

$$
d_\mathrm{min} = \sqrt{(p_a - q_a)^2 + (r_p - r_q)^2}, \qquad d_\mathrm{max} = \sqrt{(p_a - q_a)^2 + (r_p + r_q)^2}
$$

and within the hip's limited range it covers part of that interval. The lesson is in the radii: the swing grows with $r_p\,r_q$. **Ties close to the axis move little**, so the loop can be short. That is why the leads are tied at the servo mount plate *near the hip axis* rather than further out.

The wiring gate does not trust a hand formula. It places both ties in the CAD and evaluates $d(\theta)$ over the full hip range. For the front legs:

| Lead | Tie-to-tie distance over the hip range | Required loop $1.2\,d_\mathrm{max}$ | Loop in `wiring.yaml` |
|---|---|---|---|
| front thigh | 13.0–24.1 mm | 28.9 mm | 30 mm |
| front knee | 20.0–25.6 mm | 30.7 mm | 32 mm |
| rear thigh | 11.9–16.2 mm | 19.4 mm | 22 mm |
| rear knee | 11.9–16.1 mm | 19.4 mm | 22 mm |

The front knee lead's tie on the shoulder side sits at the bus holder, 17 mm towards the inner frame: its loop is a little longer, but the signal wire saves more on its way to the PCA9685, and with that the 260 mm lead reaches without an extension.

### The slack rule

The robot's rule is

$$
L_\mathrm{loop} \ge 1.2\, d_\mathrm{max}
$$

Worked for the front knee: $1.2 \times 25.6\,\mathrm{mm} = 30.7\,\mathrm{mm}$, rounded up to **32 mm**. Why not exactly $d_\mathrm{max}$? At that length the cable would be a straight, taut chord at the extreme hip angle and would pull on both ties. A cable also cannot leave a tie at any angle: it leaves in the direction it is tied and has to curve towards the other tie, and the curve costs length. The 20 % covers both. Why not much longer? Extra loop has to hang somewhere, and a long loop can droop into a moving part. The gate checks the loop's *length* only; where it hangs is not modelled, so you check that by hand (see the checklist below).

## Bend radius and flex life

Every cable has a minimum bend radius. A common rule of thumb (general, not a datasheet value; check the cable maker's data) is a few times the outer diameter (OD) for a cable that is bent once and then fixed, and about ten times the OD or more for a cable that flexes in service. `hardware/wiring.yaml` records a minimum static bend for each cable type, about three times the OD: 11 mm for 14 AWG (3.6 mm OD), 7 mm for 18 AWG (2.2 mm), 5 mm for 22 AWG (1.6 mm), 15 mm for the USB cables. The old main-fuse position left 4 mm for a 14 AWG lead, which needs 11 mm: that is why the fuse moved.

Why bending fatigues a wire: a strand of diameter $d_s$ bent to radius $R$ stretches on its outside by the bending strain (general beam result)

$$
\varepsilon \approx \frac{d_s}{2R}
$$

Copper survives many cycles at small strain and few at large strain. Two consequences:

- **Fine strands flex better.** In a stranded wire the strands can slide, so each one bends about its own centre. For an illustrative strand of $d_s = 0.08\,\mathrm{mm}$ at $R = 5\,\mathrm{mm}$, $\varepsilon \approx 0.08/10 = 0.8\,\%$. A solid 22 AWG conductor ($A = 0.33\,\mathrm{mm^2}$, so $d = \sqrt{4A/\pi} \approx 0.65\,\mathrm{mm}$) bent the same way sees $\varepsilon \approx 0.65/10 = 6.5\,\%$, eight times more. Silicone wire and servo leads are fine-stranded for this reason.
- **A longer loop bends gentler.** Spreading the same joint motion over more cable means a larger radius and a smaller strain. A loop that is just long enough bends sharply at its ends every step.

The CAD draws route corners sharp and does not check bend radii, so the radius is your job at the bench.

## Bundling, spiral wrap and ties

- **Spiral wrap** (a PE spiral that wraps around a bundle) on every bundle of **three or more cables**. It holds the bundle together, protects it from edges, and still lets single cables branch out anywhere. Strido uses about 228 mm of it (`spiral_wrap`, wire-stock check).
- **Cable ties** at the marked tie nodes of `wiring.yaml`, about 30 from a bag of 100: servo mount plate edges, shoulder frame slots, bus holder slots, frame openings. Ties fix the cable to structure so it cannot wander into a moving part, and they take pull off the terminations.
- **Adhesive tie mounts:** two 13 × 13 mm mounts on the deck side strips (`cable_tie_mounts`, modelled in the CAD) where there is no slot to tie to.
- **Tie spacing** (general practice): tie at every branch, before and after every bend, and close to every connector, so a pull on the cable ends at a tie rather than at a contact. On the robot, the tie nodes in the CAD already do this.
- **Tension** (general): pull a tie snug so the cable cannot slide, not so tight that it dents the insulation. A crushed spot is a stiff point and a future chafe point. Flush-cut the tail; a sharp tail scratches skin and insulation.

## Signal and power

A changing current $I$ in one loop induces a voltage in a nearby loop, $V = M\,\mathrm{d}I/\mathrm{d}t$, where $M$ (mutual inductance) grows with the loop areas and shrinks with distance (general). Servo currents change fast: up to 3.5 A per servo at stall. Two general habits keep that out of the signals:

- **Separate them.** Run signal wires away from high-current wires where you can, and cross them at right angles rather than in parallel. On Strido each servo lead is split at a tie: red/brown drop to the WAGO bus in the cavity, the orange signal runs on to the PCA9685 beside the Pi.
- **Keep loops small and twist pairs.** A signal and its return run side by side enclose little area. Twisting a pair (general technique; the robot's docs do not prescribe it) alternates the direction of each small loop, so induced voltages cancel along the length.

A common ground is part of the same story: a servo's signal is read against its ground, so all domains share one ground star at the battery input ([power](../hardware/power.md)).

## Connectors and terminations

### WAGO lever clamps

The servo bus is built from WAGO 221-415 lever connectors: five entries, 0.2–4 mm², rated 32 A. A spring clamp grips the bare conductor when the lever closes, with no tool. WAGO's datasheet requires a **strip length of 11 mm**: shorter and the clamp grips too little copper; longer and bare copper sticks out of the housing. Push the conductor in until the insulation meets the housing, close the lever, and tug. The housing is transparent, so you can see the conductor reach the end. One wire per entry: the gate checks this for every WAGO port.

### Crimp or solder?

- **Crimping** squeezes a metal contact cold around the bare strands (conductor grip) and around the insulation (insulation grip). The insulation grip is the **strain relief**: it takes bending and pull off the conductor joint. The strands stay flexible right up to the contact.
- **Soldering** joins the strands with molten alloy. Solder also runs up inside the insulation by capillary action (**wicking**) and turns that part of the wire into a solid rod. Bending then concentrates at the end of the wicked section, exactly as in the strain formula above (solid conductor, large $\varepsilon$), and strands break there under vibration. Wicking is a defect in harness workmanship standards such as IPC/WHMA-A-620.

So: solder where the wire is fixed and supported (and add heat-shrink as strain relief); crimp or clamp where it moves. On Strido the soldered joints are the power entry (XT60H cups, fuse holder leads, the heat-shrunk splices), the switch, regulator and button, and the XIAO pins. The XIAO pins sit 9 mm under the upper shoulder frame, and a Dupont housing is 14 mm tall, so W17 (3V3, GND, SDA, SCL) and W20 (D3 → OE) are soldered there and crimped at the PCA9685, and the display cable's Dupont ends (W21) are soldered there too. Tie these wires close to the board so no pull reaches the solder.

### Dupont contacts

Dupont contacts plug onto 2.54 mm header pins and hold by spring friction only. A heavy or swinging cable can work them loose (general), so tie the bundle near the board and let nothing hang on the contacts. On the robot they are used where they fit: W12 on the Pi (one wire per pin), W17/W20 at the PCA9685, and each servo's orange signal wire, re-crimped into a 1-pin housing on its PCA9685 channel. Where even a housing does not fit, there is another connector: the IMU sits 2.5 mm under the Pi, so W18 is a STEMMA QT cable with its low JST-SH plug.

### XT60 and the contact rule

The XT60 is the 30 A connector of the battery input, the arming port and the loop key. Describe its halves by **pins** and **sockets**, not "male/female". The loop key is a shorted connector, so it must have the same contact type as the pack's own connector: then it cannot mate with the pack ([XT60 contact rule](../../electronics.md#xt60-contact-rule-the-loop-key-must-never-fit-the-battery)).

## Cut leads to length, don't extend them

Earlier the servos were connected with 300 mm extension leads. Every extension adds a mated three-pin plug and socket per servo: twelve extra connections, 36 extra contacts, each one a candidate for fretting. Each servo now uses only its own 260 mm lead: it runs to a tie, where the red and brown wires are peeled off, cut to length and clamped in the leg's WAGO pair (red into the upper V+ connector, brown into the lower GND; ports hip 1, thigh 2, knee 3), while the orange signal wire is cut to length and re-crimped for its PCA9685 channel. Fewer connectors in a walking robot means fewer intermittent contacts, and a shorter power path ([power](../hardware/power.md)).

The **cut list** in the [wiring check](../../verification/wiring.md) gives every wire's routed length and the length to cut:

$$
L_\mathrm{cut} = L_\mathrm{routed} + t_1 + t_2 + \max(10\,\mathrm{mm},\ 0.08\,L_\mathrm{routed})
$$

with a termination allowance $t$ per end (WAGO strip 11 mm, solder 6 mm, crimp 3 mm, screw terminal 7 mm). The slack covers dressing and one re-termination. Two examples:

$$
\text{W05:}\quad 190 + 6 + 11 + 0.08 \times 190 = 222.2 \;\Rightarrow\; 222\,\mathrm{mm}
$$

$$
\text{W12:}\quad 104 + 6 + 3 + \max(10,\ 8.3) = 123\,\mathrm{mm}
$$

Ready-made cables cannot be cut, so the gate checks **reach** instead: supplied length ≥ route + terminations + 10 mm. Their excess is folded and tied: 178 mm on the Pi–XIAO USB cable (W14), 124 mm on the camera ribbon (W16), 141 mm on the display cable (W21), 55 mm on the LiDAR USB cable (W15). Servo leads have 12–124 mm to spare before cutting. The front knee leads are the tightest at 12 mm: route them exactly as the manual draws them.

## How the CAD routes the harness

`strido_cad.wiring` treats routing as a path search:

1. **Obstacles.** A voxel grid with 1 mm cells marks every base part, plus every volume a leg part sweeps over its joint limits (the hip in 1° steps, the thigh and calf over a grid of angles). A cable routed through free voxels stays clear of a leg at the sampled joint angles; the gate then re-checks the operating poses against the real meshes.
2. **Search.** Between consecutive tie nodes, Dijkstra's shortest-path algorithm finds a path through free voxels. Its cost prefers voxels within 3 mm of a surface, because real cables are tied along structure, not strung through open space.
3. **Shortcut.** The path is straightened only where the straight line stays as close to structure as the searched path did.

The result is drawn in the renders, the [3D viewer](../../viewer.md) and the assembly manual, so what you see in the build steps is the routed harness.

### What the gate proves, and what it does not

`python -m strido_verify.wiring` re-checks the routed harness independently of the router:

- **Reach:** every ready-made cable covers its route with terminations and 10 mm to spare.
- **Stock:** wire per gauge and colour, spiral wrap and ties fit the BOM.
- **Hip loops:** every loop is at least $1.2\,d_\mathrm{max}$.
- **Ports:** one cable per WAGO entry and per PCA9685 channel.
- **Clearance:** no conductor passes through a part, and every cable keeps at least 1.0 mm (warn) / 0.3 mm (fail) from every part of another body in every operating pose: stand, crouch, tall, eight trot phases, hips in and out.

It does **not** model bend radii (route corners are drawn sharp) or where a hip loop hangs. It also cannot see workmanship: a crimp that pulls out, a cold solder joint, a tie pulled too tight. Those are checked at the bench.

## Build checklist

1. Cut every wire from the cut list; label both ends with its ID.
2. Strip WAGO ends to 11 mm; tug every WAGO entry, crimp and solder joint.
3. Slide heat-shrink on before soldering; shrink it over every soldered power joint.
4. Fuses and loop key stay **out** until the wiring is checked ([electronics](../../electronics.md#wiring-harness), build order steps 3–7).
5. Tie each thigh and knee lead at the servo mount plate and at the shoulder frame / bus holder, leaving the loop between the ties (front: 30 mm thigh, 32 mm knee; rear: 22 mm).
6. Spiral wrap every bundle of three or more cables; ties at the marked points; snug, not crushing.
7. Respect bend radii by eye: no 14 AWG lead bent tighter than about 11 mm.
8. **Move every joint through its full range by hand**, loop key out: hips in and out, thighs and knees from folded to stretched. Watch every loop and bundle: nothing may pull taut, rub or come near a moving part.
9. Continuity-check each cable against the wiring list; measure the resistance between + and − at the battery input (not near 0 Ω) before connecting the pack.

## Check yourself

1. Name three ways wiring fails in a walking robot and one design measure against each.
2. The main fuse is 25 A. Why may no 18 AWG wire sit behind it alone, and how did the redesign fix the old logic tap?
3. Estimate the round-trip voltage drop of W06 (18 AWG pair, routed 151 mm) at 10 A.
4. A tie on the hip sits at radius $r_p = 10\,\mathrm{mm}$ from the hip axis and a body tie at $r_q = 15\,\mathrm{mm}$, with no axial offset. Over a full turn, between which distances would $d(\theta)$ swing? What does that say about where to put ties?
5. The gate finds a loop's largest tie-to-tie distance is 25 mm. How long must the loop be by the robot's rule, and why is a loop of exactly 25 mm not enough?
6. Why does a soldered stranded wire break sooner under vibration than a crimped one?
7. Why were the servo extensions removed?
8. Compute the cut length of W09 (routed 256 mm, solder at the fuse holder, screw terminal at the switch).
9. Name two things the wiring gate does not check, and how you check them instead.

<details>
<summary>Answers</summary>

1. Any three of: chafing (route along structure, spiral wrap, clearance check), connector fretting (fewer connectors, tie the cable so nothing hangs on contacts), flex fatigue (loops near the joint axis, no stiff points next to flexing wire), pinch (keep cables out of the volume the legs sweep), heat (size wires for their current, fuse below ampacity).
2. A fuse must be no larger than the ampacity of the thinnest wire behind it; 18 AWG is rated 16 A, so a fault between 16 and 25 A would heat it without blowing the fuse. The tap is now the logic fuse holder's own 14 AWG lead, spliced to W02.
3. $R = 0.151 \times 21 \approx 3.2\,\mathrm{m\Omega}$ per conductor; $\Delta V \approx 10 \times 2 \times 3.2 \approx 63\,\mathrm{mV}$ (with the 180 mm cut length as an upper bound, about 76 mV).
4. $d_\mathrm{min} = \lvert 10 - 15 \rvert = 5\,\mathrm{mm}$, $d_\mathrm{max} = 10 + 15 = 25\,\mathrm{mm}$. The swing grows with both radii, so ties close to the axis need a shorter loop.
5. $1.2 \times 25 = 30\,\mathrm{mm}$. At exactly 25 mm the cable is taut at the extreme angle and pulls on the ties and terminations; it also needs length to curve away from each tie.
6. Solder wicks up the strands and makes a solid, stiff section; bending concentrates at its end, where a solid conductor sees much larger strain than individual strands. A crimp leaves the strands flexible and its insulation grip relieves strain.
7. Each extension added a three-pin plug and socket per servo (36 contacts in total) that could fret loose, plus extra wire and voltage drop. Cutting each servo's own lead to length removes them.
8. $256 + 6 + 7 + 0.08 \times 256 = 289.5 \Rightarrow 290\,\mathrm{mm}$, as in the cut list.
9. Bend radii and where a loop hangs (move every joint through its range by hand and look); workmanship such as crimps, solder joints and tie tension (pull test, inspection, continuity check).

</details>

## Further reading

- [IPC/WHMA-A-620, Requirements and Acceptance for Cable and Wire Harness Assemblies (table of contents)](https://www.electronics.org/TOC/IPC-WHMA-A-620E_TOC.pdf): the industry workmanship standard for crimps, solder joints, wicking, bundling and ties.
- [NASA-STD-8739.4, Workmanship Standard for Crimping, Interconnecting Cables, Harnesses, and Wiring](https://standards.nasa.gov/sites/default/files/standards/NASA/A/4/nasa-std-87394a_w_change_4_0.pdf): a free, detailed harness workmanship standard.
- [Molex Quality Crimping Handbook](https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/commercialcrimpbookpdf/638/63800/TM-638000029-001.pdf): conductor and insulation grip, pull tests, crimp defects.
- [WAGO 221-415 data sheet](https://wago.priintcloud.com/datasheets/221-415/en): 0.2–4 mm², 32 A, strip length 11 mm.
- [HellermannTyton spiral binding (SBPE)](https://www.hellermanntyton.com/products/protective-tubing-and-spiral-binding/sbpe1.5/161-41001): spiral wrap sizes and temperature range.
- [NBS Handbook 100, Copper Wire Tables](https://nvlpubs.nist.gov/nistpubs/Legacy/hb/nbshandbook100.pdf): AWG diameters, areas and resistances.
- [PowerStream AWG table](https://www.powerstream.com/Wire_Size.htm): a widely copied chassis-wiring ampacity table (secondary source; the robot's values are deliberately lower).
- [Raspberry Pi hardware documentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html): GPIO header power pins.
- Robot docs: [electronics, wiring and power](../../electronics.md#wiring-harness), [wiring check and cut list](../../verification/wiring.md), [ADR-011](../../decisions.md#adr-011-wiring-harness-routed-and-checked-in-the-cad).
- Related in this wiki: [power](../hardware/power.md), [tools and workshop](tools-and-workshop.md), [safety](safety.md), [frames and rotations](../theory/frames-and-rotations.md).
