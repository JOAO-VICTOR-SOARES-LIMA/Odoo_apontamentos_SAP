#!/usr/bin/env bash
# Instala a tarefa agendada de backup do Postgres via cron (03:00) - equivalente Linux de
# instalar_tarefa_backup.ps1 (Windows Task Scheduler).
#
# O envio diario automatico Odoo -> SAP (02:00) NAO e mais agendado por aqui - roda por um
# cron DENTRO do proprio container "app" (ver docker/crontab, docker/entrypoint.sh e
# Dockerfile), pra funcionar igual em qualquer host que rode a imagem, sem depender de cron/
# Task Scheduler configurado no SO. O modo manual/automatico continua sendo controlado pela
# tela /automatico do app (flag no Postgres) - o cron sempre dispara, o script e que decide
# se faz algo de verdade.
#
# Se este host tinha uma instalacao antiga (versao anterior deste script, que tambem
# registrava o envio as 02:00 via scripts/rodar_odoo_automatico.sh), essa linha antiga e
# removida do crontab ao confirmar - rodando os dois ao mesmo tempo duplicaria o envio.
#
# Por seguranca, esse script NAO mexe no crontab sozinho: sem --confirmar, so mostra a
# linha que seria adicionada.
#
# Uso:
#   ./instalar_cron.sh              (so mostra a linha, nao instala nada)
#   ./instalar_cron.sh --confirmar  (instala de verdade no crontab do usuario atual)

set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SCRIPT_ENVIO_ANTIGO="$RAIZ/scripts/rodar_odoo_automatico.sh"
SCRIPT_BACKUP="$RAIZ/scripts/backup_postgres.sh"

if [[ ! -f "$SCRIPT_BACKUP" ]]; then
    echo "Nao encontrei $SCRIPT_BACKUP - rode este script a partir da raiz do projeto." >&2
    exit 1
fi

LINHA_BACKUP="0 3 * * * $SCRIPT_BACKUP >> $RAIZ/logs/cron_backup.log 2>&1"

echo "== Tarefa agendada: backup do Postgres (03:00) =="
echo "(o envio diario Odoo -> SAP as 02:00 roda dentro do container - nao precisa de cron aqui)"
echo "Linha que seria adicionada ao crontab do usuario atual:"
echo "  $LINHA_BACKUP"

if [[ "${1:-}" != "--confirmar" ]]; then
    echo ""
    echo "Nada foi instalado ainda."
    echo "Revise a linha acima e, se estiver tudo certo, rode de novo com --confirmar:"
    echo "  ./instalar_cron.sh --confirmar"
    exit 0
fi

mkdir -p "$RAIZ/logs" "$RAIZ/backups"
chmod +x "$SCRIPT_BACKUP"

echo ""
echo "Instalando no crontab..."
{
    crontab -l 2>/dev/null | grep -vF "$SCRIPT_ENVIO_ANTIGO" | grep -vF "$SCRIPT_BACKUP" || true
    echo "$LINHA_BACKUP"
} | crontab -

echo "Tarefa instalada. Confira com: crontab -l"
echo "Lembre-se: o modo manual/automatico e controlado na tela /automatico do app, nao aqui."
