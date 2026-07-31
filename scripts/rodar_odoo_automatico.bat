@echo off
REM Wrapper chamado pela Tarefa Agendada do Windows - roda o envio diario automatico Odoo -> SAP.
REM O "cd /d" e critico: load_dotenv() resolve o .env relativo ao diretorio de trabalho, nao ao
REM script - sem fixar o cwd aqui, a tarefa agendada falha por variavel de ambiente ausente mesmo
REM com tudo configurado certo.
REM ApontaSAP so usa producao - essa tarefa agendada tambem so envia pra prod.
setlocal
set SAP_ENV_AUTOMATICO=prod
cd /d "%~dp0\.."
".venv\Scripts\python.exe" "scripts\run_import_odoo_automatico.py" --env %SAP_ENV_AUTOMATICO% --send --confirm-prod
endlocal
