"""
Validation Runner
Reads Bronze records, applies validation rules, logs results,
and quarantines failed records.

Usage (from project root):
    cd scripts/validation
    python run_validation.py well_approvals
    python run_validation.py spills
"""

import sys
import os
import json
import uuid
import hashlib
from datetime import datetime, timezone

# Ensure current directory is on path for sibling imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg2
from psycopg2.extras import execute_values
from validate import validate_batch

# ---------------------------------------------------------------------------
# Database configuration
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", 5433)),
    "dbname": os.getenv("DB_NAME", "mb_petro_warehouse"),
    "user": os.getenv("DB_USER", "airflow"),
    "password": os.getenv("DB_PASSWORD", "airflow"),
}

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_connection():
    """Return a new psycopg2 connection."""
    return psycopg2.connect(**DB_CONFIG)


def fetch_bronze_records(conn, source_table):
    """Fetch all raw_payload records from a Bronze table."""
    table_map = {
        "well_approvals": "bronze.well_approvals_raw",
        "spills": "bronze.spills_raw",
    }
    if source_table not in table_map:
        raise ValueError(f"Unknown dataset '{source_table}'. Choose from: {list(table_map.keys())}")

    table_name = table_map[source_table]
    with conn.cursor() as cur:
        cur.execute(f"SELECT id, raw_payload FROM {table_name} ORDER BY id")
        rows = cur.fetchall()

    records = []
    for row_id, payload in rows:
        record = dict(payload)
        record["_bronze_id"] = row_id
        records.append(record)
    return records


def quarantine_failed_records(conn, batch_id, source_table, failed_records):
    """Insert failed records into audit.quarantine_records."""
    if not failed_records:
        return 0

    rows = []
    for record in failed_records:
        clean = {k: v for k, v in record.items() if not k.startswith("_")}
        record_hash = hashlib.sha256(
            json.dumps(clean, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        violations = record.get("_violations", [])
        error_count = sum(1 for v in violations if v["severity"] == "ERROR")
        warn_count = sum(1 for v in violations if v["severity"] == "WARN")

        rows.append((
            batch_id,
            source_table,
            record_hash,
            json.dumps(clean, ensure_ascii=False),
            json.dumps(violations),
            error_count,
            warn_count,
        ))

    with conn.cursor() as cur:
        execute_values(
            cur,
            """INSERT INTO audit.quarantine_records
               (batch_id, source_table, record_hash, raw_payload,
                violation_summary, error_count, warn_count)
               VALUES %s""",
            rows,
            template="(%s, %s, %s, %s, %s, %s, %s)",
            page_size=100,
        )
    conn.commit()
    return len(rows)


def log_validation_run(conn, batch_id, source_table, status, total, passed, failed, notes=""):
    """Log validation run to audit.validation_run_log."""
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO audit.validation_run_log
               (batch_id, source_table, status, total_records,
                passed_records, failed_records, notes)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (batch_id, source_table, status, total, passed, failed, notes),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def run_validation(dataset, pipeline_version="1.0.0"):
    """
    Validate all Bronze records for a given dataset.

    Args:
        dataset: 'well_approvals' or 'spills'
        pipeline_version: Semantic version string
    """
    conn = get_connection()
    batch_id = str(uuid.uuid4())

    try:
        records = fetch_bronze_records(conn, dataset)
        total = len(records)

        if total == 0:
            log_validation_run(conn, batch_id, dataset, "SUCCESS", 0, 0, 0, "No records")
            return {"batch_id": batch_id, "total": 0, "passed": 0, "failed": 0}

        result = validate_batch(records, dataset)
        quarantined = quarantine_failed_records(
            conn, batch_id, dataset, result["failed_records"]
        )

        notes = f"Errors: {result['errors']}, Warnings: {result['warnings']}, Quarantined: {quarantined}"
        log_validation_run(
            conn, batch_id, dataset, "SUCCESS",
            result["total"], result["passed"], result["failed"], notes,
        )

        return {
            "batch_id": batch_id,
            "total": result["total"],
            "passed": result["passed"],
            "failed": result["failed"],
            "errors": result["errors"],
            "warnings": result["warnings"],
            "quarantined": quarantined,
        }

    except Exception as exc:
        conn.rollback()
        log_validation_run(conn, batch_id, dataset, "FAILED", 0, 0, 0, str(exc)[:500])
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate Bronze records")
    parser.add_argument("dataset", choices=["well_approvals", "spills"])
    parser.add_argument("--pipeline-version", default="1.0.0")
    args = parser.parse_args()

    result = run_validation(args.dataset, args.pipeline_version)
    print(json.dumps(result, indent=2))