#!/usr/bin/env bash
# Entrypoint do container "app": grava o ambiente atual (as env vars que o Docker injetou via
# env_file/environment do docker-compose.yml) num arquivo que o cron consegue carregar - cron
# roda cada job com um ambiente minimo, NAO herda o ambiente do processo que o iniciou, entao
# sem isso o script disparado as 02:00 falharia por variavel de ambiente ausente mesmo com o
# .env todo certo. "printf %q" escapa cada valor com seguranca pra shell (funciona mesmo com
# senha contendo $, aspas etc - ex: HANA_PASSWORD).
set -e

printenv | while IFS='=' read -r nome valor; do
    [ -n "$nome" ] && printf 'export %s=%q\n' "$nome" "$valor"
done > /app/.env.runtime

mkdir -p /app/logs

cron

exec "$@"
