# Statics and dynamics

Statics asks which joint torques hold a load still. Dynamics adds the torques that accelerate masses. Together they tell you whether a servo is strong enough and how hard each part is loaded. This page derives $\boldsymbol{\tau} = \mathbf{J}^\top\mathbf{F}$ from virtual work, explains the leverage of the Strido knee linkage, and compares the torque the robot needs with the torque its servos can give.

::: tip In Strido
- **Servo limits:** SPT5435LV-180W, stall torque $3.43\,\mathrm{N\,m}$ at $6\,\mathrm{V}$ (`hardware/strength.yaml`), no-load speed $0.14\,\mathrm{s}/60^\circ$ ([servos](../hardware/servos.md)).
- **Mass:** $3.07\,\mathrm{kg}$ including the battery and the wiring harness; per-link masses in `ros2/strido_description/config/mass_report.yaml`.
- **Linkage forces:** `packages/strido-verify/src/strido_verify/strength.py` sweeps the knee linkage at stall. Results are in `docs/verification/data/strength.json`, explained in [strength](../making/strength.md).
- **Simulation:** MuJoCo clamps every actuator to $\pm 3.432\,\mathrm{N\,m}$ (`models/mujoco/strido.xml`).
:::

## Virtual work and $\boldsymbol{\tau} = \mathbf{J}^\top \mathbf{F}$

Suppose the foot pushes on the ground with force $\mathbf{F}$, and the ground pushes back with $-\mathbf{F}$. Hold the leg still and imagine a tiny joint motion $\delta\mathbf{q}$. The foot moves by $\delta\mathbf{p} = \mathbf{J}\,\delta\mathbf{q}$ (see [kinematics](kinematics.md)). In equilibrium, with no friction, the work done by the joints equals the work delivered at the foot:

$$
\boldsymbol{\tau}^\top \delta\mathbf{q} = \mathbf{F}^\top \delta\mathbf{p} = \mathbf{F}^\top \mathbf{J}\,\delta\mathbf{q}
$$

This must hold for every $\delta\mathbf{q}$, so:

$$
\boldsymbol{\tau} = \mathbf{J}^\top \mathbf{F}
$$

Two consequences:

- At a **singularity**, $\mathbf{J}$ loses rank. Some foot forces then need no joint torque at all: a straight leg carries a load along its length "on the bones". At the same time, the leg cannot push in the lost direction.
- Velocity gain and force gain trade off. Where a joint moves the foot fast (large Jacobian entries), it pushes weakly, and the other way round.

The same argument works for any mechanism with one input and one output. If the output angle changes by $\delta\theta_{\text{out}} = G\,\delta\theta_{\text{in}}$, then the output torque is $\tau_{\text{out}} = \tau_{\text{in}}/G$.

## Mechanical advantage of the knee drive

The knee servo reaches the tibia through two linkages (see [kinematics](kinematics.md)). For a link that carries force $F$ along its length, only the perpendicular part of $F$ acts on a crank of radius $r$:

$$
\tau = F\,r\,\sin\alpha
$$

Here $\alpha$ is the angle between the crank and the link. `strength.py` chains this rule through the drive:

$$
F_{\text{short}} = \frac{\tau_{\text{servo}}}{r_{\text{arm}}\sin\alpha},\qquad
\tau_{\text{crank}} = F_{\text{short}}\, r_{\text{crank,a}}\sin\alpha',\qquad
F_{\text{long}} = \frac{\tau_{\text{crank}}}{r_{\text{crank,b}}\sin\beta},\qquad
\tau_{\text{knee}} = F_{\text{long}}\, r_{\text{knee}}\sin\gamma
$$

- **Parallelogram.** Opposite sides are equal ($r_{\text{arm}} = r_{\text{crank,a}} = 24.0\,\mathrm{mm}$), so $\alpha' = \alpha$ and $\tau_{\text{crank}} = \tau_{\text{servo}}$. The ratio is $1{:}1$. The link force $F_{\text{short}}$, however, grows as $1/\sin\alpha$.
- **Four-bar.** The torque ratio is
  $$
  \frac{\tau_{\text{knee}}}{\tau_{\text{crank}}} = \frac{r_{\text{knee}}\sin\gamma}{r_{\text{crank,b}}\sin\beta}
  $$
  and it changes with the pose. When the transmission angle $\beta$ or $\gamma$ approaches $0$ or $180^\circ$, the forces become very large or the drive loses all leverage. That is why the joint limits require at least $25^\circ$ (`hardware/joint_limits.yaml`).

Sweeping every pose inside the limits with the knee servo at stall, the worst cases (`docs/verification/data/strength.json`) are $211\,\mathrm{N}$ in the short link, $192\,\mathrm{N}$ in the long link and $3.07\,\mathrm{N\,m}$ at the knee.

## Dynamics: inertia and Newton–Euler

Moving bodies need more torque. For a single rigid body, the **Newton–Euler** equations are:

$$
\mathbf{F} = m\,\ddot{\mathbf{c}}, \qquad
\boldsymbol{\tau}_c = \mathbf{I}_c\,\dot{\boldsymbol{\omega}} + \boldsymbol{\omega}\times\mathbf{I}_c\,\boldsymbol{\omega}
$$

Here $\mathbf{c}$ is the centre of mass and $\mathbf{I}_c$ the $3\times 3$ inertia tensor about it. For a link turning about a fixed axis, the parallel-axis theorem gives the inertia about the axis, $I = I_c + m r_c^2$, with $r_c$ the distance from the axis to the centre of mass. Then $\tau = I\ddot\theta$.

Chaining Newton–Euler through every link yields the standard manipulator equation:

$$
\mathbf{M}(\mathbf{q})\,\ddot{\mathbf{q}} + \mathbf{C}(\mathbf{q},\dot{\mathbf{q}})\,\dot{\mathbf{q}} + \mathbf{g}(\mathbf{q}) = \boldsymbol{\tau} + \mathbf{J}^\top\mathbf{F}_{\text{ext}}
$$

The terms are: the mass matrix $\mathbf{M}$, the Coriolis and centrifugal terms $\mathbf{C}$, gravity $\mathbf{g}$, and contact forces through $\mathbf{J}^\top$. MuJoCo solves exactly this every $2\,\mathrm{ms}$. Each Strido joint also has `armature="0.012"` ($\mathrm{kg\,m^2}$) added to its diagonal of $\mathbf{M}$. Armature models the gearbox: a rotor of inertia $I_r$ behind a reduction $N$ appears at the output as $N^2 I_r$.

## Power and the torque–speed line

Mechanical power is $P = \tau\,\omega$. A DC servo motor roughly follows a straight torque–speed line. It gives full stall torque $\tau_s$ at zero speed and zero torque at no-load speed $\omega_0$:

$$
\tau(\omega) \approx \tau_s\left(1 - \frac{\omega}{\omega_0}\right)
\quad\Rightarrow\quad
P(\omega) = \tau_s\,\omega\left(1-\frac{\omega}{\omega_0}\right),\qquad P_{\max} = \frac{\tau_s\,\omega_0}{4}\ \text{at}\ \omega = \tfrac{\omega_0}{2}
$$

For the SPT5435LV at $6\,\mathrm{V}$:

$$
\omega_0 = \frac{\pi/3}{0.14\,\mathrm{s}} = 7.48\,\mathrm{rad/s},\qquad
P_{\max} \approx \frac{3.43 \cdot 7.48}{4} = 6.4\,\mathrm{W}
$$

The linear line is a model; the datasheet gives only the two end points. A servo can deliver full torque or full speed, never both at once. The firmware caps joint speed at $6\,\mathrm{rad/s}$ (`MAX_JOINT_SPEED_RAD_S` in `strido/policy.py`, mirroring `safety.h`). At that speed the line leaves only about $3.43\,(1 - 6/7.48) \approx 0.68\,\mathrm{N\,m}$.

## Worked example: holding the stand pose

At the stand pose ($q_2 = 46.5^\circ$, $q_3 = -96.0^\circ$, foot straight below the hip, $0.17\,\mathrm{m}$ down), the planar Jacobian is (see [kinematics](kinematics.md)):

$$
\mathbf{J}_{\text{plane}} = \begin{bmatrix} -0.170 & -0.0806 \\ 0 & -0.0943 \end{bmatrix}\mathrm{m/rad}
$$

With four feet down, each foot carries a quarter of the weight:

$$
F_v = \frac{3.07 \cdot 9.81}{4} = 7.53\,\mathrm{N}
$$

The foot pushes down on the ground, so with the convention above $\mathbf{F} = (0, -7.53)\,\mathrm{N}$ in $(u, v)$ (the ground pushes back with $+7.53\,\mathrm{N}$). The joint torques that hold it are:

$$
\boldsymbol{\tau} = \mathbf{J}^\top\mathbf{F} =
\begin{bmatrix} -0.170 & 0 \\ -0.0806 & -0.0943 \end{bmatrix}
\begin{bmatrix} 0 \\ -7.53 \end{bmatrix}
= \begin{bmatrix} 0 \\ 0.71 \end{bmatrix}\mathrm{N\,m}
$$

The thigh needs no torque, because the foot is straight under its pivot and the load passes through the joint. The knee needs $+0.71\,\mathrm{N\,m}$, matching MuJoCo, where the front-left knee actuator holds the stand pose with $0.688\,\mathrm{N\,m}$ (see also [servos](../hardware/servos.md)).

Through the four-bar, $\partial q_3/\partial\psi = -1.12$ at this pose. Virtual work then gives the knee-servo torque:

$$
\tau_\psi = \tau_{q_3}\,\frac{\partial q_3}{\partial \psi} = 0.71 \cdot 1.12 = 0.80\,\mathrm{N\,m}
$$

As a cross-check, the lever-arm rule with the transmission angles $84^\circ$ and $86^\circ$ gives a ratio of $\frac{24.0\,\sin 86^\circ}{26.9\,\sin 84^\circ} = 0.89 \approx 1/1.12$. The knee servo's $0.80\,\mathrm{N\,m}$ is about $23\,\%$ of its $3.43\,\mathrm{N\,m}$ stall torque. A trot puts the weight on two feet instead of four, roughly doubling the load to about $1.6\,\mathrm{N\,m}$, which still leaves about a factor of two for accelerations and stumbles.

**Dynamics check.** The calf weighs $0.0521\,\mathrm{kg}$ with its centre of mass about $48\,\mathrm{mm}$ from the knee. That gives $m r_c^2 \approx 1.2\times10^{-4}\,\mathrm{kg\,m^2}$; with the calf's own inertia about its centre of mass ($1.5\times10^{-4}$, `mass_report.yaml`) the knee sees about $2.7\times10^{-4}\,\mathrm{kg\,m^2}$, roughly $1/44$ of the modelled armature. Swinging a light leg is therefore limited by speed and by the servo's own rotor, not by the link's inertia.

**Landing.** `strength.py` assumes a hard landing of $3\times$ body weight on one diagonal pair:

$$
F = \frac{3 \cdot 3.07 \cdot 9.81}{2} = 45.2\,\mathrm{N}
$$

per foot. Acting on the $124\,\mathrm{mm}$ tibia, that is $5.60\,\mathrm{N\,m}$ at the knee, more than stall. So a landing back-drives the servo, and the printed parts must take it. See [strength](../making/strength.md).

## Check yourself

1. Derive $\boldsymbol{\tau} = \mathbf{J}^\top\mathbf{F}$ in one line from virtual work.
2. Why does the parallelogram not change the torque, yet can still overload the short link?
3. Why does the thigh need almost no torque in the stand pose?
4. Can the servo deliver $3.43\,\mathrm{N\,m}$ while turning at $6\,\mathrm{rad/s}$?

<details><summary>Answers</summary>

1. $\boldsymbol{\tau}^\top\delta\mathbf{q} = \mathbf{F}^\top\mathbf{J}\,\delta\mathbf{q}$ for all $\delta\mathbf{q}$, so $\boldsymbol{\tau} = \mathbf{J}^\top\mathbf{F}$.
2. Its input and output cranks are equal, so the $\sin\alpha$ terms cancel in the torque ratio. The link force is $\tau/(r\sin\alpha)$, though, and it grows without bound as $\alpha \to 0$.
3. The foot is directly below the thigh pivot ($u = 0$), so the vertical force has no lever arm about it. In the Jacobian, $J_{21} = 0$.
4. No. Under the linear model, about $0.7\,\mathrm{N\,m}$ is left at $6\,\mathrm{rad/s}$. Stall torque exists only at zero speed.

</details>

## Further reading

- K. M. Lynch and F. C. Park, *Modern Robotics*, Cambridge University Press, 2017, ch. 5.2 (statics) and ch. 8 (dynamics of open chains).
- R. Featherstone, *Rigid Body Dynamics Algorithms*, Springer, 2008.
- B. Siciliano et al., *Robotics: Modelling, Planning and Control*, Springer, 2009, ch. 3.8 and 7.
- R. L. Norton, *Design of Machinery*, McGraw-Hill (linkage force analysis, transmission angle).
- [Strength of the printed parts](../making/strength.md) and [servos](../hardware/servos.md) in this wiki.
