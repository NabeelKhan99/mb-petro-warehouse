# scripts/db/init_db.py
# Purpose: Initialize the database schema for MB Petro Warehouse
# Run once before any pipeline execution

import os
import sys
import logging
from pathlib import Path
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# -----------------------------------------------------------
# Logging setup
# -----------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# -----------------------------------------------------------
# Load environment variables
# -----------------------------------------------------------
load_dotenv()

DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = os.getenv("DB_PORT", "5432")
DB_NAME     = os.getenv("DB_NAME", "mb_petro_warehouse")
DB_USER     = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    f"?sslmode=disable"
)

# -----------------------------------------------------------
# Path to schema SQL file
# -----------------------------------------------------------
SCHEMA_FILE = Path(__file__).parent / "schema.sql"


def get_engine():
    try:
        engine = create_engine(DATABASE_URL, echo=False)
        log.info("Database engine created successfully.")
        return engine
    except Exception as e:
        log.error(f"Failed to create database engine: {e}")
        sys.exit(1)


def run_schema(engine):
    if not SCHEMA_FILE.exists():
        log.error(f"Schema file not found: {SCHEMA_FILE}")
        sys.exit(1)

    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")

    try:
        with engine.begin() as conn:
            conn.execute(text(schema_sql))
        log.info("Schema executed successfully.")
    except Exception as e:
        log.error(f"Schema execution failed: {e}")
        sys.exit(1)


def verify_schema(engine):
    checks = [
        ("bronze", "well_approvals_raw"),
        ("silver", "well_approvals_cleaned"),
        ("gold",   "dim_well_status"),
        ("audit",  "pipeline_run_log"),
        ("audit",  "quarantine"),
    ]

    log.info("Verifying schema...")
    all_passed = True

    try:
        with engine.connect() as conn:
            for schema, table in checks:
                result = conn.execute(text("""
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = :schema
                        AND table_name = :table
                    )
                """), {"schema": schema, "table": table})
                exists = result.scalar()

                if exists:
                    log.info(f"  PASS: {schema}.{table}")
                else:
                    log.error(f"  FAIL: {schema}.{table} not found")
                    all_passed = False

        row_check = None
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT COUNT(*) FROM gold.dim_well_status")
            )
            row_check = result.scalar()
            log.info(f"  PASS: gold.dim_well_status seeded with {row_check} rows")

    except Exception as e:
        log.error(f"Verification failed: {e}")
        sys.exit(1)

    if all_passed:
        log.info("All schema checks passed.")
    else:
        log.error("One or more schema checks failed.")
        sys.exit(1)


def main():
    log.info("Starting MB Petro Warehouse database initialization...")
    engine = get_engine()
    run_schema(engine)
    verify_schema(engine)
    log.info("Database initialization complete.")


if __name__ == "__main__":
    main()