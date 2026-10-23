# Verifiche dello Sprint1

`./gradlew test` esegue test JUnit 4.13.2. `CargoSystemTcpTest` avvia e arresta quattro JVM con porte 18020–18023; comunica esclusivamente tramite messaggi QAK TCP. Ta e Tp conservano i valori reali di 30 e 3 secondi. La marcatura e configurata a 1 secondo per la suite, e il robot simula durate ed errori.

| Piano del documento | Test implementato e osservazioni |
|---|---|
| T1 | slot1 occupato, accettazione slot2, RESERVED, LED blink, nessun movimento prima della presenza |
| T2 | porta gia occupata; richieste busy durante attesa e trasporto; ID e deadline invariati; setup rifiutato durante il carico |
| T3 | full → load_refused, slot invariati, DISENGAGED |
| T4 | errore separatamente a IOPORT, SLOT5, SLOT1, HOME; OUT_OF_SERVICE persistente, display e LED, prenotazione/barcode conservati |
| T5 | attesa reale di 30 secondi con richieste busy ripetute; rilascio prenotazione e robot immobile |
| T6 | presenza interrotta a D=50, nessuna notifica anticipata; successivi 3 secondi continui, transito IOPORT/SLOT5 e buffer occupato |
| T7 | pulsante IOPort, marcatura, barcode, deposito e display prima di HOME, busy durante rientro, chiusura ciclo e LED off |

`DomainModelTest` verifica i vincoli di inventario e buffer, soglia stretta, continuita e dati sonar invalidi, timer vecchi e ripristino solo di test. `LayoutTest` confronta tutte le celle della mappa configurata e controlla che gli accessi siano raggiungibili.

`RobotSmartProtocolTest` avvia un peer TCP sulla porta 18019 ed esercita il ramo reale dell'adattatore (mock disabilitato): controlla le coordinate di tutte le destinazioni, STEPTIME, risposte moverobotdone/moverobotfailed/failed, mancata risposta con timeout e destinazione sconosciuta. La controparte riproduce il protocollo, senza eseguire movimenti in WEnv.

Per la prova virtuale seguire il README: stessi contesti con mock disabilitato, RobotSmart26 su 8019, mappa e scena coerenti. Verificare visivamente tutte le tappe, includendo il rientro. Non confondere il superamento dei test con robot simulato con l'esecuzione di questa prova esterna.

Il flag `-Pcargo.externalTests=true` evita l'avvio automatico dei contesti nella suite TCP: usarlo solo con quattro processi di test gia configurati con `cargo.testMode=true`, robot mock e marcatura a 1000 ms. Non e una modalita per lanciare la suite dei guasti contro il robot virtuale reale.
