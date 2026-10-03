# Выпуск HW3 — 03.10.2026

Финальный проверенный commit: `3c78e59` в ветке `hw3`.

Проверка: [GitHub Actions run 37137910217](https://github.com/harut-prog/credit-score/actions/runs/37137910217), все job `tests`, `build`, `deploy` завершились успешно на self-hosted runner `credit-kind`. Smoke прошёл через Ingress и проверил точную запись PostgreSQL.

Откат приложения: вернуть `k8s/ingress.yaml`, `k8s/configmap.yaml` или `.github/workflows/ci.yml` на предыдущий исправляющий commit и повторить push только в `hw3`. Не удалять kind-кластер, MLflow PVC и DVC remote до сдачи и сохранения скриншотов.
