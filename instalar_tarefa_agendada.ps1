# Prepara a Tarefa Agendada do Windows que dispara o envio diario automatico Odoo -> SAP
# todos os dias as 02:00 (scripts/rodar_odoo_automatico.bat -> scripts/run_import_odoo_automatico.py).
# O modo manual/automatico continua sendo controlado pela tela /automatico do app (flag no
# Postgres) - essa tarefa sempre dispara as 02:00, o script e que decide se faz algo de verdade.
#
# Por seguranca, esse script NAO mexe no Task Scheduler sozinho: sem -Confirmar, so mostra
# o comando que seria executado.
#
# Uso:
#   .\instalar_tarefa_agendada.ps1                 (so mostra o comando, nao registra nada)
#   .\instalar_tarefa_agendada.ps1 -Confirmar      (registra de verdade no Task Scheduler)

param(
    [switch]$Confirmar
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
$bat = Join-Path $raiz "scripts\rodar_odoo_automatico.bat"

if (-not (Test-Path $bat)) {
    Write-Host "Nao encontrei $bat - rode este script a partir da raiz do projeto." -ForegroundColor Red
    exit 1
}

$comando = "schtasks /Create /TN `"SAP_Import_Odoo_Automatico`" /TR `"$bat`" /SC DAILY /ST 02:00 /RL LIMITED /F"

Write-Host "== Tarefa Agendada: envio diario automatico Odoo -> SAP ==" -ForegroundColor Cyan
Write-Host "Comando que seria executado:" -ForegroundColor Yellow
Write-Host "  $comando"

if (-not $Confirmar) {
    Write-Host ""
    Write-Host "Nada foi registrado no Task Scheduler ainda." -ForegroundColor Yellow
    Write-Host "Revise o comando acima e, se estiver tudo certo, rode de novo com -Confirmar:" -ForegroundColor Yellow
    Write-Host "  .\instalar_tarefa_agendada.ps1 -Confirmar"
    exit 0
}

Write-Host ""
Write-Host "Registrando no Task Scheduler..." -ForegroundColor Cyan
Invoke-Expression $comando

if ($LASTEXITCODE -eq 0) {
    Write-Host "Tarefa 'SAP_Import_Odoo_Automatico' registrada - roda todos os dias as 02:00." -ForegroundColor Green
    Write-Host "Lembre-se: o modo manual/automatico e controlado na tela /automatico do app, nao aqui." -ForegroundColor Green
} else {
    Write-Host "Falha ao registrar a tarefa (schtasks retornou codigo $LASTEXITCODE)." -ForegroundColor Red
    exit 1
}
