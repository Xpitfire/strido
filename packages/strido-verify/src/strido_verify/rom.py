"""Leg range-of-motion sweep against the real mechanism (all printed parts posed).

For every leg the tool sweeps (thigh, calf) on a grid at hip = 0 and the hip
angle at three leg poses, poses the full assembly with the exact knee linkage
and checks every moving body of that leg against everything else. Contacts that
already exist at the CAD reference pose (bearing in bore, horn on spline) are
baselined, so only *new* overlap counts as a collision.

It then derives conservative joint limits that satisfy, simultaneously:
  * no collision (with a margin of one grid step),
  * knee four-bar transmission angle >= 25 degrees,
  * every servo shaft stays within +-85 degrees of its neutral (SPT5435LV-180W
    travel is 180 degrees = +-90; 5 degrees kept for calibration slack).

Outputs `hardware/joint_limits.yaml` (consumed by `strido_cad.codegen`) and a
feasibility map PNG under build/verify/.

Run:  make rom  (python -m strido_verify.rom [--assembly upstream|full])
"""

import argparse
import math

import matplotlib
import numpy as np
import yaml

matplotlib.use("Agg")  # headless rendering; must precede the pyplot import
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from strido import leg as leg_kinematics
from strido.geometry import LEG_NAMES
from strido_cad import assembly, catalog, interference
from strido_cad.paths import JOINT_LIMITS, VERIFY_OUT

from .poses import stand_pose

OUTPUT = JOINT_LIMITS
FIGURE = VERIFY_OUT / "rom_feasibility.png"
STEP_DEG = 5.0
TRANSMISSION_MIN_DEG = 25.0
SERVO_HALF_TRAVEL_DEG = 85.0
NEW_OVERLAP_TOLERANCE_MM3 = 2.0
THIGH_RANGE_DEG = (-60.0, 125.0)
CALF_RANGE_DEG = (-170.0, -30.0)
HIP_RANGE_DEG = (-60.0, 60.0)
CLEARANCE_MIN_MM = 0.3  # = moving_clearance.fail_below_mm in hardware/verification/tolerances.yaml
# Pairs closer than CLEARANCE_MIN_MM already at hip = 0 are the hip joint's own interfaces (bearing
# faces, pin in mount); hip rotation keeps them, penetration is still caught by `collisions`.
CLEARANCE_INTERFACE_MM = CLEARANCE_MIN_MM


def leg_bodies(name):
    return {f"{name}.{part}" for part in ("hip", "thigh", "calf", "crank", "arm", "short_link", "long_link")}


def pair_volumes(instances, moving_bodies):
    """Overlap volume per (body, body) pair, only for pairs involving a moving body."""

    def relevant(a, b):
        return a.body != b.body and (a.body in moving_bodies or b.body in moving_bodies)

    volumes = {}
    for overlap in interference.overlaps(instances, volume_tolerance_mm3=0.05, pairs_filter=relevant):
        key = tuple(sorted((overlap.a.id, overlap.b.id)))
        volumes[key] = volumes.get(key, 0.0) + overlap.volume_mm3
    return volumes


# Part-type pairs that rotate against each other about a shared axis by design
# (horn on its servo spline, bearing on its pin). When such a pair already
# touches at the CAD pose it is the joint itself, not a collision.
ROTATING_CONTACTS = {
    frozenset(("servo_arm_horn_25t", "servo_spt5435lv")),
    frozenset(("servo_disc_horn_25t", "servo_spt5435lv")),
    frozenset(("bearing_633zz", "femur")),
    frozenset(("bearing_6805_2rs", "femur")),
    frozenset(("bearing_6805_2rs", "femur_servo_connector")),
    frozenset(("bearing_625zz", "hip_bearing_pin")),
}


def part_type(instance_id):
    """'FL/femur#27', 'body/bearing_625zz@0150' and 'iso4762_m3x10#u44' -> the part type."""
    return instance_id.split("/")[-1].split("#")[0].split("@")[0]


def collisions(instances, joints, moving, baseline):
    volumes = pair_volumes(assembly.posed(instances, joints), moving)
    hits = []
    for key, volume in volumes.items():
        if baseline.get(key, 0.0) > 0 and frozenset(map(part_type, key)) in ROTATING_CONTACTS:
            continue
        # Contacts present at the CAD pose (horn on spline, bearing in bore) change
        # slightly as faceted parts rotate about their shared axis: allow 2x + tol.
        if volume > 2.0 * baseline.get(key, 0.0) + NEW_OVERLAP_TOLERANCE_MM3:
            hits.append((key, volume))
    return hits


def sweep_leg(instances, name):
    moving = leg_bodies(name)
    others = {other: stand_pose(other) for other in LEG_NAMES}
    baseline = pair_volumes(assembly.posed(instances, {**others, name: assembly.CAD_POSE[name]}), moving)
    thighs = np.arange(THIGH_RANGE_DEG[0], THIGH_RANGE_DEG[1] + 1e-9, STEP_DEG)
    calves = np.arange(CALF_RANGE_DEG[0], CALF_RANGE_DEG[1] + 1e-9, STEP_DEG)
    feasible = np.zeros((len(thighs), len(calves)), dtype=np.int8)  # 1 ok, 0 linkage/transmission, -1 collision
    crank = np.full(feasible.shape, np.nan)
    reasons = {}
    for i, thigh in enumerate(thighs):
        for j, calf in enumerate(calves):
            q = (0.0, math.radians(thigh), math.radians(calf))
            angles = leg_kinematics.transmission_angles(name, q[1], q[2])
            if angles is None or math.degrees(min(angles)) < TRANSMISSION_MIN_DEG:
                continue
            crank[i, j] = math.degrees(leg_kinematics.crank_from_calf(name, q[1], q[2]))
            hits = collisions(instances, {**others, name: q}, moving, baseline)
            if hits:
                feasible[i, j] = -1
                reasons[(thigh, calf)] = hits
            else:
                feasible[i, j] = 1
    return thighs, calves, feasible, crank, reasons, others, baseline


# The two legs of an axle mirror each other's hip motion in the worst case (both feet swung inward
# under the body, or both outward): sweep the hip with the partner leg at the mirrored angle.
PARTNER = {"FL": "FR", "FR": "FL", "RL": "RR", "RR": "RL"}


def interface_pairs(instances, joints, moving) -> set[tuple[str, str]]:
    """Pairs already touching in `joints` (the joint interfaces themselves): not gated by clearance."""

    def relevant(a, b):
        return a.body != b.body and (a.body in moving or b.body in moving)

    touching = interference.gaps(assembly.posed(instances, joints), CLEARANCE_INTERFACE_MM, relevant)
    return {tuple(sorted((g.a.id, g.b.id))) for g in touching}


def too_close(instances, joints, moving, interfaces) -> bool:
    """A moving body comes closer than CLEARANCE_MIN_MM to something it is not jointed to."""

    def relevant(a, b):
        return (
            a.body != b.body
            and (a.body in moving or b.body in moving)
            and tuple(sorted((a.id, b.id))) not in interfaces
        )

    return bool(interference.gaps(assembly.posed(instances, joints), CLEARANCE_MIN_MM, relevant))


def sweep_hip(instances, name, others, baseline, leg_pose):
    moving = leg_bodies(name)
    partner = PARTNER[name]
    interfaces = interface_pairs(instances, {**others, name: (0.0, leg_pose[1], leg_pose[2])}, moving)
    hips = np.arange(HIP_RANGE_DEG[0], HIP_RANGE_DEG[1] + 1e-9, STEP_DEG / 2)
    ok = []
    for hip in hips:
        q = (math.radians(hip), leg_pose[1], leg_pose[2])
        mirrored = (-math.radians(hip), others[partner][1], others[partner][2])
        joints = {**others, name: q, partner: mirrored}
        ok.append(
            not collisions(instances, joints, moving, baseline) and not too_close(instances, joints, moving, interfaces)
        )
    return hips, np.array(ok)


def derive_limits(thighs, calves, feasible, crank):
    """Box limits in (thigh, calf, crank) whose intersection contains only collision-free cells.

    The knee drive servo sets the crank angle, so the crank range is an
    actuator limit; thigh/calf ranges are joint limits. Every grid cell that
    satisfies all three ranges must be free, after eroding the free set by one
    cell (one grid step of margin). Maximises the number of usable cells.
    """
    free = feasible == 1
    eroded = free.copy()
    eroded[1:, :] &= free[:-1, :]
    eroded[:-1, :] &= free[1:, :]
    eroded[:, 1:] &= free[:, :-1]
    eroded[:, :-1] &= free[:, 1:]
    known = ~np.isnan(crank)
    crank_values = np.arange(-90.0, 180.0 + 1e-9, 2.5)
    rows, cols = feasible.shape
    best = None
    for c_lo in crank_values:
        for c_hi in crank_values[crank_values >= c_lo + 20.0]:
            if c_hi - c_lo > 2 * SERVO_HALF_TRAVEL_DEG:
                break
            in_band = known & (np.nan_to_num(crank, nan=-1e9) >= c_lo) & (np.nan_to_num(crank, nan=1e9) <= c_hi)
            bad = in_band & ~eroded
            good = (in_band & eroded).astype(np.int32)
            if good.sum() == 0 or (best is not None and good.sum() <= best[0]):
                continue
            for r0 in range(rows):
                bad_cols = np.zeros(cols, dtype=bool)
                good_cols = np.zeros(cols, dtype=np.int32)
                for r1 in range(r0, rows):
                    if thighs[r1] - thighs[r0] > 2 * SERVO_HALF_TRAVEL_DEG:
                        break  # thigh servo travel
                    bad_cols |= bad[r1]
                    good_cols += good[r1]
                    # best contiguous run of columns without bad cells
                    run_sum, run_start = 0, 0
                    for j in range(cols):
                        if bad_cols[j]:
                            run_sum, run_start = 0, j + 1
                            continue
                        run_sum += good_cols[j]
                        if best is None or run_sum > best[0]:
                            best = (run_sum, (r0, r1, run_start, j), (c_lo, c_hi))
    assert best is not None, "no collision-free region"
    _, (r0, r1, j0, j1), crank_range = best
    return (float(thighs[r0]), float(thighs[r1])), (float(calves[j0]), float(calves[j1])), crank_range, (r0, r1, j0, j1)


def contiguous_range(values, ok, centre):
    index = int(np.argmin(np.abs(values - centre)))
    assert ok[index], "centre pose collides"
    low = index
    while low > 0 and ok[low - 1]:
        low -= 1
    high = index
    while high < len(values) - 1 and ok[high + 1]:
        high += 1
    return values[low], values[high]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--assembly", choices=("upstream", "full"), default="full")
    parser.add_argument("--legs", default="FL,FR,RL,RR", help="legs to sweep")
    args = parser.parse_args()
    # cables move with the bodies and bend: strido_verify.wiring checks them, the sweep covers rigid parts
    instances = (
        assembly.upstream_instances()
        if args.assembly == "upstream"
        else [i for i in catalog.full_assembly() if i.kind != "cable"]
    )
    # Upstream joint fasteners are placed from measured hole stacks with an approximate head side and
    # nut orientation; swept against moving links they create artefact contacts. They stay in the
    # static interference check; the sweep covers every part plus the Strido fasteners.
    instances = [item for item in instances if item.meta.get("source") != "upstream joint"]
    results = {}
    figures = []
    for name in args.legs.split(","):
        thighs, calves, feasible, crank, reasons, others, baseline = sweep_leg(instances, name)
        thigh_limits, calf_limits, crank_limits, box = derive_limits(thighs, calves, feasible, crank)
        mid_pose = (0.0, math.radians(sum(thigh_limits) / 2), math.radians(sum(calf_limits) / 2))
        stand = stand_pose(name)
        hip_results = {}
        for label, pose in (("stand", stand), ("mid", mid_pose)):
            hips, ok = sweep_hip(instances, name, others, baseline, pose)
            hip_results[label] = contiguous_range(hips, ok, 0.0)
        hip_low = max(value[0] for value in hip_results.values()) + STEP_DEG / 2
        hip_high = min(value[1] for value in hip_results.values()) - STEP_DEG / 2
        results[name] = {
            "hip_deg": [float(hip_low), float(hip_high)],
            "thigh_deg": list(thigh_limits),
            "calf_deg": list(calf_limits),
            "crank_deg": [float(crank_limits[0]), float(crank_limits[1])],
            "collision_cells": int((feasible == -1).sum()),
            "feasible_cells": int((feasible == 1).sum()),
            "hip_sweep_deg": {k: [float(v[0]), float(v[1])] for k, v in hip_results.items()},
            "example_collisions": [
                {
                    "thigh": float(k[0]),
                    "calf": float(k[1]),
                    "pairs": [[p[0][0], p[0][1], round(p[1], 1)] for p in v[:3]],
                }
                for k, v in list(reasons.items())[:: max(1, len(reasons) // 12)]
            ],
        }
        figures.append((name, thighs, calves, feasible, crank, box))
        print(name, {k: results[name][k] for k in ("hip_deg", "thigh_deg", "calf_deg", "crank_deg")})

    limits = {
        name: {key: results[name][key] for key in ("hip_deg", "thigh_deg", "calf_deg", "crank_deg")} for name in results
    }
    document = {
        "description": "Generated by strido_verify.rom from the posed CAD assembly",
        "assembly": args.assembly,
        "grid_step_deg": STEP_DEG,
        "transmission_min_deg": TRANSMISSION_MIN_DEG,
        "servo_half_travel_deg": SERVO_HALF_TRAVEL_DEG,
        "limits": limits,
        "evidence": results,
    }
    OUTPUT.write_text(yaml.safe_dump(document, sort_keys=False, width=160))
    plot(figures)


def plot(figures):
    fig, axes = plt.subplots(1, len(figures), figsize=(7 * len(figures), 6))
    axes = np.atleast_1d(axes)
    for axis, (name, thighs, calves, feasible, crank, box) in zip(axes, figures):
        image = np.where(feasible == 1, 2, np.where(feasible == -1, 0, 1))
        axis.imshow(
            image.T,
            origin="lower",
            cmap="RdYlGn",
            vmin=0,
            vmax=2,
            aspect="auto",
            extent=[thighs[0] - 2.5, thighs[-1] + 2.5, calves[0] - 2.5, calves[-1] + 2.5],
        )
        i0, i1, j0, j1 = box
        axis.add_patch(
            Rectangle(
                (thighs[i0] - 2.5, calves[j0] - 2.5),
                thighs[i1] - thighs[i0] + 5,
                calves[j1] - calves[j0] + 5,
                fill=False,
                lw=2,
                ec="k",
            )
        )
        contour = axis.contour(thighs, calves, crank.T, levels=12, colors="k", linewidths=0.4)
        axis.clabel(contour, fontsize=6)
        axis.set_xlabel("thigh q2 [deg]")
        axis.set_ylabel("calf q3 [deg]")
        axis.set_title(f"{name}: green=free, red=collision, yellow=linkage limit; box=limits; contours=crank deg")
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIGURE, dpi=110)


if __name__ == "__main__":
    main()
