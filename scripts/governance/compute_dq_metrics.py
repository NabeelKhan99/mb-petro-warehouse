"""
Data Quality Metrics Runner
Computes completeness, uniqueness, validity, and overall quality scores
for Silver layer datasets and inserts into audit.data_quality_metrics.

Usage:
    python compute_dq_metrics.py well_approvals
    python compute_dq_metrics.py spills
"""

import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", 5433)),
    "dbname": os.getenv("DB_NAME", "mb_petro_warehouse"),
    "user": os.getenv("DB_USER", "airflow"),
    "password": os.getenv("DB_PASSWORD", "airflow"),
}

METRICS_SQL = {
    "well_approvals": """
        INSERT INTO audit.data_quality_metrics (
            batch_id, source_table, completeness_pct, uniqueness_pct,
            validity_pct, timeliness_pct, overall_score
        )
        SELECT
            %(batch_id)s::UUID,
            'well_approvals',
            ROUND((
                COUNT(*) FILTER (WHERE licence_id IS NOT NULL)::NUMERIC / COUNT(*)::NUMERIC * 100 +
                COUNT(*) FILTER (WHERE uwi IS NOT NULL)::NUMERIC / COUNT(*)::NUMERIC * 100 +
                COUNT(*) FILTER (WHERE licensee IS NOT NULL)::NUMERIC / COUNT(*)::NUMERIC * 100 +
                COUNT(*) FILTER (WHERE well_class IS NOT NULL)::NUMERIC / COUNT(*)::NUMERIC * 100 +
                COUNT(*) FILTER (WHERE formation IS NOT NULL)::NUMERIC / COUNT(*)::NUMERIC * 100
            ) / 5, 2),
            ROUND((
                SELECT COUNT(*) FROM (
                    SELECT uwi FROM silver.well_approvals_cleaned GROUP BY uwi HAVING COUNT(*) = 1
                ) u
            )::NUMERIC / COUNT(*)::NUMERIC * 100, 2),
            ROUND(
                COUNT(*) FILTER (WHERE validation_passed = TRUE)::NUMERIC / COUNT(*)::NUMERIC * 100, 2),
            100.00,
            ROUND((
                (COUNT(*) FILTER (WHERE licence_id IS NOT NULL)::NUMERIC / COUNT(*)::NUMERIC * 100 +
                 COUNT(*) FILTER (WHERE uwi IS NOT NULL)::NUMERIC / COUNT(*)::NUMERIC * 100 +
                 COUNT(*) FILTER (WHERE licensee IS NOT NULL)::NUMERIC / COUNT(*)::NUMERIC * 100 +
                 COUNT(*) FILTER (WHERE well_class IS NOT NULL)::NUMERIC / COUNT(*)::NUMERIC * 100 +
                 COUNT(*) FILTER (WHERE formation IS NOT NULL)::NUMERIC / COUNT(*)::NUMERIC * 100
                ) / 5 * 0.4 +
                (SELECT COUNT(*) FROM (
                    SELECT uwi FROM silver.well_approvals_cleaned GROUP BY uwi HAVING COUNT(*) = 1
                ) u)::NUMERIC / COUNT(*)::NUMERIC * 100 * 0.3 +
                COUNT(*) FILTER (WHERE validation_passed = TRUE)::NUMERIC / COUNT(*)::NUMERIC * 100 * 0.3
            ), 2)
        FROM silver.well_approvals_cleaned
    """,
    "spills": """
        INSERT INTO audit.data_quality_metrics (
            batch_id, source_table, completeness_pct, uniqueness_pct,
            validity_pct, timeliness_pct, overall_score
        )
        SELECT
            %(batch_id)s::UUID,
            'spills',
            ROUND((
                COUNT(*) FILTER (WHERE spill_no IS NOT NULL)::NUMERIC / COUNT(*)::NUMERIC * 100 +
                COUNT(*) FILTER (WHERE company IS NOT NULL)::NUMERIC / COUNT(*)::NUMERIC * 100 +
                COUNT(*) FILTER (WHERE spill_date IS NOT NULL)::NUMERIC / COUNT(*)::NUMERIC * 100 +
                COUNT(*) FILTER (WHERE source IS NOT NULL)::NUMERIC / COUNT(*)::NUMERIC * 100 +
                COUNT(*) FILTER (WHERE cause IS NOT NULL)::NUMERIC / COUNT(*)::NUMERIC * 100
            ) / 5, 2),
            ROUND((
                SELECT COUNT(*) FROM (
                    SELECT spill_no FROM silver.spills_cleaned GROUP BY spill_no HAVING COUNT(*) = 1
                ) s
            )::NUMERIC / COUNT(*)::NUMERIC * 100, 2),
            ROUND(
                COUNT(*) FILTER (WHERE validation_passed = TRUE)::NUMERIC / COUNT(*)::NUMERIC * 100, 2),
            100.00,
            ROUND((
                (COUNT(*) FILTER (WHERE spill_no IS NOT NULL)::NUMERIC / COUNT(*)::NUMERIC * 100 +
                 COUNT(*) FILTER (WHERE company IS NOT NULL)::NUMERIC / COUNT(*)::NUMERIC * 100 +
                 COUNT(*) FILTER (WHERE spill_date IS NOT NULL)::NUMERIC / COUNT(*)::NUMERIC * 100 +
                 COUNT(*) FILTER (WHERE source IS NOT NULL)::NUMERIC / COUNT(*)::NUMERIC * 100 +
                 COUNT(*) FILTER (WHERE cause IS NOT NULL)::NUMERIC / COUNT(*)::NUMERIC * 100
                ) / 5 * 0.4 +
                (SELECT COUNT(*) FROM (
                    SELECT spill_no FROM silver.spills_cleaned GROUP BY spill_no HAVING COUNT(*) = 1
                ) s)::NUMERIC / COUNT(*)::NUMERIC * 100 * 0.3 +
                COUNT(*) FILTER (WHERE validation_passed = TRUE)::NUMERIC / COUNT(*)::NUMERIC * 100 * 0.3
            ), 2)
        FROM silver.spills_cleaned
    """,
}


def compute_metrics(dataset: str):
    if dataset not in METRICS_SQL:
        raise ValueError(f"Unknown dataset: {dataset}. Choose from: {list(METRICS_SQL.keys())}")

    conn = psycopg2.connect(**DB_CONFIG)
    batch_id = str(uuid.uuid4())

    try:
        with conn.cursor() as cur:
            cur.execute(METRICS_SQL[dataset], {"batch_id": batch_id})
        conn.commit()
        print(f"Metrics computed for {dataset} — batch_id: {batch_id}")
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", choices=["well_approvals", "spills"])
    args = parser.parse_args()
    compute_metrics(args.dataset)