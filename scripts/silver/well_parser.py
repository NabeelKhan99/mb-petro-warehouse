"""
Silver Layer — Well Approval raw_block Parser
Parses space-delimited raw_block into typed columns.

Manitoba well approval raw_block positional structure:
  [licence_id] [well_name...] [well_class] [date] [type_code]
  [licensee...] [surface_location] [coordinates] [uwi]
  [total_depth] [formation] [elevation] [rig_name...] [rig_no]
"""

import re
from datetime import datetime
from typing import Dict


# UWI regex (Manitoba DLS 21-char format — primary anchor)
UWI_REGEX = re.compile(r"1[0A-DS-W][0-9]\.[0-9]{2}-[0-9]{2}-[0-9]{3}-[0-9]{2}W1\.[0-9]{2}")

# Date regex: DD-MON-YY
DATE_REGEX = re.compile(r"\d{1,2}-[A-Z]{3}-\d{2}")

# Surface location: LSD format like 16A-33-09-29
LSD_REGEX = re.compile(r"\d{1,2}[A-D]?-\d{2}-\d{2}-\d{2}")

# Known formations (longest first for greedy matching)
FORMATIONS = [
    "Mississippian", "Devonian", "Silurian", "Triassic",
    "Cretaceous", "Jurassic", "Ordovician", "Cambrian",
    "Precambrian",
]

# Known well class codes
WELL_CLASSES = {"DEV", "DPW", "SWD", "OBS", "INJ", "HZNTL", "PROV", "VERT"}

# Month abbreviations
MONTHS = {"JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"}


def parse_raw_block(raw_block: str) -> Dict:
    """
    Parse a raw_block string into typed fields.

    Strategy:
    1. Find UWI — the most reliable anchor.
    2. Split block into left_of_uwi and right_of_uwi.
    3. Right side has: total_depth formation elevation rig_name rig_no
    4. Left side has: licence_id well_name class date type_code licensee surface_location coordinates
    """
    result = {
        "licence_id": None,
        "well_name": None,
        "well_class": None,
        "issued_date": None,
        "well_type_code": None,
        "licensee": None,
        "surface_location": None,
        "coordinates": None,
        "uwi": None,
        "total_depth_m": None,
        "formation": None,
        "ground_elevation_m": None,
        "drilling_rig": None,
        "rig_no": None,
        "parse_status": "SUCCESS",
        "parse_notes": "",
    }

    notes = []

    if not raw_block or not raw_block.strip():
        result["parse_status"] = "FAILED"
        result["parse_notes"] = "Empty raw_block"
        return result

    block = raw_block.strip()

    # --- Step 1: Extract UWI ---
    uwi_match = UWI_REGEX.search(block)
    if not uwi_match:
        result["parse_status"] = "FAILED"
        result["parse_notes"] = "No valid UWI found"
        return result

    result["uwi"] = uwi_match.group(0)
    uwi_start, uwi_end = uwi_match.start(), uwi_match.end()

    left = block[:uwi_start].strip()
    right = block[uwi_end:].strip()

        # --- Step 2: Parse RIGHT side ---
    # Structure: total_depth formation elevation rig_name... rig_no
    tokens = right.split()

    # Pop rig_no from end if numeric
    rig_no = None
    if tokens and tokens[-1].isdigit():
        rig_no = int(tokens.pop())
    elif tokens:
        try:
            rig_no = int(tokens[-1])
            tokens.pop()
        except ValueError:
            pass
    result["rig_no"] = rig_no

    # Find formation token
    form_idx = -1
    for i, tok in enumerate(tokens):
        for fmt in FORMATIONS:
            if tok.lower() == fmt.lower():
                form_idx = i
                result["formation"] = fmt
                break
        if form_idx > -1:
            break

    if form_idx > -1:
        if form_idx > 0:
            try:
                result["total_depth_m"] = float(tokens[form_idx - 1])
            except ValueError:
                notes.append(f"Bad depth: {tokens[form_idx - 1]}")

        if form_idx < len(tokens) - 1:
            try:
                result["ground_elevation_m"] = float(tokens[form_idx + 1])
            except ValueError:
                notes.append(f"Bad elevation: {tokens[form_idx + 1]}")

        rig_start = form_idx + 2
        if rig_start < len(tokens):
            result["drilling_rig"] = " ".join(tokens[rig_start:])
    else:
        result["drilling_rig"] = " ".join(tokens)

    # --- Step 3: Parse LEFT side ---
    tokens_left = left.split()

    if not tokens_left:
        result["parse_status"] = "FAILED"
        result["parse_notes"] = "Nothing left of UWI"
        return result

    # First token = licence_id
    result["licence_id"] = tokens_left.pop(0)

    # Find date token
    date_idx = -1
    for i, tok in enumerate(tokens_left):
        if DATE_REGEX.match(tok):
            date_idx = i
            break

    if date_idx > -1:
        try:
            result["issued_date"] = datetime.strptime(
                tokens_left[date_idx], "%d-%b-%y"
            ).strftime("%Y-%m-%d")
        except ValueError:
            notes.append(f"Bad date: {tokens_left[date_idx]}")

        # Well class = one token before date
        if date_idx > 0:
            wc = tokens_left[date_idx - 1]
            if wc in WELL_CLASSES:
                result["well_class"] = wc

        # Type code = one token after date
        if date_idx < len(tokens_left) - 1:
            result["well_type_code"] = tokens_left[date_idx + 1]

    # Find LSD (surface location)
    lsd_idx = -1
    for i, tok in enumerate(tokens_left):
        if LSD_REGEX.match(tok):
            lsd_idx = i
            result["surface_location"] = tok
            break

    # Licensee: tokens between type_code and LSD
    if result["well_type_code"] and lsd_idx > -1:
        tc_idx = tokens_left.index(result["well_type_code"])
        lic_tokens = tokens_left[tc_idx + 1:lsd_idx]
        if lic_tokens:
            result["licensee"] = " ".join(lic_tokens)

    # Well name: tokens between licence_id (index 0) and well_class
    if result["well_class"] and result["well_class"] in tokens_left:
        wc_idx = tokens_left.index(result["well_class"])
        name_tokens = tokens_left[:wc_idx]
        if name_tokens:
            result["well_name"] = " ".join(name_tokens)

    # Coordinates: tokens between LSD and end of left side
    if lsd_idx > -1 and lsd_idx < len(tokens_left) - 1:
        coord_tokens = tokens_left[lsd_idx + 1:]
        if coord_tokens:
            result["coordinates"] = " ".join(coord_tokens)

    # --- Step 4: Status ---
    critical = ["licence_id", "uwi", "licensee"]
    missing = [f for f in critical if not result.get(f)]
    if missing:
        result["parse_status"] = "PARTIAL"
        notes.append(f"Missing: {missing}")
    elif notes:
        result["parse_status"] = "PARTIAL"
        result["parse_notes"] = "; ".join(notes)
    else:
        result["parse_notes"] = ""

    return result


def parse_batch(records: list) -> list:
    """Parse a batch of records that have a 'raw_block' key."""
    parsed = []
    for rec in records:
        p = parse_raw_block(rec.get("raw_block", ""))
        p["_bronze_id"] = rec.get("_bronze_id")
        if not p["licence_id"]:
            p["licence_id"] = rec.get("licence_id")
        parsed.append(p)
    return parsed


if __name__ == "__main__":
    test = (
        "12516 Tundra Daly Sinclair HZNTL 17-MAR-26 DEV "
        "TUNDRA OIL & GAS LIMITED "
        "16A-33-09-29 228.54m S of N / 60m W of E of Sec. 33 "
        "102.13-33-009-29W1.00 2194.0 Mississippian 521.45 "
        "Ensign Drilling Inc. 12"
    )

    

    r = parse_raw_block(test)
    for k, v in r.items():
        print(f"  {k:25s}: {v}")