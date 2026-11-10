"""Tightening-torque limits of thread-forming screws in printed pilots (strength check).

Pull-out shears the plastic on a cylinder of the thread diameter, F = tau · pi · d · L_e, with tau the
shear strength across the layers; the tightening torque that reaches it is T = k · F · d."""

import math


def thread_torques(fits: dict, config: dict) -> list[dict]:
    """Pull-out force and recommended tightening torque of every thread-forming joint (shortest engagement)."""
    material = config["material"]
    tau = material["shear_factor"] * material["layer_adhesion_mpa"]  # shear across the layers: the weakest direction
    k, factor = config["screws"]["torque_factor"], config["safety"]["thread_torque_factor"]
    shortest = {}
    for screw in fits["screws"]:
        for hole in screw["parts"]:
            if hole["fit"] == "thread-forming" and hole["engaged_mm"] > 0:
                key = (screw["joint"], hole["part"])
                d = float(screw["thread"].lstrip("M"))
                if key not in shortest or hole["engaged_mm"] < shortest[key][1]:
                    shortest[key] = (d, hole["engaged_mm"])
    rows = []
    for (joint, part), (d, engaged) in sorted(shortest.items()):
        pull_out_n = tau * math.pi * d * engaged
        strip_nm = k * pull_out_n * d / 1000
        rows.append(
            {
                "joint": joint,
                "part": part,
                "thread": f"M{d:g}",
                "engaged_mm": engaged,
                "pull_out_n": round(pull_out_n),
                "strip_torque_nm": round(strip_nm, 2),
                "recommended_torque_nm": round(strip_nm / factor, 2),
            }
        )
    return rows
