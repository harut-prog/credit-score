# ДЗ 3: конкретная инструкция для текущего credit-score

Первоначальная инструкция составлена 30.09.2026 после сравнения с шаблоном ML_PRO2026. Дедлайн PDF: 04.10, 23:59. Работайте из `C:\PostupashkiProject` в PowerShell 7. Большая часть блоков ниже уже реализована к 01.10; **не выполняйте их повторно без проверки текущего состояния**, иначе создадите лишние версии Registry или перезапишете V2 данных. Фактические результаты и оставшиеся задачи указаны в [REPORT.md](REPORT.md), раздел H3.

### Актуальный статус на 01.10.2026

- MLflow/Traefik/PostgreSQL/API/metrics-server/HPA работают в `credit-service`; локальный smoke через Ingress и точную строку БД прошёл.
- Три исправленных запуска обучения зарегистрировали версии 1–3: promoted, rejected, promoted. V2 данных сохранила DVC под Git SHA `7d56f4e`, на ней создана версия модели 4, champion остался 3.
- Runner `credit-kind` зарегистрирован и запущен в контейнере `gh-runner`. Его процесс `run.sh` запущен вручную: после перезапуска Docker его нужно запустить снова (раздел 8).
- Locust 10/30/60 выполнен, HPA вырос с 2 до 6. Откат champion 3→1→3 через UI и rollout проверен.
- На очереди: публикация ветки/зелёный deploy GitHub Actions, чистый clone/DVC pull, три пары красного/зелёного deploy и скриншоты GitHub Settings/k9s.

## 0. Проверенное состояние — отсюда начинаем

Прочитаны исходники, тесты, notebook, workflow, Docker/Compose/Kubernetes/platform, README/REPORT, DVC и model metadata. Проверены содержимое joblib, Git, хеши данных, Docker, Kubernetes и Helm. `.env` и значения секретов не публиковались.

| Объект | Что уже есть |
|---|---|
| Git | Ветка `hw3`, V2 данных зафиксирована отдельным коммитом `7d56f4e` |
| Исправления ДЗ 1 | Слиты PR #4, merge fe25ca2 |
| Git status | См. свежий `git status --short` перед действиями; часть последующих правок ожидает публикации |
| CSV | V1 MD5 `cce525a1d41f234f58d3bb52f3d2516b`; текущая V2 MD5 `d7123f735b51ec6675c136a2a944aa25` |
| DVC | pointer и remote закоммичены, status up to date; объект в C:\dvc-storage существует и совпадает по MD5 |
| Перевод CSV на DVC | Завершён коммитом 3c3e434; git ls-files data/credit_score.csv теперь пуст |
| kind | credit-service уже работает, порт 127.0.0.1:80 проброшен на 30080 |
| MLflow | Pod Ready; Registry содержит версии 1–4, champion=3 |
| Airflow | Deployment уже уменьшен до 0 реплик; Service/PVC сохранены |
| Traefik/Ingress | Traefik 41.6.1 установлен, Pod Ready; Ingress MLflow работает, /health=OK, Registry={} |
| API/БД/HPA | API 2–6 реплик, PostgreSQL с PVC и HPA работают |
| Model bundle | LogisticRegression, JSON и bundle metadata совпадают, missing-income indicator внутри Pipeline |
| Тесты | Без БД: 15 passed, 3 skipped; Ruff проходит |
| Скрины | 32 файла docs/img на месте и tracked |

Локальные тесты без БД требуют перекрыть `POSTGRES_HOST=''`, потому что личный `.env` задаёт внешнюю БД. Тесты с БД следует запускать отдельно. Зависимости MLflow/skops уже зафиксированы в ветке, а PostgreSQL использует PVC. Для чарта Traefik 41.6.1 ключ типа Service — `service.spec.type`; 01.10 chart обновлён до revision 2, фактический Service теперь `NodePort` 30080 и Ingress проверен.


## Как используем предоставленный шаблон

Референс: [artemovmak/ML_PRO2026](https://github.com/artemovmak/ML_PRO2026/tree/main). Прочитаны train.py, model_store.py, app/config, CI, Dockerfile, зависимости и platform-манифесты. Это полезный ориентир, но не полный результат ДЗ 3.

| В шаблоне | У нас |
|---|---|
| src/churn/train.py; python -m churn.train | src/credit/train.py; python -m credit.train |
| src/churn/model_store.py | src/credit/model_store.py, отдельный loader без переписывания predict/batch |
| Данные Telco, модель churn | Give Me Some Credit, кредитные признаки и логрегрессия |
| ROC-AUC gate, MIN_GAIN по умолчанию 0 | Validation average precision, запас 0.001 и свои три запуска |
| Реестр по alias, metadata из run | Та же схема; одна разрешённая версия для модели и metadata |
| Deploy [self-hosted, kind] | Та же схема в существующий credit-service |
| Host header к control-plane:30080 | Тот же Ingress-маршрут credit.localhost |
| Smoke: префикс version и row count по UUID | Registry identity, вероятность, порог, точные UUID/version/score в БД |
| Prometheus/Airflow части | Для обязательного ДЗ 3 не добавляются |
| DVC/HPA отсутствуют | Добавляются по условиям вашего PDF |

Имена переменных Settings остаются вашими MODEL_NAME/MODEL_ALIAS/MLFLOW_TRACKING_URI. Переделывать их в lower-case как в чужом проекте нет необходимости. Параметры обучения в нашей инструкции задаются явными CLI-флагами, чтобы три запуска были легко воспроизводимы.

Что из шаблона дорабатываем: champion_auc ловит все MlflowException — это может скрыть сетевую/серверную ошибку под отсутствие champion; у нас допускается только RESOURCE_DOES_NOT_EXIST. Порог выбирается на test — у нас отдельная validation. Smoke не проверяет диапазон score и точность записи — у нас полноценная проверка. Не копируйте tracked __pycache__ и конкретные версии чужого sklearn в ваш проект с уже сохранённой моделью.

В шаблоне deploy включён только для workflow_dispatch. У нас по умолчанию после push в master, чтобы обязательные красные/зелёные пары запускались после merge. Если берёте звёздочку ручного deploy, добавьте workflow_dispatch в on и ограничьте deploy ручным событием, как в шаблоне; запускать его надо с default branch, иначе build с условием master будет skipped и deploy из-за needs тоже не запустится. Сохраните доказательство ожидания/ручного запуска по PDF.

**Текущая точка продолжения:** шаг 1 выполнен; Ingress и MLflow из шага 2 работают; сначала синхронизировать Service Traefik командой helm upgrade ниже, затем начать шаг 3. Реализации обучения/loader/smoke/HPA/runner ещё нет.

## 1. Git/DVC уже выполнены: проверить, без повторного git rm

```powershell
Set-Location C:\PostupashkiProject
git status --short --branch
git ls-files data/credit_score.csv
uv run dvc status
uv run dvc remote list
$dataV1Commit = '3c3e434'
New-Item -ItemType Directory -Force report/hw3,docs/img/hw3 | Out-Null
```

Ожидается пустой вывод git ls-files и up to date у DVC. Коммит 3c3e434 уже удалил CSV из индекса, сохранил его на диске и убрал игнорирование docs. Повторять git rm, dvc init и remote add не нужно. Сохраните SHA V1 в REPORT.

## 2. Платформа уже работает: исправить только тип Service Traefik

Имена во всех примерах: cluster credit-service; Deployment/Service/HPA API credit-score; namespace API default; MLflow mlops/mlflow; Registry model credit-score-logreg; адреса mlflow.localhost и credit.localhost.

```powershell
kubectl config use-context kind-credit-service
kubectl get pods,svc,ingress,pvc -A
```

Замените `platform/traefik-values.yaml` целиком:

```yaml
service:
  spec:
    type: NodePort
ports:
  web:
    nodePort: 30080
  websecure:
    expose:
      default: false
ingressClass:
  name: traefik
  isDefaultClass: true
```

```powershell
helm repo add traefik https://traefik.github.io/charts
helm repo update
$traefikVersion = '41.6.1'
helm template traefik traefik/traefik --version $traefikVersion -n traefik -f platform/traefik-values.yaml
helm upgrade --install traefik traefik/traefik --version $traefikVersion -n traefik --create-namespace -f platform/traefik-values.yaml --wait --timeout 180s
kubectl -n traefik get pods,svc
```

Service должен иметь тип NodePort и порт 80:30080. Запишите выбранную версию чарта для README. При ошибке сначала проверьте helm template с этой же версией.

`platform/ingress.yaml` уже содержит правильный маршрут MLflow. Ниже его ожидаемое содержимое для сверки; переписывать совпадающий файл не нужно:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mlflow
  namespace: mlops
spec:
  ingressClassName: traefik
  rules:
    - host: mlflow.localhost
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: mlflow
                port:
                  number: 5000
```

`k8s/ingress.yaml` уже создан и ссылается на credit-score. Проверьте, что он совпадает:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: credit-score
spec:
  ingressClassName: traefik
  rules:
    - host: credit.localhost
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: credit-score
                port:
                  number: 80
```

```powershell
kubectl apply -f platform/ingress.yaml
curl.exe --fail --resolve mlflow.localhost:80:127.0.0.1 http://mlflow.localhost/health
kubectl get pods,ingress -A
```

MLflow уже доступен: повторно проверенный /health=OK. Откройте http://mlflow.localhost в Model training и сохраните скрин. При DNS-проблеме curl --resolve проверяет Ingress независимо от разрешения имени. Для браузера настройте разрешение *.localhost, если оно не работает на вашей машине.

Текущий MLflow уже содержит allowed-hosts, cors-allowed-origins и MLFLOW_SERVER_ENABLE_JOB_EXECUTION=false. Сохраните их и PVC. **Не удаляйте kind**: вместе с ним потеряются тома. Не применяйте platform целиком: там Airflow и monitoring. Airflow уже остановлен: проверка ниже должна показать 0; повторное scale не требуется:

```powershell
kubectl -n mlops get deploy airflow -o jsonpath='{.spec.replicas}'
```

Сохранить скрин UI и вывод pods/ingress. Коммит:

```powershell
git add platform/traefik-values.yaml
git commit -m 'platform: use service.spec.type with Traefik chart 41.6.1'
```

## 3. Модуль обучения src/credit/train.py — структура как в шаблоне

Существующий notebook оставьте для ДЗ 1. Файл src/credit/train.py выполняет требование PDF о своём train.py; запуск через python -m credit.train соответствует структуре шаблона. Здесь предобработка соответствует исправленному notebook, но validation выделена отдельно: порог и гейт выбираются на validation, test используется для итоговых метрик.

```powershell
# MLflow и skops уже добавлены в ваш pyproject.toml. Добавьте matplotlib явно:
uv add matplotlib
uv sync --frozen
```

MLflow/skops нужны в production-зависимостях, потому что сервис загружает модель. Версия соответствует вашему server image. Если resolver не находит 3.16.1, сначала разберите ошибку и согласуйте доступные версии client/server; не меняйте их молча.

Создайте `src/credit/train.py`:

```python
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from mlflow.models import infer_signature
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, precision_recall_curve, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

matplotlib.use("Agg")

RENAME = {
    "RevolvingUtilizationOfUnsecuredLines": "unsecured_lines",
    "NumberOfTime30-59DaysPastDueNotWorse": "past_30_59",
    "DebtRatio": "debt_ratio",
    "MonthlyIncome": "monthly_income",
    "NumberOfOpenCreditLinesAndLoans": "credit_lines",
    "NumberOfTimes90DaysLate": "past_90",
    "NumberRealEstateLoansOrLines": "real_estate",
    "NumberOfTime60-89DaysPastDueNotWorse": "past_60_89",
    "NumberOfDependents": "dependents",
}
FEATURES = [
    "unsecured_lines", "age", "past_30_59", "debt_ratio", "monthly_income",
    "credit_lines", "past_90", "real_estate", "past_60_89", "dependents",
]
MODEL_NAME = "credit-score-logreg"


def make_pipeline(c, class_weight):
    other = [f for f in FEATURES if f not in {"monthly_income", "dependents"}]
    preprocess = ColumnTransformer([
        ("income", Pipeline([
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
        ]), ["monthly_income"]),
        ("dependents", Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]), ["dependents"]),
        ("other", StandardScaler(), other),
    ])
    return Pipeline([
        ("preprocess", preprocess),
        ("model", LogisticRegression(
            C=c, max_iter=1000,
            class_weight=None if class_weight == "none" else class_weight,
        )),
    ])


def load_splits(path, seed):
    raw = pd.read_csv(path, index_col=0).rename(columns=RENAME)
    invalid = (
        raw["past_30_59"].isin([96, 98])
        | raw["past_60_89"].isin([96, 98])
        | raw["past_90"].isin([96, 98])
        | (raw["age"] == 0)
    )
    removed = int(invalid.sum())
    clean = raw.loc[~invalid].copy()
    assert not clean[["past_30_59", "past_60_89", "past_90"]].isin([96, 98]).any().any()
    assert not clean["age"].eq(0).any()
    x, y = clean[FEATURES], clean["SeriousDlqin2yrs"]
    xt, x_test, yt, y_test = train_test_split(
        x, y, test_size=0.2, stratify=y, random_state=seed,
    )
    x_train, x_val, y_train, y_val = train_test_split(
        xt, yt, test_size=0.25, stratify=yt, random_state=seed,
    )
    evaluation = x_val.copy()
    evaluation["target"] = y_val
    evaluation_md5 = hashlib.md5(evaluation.to_csv().encode("utf-8")).hexdigest()
    print(f"raw={len(raw)} removed={removed} clean={len(clean)}")
    print(f"train={len(x_train)} val={len(x_val)} test={len(x_test)}")
    return x_train, x_val, x_test, y_train, y_val, y_test, removed, evaluation_md5


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    bypass = os.environ.get("no_proxy", os.environ.get("NO_PROXY", ""))
    bypass = ",".join(filter(None, [bypass, "localhost,127.0.0.1,mlflow.localhost"]))
    os.environ["NO_PROXY"] = os.environ["no_proxy"] = bypass
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data/credit_score.csv"))
    parser.add_argument("--c", type=float, default=1.0)
    parser.add_argument("--class-weight", choices=["none", "balanced"], default="none")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-gain", type=float, default=0.001)
    args = parser.parse_args()
    if args.c <= 0 or args.min_gain < 0:
        parser.error("c must be positive and min-gain nonnegative")
    data_md5 = hashlib.md5(args.data.read_bytes()).hexdigest()
    git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    splits = load_splits(args.data, args.seed)
    x_train, x_val, x_test, y_train, y_val, y_test, removed, evaluation_md5 = splits
    pipeline = make_pipeline(args.c, args.class_weight)
    pipeline.fit(x_train, y_train)
    val_proba = pipeline.predict_proba(x_val)[:, 1]
    test_proba = pipeline.predict_proba(x_test)[:, 1]
    val_ap = float(average_precision_score(y_val, val_proba))
    precision, recall, thresholds = precision_recall_curve(y_val, val_proba)
    eligible = thresholds[recall[:-1] >= 0.70]
    threshold = float(eligible.max()) if len(eligible) else 0.0
    metadata = {
        "model_name": MODEL_NAME, "features": FEATURES, "threshold_lr": threshold,
        "data_md5": data_md5, "git_sha": git_sha, "seed": args.seed,
        "evaluation_md5": evaluation_md5, "algorithm": "LogisticRegression",
        "parameters": {"C": args.c, "class_weight": args.class_weight},
        "removed_invalid_rows": removed,
        "n_train": len(x_train), "n_validation": len(x_val), "n_test": len(x_test),
        "metrics_validation": {"average_precision": val_ap},
        "metrics_test": {
            "average_precision": float(average_precision_score(y_test, test_proba)),
            "roc_auc": float(roc_auc_score(y_test, test_proba)),
            "recall_at_threshold": float(recall_score(y_test, test_proba >= threshold)),
        },
    }
    mlflow.set_experiment("credit-score-hw3")
    client = MlflowClient()
    try:
        champion = client.get_model_version_by_alias(MODEL_NAME, "champion")
    except MlflowException as exc:
        if exc.error_code != "RESOURCE_DOES_NOT_EXIST":
            raise
        champion = None
    champion_ap = None
    if champion is not None:
        with tempfile.TemporaryDirectory() as folder:
            path = client.download_artifacts(champion.run_id, "metadata.json", folder)
            old_meta = json.loads(Path(path).read_text(encoding="utf-8"))
        if old_meta["evaluation_md5"] != evaluation_md5:
            raise RuntimeError("Validation changed; compare on the same holdout")
        old = mlflow.sklearn.load_model(f"models:/{MODEL_NAME}/{champion.version}")
        champion_ap = float(average_precision_score(y_val, old.predict_proba(x_val)[:, 1]))

    with mlflow.start_run(run_name=f"C={args.c};weight={args.class_weight}") as run:
        mlflow.log_params({
            "C": args.c, "class_weight": args.class_weight, "seed": args.seed,
            "MIN_GAIN": args.min_gain, "data_md5": data_md5,
            "git_sha": git_sha, "evaluation_md5": evaluation_md5,
        })
        mlflow.log_metrics({
            "val_average_precision": val_ap,
            "test_average_precision": metadata["metrics_test"]["average_precision"],
            "test_roc_auc": metadata["metrics_test"]["roc_auc"], "threshold": threshold,
        })
        mlflow.log_dict(metadata, "metadata.json")
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(recall, precision)
        ax.set(xlabel="Recall", ylabel="Precision", title="Credit scoring: validation PR curve")
        mlflow.log_figure(fig, "validation_pr_curve.png")
        plt.close(fig)
        info = mlflow.sklearn.log_model(
            sk_model=pipeline, name="model", registered_model_name=MODEL_NAME,
            signature=infer_signature(x_train.head(5), pipeline.predict(x_train.head(5))),
            input_example=x_train.head(5),
            skops_trusted_types=["numpy.dtype"],
        )
        version = str(info.registered_model_version)
        if version == "None":
            raise RuntimeError("No registered_model_version returned")
        client.set_registered_model_alias(MODEL_NAME, "challenger", version)
        loaded = mlflow.sklearn.load_model(f"models:/{MODEL_NAME}/{version}")
        np.testing.assert_allclose(
            loaded.predict_proba(x_val.head(20)), pipeline.predict_proba(x_val.head(20)),
            rtol=1e-10, atol=1e-12,
        )
        promoted = champion_ap is None or val_ap >= champion_ap + args.min_gain
        if promoted:
            client.set_registered_model_alias(MODEL_NAME, "champion", version)
        mlflow.set_tag("gate_decision", "promoted" if promoted else "rejected")
        if champion_ap is not None:
            mlflow.log_metric("champion_val_average_precision", champion_ap)
        print(json.dumps({
            "run_id": run.info.run_id, "version": version, "data_md5": data_md5,
            "candidate_ap": val_ap, "champion_ap": champion_ap,
            "MIN_GAIN": args.min_gain, "promoted": bool(promoted),
        }))


if __name__ == "__main__":
    main()
```

Здесь метрика average precision соответствует вашему notebook; не путайте её с трапецеидальным интегралом PR-кривой. MIN_GAIN=0.001 — запас абсолютного прироста AP на 0.1 процентного пункта, чтобы отвергать совсем малые изменения. Это учебный запас, не статистическая гарантия; обоснуйте своими словами.

Перед запуском зафиксируйте код, чтобы git_sha был настоящей версией реализации:

```powershell
uv run ruff check src/credit/train.py --fix
uv run ruff check src/credit/train.py
git add src/credit/train.py pyproject.toml uv.lock
git commit -m 'ml: track credit training and promote models through an AP gate'
$env:MLFLOW_TRACKING_URI='http://mlflow.localhost'
```

Я проверил следующие варианты на вашем CSV и отдельной validation: AP 0.3746765 → 0.3695169 → 0.3760703. Это локальное исследование, **не готовые MLflow runs**. Сделайте реальные три запуска:

```powershell
uv run python -m credit.train --c 0.00001 --class-weight none --min-gain 0.001 2>&1 | Tee-Object report/hw3/train1.txt
if ($LASTEXITCODE -ne 0) { throw 'train1 failed' }
uv run python -m credit.train --c 1 --class-weight none --min-gain 0.001 2>&1 | Tee-Object report/hw3/train2.txt
if ($LASTEXITCODE -ne 0) { throw 'train2 failed' }
uv run python -m credit.train --c 1 --class-weight balanced --min-gain 0.001 2>&1 | Tee-Object report/hw3/train3.txt
if ($LASTEXITCODE -ne 0) { throw 'train3 failed' }
```

**Уже проверено 30.09.2026 после исправления ошибок:** все три повторных запуска завершились с exit code 0. Их логи — report/hw3/train1-fixed.txt, train2-fixed.txt и train3-fixed.txt. Версия 1: AP=0.3746765251, promoted=true; версия 2: AP=0.3695169145, promoted=false; версия 3: AP=0.3760703211, promoted=true. Текущий champion в Registry — 3. Повторять эти команды сейчас ради создания ещё трёх версий не требуется; сохраните скрин Aliases и переходите к проверке loader. Старые train1.txt/train2.txt/train3.txt оставлены как доказательство найденной поломки. Правки train.py ещё нужно закоммитить.

При пустом Registry первый станет champion; второй ухудшится и останется только challenger; третий улучшает первый примерно на 0.001394, проходя запас 0.001. Сверяйте фактические результаты, не подделывайте метрики. Если champion уже существует, первый запуск не является стартом пустого реестра — учитывайте историю.

MLflow 3.16 сохраняет sklearn через skops. Проверенные на вашей машине логи показали, что Pipeline также требует явно доверить numpy.dtype; поэтому в log_model выше добавлен skops_trusted_types=["numpy.dtype"]. Не доверяйте всем найденным типам автоматически. Сервис должен загрузить sklearn flavor и вызвать predict_proba; pyfunc.predict по умолчанию выдаёт класс, а не вероятность.

### Как читать ошибки первых трёх запусков

Исходные report/hw3/train1.txt, train2.txt и train3.txt упали до регистрации: UntrustedTypesFoundException для numpy.dtype. Затем при завершении MLflow попытался напечатать Unicode-эмодзи в cp1251 и получил UnicodeEncodeError. В main выше теперь включён UTF-8 stdout/stderr. Старые логи сохраняйте для журнала проблем, повторные сохраняйте под новыми именами, например train1-fixed.txt.

При повторной проверке также обнаружен системный Windows proxy: requests.get к mlflow.localhost возвращал 503, а прямой запрос без proxy — 200 OK. Код выше добавляет локальные адреса в NO_PROXY/no_proxy, сохраняя существующий список. При запуске других локальных MLflow-команд задайте обе переменные в терминале: $env:NO_PROXY='localhost,127.0.0.1,mlflow.localhost'; $env:no_proxy=$env:NO_PROXY. Ошибка 503 или долгие retries при рабочем браузере требуют проверить proxy, а не удалять кластер.

Предупреждение Inferred schema contains integer column(s) и INFO о создании experiment сами по себе не означают провал. PowerShell может оформлять stderr как NativeCommandError даже для INFO. Критерий успеха — exit code 0, итоговый JSON и статус FINISHED в MLflow. Отказ гейта — нормальный успешный run с promoted=false и challenger; traceback и FAILED — поломка выполнения, такой run не заменяет демонстрацию гейта. В наших endpoints необязательные доход/dependents должны по-прежнему поддерживать пропуски; sklearn-loader используется напрямую, но при переходе на pyfunc отдельно проверьте входную signature.

Предъявить: логи 3 решений, Registry с aliases, свой артефакт PR-кривой. Последний challenger и champion могут указывать на одну третью версию: отказ второй виден в истории run.

## 4. Полный loader модели и точные изменения app.py

В `src/credit/config.py` после MODEL_PATH добавьте:

```python
    MODEL_NAME: str | None = None
    MODEL_ALIAS: str = "champion"
    MLFLOW_TRACKING_URI: str = "http://mlflow.localhost"
```

Остальные Settings сохраните. Создайте `src/credit/model_store.py`:

```python
import json
import logging
import math
import tempfile
from pathlib import Path

import joblib
import mlflow
import mlflow.sklearn
from mlflow import MlflowClient

from credit.config import settings
from credit.service.models import Features

logger = logging.getLogger(__name__)


def validate_metadata(pipeline, metadata):
    if not callable(getattr(pipeline, "predict_proba", None)):
        raise ValueError("Model must support predict_proba")
    features = metadata.get("features")
    if not isinstance(features, list) or len(features) != len(set(features)):
        raise ValueError("Invalid feature list")
    if set(features) != set(Features.model_fields):
        raise ValueError("Model features differ from API schema")
    threshold = metadata.get("threshold_lr")
    if not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Invalid threshold_lr")


def load_bundle():
    if not settings.MODEL_NAME:
        bundle = joblib.load(settings.MODEL_PATH)
        validate_metadata(bundle["pipeline"], bundle["metadata"])
        return bundle["pipeline"], bundle["metadata"], {
            "model_source": "file", "model_name": bundle["metadata"].get("model_name"),
            "model_alias": None, "model_version": str(bundle["metadata"]["model_version"]),
            "run_id": None,
        }
    mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
    client = MlflowClient()
    # Resolve once so model and metadata belong to the same version.
    version = client.get_model_version_by_alias(settings.MODEL_NAME, settings.MODEL_ALIAS)
    pipeline = mlflow.sklearn.load_model(f"models:/{settings.MODEL_NAME}/{version.version}")
    with tempfile.TemporaryDirectory() as folder:
        path = client.download_artifacts(version.run_id, "metadata.json", folder)
        metadata = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_metadata(pipeline, metadata)
    logger.info("Loaded registry model %s version %s alias %s", settings.MODEL_NAME, version.version, settings.MODEL_ALIAS)
    return pipeline, metadata, {
        "model_source": "registry", "model_name": settings.MODEL_NAME,
        "model_alias": settings.MODEL_ALIAS, "model_version": str(version.version),
        "run_id": version.run_id,
    }
```

В `app.py` удалите import joblib, добавьте `from credit.model_store import load_bundle`. Замените lifespan и health. Остальные endpoints, обработку ошибок и БД сохраните:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    pipeline, metadata, identity = load_bundle()
    app.state.pipeline = pipeline
    app.state.metadata = metadata
    app.state.model_identity = identity
    app.state.model_version = identity["model_version"]
    app.state.db_enabled = bool(settings.database_url)
    if app.state.db_enabled:
        db.init()
    yield
    app.state.pipeline = None
```

`app = FastAPI(...)` остаётся после определения lifespan и до декораторов маршрутов. Новый health:

```python
@app.get("/health")
def health():
    return {
        "state": "ok", **app.state.model_identity,
        "threshold": app.state.metadata["threshold_lr"], "log_level": settings.LOG_LEVEL,
    }
```

Существующий /ready уже проверяет модель и метаданные. Сохраните отрицательный test_ready_requires_model и readinessProbe на /ready. При MODEL_NAME и ошибке Registry startup должен падать с понятной причиной, без скрытого fallback. Fallback нужен **только при отсутствии MODEL_NAME**.

Проверка в отдельном терминале без внешней БД:

```powershell
$env:MODEL_NAME=''
$env:POSTGRES_HOST=''
uv run ruff check src tests --fix
uv run ruff check .
uv run pytest
```

Не удаляйте тесты 96/98, 422/500 и batch. Для новой границы Registry добавьте `tests/test_model_store.py` с двумя конкретными проверками:

```python
import json
from pathlib import Path
from types import SimpleNamespace

import joblib
import pytest
from mlflow.exceptions import MlflowException

from credit import model_store


def test_registry_model_and_metadata_use_same_version(monkeypatch):
    bundle = joblib.load("artifacts/baseline_logreg.joblib")
    calls = []

    class FakeClient:
        def get_model_version_by_alias(self, name, alias):
            assert (name, alias) == ("credit-score-logreg", "champion")
            return SimpleNamespace(version="7", run_id="run-7")

        def download_artifacts(self, run_id, artifact, folder):
            assert (run_id, artifact) == ("run-7", "metadata.json")
            path = Path(folder) / artifact
            path.write_text(json.dumps(bundle["metadata"]), encoding="utf-8")
            return str(path)

    def fake_load(uri):
        calls.append(uri)
        return bundle["pipeline"]

    monkeypatch.setattr(model_store.settings, "MODEL_NAME", "credit-score-logreg")
    monkeypatch.setattr(model_store.settings, "MODEL_ALIAS", "champion")
    monkeypatch.setattr(model_store, "MlflowClient", FakeClient)
    monkeypatch.setattr(model_store.mlflow, "set_tracking_uri", lambda _: None)
    monkeypatch.setattr(model_store.mlflow.sklearn, "load_model", fake_load)
    pipeline, metadata, identity = model_store.load_bundle()
    assert pipeline is bundle["pipeline"]
    assert metadata == bundle["metadata"]
    assert calls == ["models:/credit-score-logreg/7"]
    assert identity["model_version"] == "7"
    assert identity["run_id"] == "run-7"
    assert identity["model_source"] == "registry"


def test_missing_alias_fails_without_file_fallback(monkeypatch):
    class FakeClient:
        def get_model_version_by_alias(self, _name, _alias):
            raise MlflowException("Alias missing", error_code="RESOURCE_DOES_NOT_EXIST")

    def forbidden_fallback(_path):
        raise AssertionError("File fallback must not hide a Registry failure")

    monkeypatch.setattr(model_store.settings, "MODEL_NAME", "credit-score-logreg")
    monkeypatch.setattr(model_store, "MlflowClient", FakeClient)
    monkeypatch.setattr(model_store.mlflow, "set_tracking_uri", lambda _: None)
    monkeypatch.setattr(model_store.joblib, "load", forbidden_fallback)
    with pytest.raises(MlflowException, match="Alias missing"):
        model_store.load_bundle()
```

Запустите `uv run pytest tests/test_model_store.py`, затем всю проверку. После добавления этих двух тестов ожидаемое число обычных проверок возрастает с 13 до 15. Это тесты без сетевого MLflow; реальный Registry проверяется следующим deploy.

## 5. Полные манифесты БД и первый ручной deploy

Замените `k8s/configmap.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: credit-config
data:
  LOG_LEVEL: "INFO"
  MODEL_PATH: artifacts/baseline_logreg.joblib
  MODEL_NAME: credit-score-logreg
  MODEL_ALIAS: champion
  MLFLOW_TRACKING_URI: http://mlflow.mlops.svc.cluster.local:5000
  POSTGRES_HOST: postgres
  POSTGRES_PORT: "5432"
  POSTGRES_USER: postgres
  POSTGRES_DB: credit
```

Для постоянного kind БД нужен том: текущий postgres.yaml его не имеет. Замените `k8s/postgres.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: credit-postgres-data
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 1Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
        - name: postgres
          image: postgres:17-alpine
          ports:
            - containerPort: 5432
          env:
            - name: POSTGRES_USER
              value: postgres
            - name: POSTGRES_DB
              value: credit
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: credit-secrets
                  key: POSTGRES_PASSWORD
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
          readinessProbe:
            exec:
              command: [pg_isready, -U, postgres, -d, credit]
            periodSeconds: 3
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              memory: 256Mi
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: credit-postgres-data
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
spec:
  selector:
    app: postgres
  ports:
    - port: 5432
      targetPort: 5432
```

API Service/deployment уже правильные по selector/ports/probes. Dockerfile уже копирует src и artifacts, не CSV; новые production-зависимости попадут через uv.lock. Модуль credit.train входит вместе с src, но автоматически не запускается при старте serving image.

Выберите пароль, **такое же значение** задайте в GitHub Secret DB_PASSWORD. В терминале ввод без печати:

```powershell
$securePassword = Read-Host 'Пароль PostgreSQL (тот же DB_PASSWORD в GitHub)' -AsSecureString
$dbPassword = [System.Net.NetworkCredential]::new('', $securePassword).Password
kubectl create secret generic credit-secrets --from-literal="POSTGRES_PASSWORD=$dbPassword" --dry-run=client -o yaml | kubectl apply -f -
Remove-Variable dbPassword,securePassword
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/postgres.yaml
kubectl rollout status deploy/postgres --timeout=180s
docker build -t credit-score:hw3 .
kind load docker-image credit-score:hw3 --name credit-service
kubectl set image --local -f k8s/deployment.yaml api=credit-score:hw3 -o yaml | kubectl apply -f -
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
kubectl rollout status deploy/credit-score --timeout=180s
curl.exe --fail --resolve credit.localhost:80:127.0.0.1 http://credit.localhost/health
curl.exe --fail --resolve credit.localhost:80:127.0.0.1 http://credit.localhost/ready
```

Image подставлен до apply: нет ненужной попытки загрузить credit-score:1.0. В health ожидаются registry и числовая версия третьего run. Champion должен существовать **до старта API**.

POST и проверка точного UUID:

```powershell
$payload = @{unsecured_lines=0.3; age=35; past_30_59=0; past_90=0; past_60_89=0; debt_ratio=0.5; monthly_income=5000; credit_lines=5; real_estate=1; dependents=2} | ConvertTo-Json
$prediction = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1/v1/predict' -Headers @{Host='credit.localhost'} -ContentType 'application/json' -Body $payload
$prediction
$requestId=$prediction.request_id
kubectl exec deploy/postgres -- psql -U postgres -d credit -c "SELECT request_id,score,model_version,status_code FROM predictions WHERE request_id='$requestId';"
kubectl exec deploy/postgres -- psql -U postgres -d credit -c '\d predictions'
```

score должен быть double precision и допускать NULL. CREATE TABLE IF NOT EXISTS не мигрирует старую таблицу: если найдёте старый numeric/NOT NULL, выполните отдельную миграцию:

```sql
ALTER TABLE predictions ALTER COLUMN score DROP NOT NULL;
ALTER TABLE predictions ALTER COLUMN score TYPE double precision USING score::double precision;
```

Смена Secret не меняет пароль в уже инициализированной БД: согласуйте пароль роли и Secret. Не удаляйте PVC для смены пароля.

Интеграционные тесты: терминал 1 держит `kubectl port-forward svc/postgres 55432:5432`. Терминал 2:

```powershell
$env:MODEL_NAME=''
$env:POSTGRES_HOST='127.0.0.1'
$env:POSTGRES_PORT='55432'
$env:POSTGRES_USER='postgres'
$env:POSTGRES_DB='credit'
$securePassword=Read-Host 'Пароль PostgreSQL' -AsSecureString
$env:POSTGRES_PASSWORD=[System.Net.NetworkCredential]::new('', $securePassword).Password
Remove-Variable securePassword
uv run pytest -m integrations
Remove-Item Env:POSTGRES_PASSWORD
```

Ожидаются 3 passed без skip: записи 200/422/500. Это тестовый fallback; Registry отдельно проверен запросом к реальному API. В test_prediction_is_logged добавьте сравнение сохранённого score с response.json()['score'] через pytest.approx с малым допуском: один диапазон [0,1] не ловит округление.

## 6. HPA и три замера

Создайте `platform/metrics-server-values.yaml`:

```yaml
args:
  - --kubelet-insecure-tls
```

```powershell
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/
helm repo update
helm upgrade --install metrics-server metrics-server/metrics-server --version 3.14.0 -n kube-system -f platform/metrics-server-values.yaml --wait
kubectl top nodes
kubectl top pods
```

Создайте `k8s/hpa.yaml`:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: credit-score
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: credit-score
  minReplicas: 2
  maxReplicas: 6
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 60
```

```powershell
kubectl apply -f k8s/hpa.yaml
kubectl get hpa -w
```

В другом терминале последовательно, с ожиданием спада до 2 Pods между прогонами:

```powershell
uv run locust -f locustfile.py --headless -u 10 -r 5 -t 4m --host http://credit.localhost --csv report/hw3/hpa10
uv run locust -f locustfile.py --headless -u 30 -r 10 -t 4m --host http://credit.localhost --csv report/hw3/hpa30
uv run locust -f locustfile.py --headless -u 60 -r 20 -t 4m --host http://credit.localhost --csv report/hw3/hpa60
```

Во время: kubectl top pods, k9s → :hpa. После: kubectl describe hpa credit-score. Сохранить **рост и спад**, SuccessfulRescale и CSV. Downscale обычно ждёт около 5 минут. Если 60 users недостаточно, сохраните результат и увеличьте нагрузку осмысленно; не копируйте чужие секунды/реплики.

Таблица: users, длительность, устойчивые/максимальные реплики, p95 именно POST /v1/predict, CPU на Pod, memory, ошибки. Снимайте CPU несколько раз и укажите момент. В прежнем REPORT 390 мс у run50 относится к /health, а p95 predict=630 мс: не смешивайте строки endpoints и Aggregated.

requests CPU уже 250m; без CPU requests HPA не вычисляет проценты. memory request сейчас 512Mi/limit 1Gi: измерьте память и добавьте около трети запаса; запишите request до/после. Не берите 136Mi из PDF за ваш результат. Узел должен вмещать 6 API Pods, платформу, БД и дополнительный Pod rollout.

Формула: desired=ceil(currentReplicas × currentCPUUtilization / 60), затем границы 2..6. Например, 2 Pods ×150%/60 →5. При request 250m загрузка 150% означает 375m CPU на Pod. Фактическое решение учитывает также неготовые Pods, неполные метрики и стабилизацию.

replicas:2 в вашем Deployment можно оставить неизменным по PDF. Не меняйте это поле во время HPA. Огромный request приводит к Pending; request больше limit отклоняется API ещё при apply.

## 7. Полный smoke через Ingress и точную строку БД

Создайте `scripts/smoke_hw3.py`. Только stdlib — runner не ставит зависимости приложения:

```python
import json
import math
import os
import subprocess
import time
import urllib.request
import uuid

BASE = os.environ.get("INGRESS_URL", "http://127.0.0.1").rstrip("/")
HOST = os.environ.get("INGRESS_HOST", "credit.localhost")
PAYLOAD = {
    "unsecured_lines": 0.3, "age": 35, "past_30_59": 0, "past_90": 0,
    "past_60_89": 0, "debt_ratio": 0.5, "monthly_income": 5000,
    "credit_lines": 5, "real_estate": 1, "dependents": 2,
}


def request(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE + path, data=data,
        headers={"Host": HOST, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def main():
    health = request("/health")
    assert health["state"] == "ok", health
    assert health["model_source"] == "registry", health
    assert health["model_name"] == "credit-score-logreg", health
    assert str(health["model_version"]).isdigit(), health
    assert request("/ready")["state"] == "ready"
    result = request("/v1/predict", PAYLOAD)
    request_id = str(uuid.UUID(result["request_id"]))
    assert result["status_code"] == 200, result
    assert 0 <= result["score"] <= 1, result
    assert result["model_version"] == health["model_version"], result
    assert result["arrear"] == (result["score"] >= health["threshold"]), result
    query = (
        "SELECT json_build_object('request_id',request_id,'score',score,"
        "'model_version',model_version,'status_code',status_code) "
        f"FROM predictions WHERE request_id='{request_id}';"
    )
    row = None
    for _ in range(30):
        text = subprocess.check_output([
            "kubectl", "exec", "deploy/postgres", "--", "psql",
            "-U", "postgres", "-d", "credit", "-tAc", query,
        ], text=True).strip()
        if text:
            lines = text.splitlines()
            assert len(lines) == 1, text
            row = json.loads(lines[0])
            break
        time.sleep(0.5)
    assert row is not None, f"No DB row for request_id={request_id}"
    assert row["request_id"] == request_id, row
    assert row["status_code"] == 200, row
    assert row["model_version"] == result["model_version"], row
    assert math.isclose(row["score"], result["score"], rel_tol=1e-10, abs_tol=1e-12), row
    print(json.dumps({"health": health, "prediction": result, "db_row": row}, indent=2))


if __name__ == "__main__":
    main()
```

UUID валидируется до SQL; Primary Key обеспечивает уникальность. Фоновая запись выполняется после ответа, поэтому ограниченный polling обязателен. Общий count(*)=1 в старом workflow для постоянной БД неверен.

```powershell
$env:INGRESS_URL='http://127.0.0.1'
$env:INGRESS_HOST='credit.localhost'
uv run python scripts/smoke_hw3.py
```

## 8. Docker runner: файлы и команды целиком

Runner сейчас отсутствует. GitHub Settings → Actions → General → Require approval for all external contributors. Затем Actions → Runners → New self-hosted runner → Linux x64. Добавляем метку kind; deploy ниже не идёт из PR.

Создайте папку runner, затем `runner/Dockerfile`:

```dockerfile
ARG RUNNER_BASE
FROM ${RUNNER_BASE}
USER root
ARG KIND_VERSION
ARG KUBECTL_VERSION
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL "https://kind.sigs.k8s.io/dl/${KIND_VERSION}/kind-linux-amd64" -o /usr/local/bin/kind \
    && chmod +x /usr/local/bin/kind
RUN curl -fsSL "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" -o /usr/local/bin/kubectl \
    && chmod +x /usr/local/bin/kubectl
USER runner
WORKDIR /home/runner
CMD ["sleep", "infinity"]
```

Официальный base уже содержит runner, пользователя, Docker CLI, git, curl. Добавляем Python/kind/kubectl. Берём версии host CLI и фиксируем digest base:

```powershell
docker pull ghcr.io/actions/actions-runner:latest
$runnerBase=docker image inspect ghcr.io/actions/actions-runner:latest --format '{{index .RepoDigests 0}}'
$kindVersion=((kind version) -split ' ')[1]
$kubectlVersion=(kubectl version --client -o json | ConvertFrom-Json).clientVersion.gitVersion
docker build -f runner/Dockerfile --build-arg "RUNNER_BASE=$runnerBase" --build-arg "KIND_VERSION=$kindVersion" --build-arg "KUBECTL_VERSION=$kubectlVersion" -t credit-runner:hw3 runner
docker run -d --name gh-runner --network kind --group-add 0 -v /var/run/docker.sock:/var/run/docker.sock credit-runner:hw3
docker exec gh-runner docker version
docker exec gh-runner kind get clusters
docker exec gh-runner bash -lc 'kind export kubeconfig --name credit-service --internal && kubectl get nodes'
docker exec gh-runner curl --fail -H 'Host: mlflow.localhost' http://credit-service-control-plane:30080/health
```

Это пример x64. На другой архитектуре адаптируйте URL binaries. Запишите digest/версии в README. localhost внутри runner — сам контейнер: нужен внутренний kubeconfig и адрес control-plane:30080. HTTP по этому адресу с Host идёт через Traefik, а не напрямую в API.

Временный registration token берётся из GitHub UI, не PAT в файле. Ввод:

```powershell
$secureToken=Read-Host 'Registration token GitHub runner' -AsSecureString
$runnerToken=[System.Net.NetworkCredential]::new('', $secureToken).Password
docker exec -e "RUNNER_TOKEN=$runnerToken" gh-runner bash -lc './config.sh --unattended --url https://github.com/harut-prog/credit-score --token "$RUNNER_TOKEN" --name credit-kind --labels kind --work _work'
Remove-Variable runnerToken,secureToken
docker exec -d gh-runner bash -lc './run.sh > /home/runner/runner.log 2>&1'
docker exec gh-runner tail -n 20 /home/runner/runner.log
```

В Settings ожидается Idle, метки self-hosted/Linux/X64/kind. Docker permissions → group-add; кластер не найден → network/имя; token → срок действия. Регистрация сохраняется в контейнере до его удаления; после docker restart нужно вновь запустить run.sh. После docker rm потребуется новая регистрация. В Git Bash сокет иногда переписывается: MSYS_NO_PATHCONV=1 перед docker run; команды выше рассчитаны на PowerShell.

## 9. Полная замена job deploy в ci.yml

Сохраните существующие tests/build: они уже выполняют нужные проверки и публикуют SHA-image. В tests env добавьте MODEL_NAME: "" для fallback. Основная ветка текущего workflow master; PDF называет main. Используйте фактическую default branch, а расхождение поясните, если не переименовываете.

Замените **весь старый job deploy** в `.github/workflows/ci.yml`:

```yaml
  deploy:
    needs: build
    if: github.ref == 'refs/heads/master'
    runs-on: [self-hosted, kind]
    timeout-minutes: 15
    concurrency:
      group: credit-kind-deploy
      cancel-in-progress: false
    permissions:
      contents: read
      packages: read
    env:
      KIND_CLUSTER: credit-service
      INGRESS_HOST: credit.localhost
    steps:
      - uses: actions/checkout@v7.0.1
      - name: Select existing kind cluster
        shell: bash
        run: |
          set -euo pipefail
          echo "Runner name: $RUNNER_NAME"
          export KUBECONFIG="$RUNNER_TEMP/hw3-kubeconfig"
          rm -f "$KUBECONFIG"
          kind export kubeconfig --name "$KIND_CLUSTER" --internal
          kubectl get nodes
          echo "KUBECONFIG=$KUBECONFIG" >> "$GITHUB_ENV"
          echo "IMAGE=ghcr.io/${GITHUB_REPOSITORY_OWNER,,}/credit-service:sha-$GITHUB_SHA" >> "$GITHUB_ENV"
          echo "INGRESS_URL=http://${KIND_CLUSTER}-control-plane:30080" >> "$GITHUB_ENV"
      - uses: docker/login-action@v4.6.0
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Load built image
        shell: bash
        run: |
          set -euo pipefail
          docker pull "$IMAGE"
          kind load docker-image "$IMAGE" --name "$KIND_CLUSTER"
      - name: Apply database Secret
        shell: bash
        env:
          DB_PASSWORD: ${{ secrets.DB_PASSWORD }}
        run: |
          set -euo pipefail
          test -n "$DB_PASSWORD"
          kubectl create secret generic credit-secrets \
            --from-literal=POSTGRES_PASSWORD="$DB_PASSWORD" \
            --dry-run=client -o yaml | kubectl apply -f -
      - name: Apply database and configuration
        shell: bash
        run: |
          set -euo pipefail
          kubectl apply -f k8s/configmap.yaml
          kubectl apply -f k8s/postgres.yaml
          kubectl rollout status deploy/postgres --timeout=180s
      - name: Deploy API and autoscaler
        shell: bash
        run: |
          set -euo pipefail
          kubectl set image --local -f k8s/deployment.yaml api="$IMAGE" -o yaml | kubectl apply -f -
          kubectl apply -f k8s/service.yaml
          kubectl apply -f k8s/ingress.yaml
          kubectl apply -f k8s/hpa.yaml
          kubectl rollout restart deploy/credit-score
          kubectl rollout status deploy/credit-score --timeout=180s
      - name: Smoke through Ingress and exact DB request
        shell: bash
        run: |
          set -euo pipefail
          python3 scripts/smoke_hw3.py
      - name: Diagnostics
        if: failure()
        shell: bash
        run: |
          kind get clusters || true
          kubectl get pods,svc,ingress,hpa -A || true
          kubectl get events --sort-by=.lastTimestamp || true
          kubectl describe pods -l app=credit || true
          kubectl describe hpa credit-score || true
          kubectl logs deploy/credit-score --all-pods=true --prefix --tail=80 || true
          kubectl logs deploy/credit-score --previous --tail=80 || true
          kubectl logs deploy/postgres --tail=80 || true
```

Удалена helm/kind-action: новый кластер в CI не создаётся. ConfigMap сам не перезапускает Pods, поэтому restart обеспечивает применение alias и его поломки. Concurrency не позволяет двум deploy одновременно менять среду. Smoke проверяет exact request, а не общий count.

Перед PR все упомянутые файлы должны существовать. Коммит:

```powershell
uv run ruff check . --fix
uv run ruff check .
$env:MODEL_NAME=''
$env:POSTGRES_HOST=''
uv run pytest
git diff --check
git add src/credit/config.py src/credit/model_store.py src/credit/service/app.py k8s/configmap.yaml k8s/postgres.yaml k8s/hpa.yaml platform/metrics-server-values.yaml scripts/smoke_hw3.py runner/Dockerfile .github/workflows/ci.yml
git diff --cached --stat
git commit -m 'deploy: serve Registry champion in persistent kind via local runner'
git push -u origin hw3
```

Создайте PR hw3 → master, дождитесь tests, merge. Один push hw3 **не запускает deploy**: текущий on push ограничен master. После merge ожидается tests/build/deploy. Предъявить URL green run, Runner name: credit-kind и скрин Settings/Runners.

## 10. Откат модели по champion без нового образа

```powershell
curl.exe --fail --resolve credit.localhost:80:127.0.0.1 http://credit.localhost/health
kubectl get deploy credit-score -o jsonpath='{.spec.template.spec.containers[0].image}'
```

В UI перенесите champion с третьей версии на первую. Засеките время от сохранения в UI до ответа старой версии. Следующий таймер измеряет только часть после запуска команды, поэтому добавьте задержку от клика либо измерьте весь интервал отдельно:

```powershell
$timer=[System.Diagnostics.Stopwatch]::StartNew()
kubectl rollout restart deploy/credit-score
kubectl rollout status deploy/credit-score --timeout=180s
curl.exe --fail --resolve credit.localhost:80:127.0.0.1 http://credit.localhost/health
$timer.Stop()
$timer.Elapsed.TotalSeconds
```

Health показывает старую Registry version, image тот же. Во время rollout ответы разных Pods могут смешиваться: финальная проверка после rollout status. Сохранить до/после и время, затем вернуть champion на лучшую версию и повторить restart.

## 11. Конкретная V2 данных и проверка чистого clone

Осмысленная V2: убрать 270 невалидных строк из raw CSV. Пропуски дохода/dependents сохраняем: их поддерживает Pipeline. До этого они фильтровались в train, поэтому допустимые строки и validation сохранятся; разные raw data_md5 всё равно покажут две версии данных.

Чтобы не потерять точность floats при CSV read/write, используйте фильтрацию исходных строк по ID. Создайте `scripts/make_data_v2.py`:

```python
import csv
import hashlib
from pathlib import Path

path = Path("data/credit_score.csv")
original = path.read_bytes()
text = original.decode("utf-8-sig")
lines = text.splitlines(keepends=True)
reader = csv.DictReader(lines)
keep = [lines[0]]
removed = 0
total = 0
for line, row in zip(lines[1:], reader, strict=True):
    total += 1
    invalid = (
        row["NumberOfTime30-59DaysPastDueNotWorse"] in {"96", "98"}
        or row["NumberOfTime60-89DaysPastDueNotWorse"] in {"96", "98"}
        or row["NumberOfTimes90DaysLate"] in {"96", "98"}
        or float(row["age"]) == 0
    )
    if invalid:
        removed += 1
    else:
        keep.append(line)
if not removed:
    raise SystemExit("No invalid rows; transformation already applied")
result = "".join(keep).encode("utf-8")
path.write_bytes(result)
print({
    "before_rows": total, "removed": removed, "after_rows": total - removed,
    "before_md5": hashlib.md5(original).hexdigest(),
    "after_md5": hashlib.md5(result).hexdigest(),
})
```

Этот пример рассчитан на ваш числовой CSV без многострочных полей, сохраняет исходные записи и переводы строк. Перед перезаписью V1 pointer закоммичен, DVC status чист, данные в cache/remote.

```powershell
uv run dvc status
uv run python scripts/make_data_v2.py 2>&1 | Tee-Object report/hw3/data-v2.txt
uv run dvc add data/credit_score.csv
git add scripts/make_data_v2.py data/credit_score.csv.dvc
git commit -m 'data v2: remove 270 invalid borrower records'
$dataV2Commit=git rev-parse HEAD
uv run dvc push 2>&1 | Tee-Object report/hw3/dvc-push-v2.txt
uv run dvc diff $dataV1Commit $dataV2Commit
$env:MLFLOW_TRACKING_URI='http://mlflow.localhost'
uv run python -m credit.train --c 1 --class-weight balanced --min-gain 0.001 2>&1 | Tee-Object report/hw3/train-data-v2.txt
```

V2 run не обязан повысить champion: данные после training-cleaning одинаковые. Требуется новый data_md5 в MLflow. Если evaluation_md5 всё же изменился, не отключайте защиту гейта: найдите изменение значений/порядка/split.

Откат с конкретными SHA; не HEAD~1, который может быть другим этапом:

```powershell
git restore --source=$dataV1Commit --worktree -- data/credit_score.csv.dvc
uv run dvc checkout
Get-FileHash data/credit_score.csv -Algorithm MD5
git restore --source=$dataV2Commit --worktree -- data/credit_score.csv.dvc
uv run dvc checkout
Get-FileHash data/credit_score.csv -Algorithm MD5
git status --short
```

После демонстрации вернуть V2. Запишите оба SHA в REPORT: переменные исчезнут после закрытия PowerShell.

Опубликуйте V2 через ветку/PR, затем **новый** соседний клон:

```powershell
Set-Location C:\
git clone https://github.com/harut-prog/credit-score.git credit-score-clean-hw3
Set-Location C:\credit-score-clean-hw3
uv sync --frozen
uv run dvc pull
Get-FileHash data/credit_score.csv -Algorithm MD5
```

Если V2 ещё не слита, выберите опубликованную ветку с V2. Соседний клон найдёт тот же C:\dvc-storage. На другой машине local remote недоступен — README должен объяснить, как получить storage. При другом размещении клона:

```powershell
uv run dvc remote modify --local local url 'C:/dvc-storage'
uv run dvc pull
Set-Location C:\PostupashkiProject
```

Предъявить pointer, push/diff/pull и два MLflow runs с разными data_md5. Для восстановления данных модели N: Registry version → run_id → data_md5/git_sha → Git checkout → dvc pull/checkout → проверка MD5. В train git_sha берётся после коммита pointer, поэтому указывает на нужные данные.

## 12. Три обязательных красных deploy

Только после зелёного полного пути. PDF требует отдельный коммит поломки в основной ветке и починку следующим. Сохраните PR-историю: PR с поломкой → merge → red; PR с починкой → merge → green. Не squash обе версии в один коммит до запуска.

| Поломка | Что поменять | Ожидаемый диагноз |
|---|---|---|
| Нет alias | ConfigMap MODEL_ALIAS: prod, убедиться что alias отсутствует | Startup Registry error, rollout timeout, возможен CrashLoopBackOff |
| Нет кластера | Job env KIND_CLUSTER: credit-service-missing | Select existing kind cluster падает на export kubeconfig |
| Ingress мимо | k8s/ingress.yaml host: wrong-credit.localhost; smoke host прежний | Pods Ready, smoke HTTP 404 от Traefik |

Следующим коммитом вернуть champion/credit-service/credit.localhost соответственно. На каждый сценарий: red URL, green URL, SHA, шаг, точный фрагмент лога, 2–3 предложения диагноза без чтения diff. Не меняйте одновременно БД/image/alias. Если первая попытка упала по иной причине, сохранить и описать её, затем добиться нужного сценария.

## 13. Отчёт, README и защита от повторения ошибок ДЗ 1

В REPORT.md сохранить H1/H2, добавить H3: таблица 7 пунктов и доказательств, собственные измерения, журнал проблем, 8 ответов. Скрины терминала, k9s и MLflow обязательны. URL должны вести на конкретные runs, а не только общую страницу Actions.

Восемь ответов по 2–4 предложения своими словами:

1. Почему tests/build в облаке, deploy локально; альтернативы для кластера за NAT.
2. Роль network kind, Docker socket, group-add 0; что без каждого.
3. Dry-run/apply Secret и повторный deploy.
4. Challenger/champion, алиас/номер; откат модели/rollout undo кода.
5. Кластер до первого обучения champion; k9s и CI-log.
6. Браузер:80 → kind:30080 → Traefik → Service MLflow:5000 → Pod:5000; allowed-hosts/CORS; port mapping при создании kind.
7. Расчёт HPA на своих CPU/replicas, сравнение, задержка спада.
8. Git/DVC и восстановление данных модели N.

Шаблон таблицы нагрузки:

```markdown
| Пользователи | Реплики | p95 predict, мс | CPU на Pod | Memory | Ошибки |
|---|---|---|---|---|---|
| 10 | ... | ... | ... | ... | ... |
| 30 | ... | ... | ... | ... | ... |
| 60 | ... | ... | ... | ... | ... |
```

README: оставить простой Compose без .env; добавить HW3-порядок DVC → платформа → обучение champion → API → runner, зависимости, имена, порты, Secret, local remote и способы восстановления. Зафиксировать Traefik version и runner digest. Проверять в новом clone, потому что ваш .env может переопределять defaults:

```powershell
uv sync --frozen
$env:MODEL_NAME=''
$env:POSTGRES_HOST=''
uv run ruff check .
uv run pytest
docker compose up -d --build
Invoke-RestMethod http://localhost:8080/ready
```

Далее predict и точная строка в БД. Полный CSV обычным тестам не нужен, модель fallback tracked. Не используйте down -v без намерения удалить данные тома.

| Замечание преподавателя ДЗ 1 | Контроль в ДЗ 3 |
|---|---|
| /ready был постоянным | Сохранить отрицательный тест и readinessProbe /ready |
| Clone не запускался без .env | Новый clone, defaults Compose, актуальный README |
| Маска очистки неверная | Скобки вокруг сравнения age, count по той же маске, 270 удалённых строк |
| Метрики CatBoost при логрегрессии | Registry, паспорт и метрики одного Pipeline; reload сравнение predict_proba |
| Индикатор пропуска вручную в API | Imputer(add_indicator=True) внутри Pipeline |
| NULL/точность score/422 | Правильная схема БД, 3 интеграционных tests и exact-score smoke |

В docs/pipeline/state.md фиксировать этап/достигнутое/следующий шаг; audit.md отделяет реально проверенное от skipped и блокеров. Проверяйте наличие каждого изображения из REPORT, новые screenshots должны быть tracked.

После сдачи: docker rm -f gh-runner, Remove runner в GitHub Settings. Не удалять MLflow/DVC/кластер до сохранения необходимых данных и доказательств.

## 14. Дополнительные задания и финальная проверка

Звёздочки после основной части: ручной deploy (workflow_dispatch или environment approval с доказательством ожидания); nested MLflow runs с регистрацией только лучшего и гейтом; dvc.yaml/params.yaml с dvc repro, пропуском неизменённой подготовки и dvc metrics diff.

- [ ] CSV не tracked в Git, docs не ignored.
- [ ] MLflow доступен через Ingress, Registry и артефакты есть.
- [ ] Три настоящих решения гейта и согласованный паспорт модели.
- [ ] Registry version в /health; /ready отрицательный тест сохранён.
- [ ] БД хранит точный request/score; 200/422/500 реально проверены.
- [ ] Откат champion без нового image, собственное время.
- [ ] Green deploy на credit-kind; smoke через Ingress.
- [ ] DVC V1/V2, push/diff/checkout/pull в новом clone.
- [ ] HPA рост/спад, SuccessfulRescale, 3 прогона, requests по собственным замерам.
- [ ] 3 пары red/green с URL и диагнозом.
- [ ] README/REPORT/скрины доступны, 8 ответов, финальный PR и default branch зелёная.

Источники: PDF ДЗ 3; чат «Исправить замечания по ДЗ 1»; фактические проверки проекта 30.09.2026. Официальные технические ссылки: [MLflow sklearn](https://mlflow.org/docs/latest/api_reference/python_api/mlflow.sklearn.html), [ModelInfo/версии](https://mlflow.org/docs/latest/api_reference/python_api/mlflow.models.html), [Registry aliases](https://www.mlflow.org/docs/latest/ml/model-registry/workflow/), [HPA](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/), [runner image](https://github.com/actions/runner/blob/main/images/Dockerfile), [Traefik values](https://github.com/traefik/traefik-helm-chart/blob/master/traefik/values.yaml).
