param(
    [ValidateSet('load','button','status','preset','sensor','robot','display')]
    [string]$Action = 'status',
    [ValidateSet('empty','full','slot1_occupied')][string]$Mode = 'empty'
)
$ErrorActionPreference = 'Stop'
$port = 8020
$receiver = 'cargoservice'
$id = 'get_hold_status'
$kind = 'request'
$argument = 'none'
switch ($Action) {
    'load' { $id = 'load_request' }
    'button' { $port = 8022; $receiver = 'ioportservice'; $id = 'button_pressed'; $kind = 'dispatch' }
    'preset' { $id = 'setup_hold'; $argument = $Mode }
    'sensor' { $port = 8023; $receiver = 'sensorservice'; $id = 'get_sensor_status' }
    'robot' { $port = 8021; $receiver = 'cargorobot'; $id = 'get_robot_status' }
    'display' { $port = 8022; $receiver = 'ioportservice'; $id = 'get_ioport_status' }
}
$client = [System.Net.Sockets.TcpClient]::new()
try {
    $client.Connect('127.0.0.1', $port)
    $client.ReceiveTimeout = 15000
    $encoding = [System.Text.UTF8Encoding]::new($false)
    $writer = [System.IO.StreamWriter]::new($client.GetStream(), $encoding, 1024, $true)
    $writer.NewLine = "`n"
    $writer.AutoFlush = $true
    $writer.WriteLine("msg($id,$kind,manualclient,$receiver,$id($argument),1)")
    if ($kind -eq 'request') {
        $reader = [System.IO.StreamReader]::new($client.GetStream(), $encoding, $false, 1024, $true)
        $reader.ReadLine()
        $reader.Dispose()
    } else { Write-Output 'Pressione pulsante inviata.' }
    $writer.Dispose()
} finally { $client.Dispose() }
