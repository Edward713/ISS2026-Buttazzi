# CargoService — Sprint 1

Prototipo QAK del ciclo di carico descritto in `main_temp.tex`. Struttura, librerie UniBo, generatore Xtext e convenzioni riprendono `cargoservice_sprint0`.

## Immagine dell'architettura

`Arch_cargoservice_term.py` usa `Diagram`, `Cluster`, `Custom` ed `Edge` come `Arch_sistemasqak.py`, con le icone QAK del corso. Rappresenta i quattro attori applicativi nei rispettivi contesti, RobotSmart26 esterno, pulsante, sonar e i messaggi del ciclo di carico. Magenta indica request/reply (risposte in verde), blu dispatch e rosso puntinato eventi. Le richieste diagnostiche dei test e i timer interni sono omessi per rendere leggibile l'architettura applicativa.

```powershell
# Prima esecuzione: prepara diagrams e Graphviz portabile nella sola cartella build.
.\scripts\generate-architecture.ps1 -Setup
# Esecuzioni successive:
python .\Arch_cargoservice_term.py
```

I risultati sono `docs/architecture/cargoservice_sprint1.png`, `.svg` e `.dot`. I percorsi delle icone sono risolti rispetto allo script, quindi l'esecuzione funziona anche da un'altra directory. Il diagramma e mantenuto esplicitamente nello script, come il modello di esempio: se cambiano attori o messaggi, aggiornare anche questo file. `generateQak` non lo sovrascrive.

Riferimenti delle dipendenze: [installazione Diagrams](https://diagrams.mingrammer.com/docs/getting-started/installation), [distribuzione ufficiale Graphviz](https://graphviz.org/download/).

## Build e test

Richiede JDK 17 e Gradle Wrapper 8.6. Su PowerShell, se `java` punta allo shim Oracle, impostare prima il JDK:

```powershell
$env:JAVA_HOME = 'C:\Program Files\Java\jdk-17'
.\gradlew.bat test
```

`test` avvia automaticamente **quattro JVM distinte**, sulle porte 18020–18023, e le termina al termine della suite. Queste porte sono riservate ai test; il prototipo puo restare acceso sulle porte 8020–8023. I test usano gli attori QAK effettivi, il sonar ad eventi e il robot in modalita mock; Docker e RobotSmart26 non sono necessari. Il test T5 aspetta realmente 30 secondi. Report: `build/reports/tests/test/index.html`; log dei processi: `build/test-contexts/`.

Gli attori Kotlin generati e il descrittore Prolog sono inclusi: non serve Eclipse per compilare. Per rigenerarli dopo una modifica al QAK:

```powershell
.\gradlew.bat generateQak
# In alternativa, specificare i plugin Xtext:
.\scripts\generate-qak.ps1 -EclipsePlugins 'C:\percorso\eclipse\plugins'
```

La sorgente applicativa e `src/cargoservice_term.qak`; `src/it/` contiene il codice generato. Non modificare manualmente gli attori generati. `src/main/java/it/unibo/cargo/model/` contiene il dominio; `src/main/kotlin/it/unibo/cargo/MainContext.kt` avvia un solo contesto per processo e prepara i proxy TCP richiesti dal runtime 5.0. I main dei singoli contesti delegano allo stesso bootstrap anche se avviati dall'IDE. Usare i task qui sotto per l'avvio distribuito.

## Avvio con robot simulato

Eseguire in **quattro terminali**, un comando per terminale (JDK 17):

```powershell
.\gradlew.bat runCtxCargoService
.\gradlew.bat runCtxCargoRobot "-Pcargo.mockRobot=true"
.\gradlew.bat runCtxIoPort
.\gradlew.bat runCtxSensor
```

I task possono essere avviati contemporaneamente: un lock nel progetto serializza la compilazione e viene rilasciato prima dell'avvio dei processi applicativi. Ogni comando resta in esecuzione. I contesti completano le connessioni quando sono stati avviati tutti e quattro. Per la prova con RobotSmart26, omettere il parametro mock.

Resta disponibile anche l'avvio diretto Java tramite `prepareLaunch` e `scripts/start-context.ps1`.

Da un quinto terminale:

```powershell
.\scripts\cargo-client.ps1 -Action button
.\gradlew.bat simulateSonar
.\scripts\cargo-client.ps1 -Action status
.\scripts\cargo-client.ps1 -Action display
```

Il simulatore emette distanze 100 per 1 secondo, 40 per 4 secondi, poi 100 per 1 secondo. Una sequenza alternativa si passa con `-Dsonar.sequence=100:500,40:5000,100:500`. Il pulsante restituisce la risposta sul display simulato della IOPort. `-Action load` invia invece una richiesta diretta e stampa la risposta TCP; `-Action preset -Mode slot1_occupied` prepara la stiva solo in assenza di carichi in corso.

## Avvio con RobotSmart26 e ambiente virtuale

| Contesto | Attore | Porta TCP |
|---|---|---|
| ctxrobotsmart | robotsmart (fornito) | 8019 |
| ctxcargoservice | cargoservice | 8020 |
| ctxcargorobot | cargorobot | 8021 |
| ctxioport | ioportservice | 8022 |
| ctxsensor | sensorservice | 8023 |

Le porte seguono la sezione **Contesti di esecuzione** del documento, che prevale sulle etichette non aggiornate nel diagramma precedente.

1. Dalla cartella dei Docker forniti, avviare `docker compose -f mosquitto.yml up -d` e `docker compose -f vrWithGui26.yaml up -d`. Se i compose richiedono la rete esterna `iss-network`, crearla prima con `docker network create iss-network`. Aprire `http://localhost:8090`.
2. Configurare **la propria copia** di RobotSmart26 su 8019 e con la mappa dello sprint. Lo script seguente modifica esclusivamente configurazione e mappa, salvando gli originali:

   ```powershell
   .\scripts\configure-robotsmart.ps1 -RobotSmartRoot 'C:\percorso\robotsmart26'
   ```

3. Nella cartella RobotSmart26 eseguire `./gradlew run`, con il JDK richiesto dal progetto fornito (la versione locale del corso usa JDK 21). Verificare che ostacoli e dimensioni della scena WEnv corrispondano alla griglia 6x8 del documento e a `config/tf25map.txt`. Il file della mappa configura il pianificatore, non modifica la scena fisica di WEnv.
4. Avviare i quattro task `runCtx*` sopra, **omettendo** `-Pcargo.mockRobot=true`. Inviare pulsante e sequenza sonar come nell'esempio.

L'adattatore usa il protocollo del RobotSmart26 fornito: `moverobot(X,Y,STEPTIME)`, risposta con ID `moverobotdone` e contenuto `moverobotok(ARG)`, oppure `moverobotfailed(DONE,TODO)`. Accetta anche l'ID di errore `failed`. In questa versione del navigatore **X=riga e Y=colonna**, coerentemente con `RobotPosUtils` e il pianificatore. I punti di accesso sono HOME=(0,0), IOPORT=(4,0), A1=(0,2), A2=(0,3), A3=(4,2), A4=(4,3), A5=(2,5).

Il test `LayoutTest` verifica corrispondenza fra file della mappa e layout, e raggiungibilita di tutti i punti di accesso. La navigazione nella scena virtuale richiede una prova con i servizi esterni effettivamente avviati; i test automatici non attestano da soli la calibrazione del movimento di WEnv.

`RobotSmartProtocolTest` controlla anche il ramo reale dell'adattatore contro un peer TCP che riproduce il protocollo fornito, comprese coordinate, errori e assenza di risposta. Il peer di test usa la porta 18019, lasciando la 8019 disponibile al RobotSmart26 del prototipo.

## Compatibilita del runtime del corso

Il bootstrap installa `RuntimeCompatibility` prima di creare i contesti: nella versione `basicomm23-1.0` il parser JSON statico e condiviso fra i thread delle connessioni TCP. L'adattatore ne sincronizza l'accesso per evitare errori intermittenti durante campioni sonar e richieste concorrenti, conservando il protocollo QAK e i JAR forniti.

## Comportamento e parametri

Sequenza: `WAIT_CONTAINER → TO_IOPORT → TO_SLOT5 → WAIT_MARKER → TO_FINAL → RETURN_HOME → DISENGAGED`.

- Lo slot libero di indice minimo diventa RESERVED all'accettazione. Il servizio risponde retrylater se impegnato, se la porta e occupata o se e fuori servizio; load_refused se operativo ma a stiva piena.
- La presenza richiede D < DFREE/2 per 3 secondi continui entro i 30 secondi dall'accettazione. Campioni alla soglia, invalidi o troppo distanti nel tempo interrompono il conteggio. Il silenzio del sonar non conferma un container.
- Il timeout viene creato una sola volta ed e identificato dall'ID del carico. Scaduto il tempo, libera la prenotazione senza muovere il robot. Richieste busy e letture dello stato non cambiano la scadenza.
- In slot5 il container rimane nell'area di marcatura per N secondi (default 5); il barcode viene poi conservato anche nello slot finale. `target_reached` conferma navigazione e presa/deposito.
- Il deposito finale aggiorna subito inventario e display; il servizio e ancora impegnato durante il rientro HOME. Un errore o timeout di navigazione blocca il servizio in OUT_OF_SERVICE, spegne il LED logico e conserva i dati del carico. Nessun ripristino automatico.
- `setup_hold(empty|full|slot1_occupied)` restituisce `preset_ack(ok|busy|invalid_mode|out_of_service)`. In produzione non ripristina OUT_OF_SERVICE. Nei test, con `cargo.testMode=true`, consente il ripristino di un carico interrotto per guasto. Non modifica un carico operativo in corso.
- `get_hold_status(none)` risponde `hold_state('JSON')`: serviceStatus, phase, ioportOccupied, quattro slot con stato e barcode, slot5, errore e operazione corrente. Gli altri endpoint diagnostici sono `get_sensor_status`, `get_robot_status` e `get_ioport_status`.

| Proprieta JVM / Gradle | Default | Significato |
|---|---:|---|
| cargo.waitMillis | 30000 | Ta |
| cargo.presenceMillis | 3000 | Tp |
| cargo.markerMillis | 5000 | Durata marcatura |
| cargo.dfree | 100 | Distanza a porta libera |
| cargo.sampleGapMillis | 1000 | Massimo intervallo tra campioni continui |
| cargo.navigationMillis | 120000 | Massima durata di ogni tratta |
| cargo.stepMillis | 335 | Tempo del passo per RobotSmart26 |
| cargo.mockRobot | false | Simula la navigazione nell'attore cargorobot |
| cargo.testMode | false | Abilita controlli riservati ai test |

Passare le proprieta ai task con `-Pcargo.nome=valore`; modificare Ta/Tp/DFREE solo per esperimenti consapevoli, perche cambiano i valori richiesti. Le misure del sonar e il LED sono simulati. GUI definitiva, attuazione LED, Pico W e rilevamento fuori servizio da D > DFREE sono lasciati allo Sprint2 come richiesto.

## Prova della sola IOPort

La IOPort e configurata in (riga 4, colonna 0), secondo la posizione indicata in WEnv. Tutti i punti sono stati adattati alla griglia 6x8 della scena WEnv; le celle di riga 5 e colonna 7 sono muri. I test geometrici includono il padding anticollisione di 2 unita e il passo nominale di 4.02 unita. La prova del movimento effettivo resta necessaria.

Con CargoService WORKING/DISENGAGED, CargoRobot senza mock e RobotSmart26 e WEnv entrambi in HOME, eseguire:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-ioport.ps1
```

La prova invia solo `reach_target(ioport)`, senza pulsante, sonar, prenotazioni o trasferimento a slot5. Dopo la prova il robot resta alla IOPort. Riallineare scena e navigatore in HOME prima di avviare un ciclo completo. Una risposta positiva del navigatore va confrontata con la posizione osservata in WEnv.
