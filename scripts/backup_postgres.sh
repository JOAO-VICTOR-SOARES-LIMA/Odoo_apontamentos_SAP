#!/usr/bin/env bash
# Backup do Postgres (container sap_import_postgres) via pg_dump, formato custom (-Fc,
# restauravel com pg_restore). Gera o dump DENTRO do container e usa "docker cp" pra trazer
# pro host - equivalente Linux de scripts/backup_postgres.ps1 (Windows), mesma logica.
#
# Uso manual:
#   ./scripts/backup_postgres.sh
#
# Uso agendado: ver instalar_cron.sh (raiz do projeto).

set -euo pipefail

CONTAINER="${1:-sap_import_postgres}"
USUARIO="${2:-sap_import}"
BANCO="${3:-sap_import}"
DIAS_RETENCAO="${4:-14}"

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASTA_BACKUPS="$RAIZ/backups"
mkdir -p "$PASTA_BACKUPS"

CARIMBO="$(date +%Y%m%d_%H%M%S)"
NOME_ARQUIVO="sap_import_${CARIMBO}.dump"
DESTINO="$PASTA_BACKUPS/$NOME_ARQUIVO"
TEMP_NO_CONTAINER="/tmp/$NOME_ARQUIVO"

echo "Gerando backup ($BANCO) dentro do container $CONTAINER..."
docker exec "$CONTAINER" pg_dump -U "$USUARIO" -Fc -f "$TEMP_NO_CONTAINER" "$BANCO"

echo "Copiando para $DESTINO..."
docker cp "$CONTAINER:$TEMP_NO_CONTAINER" "$DESTINO"
docker exec "$CONTAINER" rm -f "$TEMP_NO_CONTAINER"

if [ ! -s "$DESTINO" ]; then
    echo "Falha: backup nao foi gerado ou ficou vazio." >&2
    exit 1
fi

TAMANHO="$(stat -c%s "$DESTINO" 2>/dev/null || stat -f%z "$DESTINO")"
echo "Backup ok: $DESTINO ($TAMANHO bytes)"
echo "Para restaurar: docker exec -i $CONTAINER pg_restore -U $USUARIO -d $BANCO --clean --if-exists < <arquivo>"

find "$PASTA_BACKUPS" -maxdepth 1 -name "sap_import_*.dump" -mtime "+$DIAS_RETENCAO" -print -delete
