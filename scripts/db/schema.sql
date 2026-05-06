-- ============================================================
-- MB PETRO WAREHOUSE - DATABASE SCHEMA
-- Version: 1.0.0
-- Description: Full Medallion architecture schema definition
--              Bronze, Silver, Gold, Audit layers
-- ============================================================

-- ------------------------------------------------------------
-- SCHEMAS
-- ------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS audit;

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
-- AUDIT: QUARANTINE TABLE
-- Stores records that failed Silver validation
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit.quarantine (
    id                  SERIAL PRIMARY KEY,
    batch_id            UUID NOT NULL,
    source_layer        TEXT NOT NULL,
    licence_id          TEXT,
    uwi                 TEXT,
    raw_block           TEXT,
    failure_reason      TEXT NOT NULL,
    failed_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    pipeline_version    TEXT NOT NULL DEFAULT '1.0.0'
);

CREATE INDEX IF NOT EXISTS idx_quarantine_batch_id
    ON audit.quarantine(batch_id);
CREATE INDEX IF NOT EXISTS idx_quarantine_licence_id
    ON audit.quarantine(licence_id);

-- ------------------------------------------------------------
-- BRONZE: WELL APPROVALS RAW
-- Stores raw JSON payloads exactly as extracted from source
-- No transformation applied at this layer
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.well_approvals_raw (
    id                  SERIAL PRIMARY KEY,
    batch_id            UUID NOT NULL,
    source_file         TEXT NOT NULL,
    report_date         TEXT,
    ingested_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    pipeline_version    TEXT NOT NULL DEFAULT '1.0.0',
    raw_payload         JSONB NOT NULL,
    record_hash         TEXT NOT NULL,
    CONSTRAINT uq_bronze_record_hash UNIQUE (record_hash)
);

CREATE INDEX IF NOT EXISTS idx_bronze_batch_id
    ON bronze.well_approvals_raw(batch_id);
CREATE INDEX IF NOT EXISTS idx_bronze_ingested_at
    ON bronze.well_approvals_raw(ingested_at);
CREATE INDEX IF NOT EXISTS idx_bronze_record_hash
    ON bronze.well_approvals_raw(record_hash);
CREATE INDEX IF NOT EXISTS idx_bronze_licence_id
    ON bronze.well_approvals_raw((raw_payload->>'licence_id'));

-- ------------------------------------------------------------
-- SILVER: WELL APPROVALS CLEANED
-- Parsed, typed, validated records from Bronze raw_block
-- One row per UWI (unique wellbore)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS silver.well_approvals_cleaned (
    id                  SERIAL PRIMARY KEY,
    batch_id            UUID NOT NULL,
    bronze_id           INTEGER REFERENCES bronze.well_approvals_raw(id),
    source_file         TEXT NOT NULL,
    ingested_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    pipeline_version    TEXT NOT NULL DEFAULT '1.0.0',

    -- Core fields
    licence_id          TEXT NOT NULL,
    well_name           TEXT,
    licence_issued      DATE,
    well_class          TEXT,
    licensee            TEXT,
    surface_location    TEXT,
    coordinates         TEXT,
    uwi                 TEXT NOT NULL,
    proj_td             NUMERIC(10, 2),
    geo_period          TEXT,
    ground_elev         NUMERIC(10, 2),
    drilling_rig        TEXT,
    rig_no              INTEGER,

    -- Governance flags
    is_tbd_rig          BOOLEAN DEFAULT FALSE,
    has_geo_period      BOOLEAN DEFAULT FALSE,
    has_ground_elev     BOOLEAN DEFAULT FALSE,
    uwi_valid           BOOLEAN DEFAULT FALSE,
    well_class_valid    BOOLEAN DEFAULT FALSE,
    is_contaminated     BOOLEAN DEFAULT FALSE,

    CONSTRAINT uq_silver_uwi UNIQUE (uwi, batch_id)
);

CREATE INDEX IF NOT EXISTS idx_silver_licence_id
    ON silver.well_approvals_cleaned(licence_id);
CREATE INDEX IF NOT EXISTS idx_silver_uwi
    ON silver.well_approvals_cleaned(uwi);
CREATE INDEX IF NOT EXISTS idx_silver_licensee
    ON silver.well_approvals_cleaned(licensee);
CREATE INDEX IF NOT EXISTS idx_silver_batch_id
    ON silver.well_approvals_cleaned(batch_id);
CREATE INDEX IF NOT EXISTS idx_silver_licence_issued
    ON silver.well_approvals_cleaned(licence_issued);

-- ------------------------------------------------------------
-- GOLD: WELL STATUS REFERENCE TABLE
-- Official Manitoba petroleum regulatory vocabulary
-- Seeded once, used for joins and validation
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold.dim_well_status (
    well_status_type    TEXT PRIMARY KEY,
    well_status_desc    TEXT NOT NULL,
    status_category     TEXT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Seed official Manitoba well status codes
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