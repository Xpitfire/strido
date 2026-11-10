"""Electronics consistency: pins, buses, servo channels, power budget and wire ratings.

Source of truth: hardware/electronics.yaml (wires: hardware/wiring.yaml). Checks (exit 1 on any failure):

* the firmware pin header (board_config.h) defines exactly the pins, I²C addresses,
  servo channels and frequencies of the YAML, and every header constant appears in the YAML;
* every controller pin maps to a real XIAO pad, no GPIO is used twice, strapping
  pins carry a note;
* I²C addresses (including secondary addresses such as the PCA9685 all-call) are unique;
* the 12 joints use 12 distinct PCA9685 channels (0..15) and the servo PWM frequency is
  within the servo rating;
* every converter, switch, fuse and wire carries its load: load <= fuse <= wire ampacity.

Writes docs/verification/electronics.md; `--check` only compares it (drift gate).
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from strido.workspace import path

from .electronics_report import render_report

SOURCE = path("hardware/electronics.yaml")
WIRING = path("hardware/wiring.yaml")
BOARD_CONFIG = path("firmware/strido_esp32s3/src/board_config.h")
REPORT = path("docs/verification/electronics.md")
LEG_ORDER = ("FL", "FR", "RL", "RR")
JOINT_ORDER = ("hip", "thigh", "calf")
PCA_CHANNELS = 16

# `constexpr <type> <name> = <value>;` - captures the constant name and its literal value
SCALAR_PATTERN = re.compile(r"constexpr\s+[\w:]+\s+(k\w+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)\s*;")
# `constexpr <type> <name>[<n>] = {a, b, ...};` - captures the array name and the brace contents
ARRAY_PATTERN = re.compile(r"constexpr\s+[\w:]+\s+(k\w+)\[\d*\]\s*=\s*\{([^}]*)\}\s*;")


@dataclass
class Finding:
    check: str
    ok: bool
    detail: str
    margin: bool = True  # False: passes at nominal, but the rail tolerance reaches past the rating


def firmware_constants(header: Path) -> tuple[dict[str, int], dict[str, list[int]]]:
    """Integer constants and integer arrays defined in a C++ header."""
    text = header.read_text()
    scalars = {name: int(value, 0) for name, value in SCALAR_PATTERN.findall(text)}
    arrays = {
        name: [int(item.strip(), 0) for item in body.split(",") if item.strip()]
        for name, body in ARRAY_PATTERN.findall(text)
    }
    return scalars, arrays


def check_pins(model: dict[str, Any], scalars: dict[str, int]) -> list[Finding]:
    controller = model["controller"]
    pads = controller["pads"]
    findings = []
    used: dict[int, str] = {}
    for pin in controller["pins"]:
        gpio = pads.get(pin["pad"])
        if gpio is None:
            findings.append(Finding("pin exists", False, f"{pin['function']}: pad {pin['pad']} is not a XIAO pad"))
            continue
        if gpio in used:
            findings.append(Finding("pin unique", False, f"GPIO {gpio} used by {used[gpio]} and {pin['function']}"))
        used[gpio] = pin["function"]
        firmware = scalars.get(pin["constant"])
        findings.append(
            Finding(
                "firmware pin", firmware == gpio, f"{pin['constant']} = {firmware} (YAML {pin['pad']} = GPIO {gpio})"
            )
        )
        if gpio in controller["strapping_gpio"] and "strapping" not in pin.get("note", ""):
            findings.append(
                Finding("strapping pin noted", False, f"{pin['function']} uses strapping GPIO {gpio} without a note")
            )
    return findings


def check_i2c(model: dict[str, Any], scalars: dict[str, int]) -> list[Finding]:
    bus = model["i2c"]
    findings = [
        Finding(
            "I²C frequency",
            scalars.get(bus["firmware_constant"]) == bus["frequency_hz"],
            f"{bus['firmware_constant']} = {scalars.get(bus['firmware_constant'])} (YAML {bus['frequency_hz']})",
        )
    ]
    seen: dict[int, str] = {}
    for device in bus["devices"]:
        for address in (device["address"], *device.get("also_answers", [])):
            if address in seen:
                findings.append(
                    Finding("I²C address unique", False, f"0x{address:02X}: {seen[address]} and {device['device']}")
                )
            seen[address] = device["device"]
        firmware = scalars.get(device["constant"])
        findings.append(
            Finding(
                "firmware I²C address",
                firmware == device["address"],
                f"{device['constant']} = {firmware} (YAML 0x{device['address']:02X})",
            )
        )
    if len(seen) == sum(1 + len(d.get("also_answers", [])) for d in bus["devices"]):
        findings.append(
            Finding("I²C address unique", True, ", ".join(f"0x{a:02X} {n}" for a, n in sorted(seen.items())))
        )
    return findings


def check_servos(model: dict[str, Any], scalars: dict[str, int], arrays: dict[str, list[int]]) -> list[Finding]:
    servos = model["servos"]
    expected = [servos["channels"][leg][joint] for leg in LEG_ORDER for joint in JOINT_ORDER]
    firmware = arrays.get("kServoChannel")
    return [
        Finding("servo channels unique", len(set(expected)) == len(expected) == 12, f"{expected}"),
        Finding("servo channels in range", all(0 <= c < PCA_CHANNELS for c in expected), f"0..{PCA_CHANNELS - 1}"),
        Finding("firmware servo channels", firmware == expected, f"kServoChannel = {firmware}"),
        Finding(
            "servo PWM frequency",
            scalars.get(servos["frequency_constant"]) == servos["frequency_hz"] <= servos["max_frequency_hz"],
            f"{servos['frequency_constant']} = {scalars.get(servos['frequency_constant'])} Hz, servo max {servos['max_frequency_hz']} Hz",
        ),
    ]


def branch_currents(model: dict[str, Any]) -> dict[str, float]:
    """Worst-case continuous current per named load (A) at the point it is drawn."""
    power = model["power"]
    efficiency = power["converter_efficiency"]
    pack_empty_v = power["pack"]["empty_v"]
    converters = {c["id"]: c for c in power["converters"]}
    logic_peak_w = sum(load["peak_w"] for load in power["logic_loads"])
    ubec_out_a = {cid: converters[cid]["continuous_a"] for cid in ("ubec_front", "ubec_rear")}
    servo_branch_a = (
        sum(ubec_out_a[cid] * converters[cid]["output_v"] for cid in ubec_out_a) / efficiency / pack_empty_v
    )
    logic_branch_a = logic_peak_w / efficiency / pack_empty_v
    return {
        "ubec_front": ubec_out_a["ubec_front"],
        "ubec_rear": ubec_out_a["ubec_rear"],
        "servo_branch": servo_branch_a,
        "logic_branch": logic_branch_a,
        "logic_5v": logic_peak_w / converters["logic_5v"]["output_v"],
        "logic_5v_per_pin": logic_peak_w / converters["logic_5v"]["output_v"],
        "pack": servo_branch_a + logic_branch_a,
    }


def power_wires(wiring: dict[str, Any]) -> list[dict[str, Any]]:
    """Every conductor of hardware/wiring.yaml that carries a power branch: id, gauge, load, parallel."""
    types = wiring["cable_types"]
    wires = []
    for cable in wiring["cables"]:
        if "carries" not in cable:
            continue
        parts = [(cable["id"], cable["type"], cable["carries"])] if "type" in cable else []
        for part in cable.get("branches", []) + cable.get("cores", []):
            parts.append((f"{cable['id']}/{part['name']}", part["type"], part.get("carries", cable["carries"])))
        for ident, kind, carries in parts:
            wires.append(
                {"id": ident, "gauge": types[kind]["gauge"], "carries": carries, "parallel": cable.get("parallel", 1)}
            )
    return wires


def check_power(model: dict[str, Any], wiring: dict[str, Any]) -> list[Finding]:
    power = model["power"]
    currents = branch_currents(model)
    converters = {c["id"]: c for c in power["converters"]}
    findings = []
    servos = model["servos"]
    for cid in ("ubec_front", "ubec_rear"):
        legs = converters[cid]["feeds"]
        trotting = 3 * len(legs) * servos["trotting_current_a"]
        findings.append(
            Finding(
                f"{cid} load",
                trotting <= converters[cid]["continuous_a"],
                f"6 servos trotting ≈ {trotting:.1f} A ≤ {converters[cid]['continuous_a']:.0f} A continuous",
            )
        )
        stalled = 3 * len(legs) * servos["stall_current_a"]
        findings.append(
            Finding(
                f"{cid} stall warning",
                True,
                f"6 stalled servos {stalled:.0f} A > {converters[cid]['peak_a']:.0f} A peak: never drive all joints into hard stops",
            )
        )
    findings.append(
        Finding(
            "5 V regulator load",
            currents["logic_5v"] <= converters["logic_5v"]["continuous_a"],
            f"{currents['logic_5v']:.2f} A peak ≤ {converters['logic_5v']['continuous_a']} A",
        )
    )
    findings.append(
        Finding(
            "power switch load",
            currents["logic_branch"] <= power["switch"]["continuous_a"],
            f"{currents['logic_branch']:.2f} A ≤ {power['switch']['continuous_a']} A",
        )
    )
    findings.append(
        Finding(
            "INA260 range",
            currents["logic_branch"] <= power["monitor"]["max_a"]
            and power["pack"]["full_v"] <= power["monitor"]["max_v"],
            f"{currents['logic_branch']:.2f} A, {power['pack']['full_v']} V",
        )
    )
    fuses = {f["id"]: f for f in power["fuses"]}
    findings.append(
        Finding(
            "main fuse ≥ load",
            currents["pack"] <= fuses["main"]["rating_a"],
            f"servo + logic {currents['pack']:.1f} A ≤ {fuses['main']['rating_a']} A",
        )
    )
    findings.append(
        Finding(
            "logic fuse ≥ load",
            currents["logic_branch"] <= fuses["logic"]["rating_a"],
            f"{currents['logic_branch']:.2f} A ≤ {fuses['logic']['rating_a']} A",
        )
    )
    ampacity = model["wire_ampacity_a"]
    protected_by = {cable: fuse for fuse in power["fuses"] for cable in fuse["protects"]}
    for wire in power_wires(wiring):
        load = currents[wire["carries"]] / wire.get("parallel", 1)
        limit = ampacity[wire["gauge"]]
        findings.append(
            Finding(f"wire {wire['id']} load", load <= limit, f"{wire['gauge']}: {load:.1f} A ≤ {limit:.0f} A")
        )
        fuse = protected_by.get(wire["id"], protected_by.get(wire["id"].split("/")[0]))
        if fuse is not None:
            findings.append(
                Finding(
                    f"wire {wire['id']} fuse",
                    fuse["rating_a"] <= limit,
                    f"{fuse['id']} fuse {fuse['rating_a']} A ≤ {wire['gauge']} {limit:.0f} A",
                )
            )
    return findings


def level_finding(check: str, rail: dict[str, Any], rated: list[float], source: str) -> Finding:
    """Fail if the nominal rail voltage is outside the rating or the rail can exceed the rated maximum
    (over-voltage damages); a rail minimum below the rated minimum (under-voltage: brown-out, weak
    logic high) passes without margin and is a measurement item for the build."""
    low, high = rated
    ok = low <= rail["nominal_v"] <= high and rail["max_v"] <= high
    margin = low <= rail["min_v"]
    detail = f"{rail['min_v']}-{rail['max_v']} V (nominal {rail['nominal_v']}) within {low}-{high} V ({source})"
    if not ok:
        detail = f"{rail['min_v']}-{rail['max_v']} V (nominal {rail['nominal_v']}) exceeds {low}-{high} V ({source})"
    elif not margin:
        detail = f"rail minimum {rail['min_v']} V below the rated {low} V ({source}): no margin, measure it"
    return Finding(check, ok, detail, margin)


def check_voltage_domains(model: dict[str, Any]) -> list[Finding]:
    """Every supply input and every logic signal against its rated voltage range."""
    rails = model["rails"]
    findings = [
        level_finding(f"supply: {s['device']}", rails[s["rail"]], s["rated_v"], s["source"]) for s in model["supplies"]
    ]
    findings += [
        level_finding(f"signal: {s['signal']} -> {s['receiver']}", rails[s["level_rail"]], s["accepts_v"], s["source"])
        for s in model["signals"]
    ]
    return findings


def check_header_coverage(
    model: dict[str, Any], scalars: dict[str, int], arrays: dict[str, list[int]]
) -> list[Finding]:
    """Every constant of the firmware header is described in the YAML (no unchecked pin or address)."""
    controller, bus, servos = model["controller"], model["i2c"], model["servos"]
    led = controller["onboard_led"]
    described = {pin["constant"] for pin in controller["pins"]}
    described |= {bus["firmware_constant"], *(device["constant"] for device in bus["devices"])}
    described |= {servos["frequency_constant"], "kServoChannel", led["constant"], *model["firmware_timing_constants"]}
    findings = [
        Finding(
            "on-board LED",
            scalars.get(led["constant"]) == led["gpio"],
            f"{led['constant']} = {scalars.get(led['constant'])} (YAML GPIO {led['gpio']})",
        )
    ]
    undescribed = sorted((set(scalars) | set(arrays)) - described)
    findings.append(
        Finding(
            "header constants described",
            not undescribed,
            f"not in the YAML: {', '.join(undescribed)}"
            if undescribed
            else f"{len(set(scalars) | set(arrays))} constants",
        )
    )
    return findings


def run_checks(model: dict[str, Any], header: Path, wiring: dict[str, Any]) -> list[Finding]:
    """`model`: hardware/electronics.yaml; `wiring`: hardware/wiring.yaml (its power-carrying cables)."""
    scalars, arrays = firmware_constants(header)
    return (
        check_pins(model, scalars)
        + check_i2c(model, scalars)
        + check_servos(model, scalars, arrays)
        + check_header_coverage(model, scalars, arrays)
        + check_power(model, wiring)
        + check_voltage_domains(model)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the report is stale instead of writing it")
    args = parser.parse_args()
    model = yaml.safe_load(SOURCE.read_text())
    findings = run_checks(model, BOARD_CONFIG, yaml.safe_load(WIRING.read_text()))
    report = render_report(model, findings, branch_currents(model))
    failed = [f for f in findings if not f.ok]
    for finding in failed:
        print(f"FAIL {finding.check}: {finding.detail}")
    if args.check:
        if not REPORT.is_file() or REPORT.read_text() != report:
            print("stale: docs/verification/electronics.md (run python -m strido_verify.electronics)")
            sys.exit(1)
    else:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(report)
    no_margin = [f.check for f in findings if f.ok and not f.margin]
    print(
        f"electronics: {len(findings) - len(failed)} checks passed ({len(no_margin)} without margin), {len(failed)} failed"
    )
    for check in no_margin:
        print(f"  no margin: {check}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
