$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$stateFile = Join-Path $projectRoot 'build\deployment-processes.json'
if (-not (Test-Path -LiteralPath $stateFile)) { Write-Output 'Nessun avvio registrato.'; return }
$state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
foreach ($entry in $state.processes) {
    $process = Get-Process -Id $entry.id -ErrorAction SilentlyContinue
    # ConvertFrom-Json puo convertire automaticamente ISO 8601 in DateTime:
    # confrontare gli istanti, non la rappresentazione testuale dipendente dalla cultura.
    if ($process -and $process.StartTime.ToUniversalTime().Ticks -eq ([datetime]$entry.started).ToUniversalTime().Ticks) {
        Stop-Process -Id $entry.id
    }
}
if ($state.brokerStarted) {
    Push-Location $projectRoot
    try {
        & docker compose -p cargoservice-sprint2 -f deploy/compose.yaml down
        if ($LASTEXITCODE -ne 0) { throw 'Arresto broker fallito; registro conservato per riprovare.' }
    } finally { Pop-Location }
}
Remove-Item -LiteralPath $stateFile
Write-Output 'Processi dello Sprint 2 arrestati. Stato applicativo in memoria terminato.'
