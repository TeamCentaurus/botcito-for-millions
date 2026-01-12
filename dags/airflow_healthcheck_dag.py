from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.state import State
import logging
import socket
import os

DEFAULT_ARGS = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 0,
}

def healthcheck(**context):
    logging.info("✅ Airflow healthcheck running")
    logging.info(f"Hostname: {socket.gethostname()}")
    logging.info(f"PID: {os.getpid()}")
    logging.info(f"Execution date: {context['ds']}")

    # Simple XCom test
    context["ti"].xcom_push(key="health", value="ok")

def validate_xcom(**context):
    value = context["ti"].xcom_pull(
        task_ids="healthcheck",
        key="health"
    )

    if value != "ok":
        raise ValueError("❌ XCom validation failed")

    logging.info("✅ XCom validated successfully")

with DAG(
    dag_id="airflow_healthcheck",
    description="Healthcheck DAG to verify Airflow scheduler & workers",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 1, 1),
    schedule_interval="*/5 * * * *",  # cada 5 minutos
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(minutes=2),
    tags=["critical", "health", "monitoring", "system"],
) as dag:

    t1 = PythonOperator(
        task_id="healthcheck",
        python_callable=healthcheck,
        provide_context=True,
    )

    t2 = PythonOperator(
        task_id="validate_xcom",
        python_callable=validate_xcom,
        provide_context=True,
    )

    t1 >> t2