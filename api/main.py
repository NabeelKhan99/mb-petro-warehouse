"""
MB Petro Warehouse — FastAPI REST API
Serves Gold layer data: well approvals, spills, KPI, compliance.

Usage:
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
    http://localhost:8000/docs
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, Query,HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="MB Petro Warehouse API",
    description="REST API for Manitoba petroleum regulatory data — well approvals, spills, compliance KPIs",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", 5433)),
    "dbname": os.getenv("DB_NAME", "mb_petro_warehouse"),
    "user": os.getenv("DB_USER", "airflow"),
    "password": os.getenv("DB_PASSWORD", "airflow"),
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)


def query(sql, params=None):
    """Execute a query and return results as list of dicts."""
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {"service": "MB Petro Warehouse API", "docs": "/docs"}


@app.get("/well-approvals")
def get_well_approvals(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    company: str = Query(None),
):
    """Return well approvals from the Gold layer."""
    if company:
        sql = """
            SELECT licence_id, uwi, well_name, well_class, licensee,
                   total_depth_m, formation, ground_elevation_m,
                   drilling_rig, rig_no, licence_issued, surface_location
            FROM gold.fact_well_approvals f
            JOIN gold.dim_company c ON f.company_id = c.company_id
            WHERE c.company_name ILIKE %s
            ORDER BY licence_issued DESC
            LIMIT %s OFFSET %s
        """
        params = (f"%{company}%", limit, offset)
    else:
        sql = """
            SELECT licence_id, uwi, well_name, well_class, licensee,
                   total_depth_m, formation, ground_elevation_m,
                   drilling_rig, rig_no, licence_issued, surface_location
            FROM gold.fact_well_approvals f
            JOIN gold.dim_company c ON f.company_id = c.company_id
            ORDER BY licence_issued DESC
            LIMIT %s OFFSET %s
        """
        params = (limit, offset)
    return query(sql, params)


@app.get("/spills")
def get_spills(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    company: str = Query(None),
):
    """Return spill incidents from the Gold layer."""
    if company:
        sql = """
            SELECT s.spill_no, s.spill_date, c.company_name,
                   s.source, s.cause, s.location_lsd,
                   s.oil_vol_bbl, s.sw_vol_bbl, s.recovered_vol_bbl,
                   s.total_area_m2, s.off_lease_area_m2
            FROM gold.fact_spill_incidents s
            JOIN gold.dim_company c ON s.company_id = c.company_id
            WHERE c.company_name ILIKE %s
            ORDER BY s.spill_date DESC
            LIMIT %s OFFSET %s
        """
        params = (f"%{company}%", limit, offset)
    else:
        sql = """
            SELECT s.spill_no, s.spill_date, c.company_name,
                   s.source, s.cause, s.location_lsd,
                   s.oil_vol_bbl, s.sw_vol_bbl, s.recovered_vol_bbl,
                   s.total_area_m2, s.off_lease_area_m2
            FROM gold.fact_spill_incidents s
            JOIN gold.dim_company c ON s.company_id = c.company_id
            ORDER BY s.spill_date DESC
            LIMIT %s OFFSET %s
        """
        params = (limit, offset)
    return query(sql, params)


@app.get("/company-kpi")
def get_company_kpi():
    """Return spill-to-approval KPI for all companies."""
    sql = "SELECT * FROM gold.v_company_spill_kpi_full"
    return query(sql)


@app.get("/compliance-summary")
def get_compliance_summary():
    """Return regulatory compliance summary counts."""
    sql = "SELECT * FROM gold.v_compliance_summary"
    return query(sql)


@app.get("/compliance-detail")
def get_compliance_detail(dataset: str = Query(..., regex="^(wells|spills)$")):
    """Return per-record compliance pass/fail detail."""
    if dataset == "wells":
        sql = "SELECT * FROM gold.v_regulatory_compliance_wells"
    else:
        sql = "SELECT * FROM gold.v_regulatory_compliance_spills"
    return query(sql)


@app.get("/data-quality")
def get_data_quality():
    """Return latest data quality scores."""
    sql = "SELECT * FROM gold.v_data_quality_summary"
    return query(sql)


@app.get("/health")
def health_check():
    """Database connectivity check."""
    try:
        query("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}