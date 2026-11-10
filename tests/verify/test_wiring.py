"""The wiring gate catches leads that do not reach, loops that pull tight and doubly used ports."""

import numpy as np

from strido_cad import wiring
from strido_verify import wiring as gate

DATA = wiring.load()


def row(cable, run, kind, routed, terminations=0.0):
    return {"cable": cable, "run": run, "type": kind, "routed_mm": routed, "terminations_mm": terminations}


def run_between(name, a, b):
    return wiring.Run(name, name, "servo_signal", 1, [a, b])


def test_ready_made_cable_must_keep_its_margin():
    supplied = DATA["cable_types"]["usb_a_c"]["supplied_mm"]
    limit = supplied - gate.REACH_MARGIN_MM
    assert gate.check_reach([row("W14", "W14", "usb_a_c", limit - 1)], DATA)[0].status == "ok"
    assert gate.check_reach([row("W14", "W14", "usb_a_c", limit - 5, terminations=6)], DATA)[0].status == "fail"


def test_a_cut_branch_needs_its_slack_from_the_lead():
    # the orange wire is cut with slack from the tie: route alone fits, route + slack does not
    lead = DATA["cable_types"]["servo_lead"]["supplied_mm"] - gate.REACH_MARGIN_MM
    signal = row("S-FR-calf", "S-FR-calf/signal", "servo_signal", lead - 60.0 - 5.0, terminations=3.0)
    signal["cut_mm"] = signal["routed_mm"] + 3.0 + 10.0
    rows = [row("S-FR-calf", "S-FR-calf", "servo_lead", 60.0), signal]
    assert gate.check_reach(rows, DATA)[0].status == "fail"


def test_a_servo_lead_must_reach_through_its_longest_branch():
    lead = DATA["cable_types"]["servo_lead"]["supplied_mm"] - gate.REACH_MARGIN_MM
    rows = [
        row("S-FL-calf", "S-FL-calf", "servo_lead", 60.0),
        row("S-FL-calf", "S-FL-calf/power", "servo_power", 30.0, terminations=11.0),
        row("S-FL-calf", "S-FL-calf/signal", "servo_signal", lead - 60.0 + 1.0),  # the signal branch is 1 mm too long
    ]
    assert gate.check_reach(rows, DATA)[0].status == "fail"
    rows[2]["routed_mm"] -= 2.0
    assert gate.check_reach(rows, DATA)[0].status == "ok"


def test_a_port_used_twice_fails_and_a_pair_takes_both_rails():
    pca = wiring.Point("pca:11", np.zeros(3), "base")
    split = wiring.Point("front.split0", np.ones(3), "base")
    statuses = {
        f.item: f.status for f in gate.check_ports([run_between("a", split, pca), run_between("b", split, pca)])
    }
    assert statuses["pca:11"] == "fail"
    pair = wiring.Point("wago:front.0.p2", np.zeros(3), "base")
    single = wiring.Point("wago:front.0.p2.GND", np.zeros(3), "base")
    statuses = {
        f.item: f.status
        for f in gate.check_ports([run_between("pair", split, pair), run_between("gnd", split, single)])
    }
    assert statuses["wago:front.0.p2.GND"] == "fail"
    assert statuses["wago:front.0.p2.V+"] == "ok"


def test_a_hip_loop_shorter_than_its_ties_get_apart_fails():
    nodes = wiring.nodes(DATA)
    tie = wiring._node_point("front.calf_tie.L", nodes["front.calf_tie.L"])  # rides on FL.hip
    base = wiring._node_point("front.calf_base.L", nodes["front.calf_base.L"])
    lead = wiring.Run("S-FL-calf", "S-FL-calf", "servo_lead", 3, [tie, base])
    finding = gate.check_loops([lead])[0]
    assert finding.status == "ok"
    needed = float(finding.limit.split()[1])
    short = wiring.Run(
        "x", "x", "servo_lead", 3, [wiring.Point(tie.name, tie.xyz, tie.body, tie.tie, needed - 1.0, tie.bulge), base]
    )
    assert gate.check_loops([short])[0].status == "fail"
