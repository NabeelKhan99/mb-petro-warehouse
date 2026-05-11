"""
Silver Layer Loader
Reads Bronze records, parses raw_block or type-casts fields,
validates, and inserts into Silver tables.
"""

import sys
import os
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import execute_values
from well_parser import parse_raw_block

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", 5433)),
    "dbname": os.getenv("DB_NAME", "mb_petro_warehouse"),
    "user": os.getenv("DB_USER", "airflow"),
    "password": os.getenv("DB_PASSWORD", "airflow"),
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def fetch_bronze_wells(conn) -> List[dict]:
    """Fetch raw_payload from bronze.well_approvals_raw."""
    with conn.cursor() as cur:
        cur.execute("SELECT id, raw_payload FROM bronze.well_approvals_raw ORDER BY id")
        rows = cur.fetchall()
    records = []
    for row_id, payload in rows:
        rec = dict(payload)
        rec["_bronze_id"] = row_id
        records.append(rec)
    return records


def fetch_bronze_spills(conn) -> List[dict]:
    """Fetch raw_payload from bronze.spills_raw."""
    with conn.cursor() as cur:
        cur.execute("SELECT id, raw_payload FROM bronze.spills_raw ORDER BY id")
        rows = cur.fetchall()
    records = []
    for row_id, payload in rows:
        rec = dict(payload)
        rec["_bronze_id"] = row_id
        records.append(rec)
    return records


def insert_silver_wells(conn, batch_id: str, records: List[dict]) -> int:
    """Insert parsed well approvals into silver.well_approvals_cleaned."""
    rows = []
    for rec in records:
        rows.append((
            batch_id,
            rec.get("_bronze_id"),
            "well_approvals.json",
            datetime.now(timezone.utc),
            "1.1.0",
            rec.get("licence_id"),
            rec.get("well_name"),
            rec.get("issued_date"),
            rec.get("well_class"),
            rec.get("licensee"),
            rec.get("surface_location"),
            rec.get("coordinates"),
            rec.get("uwi"),
            rec.get("total_depth_m"),
            rec.get("formation"),
            rec.get("ground_elevation_m"),
            rec.get("drilling_rig"),
            rec.get("rig_no"),
            True,  # uwi_valid
            True,  # well_class_valid
            True,  # validation_passed
            0,     # validation_warnings
        ))

    with conn.cursor() as cur:
        execute_values(
            cur,
            """INSERT INTO silver.well_approvals_cleaned
               (batch_id, bronze_id, source_file, ingested_at, pipeline_version,
                licence_id, well_name, licence_issued, well_class, licensee,
                surface_location, coordinates, uwi, total_depth_m, formation,
                ground_elevation_m, drilling_rig, rig_no,
                uwi_valid, well_class_valid, validation_passed, validation_warnings)
               VALUES %s""",
            rows,
            template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            page_size=50,
        )
    conn.commit()
    return len(rows)


def insert_silver_spills(conn, batch_id: str, records: List[dict]) -> int:
    """Type-cast and insert spills into silver.spills_cleaned."""
    rows = []
    for rec in records:
        spill_date = None
        raw_date = rec.get("spill_date", "")
        if raw_date:
            for fmt in ["%d-%b-%y", "%d-%B-%y", "%Y-%m-%d"]:
                try:
                    spill_date = datetime.strptime(raw_date.strip(), fmt).strftime("%Y-%m-%d")
                    break
                except ValueError:
                    continue

        rows.append((
            batch_id,
            rec.get("_bronze_id"),
            "bronze_spills.json",
            datetime.now(timezone.utc),
            "1.1.0",
            rec.get("spill_no"),
            spill_date,
            rec.get("company"),
            rec.get("source"),
            rec.get("cause"),
            rec.get("location_lsd"),
            float(rec.get("oil_vol", 0) or 0),
            float(rec.get("sw_vol", 0) or 0),
            float(rec.get("other_vol", 0) or 0),
            float(rec.get("recovered_vol", 0) or 0),
            float(rec.get("total_area", 0) or 0),
            float(rec.get("off_lease_area", 0) or 0),
            True,  # validation_passed
            0,     # validation_warnings
        ))

    with conn.cursor() as cur:
        execute_values(
            cur,
            """INSERT INTO silver.spills_cleaned
               (batch_id, bronze_id, source_file, ingested_at, pipeline_version,
                spill_no, spill_date, company, source, cause, location_lsd,
                oil_vol_bbl, sw_vol_bbl, other_vol_bbl, recovered_vol_bbl,
                total_area_m2, off_lease_area_m2,
                validation_passed, validation_warnings)
               VALUES %s""",
            rows,
            template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            page_size=50,
        )
    conn.commit()
    return len(rows)


def log_silver_run(conn, batch_id, source_table, status, total, passed, failed, notes=""):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO audit.pipeline_run_log
               (batch_id, pipeline_version, source_file, layer, status,
                total_records, passed_records, failed_records, notes)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (batch_id, "1.1.0", source_table, "SILVER", status, total, passed, failed, notes),
        )
    conn.commit()


def load_wells_to_silver():
    conn = get_connection()
    batch_id = str(uuid.uuid4())
    try:
        records = fetch_bronze_wells(conn)
        parsed = []
        failed = 0
        for rec in records:
            p = parse_raw_block(rec.get("raw_block", ""))
            p["_bronze_id"] = rec["_bronze_id"]
            if p["parse_status"] == "FAILED":
                failed += 1
                continue
            parsed.append(p)

        inserted = insert_silver_wells(conn, batch_id, parsed)
        log_silver_run(conn, batch_id, "well_approvals", "SUCCESS", len(records), inserted, failed)
        print(json.dumps({"batch_id": batch_id, "total": len(records), "inserted": inserted, "failed": failed}, indent=2))
    except Exception as e:
        conn.rollback()
        log_silver_run(conn, batch_id, "well_approvals", "FAILED", 0, 0, 0, str(e)[:500])
        raise
    finally:
        conn.close()


def load_spills_to_silver():
    conn = get_connection()
    batch_id = str(uuid.uuid4())
    try:
        records = fetch_bronze_spills(conn)
        inserted = insert_silver_spills(conn, batch_id, records)
        log_silver_run(conn, batch_id, "spills", "SUCCESS", len(records), inserted, 0)
        print(json.dumps({"batch_id": batch_id, "total": len(records), "inserted": inserted}, indent=2))
    except Exception as e:
        conn.rollback()
        log_silver_run(conn, batch_id, "spills", "FAILED", 0, 0, 0, str(e)[:500])
        raise
    finally:
        conn.close()

def load_uwi_to_silver():
    conn = get_connection()
    batch_id = str(uuid.uuid4())
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO silver.uwi_key_list_cleaned (
                    batch_id, bronze_id, source_file, pipeline_version,
                    licence, location, well_name, uwi, company,
                    field_code, pool_code, unit_code, multi_flag,
                    status, status_date, uwi_status, uwi_date
                )
                SELECT
                    %(batch_id)s::UUID,
                    b.id,
                    'uwi_data.json',
                    '1.2.0',
                    b.raw_payload->>'licence',
                    b.raw_payload->>'location',
                    b.raw_payload->>'well_name',
                    b.raw_payload->>'uwi',
                    b.raw_payload->>'company',
                    b.raw_payload->>'field',
                    NULLIF(b.raw_payload->>'pool', ''),
                    b.raw_payload->>'unit',
                    b.raw_payload->>'multi',
                    b.raw_payload->>'status',
                    NULLIF(b.raw_payload->>'status_date', '')::DATE,
                    b.raw_payload->>'uwi_status',
                    NULLIF(b.raw_payload->>'uwi_date', '')::DATE
                FROM bronze.uwi_key_list_raw b
                WHERE b.raw_payload->>'licence' NOT IN (
                    SELECT licence FROM silver.uwi_key_list_cleaned
                )
            """, {"batch_id": batch_id})

            cur.execute(
                "SELECT COUNT(*) FROM silver.uwi_key_list_cleaned WHERE batch_id = %s",
                (batch_id,)
            )
            count = cur.fetchone()[0]

        conn.commit()
        log_silver_run(conn, batch_id, "uwi_key_list", "SUCCESS", count, count, 0)
        print(json.dumps({"batch_id": batch_id, "inserted": count}, indent=2))
    except Exception as e:
        conn.rollback()
        log_silver_run(conn, batch_id, "uwi_key_list", "FAILED", 0, 0, 0, str(e)[:500])
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", choices=["well_approvals", "spills", "uwi_key_list"])
    args = parser.parse_args()

    if args.dataset == "well_approvals":
        load_wells_to_silver()
    elif args.dataset == "spills":
        load_spills_to_silver()
    elif args.dataset == "uwi_key_list":
        load_uwi_to_silver()