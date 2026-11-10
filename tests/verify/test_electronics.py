"""The electronics check catches the wiring mistakes that burn boards or leave servos dead."""

import copy
from pathlib import Path

import pytest
import yaml

from strido.workspace import path
from strido_verify import electronics

MODEL = yaml.safe_load(path("hardware/electronics.yaml").read_text())
WIRING = yaml.safe_load(path("hardware/wiring.yaml").read_text())
HEADER = path("firmware/strido_esp32s3/src/board_config.h")


def failed_checks(model, header=HEADER, wiring=WIRING):
    return {f.check for f in electronics.run_checks(model, header, wiring) if not f.ok}


def test_tracked_design_passes_every_check():
    assert failed_checks(MODEL) == set()


def test_firmware_pin_that_differs_from_the_yaml_fails(tmp_path: Path):
    header = tmp_path / "board_config.h"
    header.write_text(HEADER.read_text().replace("constexpr int kSda = 5;", "constexpr int kSda = 43;"))
    assert "firmware pin" in failed_checks(MODEL, header)


def test_header_pin_missing_from_the_yaml_fails(tmp_path: Path):
    header = tmp_path / "board_config.h"
    header.write_text(HEADER.read_text() + "\nconstexpr int kBuzzer = 44;  // D7\n")
    assert "header constants described" in failed_checks(MODEL, header)


def test_servo_rail_above_the_servo_rating_fails():
    model = copy.deepcopy(MODEL)
    model["rails"]["servo_6v"].update(nominal_v=7.4, min_v=7.0, max_v=7.5)  # UBEC jumpered to 7.4 V
    assert "supply: SPT5435LV servo V+" in failed_checks(model)


def test_rail_maximum_above_a_rating_fails_even_at_a_good_nominal():
    model = copy.deepcopy(MODEL)
    model["rails"]["servo_6v"]["max_v"] = 6.3  # a UBEC that measures 6.3 V unloaded
    assert "supply: SPT5435LV servo V+" in failed_checks(model)


def test_rail_minimum_below_a_rating_passes_without_margin():
    findings = {f.check: f for f in electronics.run_checks(MODEL, HEADER, WIRING)}
    pwm = findings["signal: servo PWM -> SPT5435LV signal input"]
    assert pwm.ok and not pwm.margin  # 3.3 V PWM sits exactly at the servo's lowest rated level


def test_duplicate_servo_channel_fails():
    model = copy.deepcopy(MODEL)
    model["servos"]["channels"]["RR"]["calf"] = model["servos"]["channels"]["FL"]["hip"]
    failed = failed_checks(model)
    assert {"servo channels unique", "firmware servo channels"} <= failed


def test_i2c_address_collision_with_pca9685_fails():
    model = copy.deepcopy(MODEL)
    ina = next(d for d in model["i2c"]["devices"] if d["constant"] == "kPowerMonitorAddress")
    ina["address"] = 0x40  # INA260 default address without the A0 jumper bridged
    assert "I²C address unique" in failed_checks(model)


def test_gpio_used_twice_fails():
    model = copy.deepcopy(MODEL)
    model["controller"]["pins"][0]["pad"] = model["controller"]["pins"][1]["pad"]
    assert "pin unique" in failed_checks(model)


def test_undersized_wire_for_its_fuse_fails():
    wiring = copy.deepcopy(WIRING)
    next(c for c in wiring["cables"] if c["id"] == "W03")["type"] = "wire_22awg_green"  # 22 AWG on the servo branch
    failed = failed_checks(MODEL, wiring=wiring)
    assert {"wire W03 load", "wire W03 fuse"} <= failed


def test_a_branch_is_held_to_its_own_fuse():
    # W04/logic is the 18 AWG logic return: fine behind the 7.5 A logic fuse, too thin for the 25 A main fuse
    model = copy.deepcopy(MODEL)
    for fuse in model["power"]["fuses"]:
        fuse["protects"] = [c for c in fuse["protects"] if c != "W04/logic"] + (["W04"] if fuse["id"] == "main" else [])
    assert "wire W04/logic fuse" in failed_checks(model)
    assert "wire W04/logic fuse" not in failed_checks(MODEL)


@pytest.mark.parametrize("servos_per_ubec_a", [1.8])
def test_ubec_overload_fails(servos_per_ubec_a):
    model = copy.deepcopy(MODEL)
    model["servos"]["trotting_current_a"] = servos_per_ubec_a  # 6 x 1.8 A = 10.8 A > 10 A continuous
    assert "ubec_front load" in failed_checks(model)
