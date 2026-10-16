# ДЗ 4: простой порядок работы

Работаем в ветке `hw3`. Это имя ветки, само задание — ДЗ 4.
Дедлайн: 18 октября, 23:59. Правки по фидбэку — до 25 октября, 23:59.
Все команды ниже запускаются из `C:\PostupashkiProject`. Файлы правь руками в редакторе.

## Сегодня, 8 октября

Цель дня: восстановить датасет и поднять платформу. Pandera, метрики и DAG сегодня делать не нужно.

### 1. Проверь ветку

```powershell
git branch --show-current
git status --short
```

Должна быть `hw3`. Твои изменения уже находятся в ней. `tmp/` в коммит не добавляй.

### 2. Восстанови CSV

Сейчас `data/credit_score.csv` отсутствует. Старая папка DVC `C:\dvc-storage` существует; сначала попробуй восстановить из неё:

```powershell
uv sync --frozen
uv run dvc remote modify --local local url C:/dvc-storage
uv run dvc pull -r local data/credit_score.csv
```

Открой папку `data` и убедись, что CSV появился. Если команда упала, сначала разберись с ней, дальше обучение не запускай.

Проверка версии:

```powershell
(Get-FileHash data/credit_score.csv -Algorithm MD5).Hash.ToLower()
```

Для текущего указателя ожидается `d7123f735b51ec6675c136a2a944aa25`.

### 3. Добавь недостающие файлы платформы

Открой [эталон курса](https://github.com/artemovmak/ML_PRO2026/tree/479fceba7e228b9515c73d1e6affc2c0a8eede9c).

- Скопируй содержимое `platform/s3.yaml` в свой новый `platform/s3.yaml`.
- Остальной `platform/` заново не копируй: ты уже начал его адаптировать.
- В корне создай `.gitattributes` со следующим содержимым:

```gitattributes
* text=auto
*.sh text eol=lf
*.yaml text eol=lf
*.yml text eol=lf
```

В редакторе выбери для `platform/up.sh` окончания строк **LF** и кодировку **UTF-8 без BOM**. Это нужно, чтобы Bash на Windows не падал из-за CRLF.

### 4. Исправь два имени

**В `platform/airflow.yaml`:** найди `resourceNames: [credit-service]` и замени на:

```yaml
resourceNames: [credit-score]
```

`credit-service` — имя кластера, `credit-score` — имя deployment, который перезапускает Airflow.

**В `platform/ingress.yaml`:** удали целый документ Ingress с `metadata.name: credit-service` и адресом `credit.localhost`. Документы разделены строками `---`; соседние документы сохрани.

У API уже есть правильный Ingress в `k8s/ingress.yaml`, ведущий на Service `credit-score`. Второй ему мешает. В платформенном файле оставь MLflow, Airflow, Grafana и S3.

### 5. Верни настройки metrics-server

Создай обратно `platform/metrics-server-values.yaml`:

```yaml
args:
  - --kubelet-insecure-tls
```

В `platform/up.sh`, после добавления Helm-репозиториев, вставь:

```bash
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/ >/dev/null 2>&1 || true
helm upgrade --install metrics-server metrics-server/metrics-server --version 3.14.0 \
  -n kube-system -f platform/metrics-server-values.yaml --wait
```

Это сохранит HPA при будущем запуске с нуля. В текущем кластере metrics-server уже есть.

Проверь также начало `up.sh`: там должно остаться `CLUSTER=${CLUSTER:-credit-service}`.

### 6. Запусти платформу

Открой Docker Desktop и дождись готовности. Затем:

```powershell
& 'C:\Program Files\Git\bin\bash.exe' platform/up.sh
```

Дождись завершения. При ошибке остановись и разбери первый упавший шаг; кластер удалять не нужно.

### 7. Проверь результат

```powershell
kubectl get pods -A
kubectl get ingress -A
```

Нужные компоненты должны быть готовы. У завершённых вспомогательных задач допустим `Completed`.

Открой в браузере:

- `http://credit.localhost/health` — старый API продолжает отвечать.
- `http://mlflow.localhost` — модели сохранились.
- `http://airflow.localhost` — Airflow запущен.
- `http://grafana.localhost` — Grafana доступна; учебный логин `admin`, пароль `admin`.
- `http://s3-console.localhost/rustfs/console/index.html` — S3 console; учебные defaults `dvcadmin` / `dvc-secret-123`, если ты их не менял.

В S3 console проверь, что есть бакет `dvc`. Если его нет, создай через интерфейс. Не считай финальную надпись up.sh доказательством создания бакета.

Сохрани скрин или вывод `kubectl get pods -A` и скрин бакета для будущего отчёта.

**На сегодня достаточно:** CSV восстановлен, платформа поднята, интерфейсы открываются, бакет `dvc` существует, старый API работает. Если всё это готово — этап дня закрыт.

## Дальнейшие дни

### 9–10 октября: перенести DVC в S3 и подготовить образ

1. Перенеси `dvc[s3]` из dev-зависимостей в обычные, добавь Pandera и instrumentator:

```powershell
uv remove --dev dvc
uv add 'dvc[s3]' 'pandera[pandas]' prometheus-fastapi-instrumentator
```

2. Настрой remote `laptop` на `s3://dvc` с endpoint `http://s3.localhost`, а `cluster` — на тот же бакет с endpoint `http://rustfs.mlops:9000`. Ключи ноутбука сохрани через `dvc remote modify --local`, не в Git. Подам ключи передаст Secret `s3-credentials`.
3. Выполни `uv run dvc push -r laptop`, проверь объекты в console и восстановление через pull.
4. В Dockerfile копируй `.dvc/config` и `data/*.dvc`, включи `core.no_scm true`. В образе должен быть DVC, но не CSV и не локальные ключи.
5. Обучение сейчас вызывает Git. Передавай SHA кода через `BUILD_GIT_SHA` при сборке: внутри образа `.git` нет. Локально оставь Git fallback.

Готово, когда данные загружаются с ноутбука и из Pod, а `docker run --rm <образ> ls data` показывает только указатель.

### 11 октября: проверка данных

1. Создай `src/credit/data.py`: общая очистка для validate и train, схема строк и схема всей выгрузки.
2. Проверь типы, диапазоны минимум трёх числовых признаков, категориальный домен и уникальность исходного ID. Не придумывай границы: сначала посмотри статистику своих данных. Для категориального поля можно осмысленно выделить возрастные группы, не добавляя их автоматически в признаки модели.
3. Для всей выгрузки проверь объём и распределение: например, долю просрочки или медиану дохода.
4. Ошибки сохраняй в MLflow как `failure_cases.csv`, ставь `valid=false`, завершай команду с кодом 1.
5. Напиши три теста без датасета: хорошие строки, плохое значение, маленькая выгрузка.

Готово, когда тесты зелёные и есть настоящий красный validate с отчётом в MLflow.

### 12 октября: метрики и Grafana

1. Добавь `/metrics`, технические метрики и минимум две свои: версия модели и распределение score/доля положительных ответов.
2. Подбери latency buckets по измерениям своего API. `request_id` и признаки в labels не добавляй.
3. Адаптируй ServiceMonitor и dashboard из эталона. Порт Service назови `http`, проверь selectors.
4. Добавь `preStop` и генератор трафика с твоими признаками через Ingress.
5. В Grafana покажи RPS, p50/p95, ответы модели и версию по Pod.

Готово, когда есть скрин работающего дашборда под трафиком.

### 13–14 октября: Airflow и полный CI/CD

1. Создай `dags/credit_retrain.py`: `validate → train → promoted → rollout`.
2. validate и train запускаются в отдельных Pods из образа сервиса. Перед каждой задачей — свой `dvc pull -r cluster`.
3. Образ бери из Variable `credit_image`, ключи S3 — из Secret. Расписание: CronTriggerTimetable без start_date.
4. Результат train запиши в `/airflow/xcom/return.json`: stdout не заменяет XCom. Передавай `--c`, потому что текущий train читает argparse, а не env C.
5. promoted использует настоящий результат гейта, rollout перезапускает `credit-score`.
6. CI должен публиковать DAG, обновлять `credit_image`, применять мониторинг и проверять метрику версии модели в smoke. Сохрани проверки ответа и строки PostgreSQL.
7. Удали устаревшую `fix_hw2` из условий workflow; `hw3` уже включена в build/deploy.

Готово, когда полный pipeline зелёный, DAG виден без import errors и задачи действительно выполняются.

### 15 октября: три сценария

- **Улучшение:** реальный прирост качества, новый champion, rollout, переключение версии на Grafana и ноль ошибок трафика.
- **Отказ гейта:** challenger зарегистрирован, champion прежний, rollout skipped, Pods не перезапускались.
- **Плохие данные:** читаемый CSV с неверными значениями, например сменой единиц дохода; validate красный, дальше DAG не идёт, API работает старой моделью. Затем откат данных и повторная проверка.

На изменение данных: сначала `dvc add`, затем `dvc push`, только потом Git commit/push. Поломка и откат — отдельные осмысленные коммиты, как требует задание.

Сохрани графы DAG, MLflow runs, Aliases, скрины Grafana и лог трафика. Учти: текущий train сам меняет champion, поэтому поиск параметров делай в изолированном стенде или добавь режим без promotion. Равная метрика не доказывает улучшение.

### 16 октября: запуск с нуля и отчёт

1. Напиши Quickstart от clone до ответа через Ingress, без догадок и ручного исправления YAML.
2. Подготовь независимую резервную копию CSV и нужных MLflow-артефактов. Удаление kind уничтожит S3 и MLflow внутри него; один указатель DVC данные не восстановит.
3. После подготовки проверь свежий clone и чистый кластер, замерь время.
4. В REPORT.md добавь схему, таблицу хранения версий, доказательства по каждому пункту, журнал проблем, переделки и восемь ответов из задания.

### 17–18 октября: исправления и сдача

Проверь CI, доказательства и PR из `hw3` в `master`. До дедлайна результат должен быть в основной ветке. Имя `main` в формулировке задания уточни у преподавателя; автоматически ветки не переименовывай.

Звёздочки делай только после базы. ДЗ 5 по GPU для допуска к мок-собеседованию не требуется.
