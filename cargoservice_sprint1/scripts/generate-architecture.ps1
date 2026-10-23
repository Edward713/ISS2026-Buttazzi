param([switch]$Setup, [string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$packages = Join-Path $projectRoot 'build\architecture-python'
$tools = Join-Path $projectRoot 'build\architecture-tools'

if ($Setup) {
    # Dipendenze isolate nel progetto: non modifica Python o PATH di sistema.
    & $Python -m pip install --disable-pip-version-check --no-cache-dir --target $packages -r (Join-Path $PSScriptRoot 'architecture-requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Installazione diagrams non riuscita.' }
    if (-not (Get-Command dot -ErrorAction SilentlyContinue) -and
        -not (Test-Path 'C:\Program Files\Graphviz\bin\dot.exe') -and
        -not (Get-ChildItem -LiteralPath $tools -Filter dot.exe -Recurse -ErrorAction SilentlyContinue)) {
        New-Item -ItemType Directory -Force -Path $tools | Out-Null
        $zip = Join-Path $tools 'graphviz-16.1.0-win64.zip'
        # ZIP portabile ufficiale indicato in https://graphviz.org/download/.
        $url = 'https://gitlab.com/api/v4/projects/4207231/packages/generic/graphviz-releases/16.1.0/windows_10_cmake_Release_Graphviz-16.1.0-win64.zip'
        Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
        $expectedHash = (Invoke-WebRequest -Uri "$url.sha256" -UseBasicParsing).Content
        if ($expectedHash -is [byte[]]) { $expectedHash = [Text.Encoding]::UTF8.GetString($expectedHash) }
        $hash = [regex]::Match([string]$expectedHash, '[a-fA-F0-9]{64}').Value
        if (-not $hash -or (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ne $hash) {
            throw 'Checksum Graphviz non valido.'
        }
        Expand-Archive -LiteralPath $zip -DestinationPath $tools -Force
    }
}

& $Python (Join-Path $projectRoot 'Arch_cargoservice_term.py')
if ($LASTEXITCODE -ne 0) { throw 'Generazione architettura non riuscita.' }
