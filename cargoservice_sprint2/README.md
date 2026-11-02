# CargoService — Sprint 2

Incremento dello Sprint 1: quattro attori QAK in JVM separate, web-GUI HTTP/WebSocket e **Raspberry Pi Pico W esterno al PC**, collegato via Wi-Fi/MQTT a sonar e LED. Il robot resta virtuale, controllato tramite RobotSmart26. Il simulatore MQTT serve alle prove senza dispositivi.

## Struttura

- `src/cargoservice_term.qak`: modello eseguibile; `src/it`: Kotlin rigenerato dal generatore UniBo incluso.
- `src/main/java/it/unibo/cargo/model`: inventario, operazione e filtro temporale sonar.
- `firmware`: MicroPython per il Pico W fisico; `web`: adattatore Python e pagina IOPort.
- `deploy`: Mosquitto e, con profilo `navigation`, WEnv; `scripts`: avvio/arresto e strumenti ereditati.
- `sprints/main (3).tex`: documento originale, aggiornato esclusivamente nella sezione 6.

## Preparazione

Servono JDK 17, Python 3.11+, Docker Desktop con motore Linux attivo; per rigenerare gli attori serve Eclipse/Xtext come nello Sprint 1. Impostare `JAVA_HOME` sul JDK, evitando lo shim Oracle.

```powershell
$env:JAVA_HOME = 'C:\Program Files\Java\jdk-17'
.\gradlew.bat test prepareLaunch
# Solo dopo modifiche al QAK (il Kotlin generato e gia incluso):
.\scripts\generate-qak.ps1
```

`generate-qak.ps1 -EclipsePlugins <cartella-plugins>` permette di specificare Eclipse. Dopo la rigenerazione ripetere la compilazione. `prepareLaunch` prepara un classpath assoluto: rigenerarlo se si sposta la cartella o si modificano le dipendenze.

## Deployment fisico

Il PC esegue i quattro contesti su TCP 8020–8023, Mosquitto su 1883, l'adattatore web su HTTP/WS 8080 e RobotSmart26 su 8019. WEnv usa 8090/8091. Il **Pico W e un nodo hardware separato**, alimentato via USB/alimentatore; lo scambio operativo avviene sulla LAN Wi-Fi a 2.4 GHz. Non esegue QAK e non usa una seriale USB per inviare le misure.

1. Collegare sonar HC-SR04: TRIG a GP16, ECHO a GP17 **attraverso adattamento da 5 V a 3.3 V**, GND comune e alimentazione secondo il modulo. Un partitore possibile e 1 kΩ fra ECHO e GP17 e 2 kΩ fra GP17 e GND. Non collegare ECHO a 5 V direttamente al Pico. Collegare GP15 a resistenza 330 Ω e anodo del LED, catodo a GND. Il firmware usa questo LED esterno, gestito dal PIO RP2040 anche durante attese di rete. I pin sono configurabili.
2. Installare sul Pico W il firmware MicroPython per **RPI_PICO_W**. Copiare `firmware/config.example.py` in `firmware/config.py`; impostare SSID, password e `MQTT_HOST` uguale all'**IP LAN del PC**, per esempio `192.168.1.10`. `localhost` sul Pico indicherebbe il Pico stesso. Non committare `config.py`.
3. Con il dispositivo collegato via USB e nessun altro monitor seriale aperto, installare la libreria e copiare i file (sostituire COM5):

```powershell
python -m pip install mpremote
mpremote connect COM5 mip install umqtt.simple
mpremote connect COM5 fs cp firmware/config.py :config.py
mpremote connect COM5 fs cp firmware/main.py :main.py
mpremote connect COM5 reset
```

4. Consentire al Pico di raggiungere il PC su TCP 1883 nel profilo di rete privata del firewall. Il broker incluso consente accesso anonimo per la dimostrazione in LAN; non pubblicare questa porta su Internet. Il browser usa localhost e non accede al broker.
5. Avviare broker e ambiente virtuale dalla cartella di questo progetto:

```powershell
docker compose -p cargoservice-sprint2 -f deploy/compose.yaml --profile navigation up -d
```

6. Configurare la copia di **RobotSmart26 fornita dal corso**, preservando la mappa e la scena dello Sprint 1:

```powershell
.\scripts\configure-robotsmart.ps1 -RobotSmartRoot C:\percorso\issLab2026\robotsmart26
# In un altro terminale, dentro quella cartella:
.\gradlew.bat run
```

Lo script imposta TCP 8019 e copia `config/tf25map.txt`, conservando backup degli originali. Non avviare anche il container RobotSmart della distribuzione standard su 8020, porta usata da cargoservice. Verificare WEnv su `http://localhost:8090`, robot in HOME, orientamento e scena coerenti con la mappa 6×8 dello Sprint 1. Il test `WenvGeometryTest` controlla una fixture della scena; non certifica la scena eventualmente modificata nel container.

Il Compose monta `deploy/wenv/PlayerControls.js` sul controller del simulatore. Il controller originale integra la traslazione soltanto nei fotogrammi, mentre un timer separato conclude il comando: la parte finale di ogni passo puo andare persa, anticipando le svolte fino a urtare gli slot. L'adattatore completa l'integrazione alla fine del comando, limita il tempo alla durata richiesta, usa l'angolo corrente dopo una rotazione e conserva il controllo delle collisioni con incrementi piccoli. Le rotazioni restano quelle di WEnv. Dopo un aggiornamento del controller ricreare il container WEnv, ricaricare la pagina e riavviare RobotSmart da HOME prima di nuovi carichi. Le regressioni del controller si eseguono con `node scripts/test-wenv-controls.cjs`.

7. Misurare la distanza in centimetri a porta sgombra e fissare `DFree` in configurazione. L'esempio seguente usa 100 cm: sostituirlo con il valore dell'impianto.

```powershell
.\scripts\start-system.ps1 -SkipBroker -DFree 100
```

Questo avvia **quattro JVM e un processo Python**, in background, con log in `build/deployment-logs`. Attendere l'indicazione di sonar disponibile e aprire `http://127.0.0.1:8080`. Il servizio parte con stiva vuota, sensore non disponibile e LED spento; soltanto nuove letture valide autorizzano il primo carico. Lo script controlla che RobotSmart risponda su 8019; non ne certifica la posizione HOME.

## Esecuzione simulata

Per vedere il robot muoversi in **WEnv**, usare RobotSmart26 reale con il sonar simulato. La variante Docker seguente evita di compilare il progetto esterno del corso; pubblica RobotSmart su 8019, lasciando 8020 a cargoservice. Da PowerShell nella cartella di questo progetto:

```powershell
.\scripts\stop-system.ps1
docker compose -p cargoservice-sprint2 -f deploy/compose.yaml -f deploy/compose.wenv.yaml --profile navigation up -d
# Attendere che RobotSmart sia pronto (log: docker compose ... logs robotsmart).
.\scripts\start-system.ps1 -SkipBroker
```

Aprire `http://127.0.0.1:8090` per WEnv e `http://127.0.0.1:8080` per la IOPort. Il robot deve partire in HOME con la scena dello Sprint 1. Quando si e pronti, avviare in un terminale separato:

```powershell
.\gradlew.bat simulateDevice '-Pcargo.sequence=100:15000,40:4000,100:180000'
```

Premere **Richiedi un carico** nella IOPort nei primi 15 secondi della sequenza. Dopo la conferma di presenza, seguire il robot in WEnv fino a IOPort, slot5, slot riservato e HOME. Il simulatore continua a fornire porta libera per tre minuti, per coprire il viaggio. Non aprire un secondo simulatore contemporaneamente e non azionare manualmente il robot durante la missione. Per arrestare questa variante:

```powershell
.\scripts\stop-system.ps1
docker compose -p cargoservice-sprint2 -f deploy/compose.yaml -f deploy/compose.wenv.yaml --profile navigation down
```

Il percorso fisico resta il deployment di riferimento. Per provare senza Pico e senza WEnv, spegnere il Pico e scegliere esplicitamente:

```powershell
.\scripts\start-system.ps1 -MockRobot -SimulatedDevice -Sequence '100:15000,40:4000,100:30000'
```

Aprire la GUI e richiedere il carico nei primi 15 secondi. Il simulatore termina alla fine della sequenza: dopo 2 secondi il sonar diventa indisponibile. Non eseguire due sorgenti contemporaneamente. Per altri scenari, con broker e contesti gia avviati:

```powershell
.\gradlew.bat simulateDevice '-Pcargo.sequence=100:10000,110:4000,100:5000'
.\gradlew.bat simulateDevice '-Pcargo.sequence=100:5000,silent:3000,100:5000,invalid:1000'
```

Ogni istanza ha sessione e numeri progressivi nuovi. Le misure usano `cargo/picow/sonar`, QoS 0, senza retain; il LED usa `cargo/picow/led/set`, QoS 1, con retain dello stato desiderato. I campioni retained, duplicati e fuori ordine vengono scartati. Una nuova sessione o una riconnessione azzera la continuita; una sessione gia sostituita non puo riattivarsi.

Parametri JVM/Gradle: `cargo.dfree=100` cm, `cargo.presenceMillis=3000` (anche conferma anomalia), `cargo.sampleGapMillis=500`, `cargo.staleMillis=2000`, `cargo.waitMillis=30000`, `cargo.markerMillis=5000`, `cargo.navigationMillis=120000`, `cargo.stepMillis=335`, `cargo.mqtt=tcp://127.0.0.1:1883`. Per avvii separati usare `gradlew runCtxCargoService`, `runCtxCargoRobot`, `runCtxIoPort`, `runCtxSensor` con proprieta `-Pcargo.*`, oppure lo script `start-context.ps1`. Il vecchio `simulateSonar` e riservato ai processi con `cargo.testMode=true`; il deployment usa il simulatore MQTT.

Il coordinatore controlla anche l'eta dell'ultimo aggiornamento con orologio monotono. Un campione invalido o un intervallo di conferma ancora incompleto rendono la porta non determinabile; non vengono interpretati come porta libera. Dopo un'anomalia confermata, le letture regolari non ripristinano il servizio. Durante una tratta il LED resta attivo fino all'esito; gli effetti confermati vengono registrati, poi il ciclo entra in `SUSPENDED` senza avviare altre tratte. Timer tardivi non liberano la prenotazione.

## Arresto e stato

```powershell
.\scripts\stop-system.ps1
docker compose -p cargoservice-sprint2 -f deploy/compose.yaml --profile navigation down
```

Lo script ferma soltanto i processi registrati, verificando PID e istante di avvio. Arrestare separatamente RobotSmart26. Lo stato applicativo e **in memoria**, come nello Sprint 1: conserva prenotazioni e barcode durante la sospensione della stessa esecuzione, non attraverso un riavvio. Un riavvio non e una procedura di manutenzione sicura: prima di riprendere riallineare carichi reali, inventario e robot. Il ripristino `setup_hold` del guasto richiede `cargo.testMode=true` ed e riservato alle prove.

## Verifiche

`gradlew test` esegue modello e regressione TCP senza broker. Per includere MQTT, HTTP e WebSocket con un broker isolato:

```powershell
$env:CARGO_MQTT_PORT = '18883'
docker compose -p cargoservice-sprint2-test -f deploy/compose.yaml up -d mqtt
.\gradlew.bat test prepareLaunch '-Pcargo.mqttTests=true' '-Pcargo.mqtt=tcp://127.0.0.1:18883'
docker compose -p cargoservice-sprint2-test -f deploy/compose.yaml down
Remove-Item Env:CARGO_MQTT_PORT
```

Le JVM di test usano 18020–18023, il peer RobotSmart 18019 e il web adapter 18080. Non avviare altri publisher sul broker di test. La suite usa i tempi reali di presenza/anomalia (3 s) e attesa container (30 s); simula il movimento. Piano e limiti in `docs/TEST_PLAN.md`. La prova con Pico, sonar, LED e WEnv reali richiede il banco hardware e resta distinta dai test automatici.

Riferimenti per il firmware: [MicroPython su Pico W](https://www.raspberrypi.com/documentation/microcontrollers/micropython.html), [mpremote](https://docs.micropython.org/en/latest/reference/mpremote.html), [umqtt.simple](https://github.com/micropython/micropython-lib/tree/master/micropython/umqtt.simple), [PIO RP2040](https://docs.micropython.org/en/latest/rp2/quickref.html#programmable-io-pio).
