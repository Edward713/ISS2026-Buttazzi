param([Parameter(Mandatory=$true)][string]$RobotSmartRoot)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$robotRoot = (Resolve-Path -LiteralPath $RobotSmartRoot).Path
$descriptor = Join-Path $robotRoot 'robotsmart26.pl'
$source = Join-Path $robotRoot 'src\robotsmart26.qak'
if (-not (Test-Path -LiteralPath $descriptor) -or -not (Test-Path -LiteralPath $source)) {
    throw 'Indicare la cartella robotsmart26 fornita dal corso, con robotsmart26.pl e src/robotsmart26.qak.'
}
# Operazione esplicita di configurazione: conserva una copia dei tre file originali.
foreach ($file in @($descriptor, $source, (Join-Path $robotRoot 'tf25map.txt'))) {
    if ((Test-Path -LiteralPath $file) -and -not (Test-Path -LiteralPath "$file.sprint1-backup")) {
        Copy-Item -LiteralPath $file -Destination "$file.sprint1-backup"
    }
}
$pl = [IO.File]::ReadAllText($descriptor)
$pl = [regex]::Replace($pl, '(context\(\s*ctxrobotsmart\s*,[^\r\n]*?"TCP"\s*,\s*")\d+("\s*\))', '${1}8019${2}')
[IO.File]::WriteAllText($descriptor, $pl, [Text.UTF8Encoding]::new($false))
$qak = [IO.File]::ReadAllText($source)
$qak = [regex]::Replace($qak, '(Context\s+ctxrobotsmart\s+ip\s*\[host="[^"]+"\s+port=)\d+', '${1}8019')
[IO.File]::WriteAllText($source, $qak, [Text.UTF8Encoding]::new($false))
Copy-Item -LiteralPath (Join-Path $projectRoot 'config\tf25map.txt') -Destination (Join-Path $robotRoot 'tf25map.txt')
Write-Output 'RobotSmart26 configurato su 8019 con la mappa 6x8. Originali salvati nei file .sprint1-backup.'
Write-Output 'Verificare anche la corrispondenza degli ostacoli nella scena WEnv prima della prova virtuale.'
