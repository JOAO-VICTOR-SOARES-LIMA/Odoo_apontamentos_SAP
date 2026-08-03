# Prepara a Tarefa Agendada do Windows que roda o backup diario do Postgres
# (scripts\backup_postgres.ps1) as 03:00 (depois do envio automatico Odoo -> SAP das 02:00).
#
# Por seguranca, esse script NAO mexe no Task Scheduler sozinho: sem -Confirmar, so mostra
# o comando que seria executado.
#
# Uso:
#   .\instalar_tarefa_backup.ps1                 (so mostra o comando, nao registra nada)
#   .\instalar_tarefa_backup.ps1 -Confirmar      (registra de verdade no Task Scheduler)

param(
    [switch]$Confirmar
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $raiz "scripts\backup_postgres.ps1"

if (-not (Test-Path $script)) {
    Write-Host "Nao encontrei $script - rode este script a partir da raiz do projeto." -ForegroundColor Red
    exit 1
}

$tr = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$script`""
$comando = "schtasks /Create /TN `"SAP_Import_Backup_Postgres`" /TR `"$tr`" /SC DAILY /ST 03:00 /RL LIMITED /F"

Write-Host "== Tarefa Agendada: backup diario do Postgres ==" -ForegroundColor Cyan
Write-Host "Comando que seria executado:" -ForegroundColor Yellow
Write-Host "  $comando"

if (-not $Confirmar) {
    Write-Host ""
    Write-Host "Nada foi registrado no Task Scheduler ainda." -ForegroundColor Yellow
    Write-Host "Revise o comando acima e, se estiver tudo certo, rode de novo com -Confirmar:" -ForegroundColor Yellow
    Write-Host "  .\instalar_tarefa_backup.ps1 -Confirmar"
    exit 0
}

Write-Host ""
Write-Host "Registrando no Task Scheduler..." -ForegroundColor Cyan
Invoke-Expression $comando

if ($LASTEXITCODE -eq 0) {
    Write-Host "Tarefa 'SAP_Import_Backup_Postgres' registrada - roda todos os dias as 03:00." -ForegroundColor Green
} else {
    Write-Host "Falha ao registrar a tarefa (schtasks retornou codigo $LASTEXITCODE)." -ForegroundColor Red
    exit 1
}
