# Primi piani di test funzionali

Proposta di Sprint 0 coerente con `ISS2026_sprint0_.pdf`, da discutere
con il committente. I piani descrivono il comportamento da realizzare:
T1-T6 sono obiettivi dello Sprint 1, T7 riguarda gli sprint successivi.

Precondizioni: servizio operativo, porta libera confermata, nessuna
operazione in corso, LED spento. Per i futuri scenari simulati si
assume DFREE=100 e una sequenza continua di campioni validi.

| Piano | Requisiti Sprint0 | Preparazione e stimolo | Risultato atteso |
| --- | --- | --- | --- |
| T1 - Accettazione | R1, R2, R6 | slot1 occupato, altri liberi; richiesta | slot2 RESERVED, risposta con il nome, LED lampeggiante, robot ancora fermo |
| T2 - Rinvio | R1 | Porta occupata o carico in corso; nuova richiesta | retrylater e nessuna prenotazione aggiuntiva |
| T3 - Stiva piena | R1 | Quattro slot finali occupati; richiesta | load_refused; slot5 non aumenta la capacita finale |
| T4 - Anomalia | R1, R4 | D > DFREE per almeno 3 s continui; richiesta | OUT_OF_SERVICE, display Out of service, retrylater |
| T5 - Timeout | R2, R3, R6 | Richiesta accettata, presenza non confermata entro 30 s | Prenotazione liberata, DISENGAGED, LED spento, nessun movimento |
| T6 - Presenza e spostamento | R3, R5 (passo iniziale), R6 | D < DFREE/2 per 3 s continui entro il limite; arrivo all'accesso di slot5 | Fase TO_SLOT5, slot ancora RESERVED e LED lampeggiante; nessun deposito implicito |
| T7 - Ciclo completo | R2, R5, R6 | Trasporto a slot5, marcatura e deposito finale confermati | Slot finale OCCUPIED, buffer liberato e carico concluso |

Questi sono piani futuri, non test funzionali gia implementati. Gli
aggiornamenti del display devono mostrare stato della stiva e disponibilita
del servizio, come richiesto dalla consegna; con servizio operativo il
messaggio e "Service working".

Un campione contrario interrompe la rispettiva conferma temporale.
La scelta dell'accesso a slot5 e del protocollo di navigazione sara
motivata nell'analisi del problema dello Sprint 1.

## Verifiche attuali del modello

I due test di `DomainModelTest` controllano scelta del primo slot
libero e rilascio della prenotazione, e separazione fra inventario
finale e buffer slot5. Sono verifiche dei termini formalizzati, senza
attestare la copertura dei piani funzionali T1-T7.

Lo scheletro QAK non implementa ancora la conferma temporale del sonar,
la ricezione di sensor_state nel coordinatore o l'attesa dell'esito del
robot. Non sono presenti test che dichiarino queste funzionalita come
realizzate. La compilazione verifica i sorgenti Java e Kotlin inclusi.
