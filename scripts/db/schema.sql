-- ============================================================
-- MB PETRO WAREHOUSE - COMPLETE DATABASE SCHEMA
-- Version: 1.2.0
-- Description: Medallion architecture for Manitoba petroleum data
--              Covers Bronze, Silver, Gold, Audit layers
--              Includes regulatory compliance views and KPI views
-- Last updated: 2026-05-07
-- ============================================================

-- ------------------------------------------------------------
-- SCHEMAS
-- ------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS audit;

-- ============================================================
-- AUDIT LAYER
-- ============================================================

-- Pipeline run log — tracks every batch execution
CREATE TABLE IF NOT EXISTS audit.pipeline_run_log (
    id                  SERIAL PRIMARY KEY,
    batch_id            UUID NOT NULL,
    pipeline_version    TEXT NOT NULL DEFAULT '1.0.0',
    source_file         TEXT NOT NULL,
    layer               TEXT NOT NULL,
    started_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at        TIMESTAMP WITH TIME ZONE,
    status              TEXT NOT NULL DEFAULT 'RUNNING',
    total_records       INTEGER DEFAULT 0,
    passed_records      INTEGER DEFAULT 0,
    failed_records      INTEGER DEFAULT 0,
    notes               TEXT,
    CONSTRAINT chk_layer CHECK (layer IN ('BRONZE', 'SILVER', 'GOLD')),
    CONSTRAINT chk_status CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED'))
);
CREATE INDEX IF NOT EXISTS idx_audit_batch_id ON audit.pipeline_run_log(batch_id);
CREATE INDEX IF NOT EXISTS idx_audit_layer ON audit.pipeline_run_log(layer);

-- Validation run log — per-validation batch tracking
CREATE TABLE IF NOT EXISTS audit.validation_run_log (
    id                  SERIAL PRIMARY KEY,
    batch_id            UUID NOT NULL,
    pipeline_version    TEXT NOT NULL DEFAULT '1.0.0',
    source_table        TEXT NOT NULL,
    started_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at        TIMESTAMP WITH TIME ZONE,
    status              TEXT NOT NULL DEFAULT 'RUNNING',
    total_records       INTEGER DEFAULT 0,
    passed_records      INTEGER DEFAULT 0,
    failed_records      INTEGER DEFAULT 0,
    notes               TEXT,
    CONSTRAINT chk_val_status CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED'))
);
CREATE INDEX IF NOT EXISTS idx_val_log_batch_id ON audit.validation_run_log(batch_id);

-- Quarantine records — failed validation with structured violations
CREATE TABLE IF NOT EXISTS audit.quarantine_records (
    id                  SERIAL PRIMARY KEY,
    batch_id            UUID NOT NULL,
    source_table        TEXT NOT NULL,
    record_hash         TEXT NOT NULL,
    raw_payload         JSONB NOT NULL,
    violation_summary   JSONB NOT NULL,
    error_count         INTEGER NOT NULL DEFAULT 0,
    warn_count          INTEGER NOT NULL DEFAULT 0,
    quarantined_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolution_status   TEXT NOT NULL DEFAULT 'OPEN',
    resolution_notes    TEXT,
    CONSTRAINT chk_resolution CHECK (resolution_status IN ('OPEN', 'REVIEWED', 'FIXED', 'ACCEPTED'))
);
CREATE INDEX IF NOT EXISTS idx_quarantine_batch_id ON audit.quarantine_records(batch_id);
CREATE INDEX IF NOT EXISTS idx_quarantine_source_table ON audit.quarantine_records(source_table);
CREATE INDEX IF NOT EXISTS idx_quarantine_status ON audit.quarantine_records(resolution_status);

-- Regulatory rules — machine-readable compliance rule repository
CREATE TABLE IF NOT EXISTS audit.regulatory_rules (
    id                  SERIAL PRIMARY KEY,
    rule_id             TEXT NOT NULL UNIQUE,
    category            TEXT NOT NULL,
    field               TEXT,
    description         TEXT NOT NULL,
    severity            TEXT NOT NULL DEFAULT 'ERROR',
    reference           TEXT,
    logic               TEXT,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT chk_severity CHECK (severity IN ('ERROR', 'WARN'))
);

-- Metadata catalog — self-documenting data dictionary
CREATE TABLE IF NOT EXISTS audit.metadata_catalog (
    id                  SERIAL PRIMARY KEY,
    schema_name         TEXT NOT NULL,
    table_name          TEXT NOT NULL,
    column_name         TEXT NOT NULL,
    data_type           TEXT,
    description         TEXT,
    business_definition TEXT,
    regulatory_citation TEXT,
    data_classification TEXT DEFAULT 'INTERNAL',
    pii_flag            BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Data quality metrics — per-batch quality scores
CREATE TABLE IF NOT EXISTS audit.data_quality_metrics (
    id                  SERIAL PRIMARY KEY,
    batch_id            UUID NOT NULL,
    source_table        TEXT NOT NULL,
    completeness_pct    NUMERIC(5,2),
    uniqueness_pct      NUMERIC(5,2),
    validity_pct        NUMERIC(5,2),
    timeliness_pct      NUMERIC(5,2),
    overall_score       NUMERIC(5,2),
    calculated_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- BRONZE LAYER
-- ============================================================

-- Well approvals raw — extracted from New Well Licence Approvals PDF
CREATE TABLE IF NOT EXISTS bronze.well_approvals_raw (
    id                  SERIAL PRIMARY KEY,
    batch_id            UUID NOT NULL,
    source_file         TEXT NOT NULL,
    ingested_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    pipeline_version    TEXT NOT NULL DEFAULT '1.0.0',
    raw_payload         JSONB NOT NULL,
    record_hash         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bronze_well_batch_id ON bronze.well_approvals_raw(batch_id);
CREATE INDEX IF NOT EXISTS idx_bronze_well_ingested_at ON bronze.well_approvals_raw(ingested_at);
CREATE INDEX IF NOT EXISTS idx_bronze_well_record_hash ON bronze.well_approvals_raw(record_hash);

-- Spills raw — extracted from Spill Stats PDF
CREATE TABLE IF NOT EXISTS bronze.spills_raw (
    id                  SERIAL PRIMARY KEY,
    batch_id            UUID NOT NULL,
    source_file         TEXT NOT NULL,
    ingested_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    pipeline_version    TEXT NOT NULL DEFAULT '1.0.0',
    raw_payload         JSONB NOT NULL,
    record_hash         TEXT NOT NULL,
    spill_no            TEXT GENERATED ALWAYS AS (raw_payload ->> 'spill_no') STORED,
    spill_date_raw      TEXT GENERATED ALWAYS AS (raw_payload ->> 'spill_date') STORED,
    company_raw         TEXT GENERATED ALWAYS AS (raw_payload ->> 'company') STORED
);
CREATE INDEX IF NOT EXISTS idx_bronze_spills_batch_id ON bronze.spills_raw(batch_id);
CREATE INDEX IF NOT EXISTS idx_bronze_spills_ingested_at ON bronze.spills_raw(ingested_at);
CREATE INDEX IF NOT EXISTS idx_bronze_spills_record_hash ON bronze.spills_raw(record_hash);
CREATE INDEX IF NOT EXISTS idx_bronze_spills_spill_no ON bronze.spills_raw(spill_no);
CREATE INDEX IF NOT EXISTS idx_bronze_spills_company ON bronze.spills_raw(company_raw);

-- ============================================================
-- SILVER LAYER
-- ============================================================

-- Well approvals cleaned — parsed raw_block into typed columns
CREATE TABLE IF NOT EXISTS silver.well_approvals_cleaned (
    id                  SERIAL PRIMARY KEY,
    batch_id            UUID NOT NULL,
    bronze_id           INTEGER REFERENCES bronze.well_approvals_raw(id),
    source_file         TEXT NOT NULL,
    ingested_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    pipeline_version    TEXT NOT NULL DEFAULT '1.0.0',
    licence_id          TEXT NOT NULL,
    well_name           TEXT,
    licence_issued      DATE,
    well_class          TEXT,
    licensee            TEXT,
    surface_location    TEXT,
    coordinates         TEXT,
    uwi                 TEXT NOT NULL,
    total_depth_m       NUMERIC(10,2),
    formation           TEXT,
    ground_elevation_m  NUMERIC(10,2),
    drilling_rig        TEXT,
    rig_no              INTEGER,
    uwi_valid           BOOLEAN DEFAULT FALSE,
    well_class_valid    BOOLEAN DEFAULT FALSE,
    validation_passed   BOOLEAN DEFAULT FALSE,
    validation_warnings INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_silver_well_licence_id ON silver.well_approvals_cleaned(licence_id);
CREATE INDEX IF NOT EXISTS idx_silver_well_uwi ON silver.well_approvals_cleaned(uwi);
CREATE INDEX IF NOT EXISTS idx_silver_well_licensee ON silver.well_approvals_cleaned(licensee);
CREATE INDEX IF NOT EXISTS idx_silver_well_batch_id ON silver.well_approvals_cleaned(batch_id);

-- Spills cleaned — typed and validated spill records
CREATE TABLE IF NOT EXISTS silver.spills_cleaned (
    id                  SERIAL PRIMARY KEY,
    batch_id            UUID NOT NULL,
    bronze_id           INTEGER REFERENCES bronze.spills_raw(id),
    source_file         TEXT NOT NULL,
    ingested_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    pipeline_version    TEXT NOT NULL DEFAULT '1.0.0',
    spill_no            TEXT NOT NULL,
    spill_date          DATE,
    company             TEXT,
    source              TEXT,
    cause               TEXT,
    location_lsd        TEXT,
    oil_vol_bbl         NUMERIC(10,2),
    sw_vol_bbl          NUMERIC(10,2),
    other_vol_bbl       NUMERIC(10,2),
    recovered_vol_bbl   NUMERIC(10,2),
    total_area_m2       NUMERIC(10,2),
    off_lease_area_m2   NUMERIC(10,2),
    validation_passed   BOOLEAN DEFAULT FALSE,
    validation_warnings INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_silver_spills_spill_no ON silver.spills_cleaned(spill_no);
CREATE INDEX IF NOT EXISTS idx_silver_spills_company ON silver.spills_cleaned(company);
CREATE INDEX IF NOT EXISTS idx_silver_spills_batch_id ON silver.spills_cleaned(batch_id);

-- ============================================================
-- GOLD LAYER
-- ============================================================

-- DIM: Well Status reference
CREATE TABLE IF NOT EXISTS gold.dim_well_status (
    well_status_type    TEXT PRIMARY KEY,
    well_status_desc    TEXT NOT NULL,
    status_category     TEXT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- DIM: Calendar date dimension
CREATE TABLE IF NOT EXISTS gold.dim_date (
    date_id         SERIAL PRIMARY KEY,
    full_date       DATE NOT NULL UNIQUE,
    year            INTEGER NOT NULL,
    quarter         INTEGER NOT NULL,
    month           INTEGER NOT NULL,
    month_name      TEXT NOT NULL,
    day             INTEGER NOT NULL,
    day_of_week     TEXT NOT NULL,
    is_weekend      BOOLEAN NOT NULL
);

-- DIM: Company — normalized licensee reference
CREATE TABLE IF NOT EXISTS gold.dim_company (
    company_id      SERIAL PRIMARY KEY,
    company_name    TEXT NOT NULL UNIQUE,
    display_name    TEXT,
    company_type    TEXT DEFAULT 'OPERATOR',
    first_seen_date DATE,
    last_seen_date  DATE
);

-- FACT: Well approvals
CREATE TABLE IF NOT EXISTS gold.fact_well_approvals (
    approval_id         SERIAL PRIMARY KEY,
    company_id          INTEGER REFERENCES gold.dim_company(company_id),
    date_id             INTEGER REFERENCES gold.dim_date(date_id),
    licence_id          TEXT NOT NULL,
    uwi                 TEXT NOT NULL,
    well_name           TEXT,
    well_class          TEXT,
    total_depth_m       NUMERIC(10,2),
    formation           TEXT,
    ground_elevation_m  NUMERIC(10,2),
    drilling_rig        TEXT,
    rig_no              INTEGER,
    surface_location    TEXT,
    coordinates         TEXT,
    licence_issued      DATE,
    validation_passed   BOOLEAN
);

-- FACT: Spill incidents
CREATE TABLE IF NOT EXISTS gold.fact_spill_incidents (
    spill_id            SERIAL PRIMARY KEY,
    company_id          INTEGER REFERENCES gold.dim_company(company_id),
    date_id             INTEGER REFERENCES gold.dim_date(date_id),
    spill_date          DATE, 
    spill_no            TEXT NOT NULL,
    source              TEXT,
    cause               TEXT,
    location_lsd        TEXT,
    oil_vol_bbl         NUMERIC(10,2),
    sw_vol_bbl          NUMERIC(10,2),
    other_vol_bbl       NUMERIC(10,2),
    recovered_vol_bbl   NUMERIC(10,2),
    total_area_m2       NUMERIC(10,2),
    off_lease_area_m2   NUMERIC(10,2),
    validation_passed   BOOLEAN
);

-- ============================================================
-- GOLD VIEWS
-- ============================================================

-- Regulatory compliance detail — well approvals
CREATE OR REPLACE VIEW gold.v_regulatory_compliance_wells AS
SELECT
    w.id AS silver_id,
    w.licence_id,
    w.uwi,
    w.licensee,
    w.well_class,
    w.total_depth_m,
    w.ground_elevation_m,
    w.formation,
    w.licence_issued,
    CASE WHEN LENGTH(TRIM(w.uwi)) = 21 THEN 'PASS' ELSE 'FAIL' END AS check_uwi_length,
    CASE WHEN LEFT(w.uwi, 1) = '1' THEN 'PASS' ELSE 'FAIL' END AS check_uwi_survey_code,
    CASE WHEN SUBSTRING(w.uwi, 2, 1) IN ('0','A','B','C','D','S','W') THEN 'PASS' ELSE 'FAIL' END AS check_uwi_location_code,
    CASE WHEN SUBSTRING(w.uwi, 3, 1) IN ('0','2','3','4','5','6','7','8','9') THEN 'PASS' ELSE 'FAIL' END AS check_uwi_sequence,
    CASE WHEN w.well_class IN ('DEV','DPW','SWD','OBS','INJ','HZNTL','PROV','VERT') THEN 'PASS' ELSE 'FAIL' END AS check_well_class,
    CASE WHEN w.total_depth_m > 0 THEN 'PASS' ELSE 'FAIL' END AS check_depth_positive,
    CASE WHEN w.total_depth_m BETWEEN 100 AND 5000 THEN 'PASS' ELSE 'WARN' END AS check_depth_range,
    CASE WHEN w.ground_elevation_m > 0 THEN 'PASS' ELSE 'FAIL' END AS check_elevation_positive,
    CASE WHEN w.ground_elevation_m BETWEEN 200 AND 900 THEN 'PASS' ELSE 'WARN' END AS check_elevation_range,
    CASE WHEN w.formation IS NOT NULL AND w.formation != '' THEN 'PASS' ELSE 'FAIL' END AS check_formation,
    CASE WHEN w.licensee IS NOT NULL AND TRIM(w.licensee) != '' THEN 'PASS' ELSE 'FAIL' END AS check_licensee
FROM silver.well_approvals_cleaned w;

-- Regulatory compliance detail — spills
CREATE OR REPLACE VIEW gold.v_regulatory_compliance_spills AS
SELECT
    s.id AS silver_id,
    s.spill_no,
    s.spill_date,
    s.company,
    s.source,
    s.cause,
    s.location_lsd,
    s.oil_vol_bbl,
    s.sw_vol_bbl,
    s.other_vol_bbl,
    s.recovered_vol_bbl,
    s.total_area_m2,
    s.off_lease_area_m2,
    CASE WHEN s.oil_vol_bbl >= 0 AND s.sw_vol_bbl >= 0 AND s.other_vol_bbl >= 0 THEN 'PASS' ELSE 'FAIL' END AS check_volumes_nonnegative,
    CASE WHEN (s.oil_vol_bbl + s.sw_vol_bbl + s.other_vol_bbl) > 0 THEN 'PASS' ELSE 'WARN' END AS check_total_volume_positive,
    CASE WHEN s.recovered_vol_bbl <= (s.oil_vol_bbl + s.sw_vol_bbl + s.other_vol_bbl) THEN 'PASS' ELSE 'FAIL' END AS check_recovery_not_exceeding,
    CASE WHEN s.recovered_vol_bbl >= 0 THEN 'PASS' ELSE 'FAIL' END AS check_recovery_nonnegative,
    CASE WHEN s.off_lease_area_m2 <= s.total_area_m2 THEN 'PASS' ELSE 'FAIL' END AS check_off_lease_area,
    CASE WHEN s.company IS NOT NULL AND TRIM(s.company) != '' THEN 'PASS' ELSE 'FAIL' END AS check_company
FROM silver.spills_cleaned s;

-- Compliance summary rollup
CREATE OR REPLACE VIEW gold.v_compliance_summary AS
SELECT
    'Well Approvals' AS dataset,
    COUNT(*) AS total_records,
    COUNT(*) FILTER (WHERE check_uwi_length = 'FAIL'
        OR check_uwi_survey_code = 'FAIL'
        OR check_uwi_location_code = 'FAIL'
        OR check_uwi_sequence = 'FAIL'
        OR check_well_class = 'FAIL'
        OR check_depth_positive = 'FAIL'
        OR check_elevation_positive = 'FAIL'
        OR check_formation = 'FAIL'
        OR check_licensee = 'FAIL') AS records_with_errors,
    COUNT(*) FILTER (WHERE check_uwi_length = 'FAIL') AS fail_check_1,
    COUNT(*) FILTER (WHERE check_well_class = 'FAIL') AS fail_check_2,
    COUNT(*) FILTER (WHERE check_depth_positive = 'FAIL') AS fail_check_3,
    COUNT(*) FILTER (WHERE check_formation = 'FAIL') AS fail_check_4,
    COUNT(*) FILTER (WHERE check_licensee = 'FAIL') AS fail_check_5
FROM gold.v_regulatory_compliance_wells
UNION ALL
SELECT
    'Spills' AS dataset,
    COUNT(*) AS total_records,
    COUNT(*) FILTER (WHERE check_volumes_nonnegative = 'FAIL'
        OR check_recovery_not_exceeding = 'FAIL'
        OR check_recovery_nonnegative = 'FAIL'
        OR check_off_lease_area = 'FAIL'
        OR check_company = 'FAIL') AS records_with_errors,
    COUNT(*) FILTER (WHERE check_volumes_nonnegative = 'FAIL') AS fail_check_1,
    COUNT(*) FILTER (WHERE check_recovery_not_exceeding = 'FAIL') AS fail_check_2,
    COUNT(*) FILTER (WHERE check_off_lease_area = 'FAIL') AS fail_check_3,
    0 AS fail_check_4,
    COUNT(*) FILTER (WHERE check_company = 'FAIL') AS fail_check_5
FROM gold.v_regulatory_compliance_spills;

-- Company spill-to-approval KPI
CREATE OR REPLACE VIEW gold.v_company_spill_kpi AS
WITH company_approvals AS (
    SELECT
        c.company_id,
        COALESCE(c.display_name, c.company_name) AS company_name,
        COUNT(DISTINCT f.licence_id) AS total_approvals,
        COUNT(DISTINCT f.uwi) AS unique_wells,
        MIN(f.licence_issued) AS first_approval,
        MAX(f.licence_issued) AS last_approval
    FROM gold.dim_company c
    JOIN gold.fact_well_approvals f ON c.company_id = f.company_id
    GROUP BY c.company_id, c.company_name, c.display_name
),
company_spills AS (
    SELECT
        c.company_id,
        COUNT(DISTINCT s.spill_no) AS total_spills,
        COALESCE(SUM(s.oil_vol_bbl), 0) AS total_oil_spilled_bbl,
        COALESCE(SUM(s.sw_vol_bbl), 0) AS total_sw_spilled_bbl,
        COALESCE(SUM(s.other_vol_bbl), 0) AS total_other_spilled_bbl,
        COALESCE(SUM(s.recovered_vol_bbl), 0) AS total_recovered_bbl,
        COALESCE(SUM(s.total_area_m2), 0) AS total_area_impacted_m2,
        COUNT(DISTINCT s.spill_no) FILTER (WHERE s.off_lease_area_m2 > 0) AS off_lease_spills
    FROM gold.dim_company c
    JOIN gold.fact_spill_incidents s ON c.company_id = s.company_id
    GROUP BY c.company_id
)
SELECT
    ca.company_name,
    ca.total_approvals,
    ca.unique_wells,
    COALESCE(cs.total_spills, 0) AS total_spills,
    CASE
        WHEN ca.total_approvals > 0
        THEN ROUND(cs.total_spills::NUMERIC / ca.total_approvals::NUMERIC, 2)
        ELSE NULL
    END AS spill_to_approval_ratio,
    COALESCE(cs.total_oil_spilled_bbl, 0) AS total_oil_spilled_bbl,
    COALESCE(cs.total_recovered_bbl, 0) AS total_recovered_bbl,
    CASE
        WHEN (cs.total_oil_spilled_bbl + cs.total_sw_spilled_bbl + cs.total_other_spilled_bbl) > 0
        THEN ROUND((cs.total_recovered_bbl /
            (cs.total_oil_spilled_bbl + cs.total_sw_spilled_bbl + cs.total_other_spilled_bbl)) * 100, 1)
        ELSE 0
    END AS recovery_pct,
    COALESCE(cs.total_area_impacted_m2, 0) AS total_area_impacted_m2,
    COALESCE(cs.off_lease_spills, 0) AS off_lease_spills
FROM company_approvals ca
LEFT JOIN company_spills cs ON ca.company_id = cs.company_id
ORDER BY spill_to_approval_ratio DESC NULLS LAST;

-- Company spill KPI — full (includes spill-only companies)
CREATE OR REPLACE VIEW gold.v_company_spill_kpi_full AS
SELECT
    c.company_name,
    COALESCE(ca.total_approvals, 0) AS total_approvals,
    COALESCE(ca.unique_wells, 0) AS unique_wells,
    COALESCE(cs.total_spills, 0) AS total_spills,
    CASE
        WHEN COALESCE(ca.total_approvals, 0) > 0
        THEN ROUND(cs.total_spills::NUMERIC / ca.total_approvals::NUMERIC, 2)
        ELSE NULL
    END AS spill_to_approval_ratio,
    COALESCE(cs.total_oil_spilled_bbl, 0) AS total_oil_spilled_bbl,
    COALESCE(cs.total_recovered_bbl, 0) AS total_recovered_bbl,
    CASE
        WHEN (cs.total_oil_spilled_bbl + cs.total_sw_spilled_bbl + cs.total_other_spilled_bbl) > 0
        THEN ROUND((cs.total_recovered_bbl /
            (cs.total_oil_spilled_bbl + cs.total_sw_spilled_bbl + cs.total_other_spilled_bbl)) * 100, 1)
        ELSE 0
    END AS recovery_pct,
    COALESCE(cs.total_area_impacted_m2, 0) AS total_area_impacted_m2,
    COALESCE(cs.off_lease_spills, 0) AS off_lease_spills
FROM gold.dim_company c
LEFT JOIN (
    SELECT company_id, COUNT(DISTINCT licence_id) AS total_approvals,
           COUNT(DISTINCT uwi) AS unique_wells
    FROM gold.fact_well_approvals GROUP BY company_id
) ca ON c.company_id = ca.company_id
LEFT JOIN (
    SELECT company_id, COUNT(DISTINCT spill_no) AS total_spills,
           SUM(oil_vol_bbl) AS total_oil_spilled_bbl,
           SUM(sw_vol_bbl) AS total_sw_spilled_bbl,
           SUM(other_vol_bbl) AS total_other_spilled_bbl,
           SUM(recovered_vol_bbl) AS total_recovered_bbl,
           SUM(total_area_m2) AS total_area_impacted_m2,
           COUNT(DISTINCT spill_no) FILTER (WHERE off_lease_area_m2 > 0) AS off_lease_spills
    FROM gold.fact_spill_incidents GROUP BY company_id
) cs ON c.company_id = cs.company_id
WHERE COALESCE(ca.total_approvals, 0) > 0 OR COALESCE(cs.total_spills, 0) > 0
ORDER BY spill_to_approval_ratio DESC NULLS LAST;

-- ============================================================
-- SEED DATA: Well Status Reference
-- ============================================================
INSERT INTO gold.dim_well_status (well_status_type, well_status_desc, status_category) VALUES
    ('ABD D', 'Abandoned Dry', 'ABANDONED'),
    ('ABD P', 'Abandoned Producer', 'ABANDONED'),
    ('ABD SWD', 'Abandoned Salt Water Disposal', 'ABANDONED'),
    ('ABD WIW', 'Abandoned Water Injection Well', 'ABANDONED'),
    ('CAN', 'Licence Cancelled', 'CANCELLED'),
    ('COOP', 'Capable Of Oil Production', 'PRODUCTION'),
    ('DR', 'Drilling Ahead', 'DRILLING'),
    ('GIW', 'Gas Injection Well', 'INJECTION'),
    ('LOC', 'Location', 'PRE-DRILL'),
    ('PROD GAS', 'Producing Gas', 'PRODUCTION'),
    ('ST', 'Standing', 'SUSPENDED'),
    ('SWD', 'Salt Water Disposal', 'INJECTION'),
    ('WIW', 'Water Injection Well', 'INJECTION'),
    ('WSW', 'Water Source Well', 'INJECTION')
ON CONFLICT (well_status_type) DO NOTHING;

-- ============================================================
-- SEED DATA: Calendar Dimension (2000-2030)
-- ============================================================
INSERT INTO gold.dim_date (full_date, year, quarter, month, month_name, day, day_of_week, is_weekend)
SELECT
    d::DATE,
    EXTRACT(YEAR FROM d)::INTEGER,
    EXTRACT(QUARTER FROM d)::INTEGER,
    EXTRACT(MONTH FROM d)::INTEGER,
    TO_CHAR(d, 'Month'),
    EXTRACT(DAY FROM d)::INTEGER,
    TO_CHAR(d, 'Day'),
    EXTRACT(DOW FROM d) IN (0, 6)
FROM generate_series('2000-01-01'::DATE, '2030-12-31'::DATE, '1 day'::INTERVAL) d
ON CONFLICT (full_date) DO NOTHING;

-- ============================================================
-- SEED DATA: Regulatory Rules (30 rules)
-- ============================================================
INSERT INTO audit.regulatory_rules (rule_id, category, field, description, severity, reference, logic) VALUES
    ('UWI-001', 'UWI', 'uwi', 'UWI must be 21 characters in standard Manitoba DLS format', 'ERROR', 'Manitoba Petroleum Branch - UWI Specification, Section A', 'LEN(TRIM(uwi)) == 21'),
    ('UWI-002', 'UWI', 'uwi', 'Survey System Code (position 1) must be 1 for DLS', 'ERROR', 'Manitoba Petroleum Branch - UWI Specification, Section B', 'uwi[0] = 1'),
    ('UWI-003', 'UWI', 'uwi', 'Location Exception Code (position 2) must be valid', 'ERROR', 'Manitoba Petroleum Branch - UWI Specification, Section C', 'uwi[1] IN {0,A,B,C,D,S,W}'),
    ('UWI-004', 'UWI', 'uwi', 'Drilling Sequence (position 3) must be 0 or 2-9', 'ERROR', 'Manitoba Petroleum Branch - UWI Specification, Section C', 'uwi[2] IN {0,2-9}'),
    ('UWI-005a', 'UWI', 'uwi', 'Position 15 must be 0 for DLS system', 'ERROR', 'Manitoba Petroleum Branch - UWI Specification, Section E', 'uwi[14] = 0'),
    ('UWI-005', 'UWI', 'uwi', 'Event Sequence (position 16) must be digit 0-9', 'ERROR', 'Manitoba Petroleum Branch - UWI Specification, Section E', 'uwi[15] is digit'),
    ('UWI-006', 'UWI', 'uwi', 'UWI must match Manitoba DLS regex pattern', 'ERROR', 'Manitoba Petroleum Branch - UWI Specification, Section D', 'Regex validation'),
    ('WCL-001', 'WELL_CLASS', 'well_class', 'Well class must be valid Manitoba code', 'ERROR', 'Manitoba Well Status Types', 'well_class IN valid set'),
    ('WCL-002', 'WELL_CLASS', 'well_class', 'Well class must not be NULL or empty', 'ERROR', 'Internal governance standard', 'well_class IS NOT NULL'),
    ('LIC-001', 'LICENSEE', 'licensee', 'Licensee name must not be NULL or empty', 'ERROR', 'Internal governance standard', 'licensee IS NOT NULL'),
    ('LIC-002', 'LICENSEE', 'licensee', 'Licensee name should be >= 3 characters', 'WARN', 'Internal governance standard', 'LEN >= 3'),
    ('TD-001', 'TOTAL_DEPTH', 'total_depth_m', 'Total Depth must be positive', 'ERROR', 'Manitoba well licence guidelines', 'depth > 0'),
    ('TD-002', 'TOTAL_DEPTH', 'total_depth_m', 'Total Depth should be 100-5000m', 'WARN', 'Manitoba historical range', '100 <= depth <= 5000'),
    ('ELV-001', 'ELEVATION', 'ground_elevation_m', 'Ground elevation must be positive', 'ERROR', 'Internal governance standard', 'elevation > 0'),
    ('ELV-002', 'ELEVATION', 'ground_elevation_m', 'Ground elevation should be 200-900m', 'WARN', 'Manitoba topographical range', '200 <= elev <= 900'),
    ('DAT-001', 'DATE', 'issued_date', 'Issued date must be parseable, not future', 'ERROR', 'Internal governance standard', 'date <= CURRENT_DATE'),
    ('DAT-002', 'DATE', 'issued_date', 'Issued date should be >= 2000-01-01', 'WARN', 'System migration boundary', 'date >= 2000-01-01'),
    ('FRM-001', 'FORMATION', 'formation', 'Formation must not be NULL or empty', 'ERROR', 'Internal governance standard', 'formation IS NOT NULL'),
    ('SPL-001', 'SPILL_ID', 'spill_no', 'Spill number format YYYY-NN or YYYY-NN-V', 'ERROR', 'Manitoba Spill Stats', 'Regex'),
    ('SPL-002', 'LICENSEE', 'company', 'Company name must not be NULL or empty', 'ERROR', 'Internal governance standard', 'company IS NOT NULL'),
    ('SPL-003', 'DATE', 'spill_date', 'Spill date must be parseable DD-MON-YY', 'ERROR', 'Manitoba Spill Stats', 'date format'),
    ('SPL-004', 'VOLUME', 'oil_vol, sw_vol, other_vol', 'Volume fields must be non-negative', 'ERROR', 'Internal governance standard', 'volumes >= 0'),
    ('SPL-005', 'VOLUME', 'oil_vol, sw_vol, other_vol', 'At least one volume > 0', 'WARN', 'Internal governance standard', 'sum > 0'),
    ('SPL-006', 'VOLUME', 'recovered_vol', 'Recovered <= total spilled', 'ERROR', 'Internal governance standard', 'recovered <= spilled'),
    ('SPL-007', 'VOLUME', 'recovered_vol', 'Recovered volume non-negative', 'ERROR', 'Internal governance standard', 'recovered >= 0'),
    ('SPL-008', 'AREA', 'total_area', 'Total area positive if provided', 'WARN', 'Internal governance standard', 'area > 0'),
    ('SPL-009', 'AREA', 'off_lease_area', 'Off-lease <= total area', 'ERROR', 'Internal governance standard', 'off_lease <= total'),
    ('SPL-010', 'CLASSIFICATION', 'source', 'Spill source recognized category', 'WARN', 'Manitoba Spill Stats', 'source IN categories'),
    ('SPL-011', 'CLASSIFICATION', 'cause', 'Spill cause recognized category', 'WARN', 'Manitoba Spill Stats', 'cause IN categories'),
    ('SPL-012', 'LOCATION', 'location_lsd', 'Location LSD match DLS format', 'WARN', 'Manitoba DLS system', 'Regex NN-NN-NN-NN')
ON CONFLICT (rule_id) DO NOTHING;

-- ============================================================
-- SEED DATA: Metadata Catalog
-- ============================================================
INSERT INTO audit.metadata_catalog (schema_name, table_name, column_name, data_type, description, business_definition, regulatory_citation, data_classification) VALUES
    ('bronze', 'well_approvals_raw', 'id', 'SERIAL', 'Surrogate primary key', 'Auto-generated row identifier', NULL, 'INTERNAL'),
    ('bronze', 'well_approvals_raw', 'batch_id', 'UUID', 'Pipeline run identifier', 'Groups records from one pipeline execution', NULL, 'INTERNAL'),
    ('bronze', 'well_approvals_raw', 'source_file', 'TEXT', 'Original source PDF filename', 'Government report this record came from', NULL, 'INTERNAL'),
    ('bronze', 'well_approvals_raw', 'raw_payload', 'JSONB', 'Complete source record', 'Untransformed JSON as extracted from PDF', 'Manitoba New Well Licence Approvals', 'PUBLIC'),
    ('bronze', 'well_approvals_raw', 'record_hash', 'TEXT', 'SHA256 hash', 'Deduplication control', NULL, 'INTERNAL'),
    ('bronze', 'spills_raw', 'id', 'SERIAL', 'Surrogate primary key', 'Auto-generated', NULL, 'INTERNAL'),
    ('bronze', 'spills_raw', 'raw_payload', 'JSONB', 'Complete spill record', 'Untransformed spill JSON from PDF', 'Manitoba Spill Stats', 'PUBLIC'),
    ('bronze', 'spills_raw', 'spill_no', 'TEXT', 'Spill identifier', 'Format YYYY-NN or YYYY-NN-V', 'Manitoba Spill Stats', 'PUBLIC'),
    ('bronze', 'spills_raw', 'company_raw', 'TEXT', 'Raw company name', 'Operator name as in source', NULL, 'PUBLIC'),
    ('silver', 'well_approvals_cleaned', 'licence_id', 'TEXT', 'Well licence number', 'Manitoba Petroleum Branch assigned ID', 'Well licence application guidelines', 'PUBLIC'),
    ('silver', 'well_approvals_cleaned', 'uwi', 'TEXT', 'Unique Well Identifier', '21-char Manitoba DLS UWI', 'Manitoba UWI Specification', 'PUBLIC'),
    ('silver', 'well_approvals_cleaned', 'licensee', 'TEXT', 'Operating company', 'Legal name of licence holder', NULL, 'PUBLIC'),
    ('silver', 'well_approvals_cleaned', 'well_class', 'TEXT', 'Well classification', 'DEV, DPW, SWD, HZNTL, etc.', 'Manitoba Well Status Types', 'PUBLIC'),
    ('silver', 'well_approvals_cleaned', 'total_depth_m', 'NUMERIC', 'Total depth (metres)', 'Projected wellbore depth', NULL, 'PUBLIC'),
    ('silver', 'well_approvals_cleaned', 'formation', 'TEXT', 'Target formation', 'Geological formation name', NULL, 'PUBLIC'),
    ('silver', 'well_approvals_cleaned', 'ground_elevation_m', 'NUMERIC', 'Ground elevation (metres)', 'Elevation above sea level at wellhead', NULL, 'PUBLIC'),
    ('silver', 'spills_cleaned', 'spill_no', 'TEXT', 'Spill incident ID', 'YYYY-NN-V format', 'Manitoba Spill Stats', 'PUBLIC'),
    ('silver', 'spills_cleaned', 'company', 'TEXT', 'Responsible company', 'Operator responsible for spill', NULL, 'PUBLIC'),
    ('silver', 'spills_cleaned', 'oil_vol_bbl', 'NUMERIC', 'Oil spilled (barrels)', 'Crude oil volume released', NULL, 'PUBLIC'),
    ('silver', 'spills_cleaned', 'recovered_vol_bbl', 'NUMERIC', 'Volume recovered (barrels)', 'Oil and water recovered during cleanup', NULL, 'PUBLIC'),
    ('silver', 'spills_cleaned', 'source', 'TEXT', 'Spill source', 'FLOWLINE, WELL, TANK, etc.', 'Manitoba Spill Stats', 'PUBLIC'),
    ('silver', 'spills_cleaned', 'cause', 'TEXT', 'Spill cause', 'CORROSION, EQUIPMENT_FAILURE, etc.', 'Manitoba Spill Stats', 'PUBLIC'),
    ('gold', 'dim_company', 'company_name', 'TEXT', 'Canonical company name', 'Official operating company name', NULL, 'PUBLIC'),
    ('gold', 'dim_company', 'display_name', 'TEXT', 'Standardized display name', 'For cross-dataset joins', NULL, 'INTERNAL'),
    ('gold', 'fact_well_approvals', 'uwi', 'TEXT', 'Unique Well Identifier', 'FK to well registry', 'Manitoba UWI Specification', 'PUBLIC'),
    ('gold', 'fact_spill_incidents', 'spill_no', 'TEXT', 'Spill incident number', 'FK to spill register', 'Manitoba Spill Stats', 'PUBLIC'),
    ('gold', 'fact_spill_incidents', 'oil_vol_bbl', 'NUMERIC', 'Oil spilled (barrels)', 'Environmental impact metric', NULL, 'PUBLIC'),
    ('gold', 'fact_spill_incidents', 'recovered_vol_bbl', 'NUMERIC', 'Volume recovered (barrels)', 'Cleanup effectiveness metric', NULL, 'PUBLIC')
ON CONFLICT (id) DO NOTHING;