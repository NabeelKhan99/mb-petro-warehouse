"""Tests for well_parser.py covering edge cases."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'silver'))
from well_parser import parse_raw_block


def test_to_be_determined_rig():
    """Test 1: 'To Be Determined' rig name with numeric rig_no 0."""
    block = (
        "12515 Melita Pierson Prov. HZNTL 17-MAR-26 DEV "
        "MELITA RESOURCES LTD. "
        "16C-15-02-29 60m S of N / 335.99m W of E of Sec. 15 "
        "103.16-22-002-29W1.00 2603.9 Mississippian 468.88 "
        "To Be Determined 0"
    )
    r = parse_raw_block(block)
    assert r["parse_status"] in ("SUCCESS", "PARTIAL")
    assert r["drilling_rig"] == "To Be Determined"
    assert r["rig_no"] == 0
    assert r["total_depth_m"] == 2603.9
    assert r["ground_elevation_m"] == 468.88


def test_dash_in_rig_name():
    """Test 2: Dash in rig name, no numeric rig_no at end."""
    block = (
        "12514 Tundra Daly Sinclair Prov. HZNTL 06-MAR-26 DEV "
        "TUNDRA OIL & GAS LIMITED "
        "08D-13-09-28 724.53m N of S / 60m W of E of Sec. 13 "
        "100.09-18-009-27W1.00 2302.1 Mississippian 482.73 "
        "Ensign - Trinidad Drilling 9 Inc."
    )
    r = parse_raw_block(block)
    assert r["parse_status"] in ("SUCCESS", "PARTIAL")
    assert "Ensign" in r["drilling_rig"]
    assert r["rig_no"] is None
    assert r["total_depth_m"] == 2302.1
    assert r["ground_elevation_m"] == 482.73


def test_slash_in_rig_name():
    """Test 3: Slash in rig name, non-numeric suffix '12 Canadian'."""
    block = (
        "12496 Tundra Daly Sinclair HZNTL 03-FEB-26 DEV "
        "TUNDRA OIL & GAS LIMITED "
        "04B-18-10-28 94.49m N of S / 89.9m E of W of Sec. 18 "
        "102.13-12-010-29W1.00 2376.9 Mississippian 519.15 "
        "Big Sky Drilling/Ensign 12 Canadian"
    )
    r = parse_raw_block(block)
    assert r["parse_status"] in ("SUCCESS", "PARTIAL")
    assert "Big Sky" in r["drilling_rig"]
    assert r["rig_no"] is None
    assert r["total_depth_m"] == 2376.9
    assert r["ground_elevation_m"] == 519.15


def test_silurian_formation():
    """Test 4: Silurian formation with SWD class and DPW type."""
    block = (
        "12494 Tundra Daly Sinclair SWD 03-FEB-26 DPW "
        "TUNDRA OIL & GAS LIMITED "
        "01D-27-09-29 234.98m N of S / 150m W of E of Sec. 27 "
        "105.01-27-009-29W1.00 1844.9 Silurian 529.33 "
        "Ensign Drilling Inc. 12"
    )
    r = parse_raw_block(block)
    assert r["parse_status"] in ("SUCCESS", "PARTIAL")
    assert r["well_class"] == "SWD"
    assert r["well_type_code"] == "DPW"
    assert r["formation"] == "Silurian"
    assert r["total_depth_m"] == 1844.9