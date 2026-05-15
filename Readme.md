# MB Petro Data Warehouse

An automated data engineering platform that consolidates fragmented provincial petroleum reports into a queryable relational warehouse. Ingests weekly well licence approvals, historical spill statistics, and the complete Manitoba well registry while enforcing provincial UWI regulatory standards. Built with a medallion architecture (Bronze → Silver → Gold) on PostgreSQL 15, orchestrated by Apache Airflow, and served via FastAPI.

---

## Quick Start

```bash
git clone <repo-url>
cd mb-petro-warehouse
docker-compose up -d
```

Wait 2 minutes for services to start.

| Service | URL | Credentials |
|---|---|---|
| Airflow | http://localhost:8080 | airflow / airflow |
| FastAPI Swagger | http://localhost:8000/docs | — |
| MinIO Console | http://localhost:9001 | minioadmin / minioadmin |
| PostgreSQL | localhost:5433 | airflow / airflow |

To run the pipeline: Open Airflow → trigger `mb_petro_pipeline` DAG.

To view dashboards: Open `dashboards/mb_petro_dashboard.pbix` in Power BI Desktop.

---

## Architecture

```
Sources (PDF/XLSX)
    │
    ▼
Extractors (pdfplumber) → JSON
    │
    ▼
Bronze Layer ← Raw JSONB + SHA256 dedup + batch audit
    │
    ▼
Silver Layer ← Parsed, typed, validated (30 regulatory rules)
    │
    ▼
Gold Layer ← Star schema + KPI views + compliance views
    │
    ├── FastAPI (REST API)
    ├── Power BI (Dashboards)
    └── MinIO (S3 Archive)

Airflow orchestrates all stages
```

---

## Datasets

| Dataset | Records | Source |
|---|---|---|
| Well Licence Approvals | 35 (weekly snapshot) | Manitoba New Well Approvals PDF |
| Spill Incidents | 179 | Manitoba Spill Stats PDF |
| UWI Key List (Well Registry) | 44,678 rows (12,789 unique wells) | Manitoba UWI Key List PDF |

---

## Key Features

- **30 regulatory validation rules** implementing Manitoba Petroleum Branch UWI Specification (character-level position validation, volume integrity checks, area consistency)
- **Company spill-to-approval KPI** cross-referencing spill incidents against well approvals by licensee
- **Regulatory compliance views** with per-record pass/fail audit trail
- **Data quality scoring** (completeness, uniqueness, validity, overall)
- **Metadata catalog** documenting all columns with business definitions and regulatory citations
- **Quarantine records** with resolution lifecycle (OPEN → REVIEWED → FIXED → ACCEPTED)
- **Full audit trail** tracking every pipeline run across all layers

---

## Tech Stack

| Component | Technology |
|---|---|
| Database | PostgreSQL 15 |
| Orchestration | Apache Airflow 2.8 |
| ETL Language | Python 3.11+ |
| API Layer | FastAPI |
| Visualization | Power BI Desktop |
| Object Storage | MinIO (S3-compatible) |
| Containerization | Docker Compose |

---

## Project Structure

```
├── api/                    # FastAPI application
│   └── main.py
├── config/                 # PostgreSQL init scripts
│   └── init-warehouse.sql
├── dags/                   # Airflow DAGs
│   └── mb_petro_pipeline.py
├── dashboards/             # Power BI file
│   └── mb_petro_dashboard.pbix
├── data/                   # Data directory (gitignored)
│   └── processed/          # Extracted JSON files
├── scripts/
│   ├── bronze/             # Bronze layer loader
│   ├── silver/             # Silver parser + loader
│   ├── gold/               # Gold layer loader
│   ├── validation/         # Quality rules + validation engine
│   ├── governance/         # Data quality metrics
│   ├── cloud/              # S3/MinIO archiver
│   ├── extractors/         # PDF extraction
│   └── db/                 # Schema definitions
├── sources/                # Original government files
├── tests/                  # Test suite
├── docker-compose.yaml
└── README.md
```

---

## Dashboard Pages

| Page | Content |
|---|---|
| Environmental Risk | Spill-to-approval ratio by company, KPI cards, company details |
| Compliance Overview | Pass/fail summary, failed checks by category |
| Well Registry | Status distribution, top companies, well details |
| Data Quality | Overall DQ score, completeness/uniqueness/validity by dataset |

---

## API Endpoints

| Endpoint | Description |
|---|---|
| `/well-approvals` | Well licence approvals (supports `?company=` filter) |
| `/spills` | Spill incidents (supports `?company=` filter) |
| `/company-kpi` | Spill-to-approval ratios by company |
| `/compliance-summary` | Regulatory compliance pass/fail summary |
| `/compliance-detail` | Per-record compliance results (`?dataset=wells\|spills`) |
| `/data-quality` | Data quality scores by dataset |
| `/health` | Database connectivity check |

---

## Regulatory References

- Manitoba Petroleum Branch — UWI Specification (DLS System)
- Manitoba Well Status Types
- Manitoba Pool Codes by Formation (Appendix B)

---

## Known Limitations

- **Duplicate records:** Gold fact tables currently lack unique constraints — repeated DAG runs may create duplicate records. To fix: add `ON CONFLICT DO NOTHING` to Gold INSERT statements and unique indexes on `licence_id` and `spill_no`.
- **Company name standardization:** Uses a hardcoded mapping for 3 companies (Tundra/Corex/Melita). A full implementation would use a separate mapping table.

---

## License

This project uses publicly available government data from the Manitoba Petroleum Branch. All data files in `sources/` are unmodified government publications.
