"""
Bronze Layer Loader
Reads processed JSON files and inserts records into Bronze tables
with batch tracking, deduplication, and audit logging.
"""

import json
import hashlib
import uuid
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values


# ---------------------------------------------------------------------------
# Configuration — override via environment variables or kwargs
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", 5433)),
    "dbname": os.getenv("DB_NAME", "mb_petro_warehouse"),
    "user": os.getenv("DB_USER", "airflow"),
    "password": os.getenv("DB_PASSWORD", "airflow"),
}


def get_connection():
    """Return a new psycopg2 connection."""
    return psycopg2.connect(**DB_CONFIG)


def compute_hash(record: dict) -> str:
    """
    Compute a deterministic SHA256 hash of a JSON-serializable record.
    Sorting keys ensures consistent hashing regardless of key order.
    """
    canonical = json.dumps(record, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def record_exists(conn, table_name: str, record_hash: str) -> bool:
    """Check if a record with the given hash already exists in the Bronze table."""
    query = sql.SQL("SELECT 1 FROM {} WHERE record_hash = %s LIMIT 1").format(
        sql.Identifier("bronze", table_name)
    )
    with conn.cursor() as cur:
        cur.execute(query, (record_hash,))
        return cur.fetchone() is not None


def insert_records(
    conn,
    table_name: str,
    batch_id: str,
    source_file: str,
    pipeline_version: str,
    records: List[dict],
) -> Tuple[int, int]:
    """
    Insert records into a Bronze table.
    Returns (inserted_count, skipped_count).
    Deduplicates by record_hash before inserting.
    """
    inserted = 0
    skipped = 0
    rows_to_insert = []

    for record in records:
        record_hash = compute_hash(record)
        if record_exists(conn, table_name, record_hash):
            skipped += 1
            continue
        rows_to_insert.append((
            batch_id,
            source_file,
            datetime.now(timezone.utc),
            pipeline_version,
            json.dumps(record, ensure_ascii=False),
            record_hash,
        ))
        inserted += 1

    if rows_to_insert:
        insert_sql = sql.SQL("""
            INSERT INTO {} (
                batch_id, source_file, ingested_at,
                pipeline_version, raw_payload, record_hash
            )
            VALUES %s
        """).format(sql.Identifier("bronze", table_name))

        with conn.cursor() as cur:
            execute_values(
                cur,
                insert_sql,
                rows_to_insert,
                template="(%s, %s, %s, %s, %s, %s)",
                page_size=100,
            )
        conn.commit()

    return inserted, skipped


def log_pipeline_run(
    conn,
    batch_id: str,
    pipeline_version: str,
    source_file: str,
    layer: str,
    status: str,
    total_records: int,
    passed_records: int,
    failed_records: int,
    notes: Optional[str] = None,
):
    """Insert a row into audit.pipeline_run_log."""
    query = """
        INSERT INTO audit.pipeline_run_log (
            batch_id, pipeline_version, source_file, layer,
            started_at, completed_at, status,
            total_records, passed_records, failed_records, notes
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    started_at = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        cur.execute(query, (
            batch_id, pipeline_version, source_file, layer,
            started_at, started_at, status,
            total_records, passed_records, failed_records, notes,
        ))
    conn.commit()


def load_well_approvals(
    json_path: str,
    pipeline_version: str = "1.0.0",
) -> Dict:
    """
    Load well approvals JSON into bronze.well_approvals_raw.
    The JSON structure is:
      {
        "report_metadata": {...},
        "well_licences": [
          {"licence_id": "...", "uwi": "...", "raw_block": "..."},
          ...
        ]
      }
    Each licence object is stored as a raw_payload JSONB row.
    """
    conn = get_connection()
    batch_id = str(uuid.uuid4())
    source_file = os.path.basename(json_path)

    try:
        with open(json_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        records = data.get("well_licences", [])
        total = len(records)

        inserted, skipped = insert_records(
            conn=conn,
            table_name="well_approvals_raw",
            batch_id=batch_id,
            source_file=source_file,
            pipeline_version=pipeline_version,
            records=records,
        )

        log_pipeline_run(
            conn=conn,
            batch_id=batch_id,
            pipeline_version=pipeline_version,
            source_file=source_file,
            layer="BRONZE",
            status="SUCCESS",
            total_records=total,
            passed_records=inserted,
            failed_records=skipped,
            notes=f"{skipped} duplicate(s) skipped",
        )

        return {
            "batch_id": batch_id,
            "total": total,
            "inserted": inserted,
            "skipped": skipped,
            "status": "SUCCESS",
        }

    except Exception as exc:
        conn.rollback()
        log_pipeline_run(
            conn=conn,
            batch_id=batch_id,
            pipeline_version=pipeline_version,
            source_file=source_file,
            layer="BRONZE",
            status="FAILED",
            total_records=0,
            passed_records=0,
            failed_records=0,
            notes=str(exc)[:500],
        )
        raise
    finally:
        conn.close()


def load_spills(
    json_path: str,
    pipeline_version: str = "1.0.0",
) -> Dict:
    """
    Load spills JSON into bronze.spills_raw.
    The JSON structure is a flat array of spill objects:
      [
        {"spill_no": "...", "spill_date": "...", "company": "...", ...},
        ...
      ]
    """
    conn = get_connection()
    batch_id = str(uuid.uuid4())
    source_file = os.path.basename(json_path)

    try:
        with open(json_path, "r", encoding="utf-8") as fh:
            records = json.load(fh)

        if not isinstance(records, list):
            raise ValueError(
                f"Expected a JSON array, got {type(records).__name__}"
            )

        total = len(records)

        inserted, skipped = insert_records(
            conn=conn,
            table_name="spills_raw",
            batch_id=batch_id,
            source_file=source_file,
            pipeline_version=pipeline_version,
            records=records,
        )

        log_pipeline_run(
            conn=conn,
            batch_id=batch_id,
            pipeline_version=pipeline_version,
            source_file=source_file,
            layer="BRONZE",
            status="SUCCESS",
            total_records=total,
            passed_records=inserted,
            failed_records=skipped,
            notes=f"{skipped} duplicate(s) skipped",
        )

        return {
            "batch_id": batch_id,
            "total": total,
            "inserted": inserted,
            "skipped": skipped,
            "status": "SUCCESS",
        }

    except Exception as exc:
        conn.rollback()
        log_pipeline_run(
            conn=conn,
            batch_id=batch_id,
            pipeline_version=pipeline_version,
            source_file=source_file,
            layer="BRONZE",
            status="FAILED",
            total_records=0,
            passed_records=0,
            failed_records=0,
            notes=str(exc)[:500],
        )
        raise
    finally:
        conn.close()
        
def load_uwi_key_list(
    json_path: str,
    pipeline_version: str = "1.0.0",
) -> Dict:
    """
    Load UWI Key List JSON into bronze.uwi_key_list_raw.
    The JSON structure is:
      {
        "report_title": "...",
        "province": "...",
        "records": [{...}, {...}, ...]
      }
    Each record in 'records' array is stored as a raw_payload JSONB row.
    """
    conn = get_connection()
    batch_id = str(uuid.uuid4())
    source_file = os.path.basename(json_path)

    try:
        with open(json_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        records = data.get("records", [])
        total = len(records)

        # Process in chunks to avoid memory issues with 44k records
        chunk_size = 500
        total_inserted = 0
        total_skipped = 0

        for i in range(0, total, chunk_size):
            chunk = records[i:i + chunk_size]
            inserted, skipped = insert_records(
                conn=conn,
                table_name="uwi_key_list_raw",
                batch_id=batch_id,
                source_file=source_file,
                pipeline_version=pipeline_version,
                records=chunk,
            )
            total_inserted += inserted
            total_skipped += skipped
            print(f"  Chunk {i//chunk_size + 1}: {inserted} inserted, {skipped} skipped")

        log_pipeline_run(
            conn=conn,
            batch_id=batch_id,
            pipeline_version=pipeline_version,
            source_file=source_file,
            layer="BRONZE",
            status="SUCCESS",
            total_records=total,
            passed_records=total_inserted,
            failed_records=total_skipped,
            notes=f"Loaded {total_inserted} UWI Key List records",
        )

        return {
            "batch_id": batch_id,
            "total": total,
            "inserted": total_inserted,
            "skipped": total_skipped,
            "status": "SUCCESS",
        }

    except Exception as exc:
        conn.rollback()
        log_pipeline_run(
            conn=conn,
            batch_id=batch_id,
            pipeline_version=pipeline_version,
            source_file=source_file,
            layer="BRONZE",
            status="FAILED",
            total_records=0,
            passed_records=0,
            failed_records=0,
            notes=str(exc)[:500],
        )
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI entrypoint for manual runs
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Load processed JSON into Bronze layer"
    )
    parser.add_argument(
        "dataset",
        choices=["well_approvals", "spills", "uwi_key_list"],
        help="Which dataset to load",
    )
    parser.add_argument(
        "json_path",
        help="Path to the processed JSON file",
    )
    parser.add_argument(
        "--pipeline-version",
        default="1.0.0",
        help="Semantic version of the pipeline",
    )
    args = parser.parse_args()

    loaders = {
        "well_approvals": load_well_approvals,
        "spills": load_spills,
        "uwi_key_list": load_uwi_key_list,
    }

    loader = loaders[args.dataset]
    result = loader(args.json_path, args.pipeline_version)
    print(json.dumps(result, indent=2))