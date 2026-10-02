# ДЗ 3 — оставшаяся работа

Источник требований — `homework_03_mlops.pdf`. Проект — `harut-prog/credit-score`, рабочая ветка `hw3`. Пользователь потребовал вести дальнейшие изменения только в `hw3`; новые ветки и PR для экспериментов не создаются. Поэтому три обязательные пары red/green запускаем push-коммитами в `hw3`, хотя PDF предлагает `main`.

Уже выполнены MLflow/Registry, собственный гейт качества, DVC V1/V2, сервис из Registry, откат alias, Ingress, PostgreSQL, self-hosted runner и HPA с тремя нагрузочными прогонами. Остались проверяемые red/green deploy, актуализация отчёта и обязательные скриншоты из авторизованного UI.

Проверка CI: GitHub Actions → `ci` → конкретный run; в deploy должны быть `Runner name: credit-kind`, результат smoke через Ingress и точная строка БД. Локальная среда: kind `credit-service`, контейнер `gh-runner` в Docker network `kind`.
