"""
MB Petro Warehouse Pipeline DAG
Orchestrates Bronze → Silver → Gold ETL with validation and DQ checks.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator

PROJECT_ROOT = "/opt/airflow"

default_args = {
    "owner": "data_engineer",
    "depends_on_past": False,
    "start_date": datetime(2026, 1, 1),
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="mb_petro_pipeline",
    default_args=default_args,
    description="MB Petro full ETL pipeline",
    schedule_interval=None,
    catchup=False,
    max_active_runs=1,
    tags=["mb_petro"],
) as dag:

    start = EmptyOperator(task_id="start")
    
    create_db = BashOperator(
    task_id="create_database",
    bash_command="PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d mb_petro -c 'CREATE DATABASE mb_petro_warehouse' 2>/dev/null; true",)
    
    init_db = BashOperator(
        task_id="init_database",
        bash_command="cat /opt/airflow/scripts/db/schema.sql | PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d mb_petro_warehouse",
  )

    # Load Bronze
    load_bronze_wells = BashOperator(
        task_id="load_bronze_wells",
        bash_command="cd /opt/airflow/scripts/bronze && python bronze_loader.py well_approvals /opt/airflow/data/processed/well_approvals.json",
    )

    load_bronze_spills = BashOperator(
        task_id="load_bronze_spills",
        bash_command="cd /opt/airflow/scripts/bronze && python bronze_loader.py spills /opt/airflow/data/processed/bronze_spills.json",
    )

    # Load Silver
    load_silver_spills = BashOperator(
        task_id="load_silver_spills",
        bash_command="cd /opt/airflow/scripts/silver && python silver_loader.py spills",
    )

    load_silver_wells = BashOperator(
        task_id="load_silver_wells",
        bash_command="cd /opt/airflow/scripts/silver && python silver_loader.py well_approvals",
    )

    # Load Gold
    load_gold = BashOperator(
        task_id="load_gold",
        bash_command="cd /opt/airflow/scripts/gold && python gold_loader.py",
    )

    end = EmptyOperator(task_id="end")
    
    archive = BashOperator(
        task_id="archive_to_s3",
        bash_command="cd /opt/airflow/scripts/cloud && MINIO_ENDPOINT=minio:9000 python s3_archiver.py /opt/airflow/data/processed/well_approvals.json && MINIO_ENDPOINT=minio:9000 python s3_archiver.py /opt/airflow/data/processed/bronze_spills.json",
    )

start >> create_db >> init_db
init_db >> [load_bronze_wells, load_bronze_spills]
load_bronze_wells >> load_silver_wells
load_bronze_spills >> load_silver_spills
[load_silver_wells, load_silver_spills] >> load_gold >> archive >> end