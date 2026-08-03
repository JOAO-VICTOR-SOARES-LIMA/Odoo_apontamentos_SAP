@echo off
REM Wrapper chamado pela Tarefa Agendada do Windows - roda o envio diario automatico Odoo -> SAP.
REM Roda dentro do container "app" (mesma imagem Docker que serve o painel, via docker-compose.yml)
REM em vez de uma venv separada no host - evita manter duas copias das dependencias sincronizadas.
REM Precisa da imagem ja buildada (docker compose build) e do Docker em execucao no horario
REM agendado. "--no-deps" nao sobe o servico postgres do compose (nao gerenciado por aqui neste
REM host - ver docker-compose.yml/APP_POSTGRES_DSN); numa stack completa isso e inofensivo.
REM ApontaSAP so usa producao - essa tarefa agendada tambem so envia pra prod.
setlocal
set SAP_ENV_AUTOMATICO=prod
cd /d "%~dp0\.."
docker compose run --rm --no-deps app python scripts/run_import_odoo_automatico.py --env %SAP_ENV_AUTOMATICO% --send --confirm-prod
endlocal
