-- ============================================================
-- MB PETRO WAREHOUSE - DATABASE SCHEMA
-- Version: 1.0.0
-- Description: Full Medallion architecture schema definition
--              Bronze, Silver, Gold, Audit layers
--              Manitoba Petroleum Branch regulatory data
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
-- Pipeline governance, data quality, and compliance tracking
-- ============================================================

-- ------------------------------------------------------------
-- AUDIT: PIPELINE RUN LOG
-- Tracks every batch execution across all layers
-- ------------------------------------------------------------
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

CREATE INDEX IF NOT EXISTS idx_audit_batch_id
    ON audit.pipeline_run_log(batch_id);
CREATE INDEX IF NOT EXISTS idx_audit_layer
    ON audit.pipeline_run_log(layer);
CREATE INDEX IF NOT EXISTS idx_audit_status
    ON audit.pipeline_run_log(status);

-- ------------------------------------------------------------
-- AUDIT: VALIDATION RUN LOG
-- Tracks each validation batch execution separately
-- ------------------------------------------------------------
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

CREATE INDEX IF NOT EXISTS idx_val_log_batch_id
    ON audit.validation_run_log(batch_id);

-- ------------------------------------------------------------
-- AUDIT: QUARANTINE RECORDS
-- Records that failed validation, with structured violation details
-- Supports both well approvals and spills datasets
-- ------------------------------------------------------------
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

CREATE INDEX IF NOT EXISTS idx_quarantine_batch_id
    ON audit.quarantine_records(batch_id);
CREATE INDEX IF NOT EXISTS idx_quarantine_source_table
    ON audit.quarantine_records(source_table);
CREATE INDEX IF NOT EXISTS idx_quarantine_status
    ON audit.quarantine_records(resolution_status);

-- ------------------------------------------------------------
-- AUDIT: REGULATORY RULES (Phase 2A — placeholder)
-- Machine-readable repository of all validation rules
-- ------------------------------------------------------------
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

-- ------------------------------------------------------------
-- AUDIT: METADATA CATALOG (Phase 4A — placeholder)
-- Self-documenting data dictionary stored in the database
-- ------------------------------------------------------------
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

-- ------------------------------------------------------------
-- AUDIT: DATA QUALITY METRICS (Phase 4A — placeholder)
-- Per-batch data quality scores
-- ------------------------------------------------------------
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
-- Raw data exactly as extracted from source documents
-- No transformations applied
-- ============================================================

-- ------------------------------------------------------------
-- BRONZE: WELL APPROVALS RAW
-- New well licence approvals extracted from PDF reports
-- Each row is one licence object from well_licences array
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.well_approvals_raw (
    id                  SERIAL PRIMARY KEY,
    batch_id            UUID NOT NULL,
    source_file         TEXT NOT NULL,
    ingested_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    pipeline_version    TEXT NOT NULL DEFAULT '1.0.0',
    raw_payload         JSONB NOT NULL,
    record_hash         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bronze_well_batch_id
    ON bronze.well_approvals_raw(batch_id);
CREATE INDEX IF NOT EXISTS idx_bronze_well_ingested_at
    ON bronze.well_approvals_raw(ingested_at);
CREATE INDEX IF NOT EXISTS idx_bronze_well_record_hash
    ON bronze.well_approvals_raw(record_hash);

-- ------------------------------------------------------------
-- BRONZE: SPILLS RAW
-- Spill incident reports extracted from Spill Stats PDF
-- Each row is one spill object from the JSON array
-- ------------------------------------------------------------
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

CREATE INDEX IF NOT EXISTS idx_bronze_spills_batch_id
    ON bronze.spills_raw(batch_id);
CREATE INDEX IF NOT EXISTS idx_bronze_spills_ingested_at
    ON bronze.spills_raw(ingested_at);
CREATE INDEX IF NOT EXISTS idx_bronze_spills_record_hash
    ON bronze.spills_raw(record_hash);
CREATE INDEX IF NOT EXISTS idx_bronze_spills_spill_no
    ON bronze.spills_raw(spill_no);
CREATE INDEX IF NOT EXISTS idx_bronze_spills_company
    ON bronze.spills_raw(company_raw);

-- ============================================================
-- SILVER LAYER
-- Cleaned, validated, typed, and parsed data
-- One row per unique entity (wellbore, spill incident)
-- ============================================================

-- ------------------------------------------------------------
-- SILVER: WELL APPROVALS CLEANED (Phase 3)
-- raw_block parsed into typed columns with validation flags
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS silver.well_approvals_cleaned (
    id                  SERIAL PRIMARY KEY,
    batch_id            UUID NOT NULL,
    bronze_id           INTEGER REFERENCES bronze.well_approvals_raw(id),
    source_file         TEXT NOT NULL,
    ingested_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    pipeline_version    TEXT NOT NULL DEFAULT '1.0.0',

    -- Parsed fields from raw_block
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

    -- Validation flags
    uwi_valid           BOOLEAN DEFAULT FALSE,
    well_class_valid    BOOLEAN DEFAULT FALSE,
    validation_passed   BOOLEAN DEFAULT FALSE,
    validation_warnings INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_silver_well_licence_id
    ON silver.well_approvals_cleaned(licence_id);
CREATE INDEX IF NOT EXISTS idx_silver_well_uwi
    ON silver.well_approvals_cleaned(uwi);
CREATE INDEX IF NOT EXISTS idx_silver_well_licensee
    ON silver.well_approvals_cleaned(licensee);
CREATE INDEX IF NOT EXISTS idx_silver_well_batch_id
    ON silver.well_approvals_cleaned(batch_id);

-- ------------------------------------------------------------
-- SILVER: SPILLS CLEANED (Phase 3)
-- Typed and validated spill records
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS silver.spills_cleaned (
    id                  SERIAL PRIMARY KEY,
    batch_id            UUID NOT NULL,
    bronze_id           INTEGER REFERENCES bronze.spills_raw(id),
    source_file         TEXT NOT NULL,
    ingested_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    pipeline_version    TEXT NOT NULL DEFAULT '1.0.0',

    -- Typed fields
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

    -- Validation flags
    validation_passed   BOOLEAN DEFAULT FALSE,
    validation_warnings INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_silver_spills_spill_no
    ON silver.spills_cleaned(spill_no);
CREATE INDEX IF NOT EXISTS idx_silver_spills_company
    ON silver.spills_cleaned(company);
CREATE INDEX IF NOT EXISTS idx_silver_spills_batch_id
    ON silver.spills_cleaned(batch_id);

-- ============================================================
-- GOLD LAYER
-- Business-ready star schema with fact and dimension tables
-- Regulatory compliance views and KPI aggregations
-- ============================================================

-- ------------------------------------------------------------
-- GOLD: DIMENSION — WELL STATUS
-- Official Manitoba petroleum regulatory vocabulary
-- Seeded once, used for joins and validation
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold.dim_well_status (
    well_status_type    TEXT PRIMARY KEY,
    well_status_desc    TEXT NOT NULL,
    status_category     TEXT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

INSERT INTO gold.dim_well_status (well_status_type, well_status_desc, status_category)
VALUES
    ('ABD D',           'Abandoned Dry',                                    'ABANDONED'),
    ('ABD DUAL',        'Abandoned Dual Completion Well',                   'ABANDONED'),
    ('ABD GIW',         'Abandoned Gas Injection Well',                     'ABANDONED'),
    ('ABD J',           'Junked and abandoned',                             'ABANDONED'),
    ('ABD P',           'Abandoned Producer',                               'ABANDONED'),
    ('ABD PTH',         'Abandoned Potash Test Hole',                       'ABANDONED'),
    ('ABD SSW',         'Abandoned Salt Solution Well',                     'ABANDONED'),
    ('ABD STH',         'Abandoned Stratigraphic Test Hole',                'ABANDONED'),
    ('ABD SWD',         'Abandoned Salt Water Disposal',                    'ABANDONED'),
    ('ABD WIW',         'Abandoned Water Injection Well',                   'ABANDONED'),
    ('ABD WSW',         'Abandoned Water Source Well',                      'ABANDONED'),
    ('ABDG',            'Abandoning BP Running Bridge Plug',                'ABANDONED'),
    ('CAN',             'Licence Cancelled',                                'CANCELLED'),
    ('CMT CSG',         'Cementing Casing',                                 'DRILLING'),
    ('COMINGLED',       'Comingled',                                        'PRODUCTION'),
    ('COMP',            'Completing',                                       'DRILLING'),
    ('COOP',            'Capable Of Oil Production',                        'PRODUCTION'),
    ('COR',             'Coring',                                           'DRILLING'),
    ('CSG',             'Running Casing',                                   'DRILLING'),
    ('DEEP COM',        'Deepening Commenced',                              'DRILLING'),
    ('DR',              'Drilling Ahead',                                   'DRILLING'),
    ('DST',             'Drill Stem Test',                                  'DRILLING'),
    ('FISH',            'Fishing',                                          'DRILLING'),
    ('GIW',             'Gas Injection Well',                               'INJECTION'),
    ('LOC',             'Location',                                         'PRE-DRILL'),
    ('LOG',             'Logging',                                          'DRILLING'),
    ('MIRT',            'Moving In Rotary Tools',                           'DRILLING'),
    ('NOT ISSUED',      'Well Licence Not Issued',                          'ADMINISTRATIVE'),
    ('PREP CMT CSG',    'Preparing To Cement Casing',                       'DRILLING'),
    ('PREP CSG',        'Preparing To Run Casing',                          'DRILLING'),
    ('PREP LOG',        'Preparing To Log',                                 'DRILLING'),
    ('PROD GAS',        'Producing Gas',                                    'PRODUCTION'),
    ('PTH',             'Potash Test Hole',                                 'EXPLORATORY'),
    ('RE-ENTRY',        'Re-entered',                                       'WORKOVER'),
    ('REAM',            'Reaming',                                          'DRILLING'),
    ('RECOMPLETED',     'Recompleted',                                      'WORKOVER'),
    ('RESUMED COOP',    'Resumed COOP',                                     'PRODUCTION'),
    ('RESUMED SWD',     'Resumed SWD',                                      'INJECTION'),
    ('RESUMED WIW',     'Resumed WIW',                                      'INJECTION'),
    ('RESUMED WSW',     'Resumed WSW',                                      'INJECTION'),
    ('RIG BOP',         'Rigging Up BOPs',                                  'DRILLING'),
    ('RIG REP',         'Rig Repairs',                                      'DRILLING'),
    ('SCS',             'Surface Casing Set',                               'DRILLING'),
    ('SDFC',            'Shut Down For Christmas',                          'SUSPENDED'),
    ('SETTING LINER',   'Setting Liner',                                    'DRILLING'),
    ('SSW',             'Salt Solution Well',                               'INJECTION'),
    ('ST',              'Standing',                                         'SUSPENDED'),
    ('STH',             'Stratigraphic Test Hole',                          'EXPLORATORY'),
    ('SUS DR',          'Suspended Drilling',                               'SUSPENDED'),
    ('SUSP COOP',       'Capable of Oil Production - Suspended',            'SUSPENDED'),
    ('SUSP GIW',        'Gas Injection Well - Suspended',                   'SUSPENDED'),
    ('SUSP PTH',        'Potash Test Hole - Suspended',                     'SUSPENDED'),
    ('SUSP ST',         'Standing - Suspended',                             'SUSPENDED'),
    ('SUSP STH',        'Stratigraphic Test Hole - Suspended',              'SUSPENDED'),
    ('SUSP SWD',        'Salt Water Disposal - Suspended',                  'SUSPENDED'),
    ('SUSP WAG',        'Water Alternating Gas Injection Well - Susp.',     'SUSPENDED'),
    ('SUSP WIW',        'Water Injection Well - Suspended',                 'SUSPENDED'),
    ('SUSP WSW',        'Water Source Well - Suspended',                    'SUSPENDED'),
    ('SWD',             'Salt Water Disposal',                              'INJECTION'),
    ('TEST',            'Testing',                                          'DRILLING'),
    ('TEST BOP',        'Testing BOPs',                                     'DRILLING'),
    ('WAG',             'Water Alternating Gas Injection Well',             'INJECTION'),
    ('WIW',             'Water Injection Well',                             'INJECTION'),
    ('WOC',             'Waiting On Cement',                                'DRILLING'),
    ('WOO',             'Waiting On Orders',                                'DRILLING'),
    ('WOSR',            'Waiting On Service Rig',                           'DRILLING'),
    ('WSW',             'Water Source Well',                                'INJECTION')
ON CONFLICT (well_status_type) DO NOTHING;

-- ------------------------------------------------------------
-- GOLD: DIMENSION — COMPANY (Phase 4)
-- Normalized licensee/company reference table
-- ------------------------------------------------------------
-- CREATE TABLE IF NOT EXISTS gold.dim_company (...)
-- Placeholder for Phase 4

-- ------------------------------------------------------------
-- GOLD: DIMENSION — LOCATION (Phase 4)
-- Normalized legal survey location reference
-- ------------------------------------------------------------
-- CREATE TABLE IF NOT EXISTS gold.dim_location (...)
-- Placeholder for Phase 4

-- ------------------------------------------------------------
-- GOLD: DIMENSION — DATE (Phase 4)
-- Calendar dimension for time-based aggregations
-- ------------------------------------------------------------
-- CREATE TABLE IF NOT EXISTS gold.dim_date (...)
-- Placeholder for Phase 4

-- ------------------------------------------------------------
-- GOLD: FACT — WELL APPROVALS (Phase 4)
-- Fact table for well approval events
-- ------------------------------------------------------------
-- CREATE TABLE IF NOT EXISTS gold.fact_well_approvals (...)
-- Placeholder for Phase 4

-- ------------------------------------------------------------
-- GOLD: FACT — SPILLS (Phase 4)
-- Fact table for spill incidents
-- ------------------------------------------------------------
-- CREATE TABLE IF NOT EXISTS gold.fact_spills (...)
-- Placeholder for Phase 4

-- ------------------------------------------------------------
-- GOLD: VIEW — COMPANY SPILL KPI (Phase 4)
-- Cross-references spills to approvals by company
-- ------------------------------------------------------------
-- CREATE VIEW gold.v_company_spill_kpi AS (...)
-- Placeholder for Phase 4

-- ------------------------------------------------------------
-- GOLD: VIEW — REGULATORY COMPLIANCE DETAIL (Phase 2A)
-- Per-record compliance pass/fail with specific rule violations
-- ------------------------------------------------------------
-- CREATE VIEW gold.v_regulatory_compliance_detail AS (...)
-- Placeholder for Phase 2A

-- ------------------------------------------------------------
-- GOLD: VIEW — DATA QUALITY SUMMARY (Phase 4A)
-- Per-batch data quality metrics
-- ------------------------------------------------------------
-- CREATE VIEW gold.v_data_quality_summary AS (...)
-- Placeholder for Phase 4A