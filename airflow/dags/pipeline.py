# airflow/dags/pipeline.py

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from modules.cfa_scrape_data import scrape_data

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email': ['your_email@example.com'],  # Replace with your email
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 0,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'cfa_publications_dag',
    default_args=default_args,
    description='DAG to scrape CFA publications data',
    schedule='@daily',  # 使用 `schedule` 取代 `schedule_interval`
    start_date=datetime(2023, 1, 1),
    catchup=False,
)


scrape_task = PythonOperator(
    task_id='scrape_data',
    python_callable=scrape_data,
    dag=dag,
)

scrape_task  # Only one task in this DAG
