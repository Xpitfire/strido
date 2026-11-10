# Reinforcement learning for locomotion

How a walking controller can be learned by trial and error in simulation: Markov decision processes, returns and value functions, the policy-gradient theorem, GAE, PPO, and the exact observation, action and reward used for Strido, plus how domain randomisation narrows the sim-to-real gap.

::: tip In Strido
The environment is `StridoEnv` in `packages/strido-sim/src/strido_sim/rl/env.py` (Gymnasium + MuJoCo); training is `rl/train.py` (stable-baselines3 PPO on CPU). Shared constants (`CONTROL_DT`, `ACTION_SCALE`, `COMMAND_RANGES`) live in `packages/strido-core/src/strido/policy.py`, and the robot runs the exported network in `ros2/strido_control/strido_control/policy_node.py`. Workflow: [Simulation and RL](../software/simulation-and-rl.md) and [docs/simulation.md](../../simulation.md).
:::

## The Markov decision process

An MDP is a tuple $(\mathcal{S}, \mathcal{A}, P, r, \gamma)$: states, actions, transition probabilities $P(s' \mid s, a)$, reward $r(s, a)$ and discount $\gamma \in [0, 1)$. At each step the agent observes $s_t$, samples $a_t \sim \pi_\theta(a \mid s_t)$ from a **policy** with parameters $\theta$ (a neural network), and the environment returns $r_t$ and $s_{t+1}$. *Markov* means $s_{t+1}$ depends only on $(s_t, a_t)$, not on earlier history. A real robot only sees part of the state (a POMDP); in practice we add enough history (here, the previous action and a gait clock) to make the observation nearly Markov.

## Returns and discounting

The **return** from time $t$ is the discounted sum of future rewards:

$$
G_t = \sum_{k=0}^{\infty} \gamma^k\, r_{t+k}
$$

Discounting keeps the sum finite and expresses a preference for sooner reward. The effective horizon is about $1/(1-\gamma)$ steps. **Worked example:** Strido trains with $\gamma = 0.99$ (`train.py`) at a policy rate of $50\,\mathrm{Hz}$ ($\Delta t = 0.02\,\mathrm{s}$), so the horizon is about $100$ steps $= 2\,\mathrm{s}$, i.e. five gait cycles of $0.4\,\mathrm{s}$: long enough to value not falling over, short enough to learn quickly.

The objective is the expected return $J(\theta) = \mathbb{E}_{\tau \sim \pi_\theta}[G_0]$ over trajectories $\tau$.

## Value functions

$$
V^\pi(s) = \mathbb{E}_\pi[G_t \mid s_t = s], \qquad Q^\pi(s, a) = \mathbb{E}_\pi[G_t \mid s_t = s, a_t = a]
$$

They satisfy the **Bellman equation**

$$
V^\pi(s) = \mathbb{E}_{a \sim \pi,\, s' \sim P}\left[ r(s, a) + \gamma V^\pi(s') \right]
$$

The **advantage** $A^\pi(s, a) = Q^\pi(s, a) - V^\pi(s)$ measures how much better action $a$ is than the policy's average in state $s$.

## The policy-gradient theorem

We want $\nabla_\theta J$ without differentiating through the (unknown, non-differentiable) physics. The likelihood-ratio trick gives

$$
\nabla_\theta J(\theta) = \mathbb{E}_{\pi_\theta}\left[ \sum_t \nabla_\theta \log \pi_\theta(a_t \mid s_t)\, A^{\pi}(s_t, a_t) \right]
$$

In words: increase the log-probability of actions that turned out better than average, decrease it for worse ones. Only samples from the simulator and the gradient of the network's own log-probability are needed. Using the advantage (rather than $G_t$) subtracts a baseline $V(s)$, which leaves the gradient unbiased but greatly reduces its variance.

## Generalised advantage estimation (GAE)

The advantage is estimated from a learned critic $V_\phi$. The one-step **TD error** is

$$
\delta_t = r_t + \gamma V_\phi(s_{t+1}) - V_\phi(s_t)
$$

GAE takes an exponentially weighted sum of these:

$$
\hat{A}_t = \sum_{l=0}^{\infty} (\gamma \lambda)^l\, \delta_{t+l}
$$

$\lambda = 0$ gives the low-variance but biased one-step estimate; $\lambda = 1$ gives the unbiased but high-variance Monte Carlo return minus $V$. Strido uses $\lambda = 0.95$ (`gae_lambda` in `train.py`). On termination (a fall) the bootstrap $V_\phi(s_{t+1})$ is zero; on time-limit truncation it is kept, since the robot could have continued.

## PPO: proximal policy optimisation

Plain policy gradient takes one step per batch, and a step that is too large can wreck the policy. PPO reuses each batch for several epochs while preventing the new policy from drifting far from the one that collected the data. With the probability ratio

$$
\rho_t(\theta) = \frac{\pi_\theta(a_t \mid s_t)}{\pi_{\theta_\mathrm{old}}(a_t \mid s_t)}
$$

the **clipped surrogate objective** is

$$
L^\mathrm{CLIP}(\theta) = \mathbb{E}_t\left[ \min\left( \rho_t \hat{A}_t,\; \operatorname{clip}(\rho_t, 1 - \epsilon, 1 + \epsilon)\, \hat{A}_t \right) \right]
$$

For a good action ($\hat{A} > 0$) the gain stops once $\rho > 1 + \epsilon$; for a bad one ($\hat{A} < 0$) once $\rho < 1 - \epsilon$. The $\min$ makes it a pessimistic bound, so there is no incentive to move further. The full loss adds a critic regression term and, optionally, an entropy bonus that rewards keeping the policy random enough to explore:

$$
L(\theta, \phi) = -L^\mathrm{CLIP}(\theta) + c_1\, \mathbb{E}_t\left[ \left( V_\phi(s_t) - \hat{G}_t \right)^2 \right] - c_2\, \mathbb{E}_t\left[ \mathcal{H}\left( \pi_\theta(\cdot \mid s_t) \right) \right]
$$

For continuous actions the policy is a diagonal Gaussian $\pi_\theta(a \mid s) = \mathcal{N}(\mu_\theta(s), \operatorname{diag}(\boldsymbol{\sigma}^2))$; at deployment the mean $\mu_\theta(s)$ is used.

**Strido's settings** (`train.py`): $\epsilon = 0.2$, $\gamma = 0.99$, $\lambda = 0.95$, learning rate $3 \times 10^{-4}$, $1024$ steps per environment per rollout, minibatch $2048$, 5 epochs per rollout, $c_2 = 0$ (`ent_coef=0.0`: exploration comes only from the Gaussian's own spread, `log_std_init=-1.0`), $2 \times 10^7$ total steps by default. Observations and rewards are normalised with running statistics (`VecNormalize`, observations clipped at $\pm 10$); the normaliser's mean and variance are exported with the weights so the robot applies the same scaling.

**Worked example.** Suppose an action had $\hat{A}_t = 0.5$ and after an update $\rho_t = 1.35$. Unclipped the term would be $0.675$; clipped it is $1.2 \times 0.5 = 0.6$, and the gradient through this sample is zero, so PPO stops pushing that action's probability up.

## The Strido environment

**Timing.** Policy at $50\,\mathrm{Hz}$ (`CONTROL_DT = 0.02`), physics at $500\,\mathrm{Hz}$ (10 substeps). Episodes last at most $1000$ steps ($20\,\mathrm{s}$). Servos are modelled as MJCF position actuators with a $3.43\,\mathrm{N\,m}$ torque limit (SPT5435LV stall torque at $6\,\mathrm{V}$).

**Observation** ($23$ values, `OBSERVATION_SIZE`):

$$
\mathbf{o}_t = \left[ \boldsymbol{\omega}_b,\; \mathbf{g}_b,\; \mathbf{c},\; \mathbf{a}_{t-1},\; \sin\varphi_t,\; \cos\varphi_t \right] \in \mathbb{R}^{3+3+3+12+2}
$$

- $\boldsymbol{\omega}_b$: body angular velocity from the IMU gyro;
- $\mathbf{g}_b = \mathbf{R}^\top (0, 0, -1)^\top$: the unit gravity direction in the base frame, from the IMU quaternion (encodes roll and pitch, not yaw);
- $\mathbf{c} = (v_x, v_y, \omega_z)$: the velocity command, sampled per episode from $v_x \in [-0.15, 0.30]\,\mathrm{m/s}$, $v_y \in [-0.10, 0.10]\,\mathrm{m/s}$, $\omega_z \in [-0.6, 0.6]\,\mathrm{rad/s}$, and zero with probability $0.2$;
- $\mathbf{a}_{t-1}$: the previous action;
- a gait clock $\varphi_t = 2\pi t / T$ with $T = 0.4\,\mathrm{s}$ (`GAIT_PERIOD_S`), matching the scripted trot.

Every input is available on the real robot from `/imu/data` and `/cmd_vel`; there is no base velocity or joint feedback (the servos have none).

**Action.** $\mathbf{a}_t \in [-1, 1]^{12}$ are offsets from the stand pose $\mathbf{q}_0$:

$$
\mathbf{q}^\mathrm{target}_t = \operatorname{clamp}\left( \operatorname{slew}\left( \mathbf{q}_0 + 0.3\, \mathbf{a}_t \right) \right)
$$

`ACTION_SCALE` $= 0.3\,\mathrm{rad}$; `slew_limit` caps joint speed at $6\,\mathrm{rad/s}$ (the firmware's limit), and `clamp_targets` applies the joint and knee-crank limits in the same order as the firmware, so the policy never learns to rely on motions the robot would refuse.

**Reward.** With base-frame linear velocity $\mathbf{v}_b$, angular velocity $\boldsymbol{\omega}_b$, actuator forces $\boldsymbol{\tau}$ and base height $z$:

$$
\begin{aligned}
r_t ={}& 1.0\, \exp\left( -\frac{\lVert \mathbf{v}_b^{xy} - \mathbf{c}^{xy} \rVert^2}{0.01} \right) + 0.8\, \exp\left( -\frac{(\omega_{b,z} - c_{\omega})^2}{0.05} \right) \\
&- 2.0\, v_{b,z}^2 - 0.05\, \lVert \boldsymbol{\omega}_b^{xy} \rVert^2 - 0.01\, \lVert \mathbf{a}_t - \mathbf{a}_{t-1} \rVert^2 - 0.002\, \lVert \boldsymbol{\tau} \rVert^2 - 2.0 \max(0,\, 0.15 - z)
\end{aligned}
$$

The two exponential terms reward tracking the command (at most $1.8$ per step); the penalties discourage bouncing, wobbling, jerky actions, high torque (heat, battery) and crouching below $0.15\,\mathrm{m}$. The code multiplies by `CONTROL_DT * 50`, which equals $1$ at $50\,\mathrm{Hz}$.

**Termination.** The episode ends with a $-2$ penalty when the base drops below $0.09\,\mathrm{m}$ or the body tilts so that $-g_{b,z} < 0.6$ (about $53^\circ$ roll or pitch).

**Worked example.** Commanded $v_x = 0.20\,\mathrm{m/s}$, achieved $0.15\,\mathrm{m/s}$: the tracking term is $\exp(-0.05^2/0.01) = \exp(-0.25) \approx 0.78$. The width $0.01$ means errors around $0.1\,\mathrm{m/s}$ already cost most of the reward ($\exp(-1) \approx 0.37$).

## Domain randomisation and the sim-to-real gap

A policy that exploits simulator quirks fails on hardware: the **sim-to-real gap**. Sources include unmodelled servo dynamics and backlash, friction, mass and inertia errors, sensor noise and latency. **Domain randomisation** trains on a distribution of simulators so the real robot is, hopefully, just one more sample:

$$
\max_\theta\; \mathbb{E}_{\xi \sim p(\xi)}\left[ J_\xi(\theta) \right]
$$

where $\xi$ are physics parameters. `StridoEnv._randomise` samples per episode:

| Parameter | Range |
|---|---|
| servo stiffness $k_p$ | $\times\, U(0.85, 1.15)$ |
| base mass | $\times\, U(0.90, 1.15)$ |
| floor and foot friction | $\times\, U(0.6, 1.2)$ |
| gyro noise | $\mathcal{N}(0, 0.05^2)$ per step |
| gravity-vector noise | $\mathcal{N}(0, 0.02^2)$ per step |
| initial joint angles | $\mathbf{q}_0 + \mathcal{N}(0, 0.02^2)$ |

Because the policy cannot identify which $\xi$ it is in from a single observation, it learns behaviour that is robust across all of them. Other tools against the gap (not all used here): actuator models fitted to measured servo responses, observation latency, push perturbations, and terrain curricula.

## Check yourself

1. What is the effective horizon in seconds for $\gamma = 0.99$ at $50\,\mathrm{Hz}$, and what if the policy ran at $100\,\mathrm{Hz}$ with the same $\gamma$?
   <details><summary>Answer</summary>

   About $100$ steps $= 2\,\mathrm{s}$; at $100\,\mathrm{Hz}$ it halves to $1\,\mathrm{s}$, so $\gamma$ should rise to about $0.995$ to keep the same horizon.

   </details>
2. Why does subtracting $V(s)$ in the policy gradient not bias it?
   <details><summary>Answer</summary>

   $\mathbb{E}_{a \sim \pi}[\nabla_\theta \log \pi_\theta(a \mid s)] = \nabla_\theta \sum_a \pi_\theta(a \mid s) = \nabla_\theta 1 = 0$, so any state-only baseline has zero expected contribution.

   </details>
3. With $\epsilon = 0.2$ and $\hat{A}_t < 0$, for which $\rho_t$ does the PPO term stop giving a gradient?
   <details><summary>Answer</summary>

   For $\rho_t < 0.8$: the action's probability has already been reduced enough.

   </details>
4. Why does the observation contain the gravity direction rather than Euler angles including yaw?
   <details><summary>Answer</summary>

   Walking does not depend on heading, and yaw from a magnetometer-less IMU drifts; the gravity vector is drift-free and continuous.

   </details>
5. Name two sim-to-real effects not covered by Strido's randomisation.
   <details><summary>Answer</summary>

   For example sensor and actuation latency, servo backlash or deadband, external pushes, uneven terrain.

   </details>

## Further reading

- R. S. Sutton and A. G. Barto, *Reinforcement Learning: An Introduction*, 2nd ed., MIT Press, 2018.
- J. Schulman, F. Wolski, P. Dhariwal, A. Radford and O. Klimov, "Proximal Policy Optimization Algorithms", arXiv:1707.06347, 2017.
- J. Schulman, P. Moritz, S. Levine, M. Jordan and P. Abbeel, "High-Dimensional Continuous Control Using Generalized Advantage Estimation", *ICLR*, 2016.
- J. Tobin et al., "Domain Randomization for Transferring Deep Neural Networks from Simulation to the Real World", *IROS*, 2017.
- J. Hwangbo et al., "Learning agile and dynamic motor skills for legged robots", *Science Robotics*, 2019.
