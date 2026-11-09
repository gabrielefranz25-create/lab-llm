# Strumenti MCP: meteo e note (lezione 5)

Data: 2026-11-09. Estende il progetto della lezione 4 (`2026-10-26-assistente-orologio-design.md`
e `2026-11-09-nodo-compatta-design.md`). Materiale: `materiali/LLM_Lez_5.pdf`.

## 1. Perché
La lezione 5 chiede di esporre almeno una capacità tramite **MCP** e di collegarla al grafo con
**discovery** (catalogo letto dal server) e **invocazione**. Il risultato deve tornare al modello
come `ToolMessage` correlato al `tool_call_id`, e il percorso deve essere dimostrato con i log, non
dalla plausibilità della risposta. L'MCP, finora escluso dai confini del progetto, ora entra.

Capacità scelte:
- **meteo**: condizioni attuali e previsioni (API pubblica Open-Meteo, senza chiave);
- **note persistenti**: SQLite, sopravvivono al riavvio.

## 2. Obiettivi
1. Due server MCP separati, scritti con **FastMCP**, nel pacchetto `server_mcp/` (fuori da
   `agente/`): `server_mcp.meteo` e `server_mcp.note`.
2. Trasporto **stdio**: l'agente avvia i server come sottoprocessi all'avvio e li chiude all'uscita.
3. Catalogo dei tool ottenuto dal server (`tools/list`) e convertito in tool LangChain da un
   **adattatore scritto nel progetto**. Nome, descrizione e schema non vengono mai riscritti a mano
   nell'agente.
4. Grafo e client restano **sincroni**; tutta l'asincronia MCP sta in un solo modulo.
5. L'orologio resta un tool **locale**: l'agente usa insieme tool locali e tool MCP.
6. Log del nodo strumenti con origine, call_id, argomenti ed esito (traccia della slide 23).
7. Tre esiti distinguibili: successo, errore dello strumento, errore di collegamento.
8. Funzionamento anche in Docker, con le note persistenti in un volume.

Ordine di realizzazione (decisione dell'utente): **prima il meteo**, completo e dimostrato con una
prova reale; solo dopo le note come secondo server.

## 3. Non obiettivi
- Streamable HTTP e altri trasporti, resources e prompt MCP, autenticazione.
- Conferma interattiva prima dell'eliminazione di una nota.
- Spostare l'orologio su MCP.
- Rendere asincroni grafo o client.
- Cache delle risposte meteo, scelta delle unità di misura (si usano °C, km/h, mm, %).

## 4. Anti-obiettivi
Il lavoro è fallito, anche se «funziona», se:
- nome, descrizione o schema dei tool MCP sono scritti a mano nell'agente (niente discovery);
- un errore (città inesistente, rete assente, ID di nota inesistente) produce un'ora, un meteo o
  una conferma inventati, cioè un falso successo;
- il server scrive su stdout qualcosa che non è protocollo;
- un'eliminazione ambigua cancella una nota diversa da quella indicata dall'ID.

## 5. Vincoli
- Dipendenze nuove in `requirements.txt` con versioni fissate: `fastmcp==4.1.6` (porta
  `mcp==2.3.0`, da fissare anch'esso) e `httpx==0.28.1` (già presente come dipendenza indiretta,
  ma il server meteo la usa direttamente). `langchain-mcp-adapters` **non** si usa: la 0.3.2
  richiede `mcp<2` ed è incompatibile con fastmcp 4 (decisione dell'utente: adattatore nostro). Le
  altre dipendenze introdotte da fastmcp restano indirette e non vanno fissate. La risoluzione
  insieme ai pin attuali è stata verificata con `pip install --dry-run` (Python 3.13.14). Se
  l'installazione vera fallisse, ci si ferma e si chiede all'utente, senza cambiare i pin da soli.
- Nessuna nuova dipendenza di sviluppo: i test asincroni usano `asyncio.run` dentro test sincroni.
- Valgono tutte le regole del CLAUDE.md: codice in italiano, moduli piccoli, print `[passo]`
  commentati, log su stderr, comandi documentati per PowerShell.

## 6. Comportamento

### 6.1 Server meteo (`server_mcp/meteo.py`)
`FastMCP("Meteo")` con due tool:

| Tool | Argomenti | Risultato (testo italiano) |
|---|---|---|
| `meteo_attuale` | `citta: str` | località scelta, ora di riferimento locale, temperatura (°C), umidità (%), vento (km/h), condizioni |
| `previsioni_meteo` | `citta: str`, `giorni: int = 3` (1–7) | località scelta, poi una riga per giorno: data, minima/massima (°C), probabilità di pioggia (%), condizioni |

- Le descrizioni (docstring) devono distinguere chiaramente i due tool («adesso» e «nei prossimi
  giorni»), perché il modello sceglie in base a quelle.
- **Geocoding**: `https://geocoding-api.open-meteo.com/v1/search` con `name`, `count=5`,
  `language=it`. Si usa il primo risultato; il testo dichiara la località scelta (nome, regione,
  paese) e, se ci sono altri risultati, li elenca come «Altre località con questo nome: …». Non si
  fa nessuna scelta silenziosa.
- **Previsioni**: `https://api.open-meteo.com/v1/forecast` con latitudine e longitudine,
  `timezone=auto`. Per `meteo_attuale` si chiedono i campi `current` (temperatura, umidità,
  codice meteo, vento); per `previsioni_meteo` i campi `daily` (codice meteo, massima, minima,
  probabilità di pioggia) con `forecast_days=giorni`.
- I codici meteo WMO vengono tradotti con una tabella italiana nel modulo (sereno, nuvoloso,
  pioggia, …). Un codice sconosciuto diventa «condizioni non classificate (codice N)».
- Errori, sempre sollevati come `ToolError` di FastMCP (quindi `isError` nel protocollo), con
  messaggi distinti:
  - `citta` vuota o `giorni` fuori dall'intervallo 1–7 → argomento non valido;
  - nessun risultato dal geocoding → «città non trovata: X»;
  - timeout o errore di rete → «servizio meteo non raggiungibile»;
  - HTTP 4xx/5xx → «servizio meteo non disponibile (HTTP N)»;
  - JSON senza i campi attesi → «risposta del servizio meteo non valida».
- Struttura: la logica sta in funzioni normali che ricevono un `httpx.Client` (iniettabile, così
  i test possono usare `httpx.MockTransport`); i tool FastMCP sono un involucro sottile.
- Il timeout HTTP si legge dalla variabile `METEO_TIMEOUT` (secondi, default 10).
- Log (modulo `logging`) **solo su stderr**: una riga per ogni richiesta (tool, città, esito).

### 6.2 Server note (`server_mcp/note.py`)
`FastMCP("Note")` con tre tool:

| Tool | Argomenti | Risultato |
|---|---|---|
| `aggiungi_nota` | `testo: str` | «Nota N salvata il AAAA-MM-GG HH:MM: testo» |
| `elenca_note` | `limite: int = 10` (1–50) | note dalla più recente, una per riga con ID e data; se non ce ne sono, «Nessuna nota salvata.» |
| `elimina_nota` | `id_nota: int` | «Nota N eliminata: testo» |

- Archivio SQLite nel percorso della variabile `NOTE_DB` (default `dati/note.sqlite3`, relativo
  alla cartella di lavoro). La cartella viene creata se manca, la tabella al primo avvio. Una sola
  tabella: `id INTEGER PRIMARY KEY AUTOINCREMENT, testo TEXT, creata TEXT` (ISO 8601 locale).
- Validazione: il testo viene ripulito dagli spazi e deve avere da 1 a 500 caratteri; il limite va
  da 1 a 50.
- `elimina_nota` cancella **solo per ID esatto**. Un ID inesistente dà `ToolError` «nessuna nota
  con ID N» e non cancella niente.
- Un archivio non accessibile dà `ToolError` «archivio note non accessibile».
- Una riga di log su stderr per ogni modifica (aggiunta, eliminazione).
- La descrizione dei tool dice esplicitamente che `aggiungi_nota` ed `elimina_nota` **modificano**
  l'archivio.

### 6.3 Adattatore MCP (`agente/mcp_ponte.py`)
È l'unico modulo asincrono. Il suo compito è collegare i server al grafo sincrono.

- `ServerMCP`: descrizione di un server, con nome logico (`meteo`, `note`), modulo da avviare
  (`server_mcp.meteo`) e variabili d'ambiente da passare.
- `ConnessioneMCP(servers, timeout)`: context manager.
  - All'ingresso avvia un **thread con un proprio event loop asyncio**. In quel loop, per ogni
    server, apre un `fastmcp.Client` stdio **persistente** con comando `sys.executable -m <modulo>`,
    cartella di lavoro `lab_llm/` e ambiente passato in modo esplicito (il client stdio non eredita
    tutto l'ambiente: vanno passati almeno `PATH`, le variabili di sistema necessarie su Windows e
    quelle del server, cioè `METEO_TIMEOUT` e `NOTE_DB`).
  - Esegue `list_tools()` (discovery) e, per ogni voce del catalogo, crea uno `StructuredTool`
    **sincrono** con:
    - `name` e `description` presi dal catalogo;
    - `args_schema` = `inputSchema` del catalogo (dizionario JSON Schema);
    - `metadata={"origine": "mcp:<nome server>"}`;
    - una funzione che invia `call_tool(nome, argomenti)` al loop del thread
      (`asyncio.run_coroutine_threadsafe(...).result(timeout)`) e restituisce testo.
  - All'uscita chiude i client (che terminano i sottoprocessi) e ferma il loop e il thread.
  - Espone `strumenti: list[BaseTool]` e, per diagnosi, il catalogo grezzo per server.
- Esiti restituiti come testo, cioè quello che il modello legge nel `ToolMessage`:
  - successo → il testo del contenuto restituito dal server;
  - errore del tool (`isError`, `ToolError`) → `Errore dallo strumento <nome>: <messaggio>`;
  - errore di collegamento (processo terminato, timeout dell'attesa, eccezione di trasporto) →
    `Errore di collegamento MCP con il server <server>: <dettaglio>`.
- Avvio: se un server non parte o la discovery fallisce, l'adattatore scrive un WARNING con il
  motivo e prosegue senza i suoi tool. L'agente parte comunque, perché almeno l'orologio è sempre
  disponibile. *(Scelta del progettista.)*
- Il timeout della singola chiamata si legge da `MCP_TIMEOUT` (secondi, default 30). Deve essere
  maggiore di `2 × METEO_TIMEOUT`, perché il meteo fa due richieste HTTP in sequenza (geocoding e
  previsioni). Se non lo è, si ha un `ErroreConfigurazione`, come per il controllo su
  `MESSAGGI_DA_TENERE`. *(Scelta del progettista.)*
- Server che muore durante la sessione: nessuna riconnessione automatica; le chiamate successive
  restituiscono `Errore di collegamento MCP …`. *(Scelta del progettista.)*
- Nome di tool duplicato, tra due server o con `ora_corrente`: si registra un WARNING e il
  duplicato viene scartato (vince il primo registrato, quindi l'orologio, poi i server nell'ordine
  di `SERVER_MCP`). *(Scelta del progettista.)*
- Log INFO all'avvio, per server: `server MCP <nome>: catalogo [<tool>, ...]`.

### 6.4 Grafo (`agente/graph.py`)
- La struttura resta invariata: `START → compatta → llm → (strumenti | limite | END)`. I tool MCP
  arrivano già sincroni e passano da `bind_tools` e dalla tabella `per_nome` come l'orologio.
- Log INFO del nodo strumenti, in questo formato (sostituisce la riga attuale):
  `strumento=<nome> origine=<locale|mcp:meteo|mcp:note> call_id=<id> argomenti=<json>
  esito=<ok|errore> risultato=<testo su una riga>`. L'origine è letta da `metadata` (assente
  significa `locale`). L'esito è `errore` quando il testo inizia con `Errore`.
- `PROMPT_SISTEMA` viene esteso con poche righe:
  - per meteo attuale e previsioni usare gli strumenti meteo, senza inventare dati, e citare la
    località indicata nel risultato;
  - per ricordare, elencare o eliminare note usare gli strumenti delle note; eliminare solo per ID;
    se l'ID non è noto, prima elencare;
  - se uno strumento restituisce un errore, riferirlo senza inventare un risultato.

  Le istruzioni sull'orologio restano. Il prompt nomina solo strumenti che esistono; se un server
  non parte, il modello non riceve quei tool e il prompt resta comunque innocuo.
- Il limite ai passaggi (`MAX_PASSI_STRUMENTO`), la compattazione e la correlazione via
  `tool_call_id` restano invariati.

### 6.5 Avvio (`agente/main.py`, `agente/config.py`)
- Nuove variabili in `Config` e in `.env.example`, tutte facoltative:
  - `MCP_TIMEOUT`, in secondi, default 30;
  - `METEO_TIMEOUT`, in secondi, default 10;
  - `NOTE_DB`, percorso, default `dati/note.sqlite3`;
  - `SERVER_MCP`, elenco separato da virgole dei server da avviare tra `meteo` e `note`, default
    `meteo,note`. Una stringa vuota non ne avvia nessuno. Un nome sconosciuto è un errore di
    configurazione.
- `main()` apre `ConnessioneMCP` **dopo** `verifica_modello` e la tiene aperta per tutta la
  sessione (`with`). Unisce l'orologio e i tool MCP, poi li passa a `crea_modello` e a
  `costruisci_grafo`. Con Ctrl+C la connessione si chiude in modo pulito.
- L'intestazione della sessione elenca i tool disponibili.

### 6.6 Docker
- Il `Dockerfile` copia anche `server_mcp/` e crea `/app/dati` con proprietario `appuser`.
- `compose.yaml` aggiunge un volume con nome (`note`) montato su `/app/dati`, così le note
  sopravvivono a `docker compose run --rm`.
- Nessun nuovo servizio: i server MCP girano come sottoprocessi dentro il container
  dell'assistente.
- Il container deve raggiungere Open-Meteo su Internet (rete bridge predefinita); va verificato.
- `.gitignore`: aggiungere `dati/`.

## 7. Test

### 7.1 Automatici (senza modello e senza rete)
- `tests/test_meteo.py`:
  - logica con `httpx.MockTransport`: meteo attuale e previsioni formattati; città ambigua
    dichiarata; città non trovata; timeout distinto da HTTP 5xx; JSON non valido; `giorni` fuori
    dall'intervallo;
  - in più, via `fastmcp.Client(mcp)` in memoria: il catalogo contiene i due tool con il loro
    schema, e una chiamata con errore produce `isError`.
- `tests/test_note.py`:
  - SQLite in `tmp_path`: aggiunta con ID e data; elenco ordinato e limite; elenco vuoto;
    eliminazione; ID inesistente senza cancellazioni; testo vuoto o troppo lungo; persistenza dopo
    la riapertura dell'archivio;
  - catalogo in memoria con tre tool.
- `tests/test_mcp_ponte.py`, con server stdio veri ma senza rete:
  - la discovery su `server_mcp.note` (con `NOTE_DB` in `tmp_path`) produce tool con nome, schema
    e `metadata["origine"]` presi dal server;
  - una chiamata sincrona riesce;
  - un errore del tool produce `Errore dallo strumento …`;
  - un server che non parte (modulo inesistente) produce un warning e nessun tool, senza eccezione;
  - un server che muore durante la sessione produce `Errore di collegamento MCP …`.
- `tests/test_grafo.py`: con un tool finto con `metadata={"origine": "mcp:meteo"}`, il log
  contiene origine, call_id ed esito; un risultato `Errore…` viene registrato come
  `esito=errore`.
- `tests/test_config.py`: le nuove variabili, con valori predefiniti, valori non validi e
  `SERVER_MCP` sconosciuto.
- I 71 test esistenti restano verdi; dove necessario si aggiornano le asserzioni sul formato del
  log.

### 7.2 Reali (`tests/reale/`, `PROVA_REALE=1`, LM Studio con `google/gemma-4-e2b` + rete)
- «Che tempo fa a Udine adesso?»: chiamata a `meteo_attuale`, `ToolMessage` correlato, risposta
  che cita Udine.
- «Previsioni per Tokyo nei prossimi 3 giorni»: chiamata a `previsioni_meteo` con `giorni=3`.
- Le prove reali delle note usano un `NOTE_DB` temporaneo, mai l'archivio vero. *(Scelta del
  progettista.)*
- Note: «Ricordami di consegnare il report venerdì» produce una sola `aggiungi_nota`; «Elimina la
  nota 99» produce un errore e nessuna eliminazione; dopo la riapertura della connessione la nota
  c'è ancora.
- Se la prova reale fallisce, si registra il punto esatto e il percorso non viene dichiarato
  completato.

### 7.3 Verifiche manuali documentate
- Chat da terminale con i log INFO visibili: traccia `origine=mcp:meteo call_id=… esito=ok`.
- MCP Inspector, facoltativo: `npx @modelcontextprotocol/inspector python -m server_mcp.meteo`.
- Docker: una domanda meteo e una nota, poi una seconda esecuzione in cui la nota è ancora
  presente.

## 8. Incrementi
1. Dipendenze e server meteo con i suoi test.
2. Adattatore MCP con i test stdio.
3. Configurazione, `main` e grafo (log, prompt) con i test.
4. Prova reale del meteo: **traguardo minimo della lezione**.
5. Server note, test, collegamento e prova reale.
6. Docker.
7. Documentazione: README, `COME_FUNZIONA.md`, `GUIDA_DOCKER.md`, `GUIDA_PASSO_PASSO.md`;
   CLAUDE.md (struttura con `server_mcp/`, MCP non più escluso, nuove variabili);
   `PROSSIMA_SESSIONE.md`.

## 9. Lasciato al costruttore
- Le API precise di fastmcp 4.1.6 (`Client`, trasporto stdio, `ToolError`, formato di
  `CallToolResult`): vanno verificate sulla libreria installata.
- Il testo esatto delle descrizioni dei tool e dei messaggi, nel rispetto di quanto sopra.
- La tabella WMO completa.
