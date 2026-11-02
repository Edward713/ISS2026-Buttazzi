param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('ctxcargoservice','ctxcargorobot','ctxioport','ctxsensor')]
    [string]$Context,
    [switch]$MockRobot,
    [double]$DFree = 100,
    [string]$Broker = 'tcp://127.0.0.1:1883'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$classpathFile = Join-Path $projectRoot 'build\launch-classpath.txt'
if (-not (Test-Path -LiteralPath $classpathFile)) {
    throw 'Eseguire prima .\gradlew.bat prepareLaunch in un solo terminale.'
}
$java = if ($env:JAVA_HOME) { Join-Path $env:JAVA_HOME 'bin\java.exe' } elseif (Get-Command javap -ErrorAction SilentlyContinue) {
    Join-Path (Split-Path (Get-Command javap).Source) 'java.exe'
} else { 'java' }
$javaArguments = @("-Dcargo.dfree=$DFree", "-Dcargo.mqtt=$Broker")
if ($MockRobot) { $javaArguments += '-Dcargo.mockRobot=true' }
$javaArguments += @('-cp', [IO.File]::ReadAllText($classpathFile).Trim(), 'it.unibo.cargo.MainContextKt', $Context)
Push-Location $projectRoot
try {
    & $java @javaArguments
    if ($LASTEXITCODE -ne 0) { throw "Contesto terminato con codice $LASTEXITCODE" }
} finally { Pop-Location }
