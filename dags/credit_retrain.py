"""Validate DVC data, train a challenger, and roll out a promoted champion."""

from datetime import UTC, datetime

from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.standard.operators.python import PythonOperator, ShortCircuitOperator
from airflow.timetables.trigger import CronTriggerTimetable
from kubernetes import client, config


def was_promoted(ti):
    result = ti.xcom_pull(task_ids="train")
    return isinstance(result, dict) and result.get("promoted") is True


def restart_credit_score():
    config.load_incluster_config()
    client.AppsV1Api().patch_namespaced_deployment(
        name="credit-score",
        namespace="default",
        body={"spec": {"template": {"metadata": {"annotations": {
            "kubectl.kubernetes.io/restartedAt": datetime.now(UTC).isoformat()
        }}}}},
    )


with DAG(
    dag_id="credit_retrain",
    schedule=CronTriggerTimetable("0 3 * * *", timezone="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["credit", "hw4"],
) as dag:
    common = dict(
        namespace="mlops",
        image="{{ var.value.credit_image }}",
        service_account_name="airflow",
        in_cluster=True,
        get_logs=True,
        on_finish_action="delete_pod",
        env_vars=[
            client.V1EnvVar(name="MLFLOW_TRACKING_URI", value="http://mlflow.mlops.svc.cluster.local:5000"),
            client.V1EnvVar(
                name="AWS_ACCESS_KEY_ID",
                value_from=client.V1EnvVarSource(secret_key_ref=client.V1SecretKeySelector(
                    name="s3-credentials", key="AWS_ACCESS_KEY_ID"
                )),
            ),
            client.V1EnvVar(
                name="AWS_SECRET_ACCESS_KEY",
                value_from=client.V1EnvVarSource(secret_key_ref=client.V1SecretKeySelector(
                    name="s3-credentials", key="AWS_SECRET_ACCESS_KEY"
                )),
            ),
        ],
    )

    validate = KubernetesPodOperator(
        task_id="validate",
        cmds=["/bin/sh", "-ec"],
        arguments=["uv run --no-sync dvc pull -r cluster && uv run --no-sync python -m credit.data"],
        **common,
    )
    train = KubernetesPodOperator(
        task_id="train",
        cmds=["/bin/sh", "-ec"],
        arguments=[
            "uv run --no-sync dvc pull -r cluster && "
            "AIRFLOW_XCOM_PATH=/airflow/xcom/return.json "
            "uv run --no-sync python -m credit.train "
            "--c {{ var.value.credit_c }} "
            "--class-weight {{ var.value.credit_class_weight }} "
            "--feature-set {{ var.value.credit_feature_set }} "
            "--min-gain {{ var.value.credit_min_gain }}"
        ],
        do_xcom_push=True,
        **common,
    )
    promoted = ShortCircuitOperator(task_id="promoted", python_callable=was_promoted)
    rollout = PythonOperator(task_id="rollout", python_callable=restart_credit_score)

    validate >> train >> promoted >> rollout
