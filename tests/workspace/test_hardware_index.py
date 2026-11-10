"""Hardware knowledge index (backs the MCP server): answers come from the tracked data."""

import pytest
import yaml

from strido.workspace import path
from strido_workspace import cli, hardware_index


def test_pinout_filter_returns_only_matching_pins_and_devices():
    result = hardware_index.pinout("lcd")
    assert result["pins"] and all("lcd" in pin["function"] for pin in result["pins"])
    assert {pin["gpio"] for pin in result["pins"]} == {1, 2, 3, 7, 8, 9}
    assert result["i2c"] == []


def test_joint_limits_match_the_tracked_sweep():
    limits = yaml.safe_load(path("hardware/joint_limits.yaml").read_text())["limits"]["RL"]
    assert hardware_index.joint_limits("RL")["limits_deg"] == limits


def test_unknown_leg_and_fastener_are_errors_with_hints():
    with pytest.raises(KeyError, match="FL"):
        hardware_index.joint_limits("XX")
    with pytest.raises(KeyError, match="iso4762_m3x10"):
        hardware_index.get_fastener("m3x10")


def test_bom_line_lists_offers_with_vendor_names():
    line = hardware_index.bom_line("pi5_4gb")
    assert line["offers"] and all(offer["vendor_name"] for offer in line["offers"])


def test_cli_reports_errors_with_exit_code_2(capsys):
    assert cli.main(["limits", "FL"]) == 0
    assert '"leg": "FL"' in capsys.readouterr().out
    assert cli.main(["fastener", "nope"]) == 2
    assert "unknown fastener" in capsys.readouterr().err


def test_part_listing_filters_by_kind_and_counts_every_screw():
    printed = hardware_index.list_parts("printed")
    assert printed and all(part["kind"] == "printed" for part in printed)
    screws = {part["id"]: part["qty"] for part in hardware_index.list_parts("fastener")}
    assert screws["iso4762_m3x10"] == hardware_index.get_fastener("iso4762_m3x10")["qty_in_robot"] > 0
    with pytest.raises(ValueError, match="unknown kind"):
        hardware_index.list_parts("bolts")


def test_part_details_include_print_data_and_measured_fits():
    deck = hardware_index.get_part("electronics_deck")
    assert deck["kind"] == "printed" and deck["file"].startswith("hardware/print/stl/")
    assert deck["fits"] and {fit["status"] for fit in deck["fits"]} <= {"ok", "warn"}
    with pytest.raises(KeyError, match="similar"):
        hardware_index.get_part("electronics_dek")


def test_fit_and_clearance_queries_reflect_the_last_verification_run():
    summary = hardware_index.fits_summary("fail")
    assert summary["counts"]["fail"] == 0 and summary["screws"] == []
    assert summary["bearing_seats"]["fail"] == 0
    tight = hardware_index.clearance_pairs(1.0)
    assert all(pair["gap_mm"] < 1.0 for pair in tight["pairs"])
    assert all(pair["status"] != "fail" for pair in tight["pairs"])


def test_verification_status_summarises_every_report():
    status = hardware_index.verification_status()
    assert set(status) == set(hardware_index.VERIFICATION_REPORTS)
    assert all(not text.startswith("missing") for text in status.values())


def test_missing_artefact_names_the_command_that_builds_it(tmp_path, monkeypatch):
    for relative in ("hardware/kinematics.yaml",):
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative).write_text("{}")
    monkeypatch.setattr(hardware_index, "_root", lambda: tmp_path)
    with pytest.raises(hardware_index.MissingArtefactError, match="make catalog"):
        hardware_index.list_parts()
    assert hardware_index.fits_for_part("electronics_deck") == []
