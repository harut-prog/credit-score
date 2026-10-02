# Кредитный скоринг — Give Me Some Credit

Сервис оценивает вероятность серьёзной просрочки по данным заёмщика. Рабочая модель — логистическая регрессия; `/v1/predict` принимает одну запись, `/v1/predict/batch` — до 1000 записей. История ДЗ 1 и ДЗ 2, включая нагрузочные замеры, находится в [REPORT.md](REPORT.md).

## Быстрый запуск после клонирования

Нужны Docker и Docker Compose. Файл `.env` создавать не требуется: для локального запуска заданы пользователь `postgres`, пароль `postgres` и база `credit`. Эти значения предназначены только для локальной разработки.

```bash
docker compose up -d --build
docker compose ps
curl http://localhost:8080/ready
```

После запуска `/ready` возвращает `{"state":"ready"}`. Swagger доступен по адресу http://localhost:8080/docs. Пример запроса:

```bash
curl -X POST http://localhost:8080/v1/predict \
  -H "Content-Type: application/json" \
  -d '{"unsecured_lines":0.3,"age":35,"past_30_59":0,"past_90":0,"past_60_89":0,"debt_ratio":0.5,"monthly_income":5000,"credit_lines":5,"real_estate":1,"dependents":2}'
```

На Windows PowerShell для запроса можно использовать `Invoke-RestMethod` с тем же JSON. Остановить сервис: `docker compose down`. Для смены локальных учётных данных скопируйте `.env.example` в `.env` и задайте новые значения перед первым запуском базы.

## Обучение и тесты

Нужны Python 3.11 и [uv](https://docs.astral.sh/uv/). Артефакт `artifacts/baseline_logreg.joblib` уже включён в репозиторий.

```bash
uv sync
uv run pytest
```

Чтобы заново получить файлы модели, откройте `baseline.ipynb` и выполните все ячейки по порядку. Последняя часть ноутбука сохраняет `artifacts/baseline_logreg.joblib`, `artifacts/baseline_catboost.cbm` и `artifacts/metadata.json`. Тесты с PostgreSQL запускаются, когда переменные `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD` и `POSTGRES_DB` указывают на работающую базу; без неё они пропускаются. Для локальной базы из Compose используйте `localhost`, `5432`, `postgres`, `postgres`, `credit`.

## Kubernetes (kind)

После `docker build -t credit-score:1.0 .` и `kind load docker-image credit-score:1.0 --name credit-service` создайте Secret до применения манифестов:

```bash
kubectl create secret generic credit-secrets --from-literal=POSTGRES_PASSWORD='replace-with-a-local-password'
kubectl apply -f k8s/
kubectl rollout status deployment/credit-score
kubectl port-forward service/credit-score 8000:80
```

Пароль для базы в Kubernetes хранится только в Secret; значение в команде выше — пример, который нужно заменить. Проверка готовности модели доступна по `http://localhost:8000/ready`, жизни процесса — по `/health`.

## ДЗ 3: MLflow, DVC и постоянный kind

Пошаговая инструкция и порядок проверок находятся в [instructions.md](instructions.md), результаты и ссылки — в разделе H3 [REPORT.md](REPORT.md). Для локального Compose Registry не нужен: если `MODEL_NAME` пуст, сервис берёт включённый в репозиторий `artifacts/baseline_logreg.joblib`. Личный `.env` может переопределить этот режим; перед локальными тестами задайте `MODEL_NAME=''` и `POSTGRES_HOST=''` либо временно уберите `.env`.

В Kubernetes `MODEL_NAME=credit-score-logreg`, `MODEL_ALIAS=champion`; API загружает конкретную Registry version при старте Pod. `/health` сообщает `model_source`, `model_version`, `run_id` и `threshold`. После переноса алиаса выполните `kubectl rollout restart deploy/credit-score`; новая версия появится в `/health` после завершения rollout. Секрет PostgreSQL называется `credit-secrets` и содержит ключ `POSTGRES_PASSWORD`. `k8s/postgres.yaml` использует PVC, поэтому пересоздание Pod сохраняет таблицу.

CSV `data/credit_score.csv` отслеживает DVC, а Git хранит `data/credit_score.csv.dvc`. Указанный в `.dvc/config` remote — локальная папка `C:\dvc-storage`; она не доступна на другой машине через GitHub. Для другого размещения клона настройте remote через `uv run dvc remote modify --local local url <путь>`, затем `uv run dvc pull`. Git SHA определяет версию указателя, DVC восстанавливает CSV, а `data_md5` в MLflow проверяет точный файл. V2 удаляет 270 невалидных строк, сохраняя исходные значения остальных записей. Для возврата V1/V2 восстановите нужный `.dvc` указатель из Git и запустите `uv run dvc checkout`.

Постоянный кластер `credit-service` создан с `platform/kind-config.yaml`: localhost:80 направлен на NodePort 30080 Traefik. MLflow открыт по `http://mlflow.localhost`, API — по `http://credit.localhost`; при системном прокси добавьте `.localhost` в `NO_PROXY`. Порядок первого развёртывания: DVC pull → kind/Traefik/MLflow → обучение и alias `champion` → PostgreSQL/API/HPA → self-hosted runner. Runner подключён к Docker network `kind` с Docker socket и меткой `kind`; GitHub Actions строит образ в облаке, а job `deploy` разворачивает его в существующий кластер и проверяет точный `request_id` в БД. Пока ДЗ проверяется, сохраняйте кластер, MLflow PVC и DVC remote.
