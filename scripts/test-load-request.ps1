param([switch]$Button)
$ErrorActionPreference = 'Stop'

# Client manuale dello scheletro Sprint0; non implementa il ciclo di carico.
$port = if ($Button) { 8021 } else { 8020 }
$receiver = if ($Button) { 'ioportservice' } else { 'cargoservice' }
$messageId = if ($Button) { 'button_pressed' } else { 'load_request' }
$messageType = if ($Button) { 'dispatch' } else { 'request' }
$client = [System.Net.Sockets.TcpClient]::new()
$client.ReceiveTimeout = 5000
$client.SendTimeout = 5000
$writer = $null
$reader = $null
try {
    $client.Connect([System.Net.IPAddress]::Loopback, $port)
    $encoding = [System.Text.UTF8Encoding]::new($false)
    $stream = $client.GetStream()
    $writer = [System.IO.StreamWriter]::new($stream, $encoding, 1024, $true)
    $writer.NewLine = "`n"
    $writer.AutoFlush = $true
    $reader = [System.IO.StreamReader]::new($stream, $encoding, $false, 1024, $true)

    foreach ($sequence in 1..2) {
        $message = "msg($messageId,$messageType,manualclient,$receiver,$messageId(none),$sequence)"
        $writer.WriteLine($message)
        Write-Output "INVIATO: $message"
        if (-not $Button) {
            $response = $reader.ReadLine()
            if ($null -eq $response) { throw 'Il servizio ha chiuso la connessione senza rispondere.' }
            Write-Output "RISPOSTA: $response"
        }
        Start-Sleep -Milliseconds 500
    }
    if ($Button) {
        Write-Output 'Controlla le risposte [IOPORT] nel terminale di runCargoSystem.'
    }
} finally {
    if ($null -ne $reader) { $reader.Dispose() }
    if ($null -ne $writer) { $writer.Dispose() }
    $client.Dispose()
}
