# Credit score: Give Me Some Credit

Сервис оценивает вероятность серьёзной просрочки на основе десяти признаков заёмщика. Логистическая регрессия обучается по версионированному CSV, проходит сравнение с текущим champion в MLflow и обслуживает одиночные и пакетные запросы. История ДЗ 1–4 и доказательства находятся в [REPORT.md](REPORT.md).

## Quickstart: чистый Windows-компьютер и kind

Нужны Git (с Git Bash), Docker Desktop, Python 3.11, [uv](https://docs.astral.sh/uv/), [kind](https://kind.sigs.k8s.io/), kubectl и Helm. Docker Desktop должен быть запущен. Команды ниже — PowerShell; две команды `port-forward` держите в отдельных окнах. Дефолтные пароли ниже учебные, только для локального kind.

```powershell
git clone -b hw4 https://github.com/harut-prog/credit-score.git
cd credit-score
uv sync --frozen
& 'C:\Program Files\Git\bin\bash.exe' platform/up.sh
kubectl get pods -A
```

`platform/up.sh` создаёт kind, MLflow, Airflow, RustFS с бакетом `dvc`, Prometheus и Grafana. На свежей машине бакет пуст. Скрипт ниже скачает публичный оригинал Give Me Some Credit, проверит SHA256, удалит ровно 270 строк со специальными кодами просрочки или нулевым возрастом и подтвердит MD5 DVC-версии. При несовпадении скрипт остановится; данные не придётся подбирать вручную.

```powershell
uv run python scripts/bootstrap_data.py
```

Откройте **второе окно PowerShell** в папке репозитория и оставьте эту команду работающей:

```powershell
kubectl -n mlops port-forward svc/rustfs 9000:9000
```

В первом окне задайте личные настройки DVC (они сохраняются в игнорируемом `.dvc/config.local`) и отправьте данные в бакет. Значения ключей должны совпадать с `S3_KEY` и `S3_SECRET`, которые вы передали в `platform/up.sh`; ниже его учебные значения по умолчанию.

```powershell
uv run dvc remote modify --local laptop endpointurl http://127.0.0.1:9000
uv run dvc remote modify --local laptop access_key_id dvcadmin
uv run dvc remote modify --local laptop secret_access_key dvc-secret-123
uv run dvc push -r laptop
```

Откройте **третье окно PowerShell** и оставьте вторую пересылку портов работающей:

```powershell
kubectl -n mlops port-forward svc/mlflow 5000:5000
```

В первом окне обучите и зарегистрируйте исходный champion:

```powershell
$env:MLFLOW_TRACKING_URI='http://127.0.0.1:5000'
uv run python -m credit.data
uv run python -m credit.train --c 1.0
```

В конце вывода обучения ожидается JSON с `"promoted": true`. Теперь соберите образ без CSV и разверните API. Секрет должен совпадать с паролем нового Postgres; для первого локального запуска используется `postgres`.

```powershell
$commitSha = git rev-parse HEAD
docker build --build-arg BUILD_GIT_SHA=$commitSha -t credit-score:hw4 .
kind load docker-image credit-score:hw4 --name credit-service
kubectl create secret generic credit-secrets --from-literal=POSTGRES_PASSWORD=postgres --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f k8s/configmap.yaml -f k8s/postgres.yaml
kubectl rollout status deployment/postgres
kubectl set image --local -f k8s/deployment.yaml api=credit-score:hw4 -o yaml | kubectl apply -f -
kubectl apply -f k8s/service.yaml -f k8s/ingress.yaml -f k8s/hpa.yaml
kubectl apply -f platform/service-monitor.yaml -f platform/dashboard.yaml
kubectl rollout status deployment/credit-score
kubectl -n mlops create configmap airflow-dags --from-file=dags/ --dry-run=client -o yaml | kubectl apply -f -
kubectl -n mlops exec deploy/airflow -- airflow variables set credit_image credit-score:hw4
kubectl -n mlops exec deploy/airflow -- airflow variables set credit_c 1.0
kubectl -n mlops exec deploy/airflow -- airflow variables set credit_class_weight balanced
kubectl -n mlops exec deploy/airflow -- airflow variables set credit_feature_set quantile
kubectl -n mlops exec deploy/airflow -- airflow variables set credit_min_gain 0.001
```

Проверьте ответ через Ingress (PowerShell `curl.exe`, без DNS-запроса к `*.localhost` из Python):

```powershell
curl.exe -H 'Host: credit.localhost' http://127.0.0.1/health
curl.exe -H 'Host: credit.localhost' -H 'Content-Type: application/json' -d '{"unsecured_lines":0.3,"age":35,"past_30_59":0,"past_90":0,"past_60_89":0,"debt_ratio":0.5,"monthly_income":5000,"credit_lines":5,"real_estate":1,"dependents":2}' http://127.0.0.1/v1/predict
curl.exe -H 'Host: credit.localhost' http://127.0.0.1/metrics
```

Интерфейсы: [MLflow](http://mlflow.localhost), [Airflow](http://airflow.localhost), [Grafana](http://grafana.localhost/d/credit-hw4/credit-score-service), [RustFS](http://s3-console.localhost/rustfs/console/index.html). Grafana: `admin/admin` в учебном кластере. DAG `credit_retrain` выполняет `validate → train → promoted → rollout`. Для ручного запуска нажмите **Trigger** в Airflow; для длительной нагрузки выполните `uv run python scripts/traffic.py --seconds 300`.

Для CI зарегистрируйте self-hosted runner в **GitHub → Settings → Actions → Runners** на том же компьютере, где запущен kind. Выполните показанные GitHub команды регистрации и добавьте labels `self-hosted`, `kind`. Добавьте секрет репозитория `DB_PASSWORD` со значением, использованным для Postgres. После вашего коммита и push ветки `hw4` запустите workflow `ci` кнопкой **Run workflow**; deploy применит DAG и мониторинг, затем проверит ответ, БД и метрику версии модели. На чистом кластере сначала выполните шаги выше, чтобы появился champion.

Если используете уже зарегистрированный контейнер `gh-runner` на этой машине, после перезапуска Docker запустите его слушатель:

```powershell
docker start gh-runner
docker exec -d -w /home/runner gh-runner ./run.sh
docker exec gh-runner pgrep -af Runner.Listener
```

Runner должен показываться как **Idle** на странице GitHub Runners перед push или ручным запуском workflow. Повторно регистрировать существующий runner не нужно.

## Разработка и восстановление

```powershell
uv run ruff check .
uv run pytest
```

В Git лежат код, манифесты и `data/credit_score.csv.dvc`; сам CSV исключён из Git и образа. В `dvc` есть два remote для одного бакета: `laptop` с доступом через локальный port-forward и `cluster` по адресу RustFS внутри kind. Новые версии данных сначала отправляйте `dvc push -r laptop`, затем сохраняйте указатель `data/credit_score.csv.dvc` в Git. Независимую копию CSV и важных MLflow-артефактов держите вне kind: `kind delete cluster` удаляет локальные тома кластера.

Модель и её версия видны в `/health`, прогнозы сохраняются в PostgreSQL, метрики `/metrics` собирает Prometheus. Локально без кластера можно запустить прежний Compose-режим с моделью из `artifacts/baseline_logreg.joblib`: `docker compose up -d --build`, затем `curl.exe http://localhost:8080/ready`.
