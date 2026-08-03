#!/usr/bin/env bash
# Instala as tarefas agendadas do ApontaSAP via cron: envio diario automatico Odoo -> SAP
# as 02:00 e backup do Postgres as 03:00 - equivalente Linux de instalar_tarefa_agendada.ps1
# e instalar_tarefa_backup.ps1 (Windows Task Scheduler).
#
# O modo manual/automatico continua sendo controlado pela tela /automatico do app (flag no
# Postgres) - o cron sempre dispara as 02:00, o script e que decide se faz algo de verdade.
#
# Por seguranca, esse script NAO mexe no crontab sozinho: sem --confirmar, so mostra as
# linhas que seriam adicionadas.
#
# Uso:
#   ./instalar_cron.sh              (so mostra as linhas, nao instala nada)
#   ./instalar_cron.sh --confirmar  (instala de verdade no crontab do usuario atual)

set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SCRIPT_ENVIO="$RAIZ/scripts/rodar_odoo_automatico.sh"
SCRIPT_BACKUP="$RAIZ/scripts/backup_postgres.sh"

if [[ ! -f "$SCRIPT_ENVIO" || ! -f "$SCRIPT_BACKUP" ]]; then
    echo "Nao encontrei $SCRIPT_ENVIO e/ou $SCRIPT_BACKUP - rode este script a partir da raiz do projeto." >&2
    exit 1
fi

LINHA_ENVIO="0 2 * * * $SCRIPT_ENVIO >> $RAIZ/logs/cron_envio.log 2>&1"
LINHA_BACKUP="0 3 * * * $SCRIPT_BACKUP >> $RAIZ/logs/cron_backup.log 2>&1"

echo "== Tarefas agendadas: envio diario Odoo -> SAP (02:00) + backup Postgres (03:00) =="
echo "Linhas que seriam adicionadas ao crontab do usuario atual:"
echo "  $LINHA_ENVIO"
echo "  $LINHA_BACKUP"

if [[ "${1:-}" != "--confirmar" ]]; then
    echo ""
    echo "Nada foi instalado ainda."
    echo "Revise as linhas acima e, se estiver tudo certo, rode de novo com --confirmar:"
    echo "  ./instalar_cron.sh --confirmar"
    exit 0
fi

mkdir -p "$RAIZ/logs" "$RAIZ/backups"
chmod +x "$SCRIPT_ENVIO" "$SCRIPT_BACKUP"

echo ""
echo "Instalando no crontab..."
{
    crontab -l 2>/dev/null | grep -vF "$SCRIPT_ENVIO" | grep -vF "$SCRIPT_BACKUP" || true
    echo "$LINHA_ENVIO"
    echo "$LINHA_BACKUP"
} | crontab -

echo "Tarefas instaladas. Confira com: crontab -l"
echo "Lembre-se: o modo manual/automatico e controlado na tela /automatico do app, nao aqui."
