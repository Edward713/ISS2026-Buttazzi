param([string]$EclipsePlugins)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $EclipsePlugins) {
    $candidates = @(
        (Join-Path $env:USERPROFILE 'eclipse\java-2025-03-dsl\eclipse\plugins'),
        (Join-Path $env:USERPROFILE 'Desktop\eclipse\plugins')
    )
    $EclipsePlugins = $candidates | Where-Object {
        (Test-Path -LiteralPath $_) -and (Get-ChildItem -LiteralPath $_ -Filter 'org.eclipse.xtext_*.jar')
    } | Select-Object -First 1
}
if (-not $EclipsePlugins -or -not (Test-Path -LiteralPath $EclipsePlugins)) {
    throw 'Specificare -EclipsePlugins con la cartella plugins di Eclipse dotato di Xtext.'
}
# Use only generator dependencies. Loading all Eclipse plugins would initialize unrelated IDE services.
$pattern = '^(com\.google\.(inject|guava|guava\.failureaccess)|jakarta\.inject\.jakarta\.inject-api|javax\.inject|org\.antlr\.runtime|org\.apache\.log4j|org\.eclipse\.(xtext|xtext\.util|xtext\.xbase|xtext\.xbase\.lib|xtext\.common\.types|xtext\.logging|xtend\.lib|xtend\.lib\.macro|emf\.common|emf\.ecore|emf\.ecore\.xmi|equinox\.common|core\.runtime|core\.resources|core\.jobs|core\.contenttype|equinox\.registry|equinox\.preferences)|org\.slf4j\.api|org\.osgi\.service\.prefs|org\.eclipse\.osgi)_[0-9].*\.jar$'
$jars = Get-ChildItem -LiteralPath $EclipsePlugins -File | Where-Object {
    $_.Name -match $pattern -and $_.Name -notmatch 'jakarta.inject-api_1\.'
}
$qakJar = Join-Path $projectRoot 'build-tools\it.unibo.Qactork_1.6.4.jar'
$launcher = Join-Path $projectRoot 'build-tools\QakGenerate.java'
$source = Join-Path $projectRoot 'src\cargoservice_term.qak'
$output = Join-Path $projectRoot 'src-gen'
$generatorClasspath = $qakJar + ';' + ($jars.FullName -join ';')
$javaCommand = if ($env:JAVA_HOME) {
    Join-Path $env:JAVA_HOME 'bin\java.exe'
} elseif (Get-Command javap -ErrorAction SilentlyContinue) {
    # Evita lo shim Oracle javapath, che su alcuni PC non avvia il JDK atteso.
    Join-Path (Split-Path (Get-Command javap).Source) 'java.exe'
} else { 'java' }
Push-Location $projectRoot
try {
    & $javaCommand -cp $generatorClasspath $launcher $source $output
    if ($LASTEXITCODE -ne 0) { throw "Generatore QAK terminato con codice $LASTEXITCODE" }
    Write-Output 'Rigenerati i quattro attori FSM, i main dei contesti e il descrittore Prolog.'
} finally { Pop-Location }
