# H1 — Домашка 1

## 3 команды проверки

```bash
uv run pytest
```

```bash
docker build -t credit-score:1.0 .
docker compose up -d --build
```

```bash
kind create cluster --name credit-score 
kind load docker-image credit-score:1.0 --name credit-score 
kubectl apply -f k8s/ 
kubectl rollout status deploy/credit-score 
kubectl port-forward svc/credit-score 8000:80
```

## Тесты

Запустил командой `uv run pytest`, результат приложен в скрине ниже

![image](docs/img/pasted-image-20260918111538.png)

## Логи в базе данных

![image](docs/img/pasted-image-20260918112324.png)

## Оркестрация в K8s

![image](docs/img/pasted-image-20260918112823.png)

![image](docs/img/pasted-image-20260918125306.png)

![image](docs/img/pasted-image-20260918113715.png)

![image](docs/img/pasted-image-20260918113800.png)

## Нагрузочное тестирование locust

-- run10.csv --

| Type             | RPS   | median | p95 | max    | errors |
| ---------------- | ----- | ------ | --- | ------ | ------ |
| GET /health      | 8.17  | 8      | 26  | 154.56 | 0      |
| POST /v1/predict | 22.00 | 19     | 49  | 240.03 | 0      |
| Aggregated       | 30.17 | 17     | 47  | 240.03 | 0      |

-- run50.csv --

| Type             | RPS   | median | p95 | max    | errors |
| ---------------- | ----- | ------ | --- | ------ | ------ |
| GET /health      | 22.32 | 130    | 390 | 626.36 | 0      |
| POST /v1/predict | 67.00 | 220    | 630 | 946.74 | 0      |
| Aggregated       | 89.33 | 200    | 590 | 946.74 | 0      |

-- run100.csv -- 

| Type             | RPS   | median | p95  | max     | errors |
| ---------------- | ----- | ------ | ---- | ------- | ------ |
| GET /health      | 21.06 | 480    | 900  | 1352.18 | 0      |
| POST /v1/predict | 64.54 | 890    | 1400 | 1860.69 | 0      |
| Aggregated       | 85.60 | 830    | 1300 | 1860.69 | 0      |

При 10 пользователях сервис работает с запасом: p95 (47 мс) отличается от медианы (17 мс) всего в ~2.8 раза, ошибок нет. 

Уже при переходе к 50 пользователям разрыв между p95 и медианой резко растёт (390 мс против 30 мс на 10 пользователях). Здесь начинается очередь на воркерах. 

При этом RPS почти не растёт при переходе от 50 к 100 пользователям (89.3 -> 85.6). Сервис уже упёрся ещё на 50 пользователях, а дальнейшая нагрузка лишь увеличивает время ожидания в очереди (медиана растёт с 200 до 830 мс), а не пропускную способность. 

Ошибок не было ни на одном из трёх прогонов, только растет время ожидания.

## Батч‐эндпоинт с замером

Для проверки написан скрипт scripts/measure_batch.py. Посчитана медиана из десятка повторов

![image](docs/img/pasted-image-20260918120630.png)

Медиана из 10 повторов: 1 строка = 6.835 мс, 500 строк = 111.395 мс. Батч из 500 строк дороже одиночного запроса всего в 16.3 раз, а не в 500. Причина в том, что sklearn считают предсказание для всей матрицы признаков одним векторизованным вызовом, а не строка за строкой.

## Выкат новой версии и откат

```
kubectl get deploy,svc,pods
kubectl get pods -w
kubectl set image deploy/credit-score api=credit-score:1.1
kubectl rollout status deploy/credit-score
kubectl rollout undo deploy/credit-score
kubectl rollout history deploy/credit-score
kubectl port-forward svc/credit-score 8000:80
```

![image](docs/img/pasted-image-20260918121844.png)

![image](docs/img/pasted-image-20260918122338.png)

![image](docs/img/pasted-image-20260918122341.png)

![image](docs/img/pasted-image-20260918122406.png)

![image](docs/img/pasted-image-20260918122453.png)
Версия FastAPI действительно поменялась

![image](docs/img/pasted-image-20260918122707.png)

Откат по версии

![image](docs/img/pasted-image-20260918122842.png)

![image](docs/img/pasted-image-20260918122910.png)

![image](docs/img/pasted-image-20260918122852.png)

![image](docs/img/pasted-image-20260918122953.png)

![image](docs/img/pasted-image-20260918123036.png)

Опять пробросил порт, и версия FastAPI вернулась к 1.0

![image](docs/img/pasted-image-20260918123141.png)

## Журнал проблем

Здесь скорее то, к каким архитектурным решениям я пришел. Не совсем уверен, что правильно их реализовал, поэтому был бы рад фидбеку.

В compose файле при инициализации БД я сделал подключение к ней через переменные окружения (хост, пароль, таблица и пользователь в .env файле). Но это немного усложнило тест работы БД. Для compose postgres лежит по хосту db, для docker файла и подов в k8s по localhost. Поэтому в .yml файле для compose хост задан напрямую (db), остальные параметры из окружения, а в остальных вариантах хост подтягивается из .env и подключается к локалке.

Выглядит немного как костыль, но мне хотелось, чтобы пароль к БД не был указан напрямую в yaml. В первой домашке я тогда не стал настраивать Secret в Kubernetes. Во второй домашке пароль передаётся через GitHub Secret `DB_PASSWORD`, а CI создаёт Kubernetes Secret `credit-secrets`, который Deployment подключает к контейнеру.

Логирование (не запись в БД, а в консольке через logger) только в app.py реализовано. Не совсем информативно

# H2 — Домашка 2: CI/CD

## Реализация пайплайна

Workflow `.github/workflows/ci.yml` запускает `tests` для pull request и push в `master`. Job `tests` поднимает PostgreSQL, запускает Ruff и pytest. На push в `master` после успешных тестов job `build` собирает Docker-образ и публикует его в GHCR с тегом по SHA коммита, а `deploy` создаёт кластер kind, разворачивает PostgreSQL и API, затем выполняет smoke test.

Пароль БД хранится в GitHub Secret `DB_PASSWORD`: workflow создаёт Kubernetes Secret `credit-secrets`, а Deployment импортирует его переменные через `secretRef`. Настройка `LOG_LEVEL` приходит из ConfigMap и возвращается в `/health`. Smoke test посылает реальные признаки, проверяет `0 <= score <= 1` и проверяет, что запрос записан в таблицу. При сбое диагностика собирает Pods, события, `describe` и логи, включая `--previous`.

## Таблица требований и доказательств

| Пункт | Результат | Доказательство |
|---|---|---|
| Три job: tests, build, deploy | Все три завершились успешно в run #20. | [Скриншот run #20](docs/img/hw2_memory_requests_green.jpg); [Actions](https://github.com/harut-prog/credit-score/actions) |
| GHCR-образ с тегом SHA | В run #20 использован `ghcr.io/harut-prog/credit-service:sha-7124af61c8c0eb3149055aeb5c471f043b196d3c`. | [Скриншот с тегом](docs/img/hw2_memory_requests_green.jpg); [страница пакета](https://github.com/harut-prog/credit-score/pkgs/container/credit-service) |
| Pull request: намеренно сломанный тест, затем исправление | Красная проверка показала `assert 200 == 201`; после исправления тесты прошли. На PR `build` и `deploy` ожидаемо пропущены. | [PR #1](https://github.com/harut-prog/credit-score/pull/1); [красная проверка](docs/img/hw2_broken_test.jpg), [ошибка assertion](docs/img/hw2_assertion_error_test.jpg), [зелёная проверка](docs/img/hw2_ci_all_green.jpg) |
| ConfigMap: неверный путь к модели | Run #13 упал при запуске API из-за отсутствующего файла; run #14 после исправления успешен. | [Красный run #13](docs/img/hw2_broken_model_path.jpg), [FileNotFoundError](docs/img/hw2_fake_joblib.jpg), [зелёный run #14](docs/img/hw2_fixed_model_path.jpg) |
| Secret: имя `secretRef` не совпадает с именем созданного секрета | Run #15 упал на rollout; диагностика показала `CreateContainerConfigError`. Run #16 после исправления успешен. | [Красный run #15](https://github.com/harut-prog/credit-score/actions/runs/361100731); [диагностика](docs/img/hw2_secret_ref_red.jpg), [зелёный run #16](docs/img/hw2_secret_ref_fix.jpg) |
| Ресурсы: запрос памяти не помещается на узле | В run #19 диагностика показала Pod в `Pending` и `FailedScheduling` из-за `Insufficient memory`; run #20 после возврата обычных значений успешен. | [Красный run #19 — rollout](docs/img/hw2_memory_request_failed.jpg), [диагностика `Pending` / `Insufficient memory`](docs/img/hw2_failed_scheduling.jpg), [зелёный run #20](docs/img/hw2_memory_requests_green.jpg) |
| Диагностика при сбое | Шаг `Diagnostics` собирает состояние Pods, события кластера и текущие/предыдущие логи контейнеров. | Скриншоты красных runs выше; команды находятся в `.github/workflows/ci.yml` в шаге `Diagnostics`. |

## Семь вопросов

1. В двух первых сравниваемых Actions runs job `build` занял 25 секунд в run #13 и 14 секунд в run #14. Между ними менялись Kubernetes-манифесты, а `Dockerfile`, `pyproject.toml` и `uv.lock` оставались прежними. Поэтому BuildKit мог взять из GHA cache слой установки зависимостей `RUN uv sync --frozen --no-dev --no-install-project`, а также последующие неизменившиеся слои.

2. Эти `ImagePullBackOff` Pods появляются при первоначальном применении `k8s/deployment.yaml`: там стоит шаблонный образ `credit-score:1.0`, которого нет в kind. Следом workflow выполняет `kubectl set image` на SHA-тег из GHCR; новые Pods запускаются, а временные Pods старого ReplicaSet удаляются. Поэтому само наличие переходных Pods в логе ещё не означает провал финального rollout.

3. Пароль задаётся в GitHub Secrets как `DB_PASSWORD`, workflow передаёт его в переменную окружения шага, а `kubectl create secret` сохраняет значение в Kubernetes Secret `credit-secrets` под ключом `POSTGRES_PASSWORD`. Deployment через `secretRef` передаёт этот ключ в контейнер как переменную окружения. В ConfigMap пароль хранить нельзя: ConfigMap предназначен для обычной конфигурации, а не секретных данных.

4. Без `needs: tests` сборка может стартовать параллельно с тестами. Если тесты упадут, build всё равно способен опубликовать образ, а deploy — выкатить его на `master`, поскольку его зависимостью останется build; в результате непроверенная версия попадёт в кластер.

5. На pull request запускается только `tests`, потому что у jobs `build` и `deploy` стоит условие `if: github.ref == 'refs/heads/master'`. Для PR ref имеет вид `refs/pull/.../merge`, поэтому условие ложно. Это не даёт собирать и выкатывать образ из непроверенной ветки PR и не запускает deployment до слияния в `master`.

6. `pg_advisory_xact_lock(12345)` в `db.init()` сериализует инициализацию схемы и автоматически освобождается в конце транзакции. Без блокировки два API-pod могут одновременно начать создавать таблицу в пустой базе; при гонке одна инициализация может завершиться ошибкой, из-за которой соответствующий pod не поднимется. Речь о двух репликах приложения `credit-score`, а не о репликах PostgreSQL.

7. В трёх намеренно сломанных сценариях зафиксированы разные состояния Pod: `Pending` при нехватке памяти (`FailedScheduling` / `Insufficient memory`), `CreateContainerConfigError` при неверном `secretRef` и `CrashLoopBackOff` при несуществующем пути к модели. Это три отдельных сбоя конфигурации, а не последовательные стадии одного Pod. Скрин run #19 подтверждает `Pending` и нехватку памяти; остальные состояния видны в диагностических скриншотах соответствующих запусков.

## Журнал проблем

1. **Тест в PR.** Я временно ожидал статус `201`, но endpoint вернул `200`: pytest показал `assert 200 == 201` и завершился с одним упавшим тестом. Исправил ожидаемый статус на фактический `200`, отправил следующий коммит и дождался зелёной проверки PR.

2. **Неверный путь к модели (runs #13 → #14).** В ConfigMap указал несуществующий путь. В `deploy` сломался rollout, а логи контейнера показали `FileNotFoundError` для `artifacts/no_baseline_be_sure.joblib` и `Application startup failed`. Исправил `MODEL_PATH` на существующий файл модели; следующий запуск завершил `tests`, `build` и `deploy` успешно.

3. **Неверное имя Secret (runs #15 → #16).** Workflow создаёт `credit-secrets`, а в `secretRef` временно было указано `credit-secret`. `Deploy API` не дождался rollout; диагностика показала Pod в `CreateContainerConfigError`. Вернул точное имя `credit-secrets`; следующий run прошёл.

4. **Недоступная память (runs #19 → #20).** Первая попытка с огромным `requests.memory` при `limits.memory: 1Gi` была отклонена Kubernetes API ещё при `kubectl apply`, потому что request превышал limit. Для повторной симуляции я сделал request и limit одинаково большими: манифест применился, rollout завершился таймаутом, а диагностика подтвердила Pod `Pending` и `FailedScheduling` с причиной `Insufficient memory`. Затем вернул `requests.memory: 512Mi` и `limits.memory: 1Gi`; run #20 прошёл все три job.

Для исправленных сценариев я сохранял отдельные коммиты: `f3ecaa2` — модель, `6eea4da` — Secret, `7124af6` — память. Первоначальную ошибочную попытку с request больше limit оставил в истории как диагностический шаг, а в отчёте основным ресурсным сценарием указал повтор run #19.
