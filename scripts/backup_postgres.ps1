# Backup do Postgres (container sap_import_postgres) via pg_dump, formato custom (-Fc,
# restauravel com pg_restore). Gera o dump DENTRO do container e usa "docker cp" pra trazer
# pro host - evita passar binario pelo pipeline do PowerShell (redirecionamento >/| corrompe
# arquivo binario por causa de conversao de encoding).
#
# Uso manual:
#   .\scripts\backup_postgres.ps1
#
# Uso agendado: ver instalar_tarefa_backup.ps1 (raiz do projeto).

param(
    [string]$Container = "sap_import_postgres",
    [string]$Usuario = "sap_import",
    [string]$Banco = "sap_import",
    [int]$DiasRetencao = 14
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$pastaBackups = Join-Path $raiz "backups"
New-Item -ItemType Directory -Force -Path $pastaBackups | Out-Null

$carimbo = Get-Date -Format "yyyyMMdd_HHmmss"
$nomeArquivo = "sap_import_$carimbo.dump"
$destino = Join-Path $pastaBackups $nomeArquivo
$tempNoContainer = "/tmp/$nomeArquivo"

Write-Host "Gerando backup ($Banco) dentro do container $Container..."
docker exec $Container pg_dump -U $Usuario -Fc -f $tempNoContainer $Banco

Write-Host "Copiando para $destino..."
docker cp "${Container}:$tempNoContainer" $destino
docker exec $Container rm -f $tempNoContainer

if (-not (Test-Path $destino) -or (Get-Item $destino).Length -eq 0) {
    Write-Host "Falha: backup nao foi gerado ou ficou vazio." -ForegroundColor Red
    exit 1
}

Write-Host "Backup ok: $destino ($((Get-Item $destino).Length) bytes)" -ForegroundColor Green
Write-Host "Para restaurar: docker exec -i $Container pg_restore -U $Usuario -d $Banco --clean --if-exists < <arquivo>"

$limite = (Get-Date).AddDays(-$DiasRetencao)
Get-ChildItem -Path $pastaBackups -Filter "sap_import_*.dump" |
    Where-Object { $_.LastWriteTime -lt $limite } |
    ForEach-Object {
        Write-Host "Removendo backup antigo: $($_.Name)"
        Remove-Item $_.FullName -Force
    }
