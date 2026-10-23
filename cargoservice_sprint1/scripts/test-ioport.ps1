# Prova della sola tratta HOME -> IOPort, senza avviare il ciclo di carico.
param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
function Invoke-QakRequest([int]$Port, [string]$Receiver, [string]$Id, [string]$Argument, [int]$TimeoutMillis = 8000) {
    $client = [Net.Sockets.TcpClient]::new()
    try {
        Write-Host "[IOPORT TEST] $Id -> $Receiver (porta $Port), attendo risposta..."
        $connecting = $client.ConnectAsync('127.0.0.1', $Port)
        if (-not $connecting.Wait(3000)) { throw 'Timeout di connessione.' }
        $null = $connecting.GetAwaiter().GetResult()
        $client.ReceiveTimeout = $TimeoutMillis
        $client.SendTimeout = 3000
        $encoding = [Text.UTF8Encoding]::new($false)
        $writer = [IO.StreamWriter]::new($client.GetStream(), $encoding, 1024, $true)
        $writer.NewLine = "`n"
        $writer.AutoFlush = $true
        $reader = [IO.StreamReader]::new($client.GetStream(), $encoding, $false, 1024, $true)
        $writer.WriteLine("msg($Id,request,ioportprobe,$Receiver,$Id($Argument),1)")
        $reply = $reader.ReadLine()
        if (-not $reply) { throw 'Connessione chiusa senza risposta.' }
        Write-Host "[IOPORT TEST] Risposta ricevuta da $Receiver."
        return $reply
    } catch {
        throw "Richiesta $Id a $Receiver sulla porta $Port fallita: $($_.Exception.Message)"
    } finally { $client.Dispose() }
}
Write-Host '[IOPORT TEST] Controllo dei servizi; nessun movimento e stato ancora richiesto.'
$hold = Invoke-QakRequest 8020 cargoservice get_hold_status none
if (-not $hold.Contains('"phase":"DISENGAGED"') -or -not $hold.Contains('"serviceStatus":"WORKING"')) {
    throw 'La prova richiede CargoService WORKING e DISENGAGED. Riavviare i contesti dopo il guasto; non inviare un carico.'
}
$position = Invoke-QakRequest 8019 robotsmart getrobotstate none
if ($position -notmatch 'robotstate\(pos\(0,\s*0\),') {
    throw "Il navigatore non e in HOME: $position. Riallineare prima scena WEnv e RobotSmart26."
}
if ($CheckOnly) {
    Write-Host '[IOPORT TEST] Controlli completati. Nessun movimento richiesto.'
    return
}
Write-Output 'Prova della sola navigazione verso IOPort (riga 4, colonna 0).'
$result = Invoke-QakRequest 8021 cargorobot reach_target ioport 130000
Write-Output $result
if (-not $result.Contains('target_reached(ioport)')) { throw 'Tratta fallita: controllare i log di RobotSmart26.' }
Write-Output 'IOPort raggiunta secondo il navigatore. Verificare anche la posizione fisica in WEnv.'
Write-Output 'Il robot resta alla IOPort. Prima del ciclo completo riallineare nuovamente WEnv e navigatore in HOME.'
