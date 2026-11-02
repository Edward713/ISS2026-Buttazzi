param(
    [double]$DFree = 100,
    [string]$Broker = 'tcp://127.0.0.1:1883',
    [switch]$SkipBroker,
    [switch]$MockRobot,
    [switch]$SimulatedDevice,
    [string]$Sequence = '100:10000,40:4000,100:30000',
    [string]$Python = 'python',
    [int]$WebPort = 8080
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$stateFile = Join-Path $projectRoot 'build\deployment-processes.json'
$classpathFile = Join-Path $projectRoot 'build\launch-classpath.txt'
if (Test-Path -LiteralPath $stateFile) { throw 'Esiste un avvio registrato: eseguire scripts/stop-system.ps1 prima del riavvio.' }
if (-not (Test-Path -LiteralPath $classpathFile)) { throw 'Eseguire prima .\gradlew.bat test prepareLaunch.' }
if ($DFree -le 0) { throw 'DFree deve essere una distanza positiva in centimetri.' }
$javaCommand = if ($env:JAVA_HOME) { Join-Path $env:JAVA_HOME 'bin\java.exe' } elseif (Get-Command javap -ErrorAction SilentlyContinue) {
    Join-Path (Split-Path (Get-Command javap).Source) 'java.exe'
} else { (Get-Command java).Source }
$pythonCommand = (Get-Command $Python).Source
$processes = [Collections.Generic.List[object]]::new()
$brokerStarted = $false
$logDir = Join-Path $projectRoot 'build\deployment-logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
function Start-CargoProcess([string]$Name, [string]$Executable, [string[]]$Arguments) {
    # I percorsi classpath possono contenere spazi: quotare ogni argomento per Start-Process.
    $quoted = $Arguments | ForEach-Object { '"' + $_.Replace('"','\"') + '"' }
    $process = Start-Process -FilePath $Executable -ArgumentList $quoted -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logDir "$Name.out.log") -RedirectStandardError (Join-Path $logDir "$Name.err.log")
    $processes.Add(@{ id=$process.Id; started=$process.StartTime.ToUniversalTime().ToString('o'); name=$Name })
}
Push-Location $projectRoot
try {
    foreach ($port in @(8020,8021,8022,8023,$WebPort)) {
        $probe = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $port)
        try { $probe.Start() } finally { $probe.Stop() }
    }
    if (-not $MockRobot) {
        $probe = [Net.Sockets.TcpClient]::new()
        try { $probe.Connect('127.0.0.1',8019) } finally { $probe.Dispose() }
    }
    if (-not $SkipBroker) {
        & docker compose -p cargoservice-sprint2 -f deploy/compose.yaml up -d
        if ($LASTEXITCODE -ne 0) { throw 'Avvio broker fallito: verificare Docker Desktop.' }
        $brokerStarted = $true
    }
    $classpath = [IO.File]::ReadAllText($classpathFile).Trim()
    $common = @("-Dcargo.dfree=$DFree", "-Dcargo.mqtt=$Broker", "-Dcargo.mockRobot=$($MockRobot.IsPresent.ToString().ToLower())", '-cp', $classpath)
    foreach ($ctx in @('ctxcargoservice','ctxcargorobot','ctxioport','ctxsensor')) {
        Start-CargoProcess $ctx $javaCommand ($common + @('it.unibo.cargo.MainContextKt', $ctx))
    }
    Start-CargoProcess 'web' $pythonCommand @('-u','web/server.py','--port',"$WebPort")
    if ($SimulatedDevice) {
        Write-Warning 'Modalita simulata: tenere spento il firmware del Pico W.'
        Start-CargoProcess 'device-simulator' $javaCommand ($common + @('it.unibo.cargo.tools.MqttDeviceSimulator',$Sequence))
    }
    @{ processes=@($processes.ToArray()); brokerStarted=$brokerStarted } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $stateFile -Encoding UTF8
    Write-Output "IOPort: http://127.0.0.1:$WebPort . Log: $logDir"
    Write-Output 'Attendere le letture del Pico W esterno; al boot il sensore non e ancora disponibile.'
} catch {
    foreach ($entry in $processes) { Stop-Process -Id $entry.id -ErrorAction SilentlyContinue }
    if ($brokerStarted) { & docker compose -p cargoservice-sprint2 -f deploy/compose.yaml down }
    throw
} finally { Pop-Location }
