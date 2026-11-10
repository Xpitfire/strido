# Strength, torque and failure

Will a printed leg break, bend or tear out its screws? This page covers the mechanics behind that question: torque, stress and strain, bending, buckling, joints and safety factors. Each formula is worked through with Strido's own numbers. The same formulas run as an automatic check on every design change.

::: tip In Strido
**Gate:** `python -m strido_verify.strength` (part of `make verify`) computes 19 checks from the printed STLs, the leg geometry and the fit report; results in the [strength report](../../verification/strength.md). **Inputs:** `hardware/strength.yaml` (loads, PETG and screw data with sources). **Decision:** [ADR-010](../../decisions.md): the long link's buckling, once the one known weak point, fixed by the stiff long link (no check needs an exception now). **Each part's results** appear on its page in the [print kit](../../print-kit.md) and the [shop](../../shop.md). The forces in the legs come from [statics and dynamics](../theory/statics-and-dynamics.md).
:::

## Torque: force times lever

A torque $T$ (German *Drehmoment*) is a force $F$ acting at a distance $r$ from an axis. Only the force component at right angles to the lever turns the axis. With $\alpha$ the angle between lever and force:

$$
T = r\,F\,\sin\alpha \qquad [\mathrm{N\,m}] = [\mathrm{m}]\cdot[\mathrm{N}]
$$

In vector form this is the cross product $\mathbf{T} = \mathbf{r}\times\mathbf{F}$. Servo datasheets give torque in kg·cm: the weight of 1 kg hanging 1 cm from the axis. With $g = 9.81\,\mathrm{m/s^2}$:

$$
35\,\mathrm{kg\,cm} = 35 \cdot 9.81\,\mathrm{N} \cdot 0.01\,\mathrm{m} = 3.43\,\mathrm{N\,m} \qquad \text{(SPT5435LV at 6.0 V, stall)}
$$

Read backwards, the same formula gives the force a servo can push through an arm. The knee-drive arm horn is $r = 24\,\mathrm{mm}$:

$$
F = \frac{T}{r\,\sin\alpha} = \frac{3.43\,\mathrm{N\,m}}{0.024\,\mathrm{m}\cdot 1.0} = 143\,\mathrm{N}\ \ (\alpha = 90^\circ), \qquad
\frac{3.43}{0.024 \cdot 0.68} = 211\,\mathrm{N}\ \ \text{(worst angle within the joint limits)}
$$

Small levers and flat angles turn modest torques into large forces. As $\alpha \to 0$ the force grows without bound: that is the *dead point* (toggle) of a linkage. The check sweeps every pose inside the joint limits and keeps the largest force.

## Where the loads come from

1. **Weight and landings.** The robot weighs $m g = 3.07 \cdot 9.81 = 30.1\,\mathrm{N}$. While it trots, one diagonal pair of feet carries it. A hard landing multiplies the force by an impact factor $k$. The check assumes $k = 3$ on two feet:

$$
F_\text{foot} = \frac{k\,m\,g}{2} = \frac{3 \cdot 30.1}{2} = 45.2\,\mathrm{N}
$$

(an assumption; measured trotting dogs peak at about 1–1.2 × their weight per front leg).

2. **The servos themselves.** Each servo pushes with at most its stall torque $T_\text{stall}$, and that is the design load for the joints. A landing would need $F_\text{foot}\,L_\text{tibia} = 45.2 \cdot 0.124 = 5.6\,\mathrm{N\,m}$ at the knee. The knee servo applies only $3.07\,\mathrm{N\,m}$ there, so the knee gives way and the servo is back-driven. Back-driving a geared servo takes more than its stall torque, though. With forward and reverse gear efficiencies $\eta_f$ and $\eta_r$ it takes roughly $T_\text{stall}/(\eta_f\,\eta_r)$, about 1.5–3 × (an estimate). Hard impacts can therefore exceed the design loads, and the safety factors have to cover that. Pins and bearings carry the full landing force along the leg.

## Stress and strain

Load on a part is spread over its cross-section. **Stress** $\sigma$ is force per area, in $\mathrm{N/mm^2} = \mathrm{MPa}$. **Strain** $\varepsilon$ is the relative stretch $\Delta L / L$. For small strains most materials are linear-elastic (Hooke's law), with Young's modulus $E$:

$$
\sigma = \frac{F}{A}, \qquad \varepsilon = \frac{\Delta L}{L}, \qquad \sigma = E\,\varepsilon
$$

PETG has $E \approx 1.5\,\mathrm{GPa}$ and yields at about $47\,\mathrm{MPa}$; Hooke's law would put that at $\varepsilon = 47/1500 \approx 3\,\%$, the data sheet measures $5\,\%$ because PETG softens before it yields. Steel has $E \approx 200\,\mathrm{GPa}$, so for the same stress it stretches 130 times less. Beyond the **yield strength** the part deforms permanently. Beyond the **tensile strength** it breaks.

Real parts carry several stresses at once (tension, bending, shear). The **von Mises** equivalent stress turns them into one number to compare with the tensile yield strength. For normal stress $\sigma$ plus shear $\tau$:

$$
\sigma_\text{v} = \sqrt{\sigma^2 + 3\,\tau^2} \qquad\Rightarrow\qquad \tau_\text{allow} = \frac{\sigma_\text{allow}}{\sqrt 3} \approx 0.577\,\sigma_\text{allow}
$$

## Bending

A beam bent by a moment $M$ stretches on one side and compresses on the other. The stress grows linearly from the neutral axis (zero stress) to the outermost fibre at distance $c$. Euler–Bernoulli beam theory gives:

$$
\sigma(y) = \frac{M\,y}{I}, \qquad \sigma_\text{max} = \frac{M\,c}{I} = \frac{M}{W}, \qquad I = \int_A y^2\,\mathrm{d}A, \qquad W = \frac{I}{c}
$$

$I$ is the **second moment of area**: it measures how far the material sits from the neutral axis. $W$ is the **section modulus**. For a solid rectangle of width $b$ and height $h$, bent across $h$:

$$
I = \frac{b\,h^3}{12}, \qquad W = \frac{b\,h^2}{6}
$$

Height counts with its cube: doubling the height makes a link 8 times stiffer and 4 times stronger in bending. That is why I-beams put their material far from the middle.

**Printed parts are mostly shells.** The slicer profile prints 3 perimeters (1.2 mm) and only 30 % gyroid infill. The check computes $I$ and $W$ for the 1.2 mm walls only and ignores the infill, which is conservative. It takes 41 sections along each link and uses the weakest one. Example: the femur's weakest section has $W = 236\,\mathrm{mm^3}$ in the leg plane, and the thigh servo applies $M = 3430\,\mathrm{N\,mm}$:

$$
\sigma = \frac{3430\,\mathrm{N\,mm}}{236\,\mathrm{mm^3}} = 14.5\,\mathrm{MPa}, \qquad S = \frac{47}{14.5} = 3.2
$$

## Printed plastic is anisotropic

An FDM part is a stack of welded layers. Prusament's PETG data sheet gives:

| Direction | Strength |
|---|---|
| Along the layers (printed flat) | $47\,\mathrm{MPa}$ tensile yield |
| Across the layers (layer adhesion) | $18 \pm 4\,\mathrm{MPa}$ |

Printed parts usually fail by pulling layers apart. They tear (German *reißen*) along a layer line, often at a sharp corner where the stress concentrates. That is why the print list lays the links, femurs and tibias flat. Their bending stress then runs along the layers. The check uses $47\,\mathrm{MPa}$ when a link lies flat and $18\,\mathrm{MPa}$ when its long axis points up in its print orientation.

## Safety factor

$$
S = \frac{\text{allowable}}{\text{actual}}
$$

The check fails below $S = 1.5$ and warns below $2.0$. FDM strength scatters from printer to printer and PETG creeps under a standing load. Repeated loading also causes **fatigue**: millions of steps at a stress well below the static strength can grow a crack. None of that is in a static calculation, so the margin covers it. On the robot the lowest factors are the tibia halves ($S = 2.2$) and the long link's buckling ($S = 2.5$, next section), which was far below everything else until the link was redesigned.

## Buckling

A slender bar in compression does not crush. It suddenly bows sideways once the force reaches Euler's critical load. The deflected bar is in equilibrium when $E I\,w'' + F\,w = 0$. The smallest non-zero solution of this equation gives:

$$
F_\text{cr} = \frac{\pi^2 E I}{(K L)^2}
$$

$L$ is the pin spacing and $K$ the effective-length factor of the end conditions: $1.0$ for pinned ends, $0.5$ for clamped ends, $0.7$ for one of each. Below $F_\text{cr}$ nothing visible happens. At $F_\text{cr}$ the bar loses its stiffness against sideways deflection.

The upstream long knee link is a bar $5\,\mathrm{mm}$ wide in the leg plane and $8\,\mathrm{mm}$ across it, $130\,\mathrm{mm}$ between its pins. In the leg plane its ends turn freely on pins ($K = 1$), and its walls give $I \approx 75\,\mathrm{mm^4}$:

$$
F_\text{cr} = \frac{\pi^2 \cdot 1500\,\mathrm{MPa} \cdot 75\,\mathrm{mm^4}}{(130\,\mathrm{mm})^2} \approx 65\,\mathrm{N}
\qquad F_\text{knee servo, worst pose} = 192\,\mathrm{N} \qquad S \approx 0.34
$$

That made it the robot's weakest point by far. Standing loads it with about $0.70\,\mathrm{N\,m} / (0.024\,\mathrm{m}\cdot\sin 86^\circ) \approx 29\,\mathrm{N}$ ($S \approx 2.2$; see [statics and dynamics](../theory/statics-and-dynamics.md)), so it held in normal walking, but a knee pushing at stall against a blocked foot or a hard stop bends it sideways ([ADR-010](../../decisions.md)).

Because $I \propto h^3$, width in the leg plane is what buys stiffness. Strido therefore prints a **stiff long link** (`stiff_long_link`): the same pins and bushing eyes, but a $10 \times 10\,\mathrm{mm}$ shaft. With $1.2\,\mathrm{mm}$ walls only, a hollow square gives $I = (10^4 - 7.6^4)/12 \approx 555\,\mathrm{mm^4}$, more than seven times the upstream bar:

$$
F_\text{cr} = \frac{\pi^2 \cdot 1500\,\mathrm{MPa} \cdot 555\,\mathrm{mm^4}}{(131\,\mathrm{mm})^2} \approx 480\,\mathrm{N}
\qquad S \approx \frac{480}{192} \approx 2.5
$$

The gate measures the printed STL section by section and reports $S = 2.53$. A wider part also needs room: centred on the pin line, the link came within $0.25\,\mathrm{mm}$ of the femur at the stretched knee, so its shaft sits $2\,\mathrm{mm}$ off the pin line, away from the femur. Every neighbour keeps at least $1\,\mathrm{mm}$, and the joint limits did not change.

## Screws in shear and in printed holes

A screw that clamps two parts which try to slide past each other is loaded in **shear**. The stress is spread over the tensile stress area $A_s$ ($5.03\,\mathrm{mm^2}$ for M3). When a torque $T$ is carried by $n$ screws on a bolt circle of radius $r$:

$$
F = \frac{T}{n\,r}, \qquad \tau = \frac{F}{A_s}
$$

The kit's DIN 912 A2-70 stainless screws have a yield strength of $R_{p0.2} = 450\,\mathrm{MPa}$, so $\tau_\text{allow} = 0.577 \cdot 450 = 260\,\mathrm{MPa}$. The femur is bolted to its horn with $4 \times$ M3 on $r = 7\,\mathrm{mm}$:

$$
F = \frac{3.43}{4 \cdot 0.007} = 122\,\mathrm{N}, \qquad \tau = \frac{122}{5.03} = 24\,\mathrm{MPa}, \qquad S = 10.7
$$

The screw is rarely the problem. The plastic around it is. The **hole bearing pressure** is the force over the projected area of the hole (diameter $d$, material thickness $t$):

$$
p = \frac{F}{d\,t}
$$

For the hip horn screws in the servo mount this is $17.9\,\mathrm{MPa}$ against $47\,\mathrm{MPa}$ ($S = 2.6$), the lowest of the screw joints.

## Pull-out and tightening torque

A thread-forming screw in a printed pilot hole holds by the plastic thread it cuts. Pulled hard enough, it shears out a cylinder of plastic (*ausreißen*) of diameter $d$ and engaged length $L_e$. The shear strength across the layers is $\tau = 0.577 \cdot 18 = 10.4\,\mathrm{MPa}$:

$$
F_\text{pull} = \tau\,\pi\,d\,L_e
$$

Tightening turns torque into axial preload. Most of the torque goes into friction in the thread and under the head. The *nut factor* $k$ (about 0.2 for dry stainless threads) lumps all of that into one number:

$$
T = k\,F\,d
$$

So every printed pilot has a torque that strips it. Example: the knee axle screws engage $L_e = 4.0\,\mathrm{mm}$ of the femur:

$$
F_\text{pull} = 10.4 \cdot \pi \cdot 3 \cdot 4 = 392\,\mathrm{N}, \qquad T_\text{strip} = 0.2 \cdot 392\,\mathrm{N} \cdot 0.003\,\mathrm{m} = 0.24\,\mathrm{N\,m}
$$

**Tighten to at most half of that, about $0.12\,\mathrm{N\,m}$.** That is a gentle two-finger turn on the short arm of a 2.5 mm hex key: snug, not tight. The [strength report](../../verification/strength.md#tightening-torque-into-printed-pilots) lists the limit for every printed pilot (0.05–0.35 N·m). For comparison, an M3 A2-70 screw into a steel nut may take up to about $1.26\,\mathrm{N\,m}$ (Bossard, $\mu = 0.2$), ten times more.

## Bearings

Ball bearings have a **static load rating** $C_0$: the load that dents the races permanently. The static safety factor is $S_0 = C_0 / F_r$. The two knee bearings share the knee force (237 N: landing plus the largest link force). Each 633ZZ therefore sees $118\,\mathrm{N}$ against $C_0 = 490\,\mathrm{N}$ (Koyo), $S_0 = 4.2$.

Rotating bearings also wear out by fatigue. Their **rating life** in millions of revolutions follows from the dynamic rating $C$ and the equivalent load $P$:

$$
L_{10} = \left(\frac{C}{P}\right)^3 \quad [10^6\ \text{revolutions}]
$$

90 % of bearings reach this life. The knee joints only oscillate through a small angle, so the static rating matters more here. The kit's unbranded bearings are assumed no better than the branded ratings.

## Check yourself

1. A servo is rated 25 kg·cm. What force can it push through a 20 mm arm at right angles?
2. Why does a printed link lie flat on the bed rather than stand up?
3. You make a link 1.5 × thicker. How do its bending strength and its buckling load change?
4. What limits the bending moment in the legs, the landing or the servo?
5. A pilot hole engages 6 mm of an M3 screw. What is the maximum tightening torque by this page's rule?

<details>
<summary>Answers</summary>

1. $T = 25 \cdot 9.81 \cdot 0.01 = 2.45\,\mathrm{N\,m}$; $F = 2.45 / 0.020 = 123\,\mathrm{N}$.
2. So that bending stress runs along the layers ($47\,\mathrm{MPa}$) instead of across them ($18\,\mathrm{MPa}$ layer adhesion).
3. Bending across that thickness: $W \propto h^2$, so $2.25\times$. Buckling across it: $I \propto h^3$, so $3.4\times$.
4. The servo's stall torque is the design load: the knee gives way above it. Back-driving a geared servo takes more than its stall torque, so hard impacts can exceed the design load; pins and bearings always see the full landing force.
5. $F = 10.4 \cdot \pi \cdot 3 \cdot 6 = 588\,\mathrm{N}$; $T_\text{strip} = 0.2 \cdot 588 \cdot 0.003 = 0.35\,\mathrm{N\,m}$; tighten to at most about $0.18\,\mathrm{N\,m}$.

</details>

## Further reading

- R. C. Hibbeler, *Mechanics of Materials*: stress, bending, buckling, the textbook treatment of every formula above.
- [Prusament PETG technical data sheet](https://www.prusa3d.com/file/3464616/prusament-petg-technical-data-sheet.pdf): printed tensile and layer-adhesion values used here.
- [Bossard: preload and tightening torques (VDI 2230)](https://assets.eu.ctfassets.net/0vp0u5uh75zd/3S40LEUM235Qk3rJk2phR1/c715f9f45232756c12b59aa681c7fede/060_074_Preload_tightening_torques_Fastening_EN_01_2025.pdf).
- [SKF deep groove ball bearings](https://www.skf.com/group/products/rolling-bearings/ball-bearings/deep-groove-ball-bearings): load ratings, static safety and rating life.
- Related in this wiki: [statics and dynamics](../theory/statics-and-dynamics.md), [fasteners](fasteners.md), [3D printing](3d-printing.md), [mechanics and bearings](../hardware/mechanics.md), [servos](../hardware/servos.md).
