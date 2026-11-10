"""Train a velocity-tracking walking policy for Strido with PPO (stable-baselines3, CPU).

    make rl-train                                     # 20 M steps, 8 envs
    python -m strido_sim.rl.train --smoke            # 20 k steps, checks the pipeline

Outputs build/rl/<run>/: policy.zip (SB3), policy.npz (plain MLP weights for the robot's
numpy policy node), vecnormalize.pkl, progress.csv.
"""

import argparse
import time
from pathlib import Path

import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.logger import configure
from stable_baselines3.common.vec_env import SubprocVecEnv, VecNormalize

from strido.workspace import build_dir

from .env import StridoEnv


def export_numpy(model: PPO, normaliser: VecNormalize, path: Path) -> None:
    """Deterministic actor as plain arrays: obs -> normalise -> tanh MLP -> linear head."""
    weights = {}
    layers = [m for m in model.policy.mlp_extractor.policy_net if hasattr(m, "weight")]
    for index, layer in enumerate(layers):
        weights[f"w{index}"] = layer.weight.detach().cpu().numpy()
        weights[f"b{index}"] = layer.bias.detach().cpu().numpy()
    weights["w_out"] = model.policy.action_net.weight.detach().cpu().numpy()
    weights["b_out"] = model.policy.action_net.bias.detach().cpu().numpy()
    weights["obs_mean"] = normaliser.obs_rms.mean.astype(np.float32)
    weights["obs_var"] = normaliser.obs_rms.var.astype(np.float32)
    weights["obs_clip"] = np.array(normaliser.clip_obs, dtype=np.float32)
    np.savez(path, **weights)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timesteps", type=int, default=20_000_000)
    parser.add_argument("--envs", type=int, default=8)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--run", default=None)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if args.smoke:
        args.timesteps, args.envs = 20_000, 2
    run = args.run or time.strftime("ppo-%Y%m%d-%H%M%S")
    out = build_dir("rl", run)
    venv = make_vec_env(
        StridoEnv, n_envs=args.envs, seed=args.seed, vec_env_cls=SubprocVecEnv if args.envs > 1 else None
    )
    venv = VecNormalize(venv, norm_obs=True, norm_reward=True, clip_obs=10.0)
    model = PPO(
        "MlpPolicy",
        venv,
        seed=args.seed,
        n_steps=1024 if not args.smoke else 256,
        batch_size=2048 if not args.smoke else 256,
        n_epochs=5,
        learning_rate=3e-4,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.0,
        policy_kwargs={"net_arch": {"pi": [128, 128], "vf": [256, 256]}, "log_std_init": -1.0},
        verbose=0,
        device="cpu",
    )
    model.set_logger(configure(str(out), ["csv", "stdout"]))
    started = time.time()
    model.learn(total_timesteps=args.timesteps, progress_bar=False)
    model.save(out / "policy.zip")
    venv.save(str(out / "vecnormalize.pkl"))
    export_numpy(model, venv, out / "policy.npz")
    print(f"trained {args.timesteps} steps in {time.time() - started:.0f} s -> {out}")


if __name__ == "__main__":
    main()
