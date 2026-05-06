"""Smoke tests for well_parser.py covering edge cases."""

from well_parser import parse_raw_block

# Test 1: "To Be Determined" rig name
b1 = (
    "12515 Melita Pierson Prov. HZNTL 17-MAR-26 DEV "
    "MELITA RESOURCES LTD. "
    "16C-15-02-29 60m S of N / 335.99m W of E of Sec. 15 "
    "103.16-22-002-29W1.00 2603.9 Mississippian 468.88 "
    "To Be Determined 0"
)
r1 = parse_raw_block(b1)
print("Test 1 — To Be Determined:")
print(f"  rig: {r1['drilling_rig']}, rig_no: {r1['rig_no']}, depth: {r1['total_depth_m']}, elev: {r1['ground_elevation_m']}")
print(f"  status: {r1['parse_status']}")
print()

# Test 2: Dash in rig name, no rig number at end
b2 = (
    "12514 Tundra Daly Sinclair Prov. HZNTL 06-MAR-26 DEV "
    "TUNDRA OIL & GAS LIMITED "
    "08D-13-09-28 724.53m N of S / 60m W of E of Sec. 13 "
    "100.09-18-009-27W1.00 2302.1 Mississippian 482.73 "
    "Ensign - Trinidad Drilling 9 Inc."
)
r2 = parse_raw_block(b2)
print("Test 2 — Dash in rig name, no numeric rig_no:")
print(f"  rig: {r2['drilling_rig']}, rig_no: {r2['rig_no']}")
print(f"  depth: {r2['total_depth_m']}, elev: {r2['ground_elevation_m']}")
print(f"  status: {r2['parse_status']}")
print()

# Test 3: Slash in rig name, non-numeric ending ("12 Canadian")
b3 = (
    "12496 Tundra Daly Sinclair HZNTL 03-FEB-26 DEV "
    "TUNDRA OIL & GAS LIMITED "
    "04B-18-10-28 94.49m N of S / 89.9m E of W of Sec. 18 "
    "102.13-12-010-29W1.00 2376.9 Mississippian 519.15 "
    "Big Sky Drilling/Ensign 12 Canadian"
)
r3 = parse_raw_block(b3)
print("Test 3 — Slash in name, '12 Canadian' ending:")
print(f"  rig: {r3['drilling_rig']}, rig_no: {r3['rig_no']}")
print(f"  depth: {r3['total_depth_m']}, elev: {r3['ground_elevation_m']}")
print(f"  status: {r3['parse_status']}")
print()

# Test 4: Missing formation (Silurian should still parse)
b4 = (
    "12494 Tundra Daly Sinclair SWD 03-FEB-26 DPW "
    "TUNDRA OIL & GAS LIMITED "
    "01D-27-09-29 234.98m N of S / 150m W of E of Sec. 27 "
    "105.01-27-009-29W1.00 1844.9 Silurian 529.33 "
    "Ensign Drilling Inc. 12"
)
r4 = parse_raw_block(b4)
print("Test 4 — Silurian formation, SWD/DPW class/type:")
print(f"  well_class: {r4['well_class']}, type: {r4['well_type_code']}")
print(f"  formation: {r4['formation']}, depth: {r4['total_depth_m']}")
print(f"  status: {r4['parse_status']}")