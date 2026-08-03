#!/usr/bin/env bash
# Wrapper chamado pelo cron - roda o envio diario automatico Odoo -> SAP.
# Roda dentro do container "app" (mesma imagem Docker que serve o painel, via docker-compose.yml)
# - precisa da imagem ja buildada (docker compose build) e do Docker em execucao no horario
# agendado. Equivalente Linux de scripts/rodar_odoo_automatico.bat (Windows).
# ApontaSAP so usa producao - esse wrapper tambem so envia pra prod.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
docker compose run --rm --no-deps app python scripts/run_import_odoo_automatico.py --env prod --send --confirm-prod
