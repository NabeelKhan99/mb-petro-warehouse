"""
Validation Engine
Applies quality rules from quality_rules.py to Bronze records.
Outputs: passed_records list, failed_records list with rule violations.
"""

import re
import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Any, Optional
from quality_rules import RULE_SETS


# ---------------------------------------------------------------------------
# UWI Validation Functions (Manitoba Petroleum Branch spec)
# ---------------------------------------------------------------------------

UWI_REGEX = re.compile(
    r"^1[0A-DS-W][0-9]\.[0-9]{2}-[0-9]{2}-[0-9]{3}-[0-9]{2}W1\.[0-9]{2}$"
)

VALID_LOCATION_CODES = {"0", "A", "B", "C", "D", "S", "W"}
VALID_SEQUENCE_CODES = {"0", "2", "3", "4", "5", "6", "7", "8", "9"}
VALID_WELL_CLASSES = {"DEV", "DPW", "SWD", "OBS", "INJ", "HZNTL", "PROV", "VERT"}
VALID_SPILL_SOURCES = {"FLOWLINE", "WELL", "TANK", "PIPELINE", "BATTERY", "OTHER"}
VALID_SPILL_CAUSES = {"CORROSION", "HEAD", "EQUIPMENT_FAILURE", "HUMAN_ERROR", "WEATHER", "OTHER"}
SPILL_NO_REGEX = re.compile(r"^\d{4}-\d{2}-[A-Z]$")
LSD_REGEX = re.compile(r"^\d{2}-\d{2}-\d{2}-\d{2}$")


# ---------------------------------------------------------------------------
# Rule application functions — each maps to a rule_id in quality_rules.py
# ---------------------------------------------------------------------------

def apply_rule_uwi_001(record: dict) -> Tuple[bool, str]:
    """UWI-001: UWI must be 21 characters in standard Manitoba format."""
    uwi = record.get("uwi", "")
    if len(uwi.strip()) != 21:
        return False, f"UWI length is {len(uwi.strip())}, expected 21"
    return True, ""


def apply_rule_uwi_002(record: dict) -> Tuple[bool, str]:
    """UWI-002: Survey System Code must be 1."""
    uwi = record.get("uwi", "").strip()
    if len(uwi) < 1 or uwi[0] != "1":
        return False, f"Survey System Code is '{uwi[0] if uwi else ''}', expected '1'"
    return True, ""


def apply_rule_uwi_003(record: dict) -> Tuple[bool, str]:
    """UWI-003: Location Exception Code must be valid."""
    uwi = record.get("uwi", "").strip()
    if len(uwi) < 2 or uwi[1] not in VALID_LOCATION_CODES:
        return False, f"Location Exception Code is '{uwi[1] if len(uwi) > 1 else ''}', expected one of {VALID_LOCATION_CODES}"
    return True, ""


def apply_rule_uwi_004(record: dict) -> Tuple[bool, str]:
    """UWI-004: Drilling Sequence must be 0 or 2-9."""
    uwi = record.get("uwi", "").strip()
    if len(uwi) < 3 or uwi[2] not in VALID_SEQUENCE_CODES:
        return False, f"Drilling Sequence is '{uwi[2] if len(uwi) > 2 else ''}', expected one of {VALID_SEQUENCE_CODES}"
    return True, ""


def apply_rule_uwi_005(record: dict) -> Tuple[bool, str]:
    """UWI-005: Event Sequence must be a digit."""
    uwi = record.get("uwi", "").strip()
    if len(uwi) < 16 or not uwi[15].isdigit():
        return False, f"Event Sequence is '{uwi[15] if len(uwi) > 15 else ''}', expected digit 0-9"
    return True, ""

def apply_rule_uwi_005a(record: dict) -> Tuple[bool, str]:
    """UWI-005a: Position 15 (DLS reserved) must be 0 for Manitoba wells."""
    uwi = record.get("uwi", "").strip()
    if len(uwi) < 15 or uwi[14] != "0":
        return False, f"Position 15 (DLS reserved) is '{uwi[14] if len(uwi) > 14 else ''}', expected '0'"
    return True, ""


def apply_rule_uwi_006(record: dict) -> Tuple[bool, str]:
    """UWI-006: UWI must match canonical regex."""
    uwi = record.get("uwi", "").strip()
    if not UWI_REGEX.match(uwi):
        return False, f"UWI '{uwi}' does not match Manitoba DLS pattern"
    return True, ""


def apply_rule_wcl_001(record: dict) -> Tuple[bool, str]:
    """WCL-001: Well class must be valid."""
    wc = record.get("well_class", "").strip().upper()
    if wc not in VALID_WELL_CLASSES:
        return False, f"Well class '{wc}' not in valid codes: {VALID_WELL_CLASSES}"
    return True, ""


def apply_rule_wcl_002(record: dict) -> Tuple[bool, str]:
    """WCL-002: Well class must not be null or empty."""
    wc = record.get("well_class", "")
    if not wc or not wc.strip():
        return False, "Well class is null or empty"
    return True, ""


def apply_rule_lic_001(record: dict) -> Tuple[bool, str]:
    """LIC-001: Licensee must not be null or empty."""
    lic = record.get("licensee", record.get("company", ""))
    if not lic or not lic.strip():
        return False, "Licensee/Company name is null or empty"
    return True, ""


def apply_rule_lic_002(record: dict) -> Tuple[bool, str]:
    """LIC-002: Licensee name should be at least 3 characters."""
    lic = record.get("licensee", record.get("company", ""))
    if lic and len(lic.strip()) < 3:
        return False, f"Licensee name '{lic.strip()}' is shorter than 3 characters"
    return True, ""


def apply_rule_td_001(record: dict) -> Tuple[bool, str]:
    """TD-001: Total Depth must be positive."""
    td = record.get("total_depth_m")
    if td is None:
        return False, "Total Depth is null"
    try:
        if float(td) <= 0:
            return False, f"Total Depth {td} is not positive"
    except (ValueError, TypeError):
        return False, f"Total Depth '{td}' is not a valid number"
    return True, ""


def apply_rule_td_002(record: dict) -> Tuple[bool, str]:
    """TD-002: Total Depth should be in reasonable range."""
    td = record.get("total_depth_m")
    if td is None:
        return True, ""
    try:
        val = float(td)
        if val < 100 or val > 5000:
            return False, f"Total Depth {val}m is outside expected range 100-5000m"
    except (ValueError, TypeError):
        return False, f"Total Depth '{td}' is not a valid number"
    return True, ""


def apply_rule_elv_001(record: dict) -> Tuple[bool, str]:
    """ELV-001: Ground elevation must be positive."""
    elv = record.get("ground_elevation_m")
    if elv is None:
        return False, "Ground elevation is null"
    try:
        if float(elv) <= 0:
            return False, f"Ground elevation {elv} is not positive"
    except (ValueError, TypeError):
        return False, f"Ground elevation '{elv}' is not a valid number"
    return True, ""


def apply_rule_elv_002(record: dict) -> Tuple[bool, str]:
    """ELV-002: Ground elevation should be in Manitoba range."""
    elv = record.get("ground_elevation_m")
    if elv is None:
        return True, ""
    try:
        val = float(elv)
        if val < 200 or val > 900:
            return False, f"Ground elevation {val}m is outside expected Manitoba range 200-900m"
    except (ValueError, TypeError):
        return False, f"Ground elevation '{elv}' is not a valid number"
    return True, ""


def apply_rule_dat_001(record: dict) -> Tuple[bool, str]:
    """DAT-001: Date must be parseable and not in the future."""
    date_str = record.get("issued_date", record.get("spill_date", ""))
    if not date_str:
        return False, "Date field is null or empty"
    for fmt in ["%d-%b-%y", "%d-%B-%y", "%Y-%m-%d"]:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            if dt.date() > datetime.now(timezone.utc).date():
                return False, f"Date {date_str} is in the future"
            return True, ""
        except ValueError:
            continue
    return False, f"Date '{date_str}' is not parseable"


def apply_rule_dat_002(record: dict) -> Tuple[bool, str]:
    """DAT-002: Date should not be before year 2000."""
    date_str = record.get("issued_date", record.get("spill_date", ""))
    if not date_str:
        return True, ""
    for fmt in ["%d-%b-%y", "%d-%B-%y", "%Y-%m-%d"]:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            if dt.year < 2000:
                return False, f"Date {date_str} is before year 2000"
            return True, ""
        except ValueError:
            continue
    return True, ""


def apply_rule_frm_001(record: dict) -> Tuple[bool, str]:
    """FRM-001: Formation must not be null or empty."""
    frm = record.get("formation", "")
    if not frm or not frm.strip():
        return False, "Formation is null or empty"
    return True, ""


def apply_rule_spl_001(record: dict) -> Tuple[bool, str]:
    """SPL-001: Spill number must match format."""
    sn = record.get("spill_no", "")
    if not SPILL_NO_REGEX.match(sn.strip()):
        return False, f"Spill number '{sn}' does not match format YYYY-NN-V"
    return True, ""


def apply_rule_spl_002(record: dict) -> Tuple[bool, str]:
    """SPL-002: Company name must not be null."""
    return apply_rule_lic_001(record)


def apply_rule_spl_003(record: dict) -> Tuple[bool, str]:
    """SPL-003: Spill date must be parseable."""
    return apply_rule_dat_001(record)


def apply_rule_spl_004(record: dict) -> Tuple[bool, str]:
    """SPL-004: Volume fields must be non-negative."""
    for field in ["oil_vol", "sw_vol", "other_vol"]:
        val = record.get(field)
        if val is not None:
            try:
                if float(val) < 0:
                    return False, f"{field} is negative: {val}"
            except (ValueError, TypeError):
                return False, f"{field} is not a valid number: {val}"
    return True, ""


def apply_rule_spl_005(record: dict) -> Tuple[bool, str]:
    """SPL-005: At least one volume > 0."""
    total = sum(float(record.get(f, 0) or 0) for f in ["oil_vol", "sw_vol", "other_vol"])
    if total <= 0:
        return False, "Total spill volume is zero — suspect record"
    return True, ""


def apply_rule_spl_006(record: dict) -> Tuple[bool, str]:
    """SPL-006: Recovered volume <= total spilled."""
    total = sum(float(record.get(f, 0) or 0) for f in ["oil_vol", "sw_vol", "other_vol"])
    recovered = float(record.get("recovered_vol", 0) or 0)
    if recovered > total:
        return False, f"Recovered volume {recovered} exceeds total spilled {total}"
    return True, ""


def apply_rule_spl_007(record: dict) -> Tuple[bool, str]:
    """SPL-007: Recovered volume non-negative."""
    recovered = float(record.get("recovered_vol", 0) or 0)
    if recovered < 0:
        return False, f"Recovered volume is negative: {recovered}"
    return True, ""


def apply_rule_spl_008(record: dict) -> Tuple[bool, str]:
    """SPL-008: Total area must be positive."""
    area = record.get("total_area")
    if area is not None:
        try:
            if float(area) <= 0:
                return False, f"Total area {area} is not positive"
        except (ValueError, TypeError):
            return False, f"Total area '{area}' is not a valid number"
    return True, ""


def apply_rule_spl_009(record: dict) -> Tuple[bool, str]:
    """SPL-009: Off-lease area <= total area."""
    total = record.get("total_area", 0) or 0
    off_lease = record.get("off_lease_area", 0) or 0
    try:
        if float(off_lease) > float(total):
            return False, f"Off-lease area {off_lease} exceeds total area {total}"
    except (ValueError, TypeError):
        return False, "Area values are not valid numbers"
    return True, ""


def apply_rule_spl_010(record: dict) -> Tuple[bool, str]:
    """SPL-010: Source must be recognized category."""
    src = record.get("source", "").strip().upper()
    if src and src not in VALID_SPILL_SOURCES:
        return False, f"Source '{src}' not in recognized categories: {VALID_SPILL_SOURCES}"
    return True, ""


def apply_rule_spl_011(record: dict) -> Tuple[bool, str]:
    """SPL-011: Cause must be recognized category."""
    cause = record.get("cause", "").strip().upper()
    if cause and cause not in VALID_SPILL_CAUSES:
        return False, f"Cause '{cause}' not in recognized categories: {VALID_SPILL_CAUSES}"
    return True, ""


def apply_rule_spl_012(record: dict) -> Tuple[bool, str]:
    """SPL-012: Location LSD should match format."""
    lsd = record.get("location_lsd", "")
    if lsd and not LSD_REGEX.match(lsd.strip()):
        return False, f"Location LSD '{lsd}' does not match format NN-NN-NN-NN"
    return True, ""


# ---------------------------------------------------------------------------
# Rule function registry — maps rule_id to its implementation
# ---------------------------------------------------------------------------

RULE_FUNCTIONS = {
    # Well approval rules
    "UWI-001": apply_rule_uwi_001,
    "UWI-002": apply_rule_uwi_002,
    "UWI-003": apply_rule_uwi_003,
    "UWI-004": apply_rule_uwi_004,
    "UWI-005": apply_rule_uwi_005,
    "UWI-006": apply_rule_uwi_006,
    "WCL-001": apply_rule_wcl_001,
    "WCL-002": apply_rule_wcl_002,
    "LIC-001": apply_rule_lic_001,
    "LIC-002": apply_rule_lic_002,
    "TD-001": apply_rule_td_001,
    "TD-002": apply_rule_td_002,
    "ELV-001": apply_rule_elv_001,
    "ELV-002": apply_rule_elv_002,
    "DAT-001": apply_rule_dat_001,
    "DAT-002": apply_rule_dat_002,
    "FRM-001": apply_rule_frm_001,
    # Spill rules
    "SPL-001": apply_rule_spl_001,
    "SPL-002": apply_rule_spl_002,
    "SPL-003": apply_rule_spl_003,
    "SPL-004": apply_rule_spl_004,
    "SPL-005": apply_rule_spl_005,
    "SPL-006": apply_rule_spl_006,
    "SPL-007": apply_rule_spl_007,
    "SPL-008": apply_rule_spl_008,
    "SPL-009": apply_rule_spl_009,
    "SPL-010": apply_rule_spl_010,
    "SPL-011": apply_rule_spl_011,
    "SPL-012": apply_rule_spl_012,
}


# ---------------------------------------------------------------------------
# Main validation function
# ---------------------------------------------------------------------------

def validate_record(
    record: dict,
    dataset: str,
) -> Tuple[bool, List[Dict]]:
    """
    Validate a single record against all rules for its dataset.

    Args:
        record: The record dict with fields to validate.
        dataset: 'well_approvals' or 'spills'.

    Returns:
        (passed, violations): Tuple where passed is True if no ERROR-level
        violations occurred, and violations is a list of violation dicts.
    """
    rules = RULE_SETS.get(dataset, [])
    violations = []
    has_error = False

    for rule in rules:
        rule_id = rule["rule_id"]
        func = RULE_FUNCTIONS.get(rule_id)

        if func is None:
            violations.append({
                "rule_id": rule_id,
                "severity": rule["severity"],
                "passed": True,
                "message": f"Rule {rule_id} has no implementation — skipped",
            })
            continue

        passed, message = func(record)

        if not passed:
            violations.append({
                "rule_id": rule_id,
                "severity": rule["severity"],
                "category": rule["category"],
                "passed": False,
                "message": message,
            })
            if rule["severity"] == "ERROR":
                has_error = True

    return (not has_error), violations


def validate_batch(
    records: List[dict],
    dataset: str,
) -> Dict[str, Any]:
    """
    Validate a batch of records.

    Returns:
        Dict with passed_records, failed_records, and summary counts.
    """
    passed_records = []
    failed_records = []
    total_violations = 0
    error_count = 0
    warn_count = 0

    for record in records:
        passed, violations = validate_record(record, dataset)
        record["_validation_passed"] = passed
        record["_violations"] = violations

        if passed:
            passed_records.append(record)
        else:
            failed_records.append(record)

        for v in violations:
            total_violations += 1
            if v["severity"] == "ERROR":
                error_count += 1
            else:
                warn_count += 1

    return {
        "total": len(records),
        "passed": len(passed_records),
        "failed": len(failed_records),
        "total_violations": total_violations,
        "errors": error_count,
        "warnings": warn_count,
        "passed_records": passed_records,
        "failed_records": failed_records,
    }


if __name__ == "__main__":
    # Quick smoke test
    test_well = {
        "uwi": "102.13-33-009-29W1.00",
        "well_class": "HZNTL",
        "licensee": "TUNDRA OIL & GAS LIMITED",
        "total_depth_m": 2194.0,
        "ground_elevation_m": 521.45,
        "issued_date": "17-MAR-26",
        "formation": "Mississippian",
    }

    test_spill = {
        "spill_no": "2021-08-V",
        "spill_date": "13-APR-21",
        "company": "Corex",
        "source": "FLOWLINE",
        "cause": "CORROSION",
        "location_lsd": "04-22-11-26",
        "oil_vol": 1.0,
        "sw_vol": 4.0,
        "other_vol": 0.0,
        "recovered_vol": 5.0,
        "total_area": 500.0,
        "off_lease_area": 500.0,
    }

    print("Testing well approval record...")
    passed, violations = validate_record(test_well, "well_approvals")
    print(f"  Passed: {passed}")
    for v in violations:
        print(f"  [{v['severity']}] {v['rule_id']}: {v['message']}")

    print("\nTesting spill record...")
    passed, violations = validate_record(test_spill, "spills")
    print(f"  Passed: {passed}")
    for v in violations:
        print(f"  [{v['severity']}] {v['rule_id']}: {v['message']}")