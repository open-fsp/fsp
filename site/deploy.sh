#!/usr/bin/env bash
# Сборка витрины и заливка на контент-сервер (openfsp.ru).
# Запуск из корня репозитория: ./site/deploy.sh
#
# Собираем локально: на сервере node 18.19, для Astro 6 он слишком стар.
# Обновление контента = ещё один прогон этого скрипта; контейнер не пересоздаётся.
set -euo pipefail

HOST="${OPENFSP_HOST:-root@155.212.191.63}"
REMOTE=/opt/openfsp
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "→ валидатор стандарта"
python3 "$HERE/../validate.py" >/dev/null

echo "→ сборка витрины"
npm --prefix "$HERE" ci --silent
npm --prefix "$HERE" run build --silent

echo "→ проверка внутренних ссылок"
python3 "$HERE/check_links.py" >/dev/null

echo "→ заливка на $HOST"
ssh "$HOST" "mkdir -p $REMOTE/dist $REMOTE/nginx"
rsync -a --delete "$HERE/dist/" "$HOST:$REMOTE/dist/"
rsync -a "$HERE/deploy/nginx.conf" "$HOST:$REMOTE/nginx/nginx.conf"
rsync -a "$HERE/deploy/docker-compose.yml" "$HOST:$REMOTE/docker-compose.yml"

echo "→ подъём контейнера"
ssh "$HOST" "cd $REMOTE && docker compose up -d && docker compose exec -T openfsp_nginx nginx -s reload"

echo "→ проверка"
for path in / /modules/pricing/ /1.0/core/schema.json /llms.txt; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "https://openfsp.ru$path")
  echo "   $code  https://openfsp.ru$path"
done
