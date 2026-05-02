"""
DAG : Job Intelligent Pipeline (parallèle)
============================================
Pipeline :
1. Les 4 scrapers tournent EN PARALLÈLE (gain de temps)
2. dbt run lance après que TOUS les scrapers soient finis
3. Bronze → Silver → Gold
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator

# ====== Arguments par défaut ======
default_args = {
    "owner": "hafsa",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

# ====== Définition du DAG ======
with DAG(
    dag_id="job_intelligent_pipeline",
    description="Pipeline parallèle : 4 scrapers + dbt (Bronze → Silver → Gold)",
    default_args=default_args,
    start_date=datetime(2026, 4, 26),
    schedule=None,                          # Lancement manuel
    catchup=False,
    max_active_tasks=4,                     # Max 4 tâches en parallèle
    tags=["job-intelligent", "scraping", "dbt"],
) as dag:

    start = EmptyOperator(task_id="start")
    end = EmptyOperator(task_id="end")

    # --- 4 scrapers EN PARALLÈLE ---
    scrape_rekrute = BashOperator(
        task_id="scrape_rekrute",
        bash_command="cd /opt/airflow/scrapers && python rekrute_scraper.py",
    )

    scrape_dreamjob = BashOperator(
        task_id="scrape_dreamjob",
        bash_command="cd /opt/airflow/scrapers && python dreamjob_scraper.py",
    )

    scrape_indeed = BashOperator(
        task_id="scrape_indeed",
        bash_command="cd /opt/airflow/scrapers && python indeed_scraper.py",
    )

    scrape_linkedin = BashOperator(
        task_id="scrape_linkedin",
        bash_command="cd /opt/airflow/scrapers && python linkedin_scraper.py",
    )

    # --- dbt run après TOUS les scrapers ---
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command="cd /opt/airflow/dbt_project && dbt run",
    )

    # ====== Orchestration parallèle ======
    # start déclenche les 4 scrapers en même temps
    # dbt_run attend que TOUS les scrapers soient finis (fan-in)
    start >> [scrape_rekrute, scrape_dreamjob, scrape_indeed, scrape_linkedin] >> dbt_run >> end