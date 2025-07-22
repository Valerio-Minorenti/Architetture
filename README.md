# Architetture
## Analisi dei Requisiti
### Requisiti Funzionali
Il sistema deve essere in grado di attivare dinamicamente nuove code gestite dagli operatori in tempo reale tramite un'interfaccia. Gli utenti possono richiedere un ticket e devono essere assegnati in modo progressivo e automatico alla coda meno carica. Inoltre, qualora un utente richiedesse un biglietto online,  è possibile visualizzare lo stato del ticket tramite una pagina dedicata che mostra il numero di persone in attesa e il cliente servito.

Gli operatori , dopo essersi autenticati, possono chiamare il  numero successivo in lista, chiudere la coda o aprirla. Il sistema permette di creare e gestire più code contemporaneamente

In caso di chiusura di una coda, il sistema ricolloca automaticamente gli utenti nelle file con meno persone; garantendo una gestione efficiente delle risorse. 
### Requisiti non Funzionali
Qmaster ha dverse specifiche non funzionali:

• Velocità: ogni operazione ha una latenza inferiore al secondo;

• Scalabilità: il sistema è in grado di supportare un numero massiccio di utenti contemporanemente;

• Affidabilità: in caso di guasto, i servizi continuano a funzionare se indipendenti dagli altri;

• Disponibilità: tutti i componenti sono containerizzati e permettono un facile deployment e la massima portabilità;

• Connesso: WebSocket permette di inviare notifiche agli utenti in modo rapido;

• Privacy: tutti gli utenti sono identificati con un token univoco e non sono esposti dati sensibili quali il nome o il cognome;

• Sicurezza: la pagina admin è dotata di un robusto sistema di autenticazione.

## Progettazione Architetturale
### Servizi
Il sistema è composto da una serie di servizi che hanno una responsabilità chiara e limitata. L’obiettivo è favorire la modularità, la scalabilità e la resilienza del sistema. Le principali componenti sono:

• Queue Service: Si occupa dello stato delle code, l'assegnazione dei numeri, chiusura e apertura delle code e riallocazione degli utenti;

• Ticket Online Service: permette agli utenti di richiedere un ticket tramite un'interfaccia web e di ricevere delle notifiche sullo stato della coda e il proprio turno;

• Ticket Service: permette all'utente di ottenere un biglietto e di essere allocato aautomaticamente;

• Admin Service: consente agli operatori di aprire o chiudere la coda, chiamare il prossimo numero e osservare la situazione dello sportello.

• Display Service: è un'interfaccia pubblica che mostra le code aperte, il numero servito e le persone in attesa.

### Tecnologie scelte
La scelta delle tecnologie è ricaduta su:

• Python e Flask: si occupano del backend per ogni microservizio;

• Redis: un server database che memorizza lo stato delle code;

• RabbitMQ: utilizzato come sistema di messaggistica per comunicazioni asincrone tra servizi e per aggiornare i client in tempo reale;

• Docker: containerizza i servizi;

• Flask e SocketIO: mandano in tempo reale aggiornamenti sincroni online agli utenti;

• HTML, CSS e JS: si occupano della gestione delle pagine HTML;

• RestAPI: usato per operazioni sincrone, quali lo stato della coda e la richiesta del biglietto.

### Gestione Aspetti Chiave
Di seguito verranno elencati tutti gli aspetti chiave e come sono gestiti:

• Scalabilità: ogni microservizio scala orizzontalmente, quindi può essere replicato su più istanze;

• Load Balancing: gli utenti sono efficientemente distribuiti in modo automatico nelle varie code;

• Caching: le informazioni richieste più frequentemente sono salvati in Redis;

• Consistenza: Redis permette di assegnare in modo univoco i dati anche in presenza di accessi concorrenti;

• Tolleranza ai guasti: in caso di disservizio gli utenti sono avvisati e ricoloccati nelle code.
## Piano di Sviluppo
Di seguito sono riportati gli step principali che hanno portato alla realizzazione del progetto.
### Milestone 1 - Setup e Infrastruttura
• Inizializzazione del repository del progetto;

• Configurazione del docker;

• Setup di rabbit e redis;

• Definizione dei volumi e reti;

### Milestone 2 - Queue Service
• Sviluppo del queue service con API rest;

• Creazione e attivazione delle code;

• Assegnazione dei numeri progressivi;

• Chiamata utente e redistribuzione degli utenti.

### Milestone 3 - Admin Service

• Sviluppo dell'Admin Service;

• Implementazione di un sistema di login;

• Form per inserire ID coda e attivarla

• Pagina di gestione della coda

• Comunicazione REST tra Admin e Queue Service
### Milestone 4 - Ticket Online Service
• Sviluppo del Ticket Online Service;

• Assegnazione automatica della coda con meno carico;

• Salavataggio su Redis dei dati utente;

• Aggiornamento periodico per la notifica di chiamata;

• Integrazione WebSocket per aggiornamenti live;

• Creazione della pagina per visualizzare lo stato del biglietto e della coda.
### Milestone 5 - Ticket  Service
• Sviluppo del Ticket Service;

• Assegnazione automatica della coda con meno carico;

• Salavataggio su Redis dei dati utente;

• Creazione della pagina per richiedere un ticket.
### Milestone 6 - Display Service
•	Creazione del Display Service;

•	Connessione a RabbitMQ per ricevere eventi;

•	Visualizzazione dei ticket attualmente serviti e in attesa per ogni coda.
### Milestone 7 - Test e Affidabilità
• Test unitari per funzioni critiche nel Queue Service.
•	Test d’integrazione: flusso utente completo;
•	Test di resilienza: simulazione guasto servizio;
•	Verifica comportamento su chiusura coda: corretta riallocazione utenti e aggiornamento live.

### Milestone 8 - Containerizzazione finale e PoC
•	Dockerizzazione completa di tutti i servizi;
•	File docker-compose.yml aggiornato con tutte le dipendenze;
•	Verifica del comportamento in ambiente simulato.
•	Preparazione istruzioni per avvio locale del PoC.

