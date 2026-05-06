"""
Data Quality Rules and Governance Contracts
Manitoba Petroleum Data Warehouse

Each rule is defined as a dictionary with:
  - rule_id:       Unique identifier (e.g., UWI-001)
  - category:      Domain category (UWI, WELL_CLASS, COORDINATES, SPILL, etc.)
  - field:         Target field(s) the rule applies to
  - description:   Plain-English explanation of the rule
  - severity:      ERROR (reject record) or WARN (flag but accept)
  - reference:     Regulatory or industry citation
  - logic:         Brief description of the validation logic

Rules are grouped into rule_sets for each dataset.
"""

# ===========================================================================
# WELL APPROVALS — QUALITY RULES
# ===========================================================================

WELL_APPROVAL_RULES = [

    # --- UWI Format Rules ---
  {
    "rule_id": "UWI-001",
    "category": "UWI",
    "field": "uwi",
    "description": "UWI must be 21 characters in standard Manitoba DLS format",
    "severity": "ERROR",
    "reference": "Manitoba Petroleum Branch — UWI Specification, Section A (21-char observed standard)",
    "logic": "LEN(TRIM(uwi)) == 21",
},
    {
        "rule_id": "UWI-002",
        "category": "UWI",
        "field": "uwi",
        "description": "Survey System Code (position 1) must be 1 for DLS in Manitoba",
        "severity": "ERROR",
        "reference": "Manitoba Petroleum Branch — UWI Specification, Section B",
        "logic": "uwi[0] == '1'",
    },
    {
        "rule_id": "UWI-003",
        "category": "UWI",
        "field": "uwi",
        "description": "Location Exception Code (position 2) must be in [0, A, B, C, D, S, W]",
        "severity": "ERROR",
        "reference": "Manitoba Petroleum Branch — UWI Specification, Section C",
        "logic": "uwi[1] in {'0','A','B','C','D','S','W'}",
    },
    {
        "rule_id": "UWI-004",
        "category": "UWI",
        "field": "uwi",
        "description": "Drilling Sequence (position 3) must be a digit 0-9, excluding 1",
        "severity": "ERROR",
        "reference": "Manitoba Petroleum Branch — UWI Specification, Section C",
        "logic": "uwi[2] in {'0','2','3','4','5','6','7','8','9'}",
    },
    {
        "rule_id": "UWI-005",
        "category": "UWI",
        "field": "uwi",
        "description": "Event Sequence (position 16) must be a digit 0-9",
        "severity": "ERROR",
        "reference": "Manitoba Petroleum Branch — UWI Specification, Section E",
        "logic": "uwi[15] in set('0123456789')",
    },
    {
        "rule_id": "UWI-006",
        "category": "UWI",
        "field": "uwi",
        "description": "UWI must match canonical regex pattern for Manitoba DLS wells",
        "severity": "ERROR",
        "reference": "Manitoba Petroleum Branch — UWI Specification, Section D",
        "logic": "Regex: ^1[0A-DS-W][0-9]\\.[0-9]{2}-[0-9]{2}-[0-9]{3}-[0-9]{2}W1\\.[0-9]{2}$",
    },

    # --- Well Class Rules ---
    {
        "rule_id": "WCL-001",
        "category": "WELL_CLASS",
        "field": "well_class",
        "description": "Well class must be one of the valid Manitoba Petroleum Branch codes",
        "severity": "ERROR",
        "reference": "Manitoba Well Status Types documentation",
        "logic": "well_class in {'DEV', 'DPW', 'SWD', 'OBS', 'INJ', 'HZNTL', 'PROV', 'VERT'}",
        "note": "DEV=Development, DPW=Disposal Well, SWD=Salt Water Disposal, OBS=Observation, INJ=Injection, PROV=Proven, VERT=Vertical"
    },
    {
        "rule_id": "WCL-002",
        "category": "WELL_CLASS",
        "field": "well_class",
        "description": "Well class must not be NULL or empty string",
        "severity": "ERROR",
        "reference": "Internal governance standard",
        "logic": "well_class IS NOT NULL AND well_class != ''",
    },

    # --- Licensee Rules ---
    {
        "rule_id": "LIC-001",
        "category": "LICENSEE",
        "field": "licensee",
        "description": "Licensee name must not be NULL, empty, or whitespace-only",
        "severity": "ERROR",
        "reference": "Internal governance standard",
        "logic": "licensee IS NOT NULL AND TRIM(licensee) != ''",
    },
    {
        "rule_id": "LIC-002",
        "category": "LICENSEE",
        "field": "licensee",
        "description": "Licensee name must be at least 3 characters",
        "severity": "WARN",
        "reference": "Internal governance standard",
        "logic": "LEN(TRIM(licensee)) >= 3",
    },

    # --- Total Depth Rules ---
    {
        "rule_id": "TD-001",
        "category": "TOTAL_DEPTH",
        "field": "total_depth_m",
        "description": "Total Depth must be a positive number",
        "severity": "ERROR",
        "reference": "Manitoba Petroleum Branch — well licence application guidelines",
        "logic": "total_depth_m > 0",
    },
    {
        "rule_id": "TD-002",
        "category": "TOTAL_DEPTH",
        "field": "total_depth_m",
        "description": "Total Depth should be between 100m and 5000m for Manitoba wells",
        "severity": "WARN",
        "reference": "Manitoba historical well data range analysis",
        "logic": "100 <= total_depth_m <= 5000",
    },

    # --- Ground Elevation Rules ---
    {
        "rule_id": "ELV-001",
        "category": "ELEVATION",
        "field": "ground_elevation_m",
        "description": "Ground elevation must be positive",
        "severity": "ERROR",
        "reference": "Internal governance standard",
        "logic": "ground_elevation_m > 0",
    },
    {
        "rule_id": "ELV-002",
        "category": "ELEVATION",
        "field": "ground_elevation_m",
        "description": "Ground elevation should be between 200m and 900m for Manitoba",
        "severity": "WARN",
        "reference": "Manitoba topographical range analysis",
        "logic": "200 <= ground_elevation_m <= 900",
    },

    # --- Date Rules ---
    {
        "rule_id": "DAT-001",
        "category": "DATE",
        "field": "issued_date",
        "description": "Issued date must be parseable and not in the future",
        "severity": "ERROR",
        "reference": "Internal governance standard",
        "logic": "issued_date is valid date AND issued_date <= CURRENT_DATE",
    },
    {
        "rule_id": "DAT-002",
        "category": "DATE",
        "field": "issued_date",
        "description": "Issued date should not be older than January 1, 2000 for current system",
        "severity": "WARN",
        "reference": "System migration boundary",
        "logic": "issued_date >= '2000-01-01'",
    },

    # --- Formation Rules ---
    {
        "rule_id": "FRM-001",
        "category": "FORMATION",
        "field": "formation",
        "description": "Formation must not be NULL or empty",
        "severity": "ERROR",
        "reference": "Internal governance standard",
        "logic": "formation IS NOT NULL AND formation != ''",
    },
]

# ===========================================================================
# SPILLS — QUALITY RULES
# ===========================================================================

SPILL_RULES = [

    # --- Spill Identifier Rules ---
    {
        "rule_id": "SPL-001",
        "category": "SPILL_ID",
        "field": "spill_no",
        "description": "Spill number must match format YYYY-NN or YYYY-NN-V",
        "severity": "ERROR",
        "reference": "Manitoba Spill Stats reporting format",
        "logic": "Regex: ^\\d{4}-\\d{2}-[A-Z]$",
    },

    # --- Company Rules ---
    {
        "rule_id": "SPL-002",
        "category": "LICENSEE",
        "field": "company",
        "description": "Company name must not be NULL, empty, or whitespace-only",
        "severity": "ERROR",
        "reference": "Internal governance standard",
        "logic": "company IS NOT NULL AND TRIM(company) != ''",
    },

    # --- Date Rules ---
    {
        "rule_id": "SPL-003",
        "category": "DATE",
        "field": "spill_date",
        "description": "Spill date must be parseable in DD-MON-YY format",
        "severity": "ERROR",
        "reference": "Manitoba Spill Stats reporting format",
        "logic": "spill_date matches DD-MON-YY (e.g., '13-APR-21')",
    },

    # --- Volume Rules ---
    {
        "rule_id": "SPL-004",
        "category": "VOLUME",
        "field": "oil_vol, sw_vol, other_vol",
        "description": "All volume fields must be non-negative numbers",
        "severity": "ERROR",
        "reference": "Internal governance standard",
        "logic": "oil_vol >= 0 AND sw_vol >= 0 AND other_vol >= 0",
    },
    {
        "rule_id": "SPL-005",
        "category": "VOLUME",
        "field": "oil_vol, sw_vol, other_vol",
        "description": "At least one volume field must be greater than zero (a spill with zero volume is suspect)",
        "severity": "WARN",
        "reference": "Internal governance standard",
        "logic": "(oil_vol + sw_vol + other_vol) > 0",
    },

    # --- Recovery Rules ---
    {
        "rule_id": "SPL-006",
        "category": "VOLUME",
        "field": "recovered_vol",
        "description": "Recovered volume must not exceed total spilled volume",
        "severity": "ERROR",
        "reference": "Internal governance standard",
        "logic": "recovered_vol <= (oil_vol + sw_vol + other_vol)",
    },
    {
        "rule_id": "SPL-007",
        "category": "VOLUME",
        "field": "recovered_vol",
        "description": "Recovered volume must be non-negative",
        "severity": "ERROR",
        "reference": "Internal governance standard",
        "logic": "recovered_vol >= 0",
    },

    # --- Area Rules ---
    {
        "rule_id": "SPL-008",
        "category": "AREA",
        "field": "total_area",
        "description": "Total affected area must be positive if provided",
        "severity": "WARN",
        "reference": "Internal governance standard",
        "logic": "total_area > 0",
    },
    {
        "rule_id": "SPL-009",
        "category": "AREA",
        "field": "off_lease_area",
        "description": "Off-lease affected area must not exceed total area",
        "severity": "ERROR",
        "reference": "Internal governance standard",
        "logic": "off_lease_area <= total_area",
    },

    # --- Source Classification ---
    {
        "rule_id": "SPL-010",
        "category": "CLASSIFICATION",
        "field": "source",
        "description": "Spill source must be a recognized category",
        "severity": "WARN",
        "reference": "Manitoba Spill Stats classification",
        "logic": "source in {'FLOWLINE', 'WELL', 'TANK', 'PIPELINE', 'BATTERY', 'OTHER', 'RISER', 'TRUCK', 'TREATER', 'SATELLITE', 'INJECTOR'}",
    },
    {
        "rule_id": "SPL-011",
        "category": "CLASSIFICATION",
        "field": "cause",
        "description": "Spill cause must be a recognized category",
        "severity": "WARN",
        "reference": "Manitoba Spill Stats classification",
        "logic": "cause in {'CORROSION', 'HEAD', 'EQUIPMENT_FAILURE', 'HUMAN_ERROR', 'WEATHER', 'OTHER', 'ROLLOVER', 'MECHANICAL', 'LEAK', 'RUPTURE', 'OVERFLOW', 'UNKNOWN'}",
    },

    # --- Location Rules ---
    {
        "rule_id": "SPL-012",
        "category": "LOCATION",
        "field": "location_lsd",
        "description": "Location LSD should match legal survey format (e.g., 04-22-11-26)",
        "severity": "WARN",
        "reference": "Manitoba DLS system",
        "logic": "Regex: ^\\d{2}-\\d{2}-\\d{2}-\\d{2}$",
    },
]

# ===========================================================================
# AGGREGATE RULE SETS
# ===========================================================================

RULE_SETS = {
    "well_approvals": WELL_APPROVAL_RULES,
    "spills": SPILL_RULES,
}

# ===========================================================================
# RULE SEVERITY SUMMARY
# ===========================================================================

def summarize_rules():
    """Print a summary of all rules by category and severity."""
    for dataset_name, rules in RULE_SETS.items():
        print(f"\n{'='*60}")
        print(f"Dataset: {dataset_name}")
        print(f"Total rules: {len(rules)}")
        errors = [r for r in rules if r["severity"] == "ERROR"]
        warns = [r for r in rules if r["severity"] == "WARN"]
        print(f"  ERROR: {len(errors)}")
        print(f"  WARN:  {len(warns)}")
        print(f"  Categories: {sorted(set(r['category'] for r in rules))}")
    print(f"\n{'='*60}")


if __name__ == "__main__":
    summarize_rules()