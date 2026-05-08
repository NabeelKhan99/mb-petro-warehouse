"""
Gold Layer Loader
Populates dim_company, fact_well_approvals, and fact_spill_incidents
from Silver layer data with company name standardization.

Usage:
    python gold_loader.py
"""

import sys
import os
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import execute_values

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", 5433)),
    "dbname": os.getenv("DB_NAME", "mb_petro_warehouse"),
    "user": os.getenv("DB_USER", "airflow"),
    "password": os.getenv("DB_PASSWORD", "airflow"),
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def log_gold_run(conn, batch_id, status, total, passed, failed, notes=""):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO audit.pipeline_run_log
               (batch_id, pipeline_version, source_file, layer, status,
                total_records, passed_records, failed_records, notes)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (batch_id, "1.2.0", "gold_loader.py", "GOLD", status, total, passed, failed, notes),
        )
    conn.commit()


def populate_dim_company(conn):
    """Extract unique companies from both Silver tables and populate dim_company."""
    with conn.cursor() as cur:
        # Insert from well approvals
        cur.execute("""
            INSERT INTO gold.dim_company (company_name, company_type, first_seen_date)
            SELECT DISTINCT
                licensee,
                'OPERATOR',
                MIN(licence_issued) OVER (PARTITION BY licensee)
            FROM silver.well_approvals_cleaned
            WHERE licensee IS NOT NULL AND TRIM(licensee) != ''
            ON CONFLICT (company_name) DO NOTHING
        """)

        # Insert from spills
        cur.execute("""
            INSERT INTO gold.dim_company (company_name, company_type, first_seen_date)
            SELECT DISTINCT
                company,
                'OPERATOR',
                MIN(spill_date) OVER (PARTITION BY company)
            FROM silver.spills_cleaned
            WHERE company IS NOT NULL AND TRIM(company) != ''
            ON CONFLICT (company_name) DO NOTHING
        """)

        # Standardize display names for cross-dataset matching
        cur.execute("""
            UPDATE gold.dim_company
            SET display_name = CASE
                WHEN company_name = 'Tundra' THEN 'TUNDRA OIL & GAS LIMITED'
                WHEN company_name = 'Corex' THEN 'COREX RESOURCES LTD.'
                WHEN company_name = 'Melita' THEN 'MELITA RESOURCES LTD.'
                ELSE company_name
            END
            WHERE display_name IS NULL
        """)

    conn.commit()
    print("dim_company populated.")


def populate_fact_well_approvals(conn):
    """Insert well approvals from Silver into fact table with FK joins."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO gold.fact_well_approvals (
                company_id, date_id, licence_id, uwi, well_name, well_class,
                total_depth_m, formation, ground_elevation_m, drilling_rig,
                rig_no, surface_location, coordinates, licence_issued, validation_passed
            )
            SELECT
                c.company_id,
                d.date_id,
                w.licence_id,
                w.uwi,
                w.well_name,
                w.well_class,
                w.total_depth_m,
                w.formation,
                w.ground_elevation_m,
                w.drilling_rig,
                w.rig_no,
                w.surface_location,
                w.coordinates,
                w.licence_issued,
                w.validation_passed
            FROM silver.well_approvals_cleaned w
            LEFT JOIN gold.dim_company c ON w.licensee = c.company_name
            LEFT JOIN gold.dim_date d ON w.licence_issued = d.full_date
            WHERE w.licence_id NOT IN (
                SELECT licence_id FROM gold.fact_well_approvals
            )
        """)
    conn.commit()
    print("fact_well_approvals populated.")


def populate_fact_spill_incidents(conn):
    """Insert spills from Silver into fact table with FK joins and company remapping."""
    with conn.cursor() as cur:
        # Remap spill company_ids to canonical dim_company using display_name
        cur.execute("""
            UPDATE gold.fact_spill_incidents s
            SET company_id = c2.company_id
            FROM gold.dim_company c1
            JOIN gold.dim_company c2 ON c1.display_name = c2.company_name
            WHERE s.company_id = c1.company_id
              AND c1.display_name IS NOT NULL
              AND c1.company_name != c2.company_name
        """)

        # Insert from Silver
        cur.execute("""
            INSERT INTO gold.fact_spill_incidents (
                company_id, date_id, spill_no, source, cause, location_lsd,
                oil_vol_bbl, sw_vol_bbl, other_vol_bbl, recovered_vol_bbl,
                total_area_m2, off_lease_area_m2, validation_passed
            )
            SELECT
                c.company_id,
                d.date_id,
                s.spill_no,
                s.source,
                s.cause,
                s.location_lsd,
                s.oil_vol_bbl,
                s.sw_vol_bbl,
                s.other_vol_bbl,
                s.recovered_vol_bbl,
                s.total_area_m2,
                s.off_lease_area_m2,
                s.validation_passed
            FROM silver.spills_cleaned s
            LEFT JOIN gold.dim_company c ON s.company = c.company_name
            LEFT JOIN gold.dim_date d ON s.spill_date = d.full_date
            WHERE s.spill_no NOT IN (
                SELECT spill_no FROM gold.fact_spill_incidents
            )
        """)
    conn.commit()
    print("fact_spill_incidents populated.")


def run_gold_load():
    conn = get_connection()
    batch_id = str(uuid.uuid4())
    total = 0
    passed = 0

    try:
        # Populate dimensions first (FK dependencies)
        populate_dim_company(conn)

        # Populate facts
        populate_fact_well_approvals(conn)
        populate_fact_spill_incidents(conn)

        # Count results
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM gold.fact_well_approvals")
            wa_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM gold.fact_spill_incidents")
            sp_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM gold.dim_company")
            co_count = cur.fetchone()[0]

        total = wa_count + sp_count
        passed = total

        log_gold_run(conn, batch_id, "SUCCESS", total, passed, 0,
                     f"Companies: {co_count}, Well Approvals: {wa_count}, Spills: {sp_count}")

        print(f"Gold load complete. Companies: {co_count}, Approvals: {wa_count}, Spills: {sp_count}")

    except Exception as e:
        conn.rollback()
        log_gold_run(conn, batch_id, "FAILED", 0, 0, 0, str(e)[:500])
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_gold_load()