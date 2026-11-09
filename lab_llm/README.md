# Assistente del laboratorio

Chat da terminale in Python che usa un grafo LangGraph esplicito per parlare con un modello servito da
**LM Studio** sull'host. Il modello può chiedere l'ora con lo strumento `ora_corrente`, che il
programma esegue davvero e che indica sempre il fuso orario (predefinito `Europe/Rome`).
La cronologia resta in memoria per la durata della sessione: non viene salvata. Quando diventa lunga,
il nodo `compatta` la fa riassumere al modello e tiene solo il riassunto e gli ultimi messaggi.

Dalla lezione 5 l'assistente usa anche strumenti **MCP**: due server locali, avviati come
sottoprocessi, che l'agente scopre da sé leggendone il catalogo. Il server `meteo` offre
`meteo_attuale` e `previsioni_meteo` (dati di Open-Meteo, serve la rete); il server `note` offre
`aggiungi_nota`, `elenca_note` ed `elimina_nota` e salva le note in un file SQLite, quindi **le note
restano** anche dopo la chiusura del programma (la cronologia della chat no).

Come funziona dentro (grafo, stato, nodi, strumenti, ponte MCP, log): [docs/COME_FUNZIONA.md](docs/COME_FUNZIONA.md).
Docker su Windows e risoluzione dei problemi: [docs/GUIDA_DOCKER.md](docs/GUIDA_DOCKER.md).

Tutti i comandi qui sotto sono stati eseguiti su Windows 11 con PowerShell 5.1, dalla cartella
`lab_llm/`, e partono da questa cartella.

## Requisiti

- Python 3.13 (launcher `py`).
- LM Studio con il server avviato (Developer → Start Server, porta 1234) e il modello caricato.
  Modello usato nelle prove: `google/gemma-4-e2b`.
- Solo per Docker: Docker Desktop con backend WSL 2.

## Installazione

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

- `requirements.txt` contiene le dipendenze di esecuzione (versioni fissate); `requirements-dev.txt`
  aggiunge `pytest`.
- Se nel terminale è attivo il venv di un altro progetto, prima dai `deactivate`.

## Configurazione (`.env`)

```powershell
Copy-Item .env.example .env
```

Poi completa `.env`. L'identificativo del modello va copiato da quello che restituisce il server:

```powershell
Invoke-RestMethod http://localhost:1234/v1/models | Select-Object -ExpandProperty data | Select-Object id
```

| Variabile | Obbligatoria | Default | Note |
|---|---|---|---|
| `LM_BASE_URL` | sì | — | `http://localhost:1234/v1`; in Docker la sovrascrive `compose.yaml` |
| `LM_MODEL` | sì | — | l'`id` restituito da `/v1/models`, per esempio `google/gemma-4-e2b` |
| `FUSO_ORARIO_PREDEFINITO` | no | `Europe/Rome` | nome IANA, validato all'avvio |
| `MAX_PASSI_STRUMENTO` | no | `3` | giri di strumento per domanda, intero ≥ 1 |
| `MAX_MESSAGGI_CONTESTO` | no | `20` | oltre questa soglia la cronologia viene riassunta; anche massimo di messaggi inviati al modello, intero ≥ 2 |
| `MESSAGGI_DA_TENERE` | no | `6` | messaggi recenti tenuti accanto al riassunto, intero ≥ 2 e < `MAX_MESSAGGI_CONTESTO` |
| `LM_TIMEOUT` | no | `60` | secondi di attesa per una risposta |
| `LOG_LEVEL` | no | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`; passa anche ai server MCP |
| `MCP_TIMEOUT` | no | `30` | secondi di attesa per l'avvio di un server MCP e per ogni sua chiamata; deve essere maggiore del doppio di `METEO_TIMEOUT` |
| `METEO_TIMEOUT` | no | `10` | secondi di attesa per ogni richiesta HTTP del server meteo (ne fa due in sequenza: geocoding e previsioni) |
| `NOTE_DB` | no | `dati/note.sqlite3` | file SQLite delle note; in Docker sta nel volume `note` (vedi sotto); un percorso relativo parte dalla cartella `lab_llm/` (directory di lavoro dei server, `CARTELLA_PROGETTO` in `agente/mcp_ponte.py`), non da quella della shell |
| `SERVER_MCP` | no | `meteo,note` | server MCP da avviare, separati da virgole; se la variabile è presente ma vuota non parte nessun server; un nome sconosciuto dà un errore di configurazione |
| `PROVA_REALE` | no | — | solo per i test con LM Studio vero (vedi sotto) |

`.env` resta fuori da Git; `.env.example` non contiene credenziali (LM Studio non usa chiavi).
Le variabili già impostate nel terminale hanno la precedenza su `.env`.

## Avvio locale

```powershell
.\.venv\Scripts\Activate.ps1
python -m agente
```

```
Assistente del laboratorio
Modello: google/gemma-4-e2b  |  Server: http://localhost:1234/v1  |  Fuso predefinito: Europe/Rome
Scrivi una domanda e premi Invio. Per uscire: esci (oppure Ctrl+C).

Tu> Che ore sono?
... INFO  agente.graph | strumento ora_corrente {} -> Fuso orario: Europe/Rome (CET, UTC+01:00) | ...
Assistente> ...
```

- Per uscire: `esci`, `exit`, `quit`, Ctrl+C oppure Ctrl+Z e Invio.
- I log vanno su stderr, la chat su stdout.
- Prova non interattiva: `"Che ore sono?`nesci" | python -m agente`.

## Avvio con Docker

LM Studio resta sull'host; il container lo raggiunge su `http://host.docker.internal:1234/v1`.

```powershell
docker compose build
docker compose run --rm assistente
```

- Si usa `run` e non `up`, perché la chat ha bisogno di uno stdin interattivo; `--rm` elimina il
  container all'uscita.
- Verificato su questo PC con LM Studio in ascolto su `0.0.0.0:1234` («Serve on Local Network»
  attivo). Il caso con l'opzione disattivata non è stato provato.
- La chat con la tty interattiva va ancora provata nel terminale; è stata verificata con l'input
  passato via pipe: `"Che ore sono?`nesci" | docker compose run --rm -T assistente`.
- Dal container la rete verso Open-Meteo funziona (verificato, codice HTTP 200):
  `docker compose run --rm assistente python -c "import httpx; print(httpx.get('https://api.open-meteo.com/v1/forecast?latitude=46&longitude=13&current=temperature_2m', timeout=10).status_code)"`.
- Prova con meteo e note (input via pipe):
  `"Che tempo fa a Udine?`nRicordami di comprare il pane`nesci" | docker compose run --rm -T assistente`
  ha chiamato `meteo_attuale` e `aggiungi_nota`. Le note stanno nel volume `note`: una seconda
  esecuzione con «Elenca le mie note» le ha ritrovate. Come svuotarle:
  [docs/GUIDA_DOCKER.md](docs/GUIDA_DOCKER.md), sezione 10.

## Test

```powershell
python -m pytest
```

Esito del 2026-11-09: `122 passed, 10 skipped` (le 10 prove reali risultano `skipped` senza `PROVA_REALE`). I test non richiedono
LM Studio: il grafo usa un modello finto e lo strumento un istante fissato.

### Prove reali con LM Studio

Richiedono LM Studio acceso con il modello di `.env` caricato. Verificano che il modello chiami davvero
`ora_corrente` (con `Asia/Tokyo` per Tokyo, e con il fuso predefinito quando non c'è un luogo).

```powershell
$env:PROVA_REALE="1"; python -m pytest -m reale -v
Remove-Item Env:PROVA_REALE
```

Esito del 2026-11-03: `3 passed` in circa un minuto.

Prove reali dei server MCP (servono anche la rete, per Open-Meteo, e il modello caricato). Le prove
sul meteo usano solo il server `meteo`, quelle sulle note solo il server `note` con un file
temporaneo (mai il tuo `dati/note.sqlite3`). Con i log in chiaro si vede ogni chiamata:

```powershell
$env:PROVA_REALE="1"; python -m pytest tests/reale/test_mcp_reale.py -v -o log_cli=true --log-cli-level=INFO
Remove-Item Env:PROVA_REALE
```

Esito del 2026-11-09: `6 passed`: meteo attuale a Udine, previsioni a 3 giorni a Tokyo, chiamata
diretta con una città inesistente; nota aggiunta («Ricordami di consegnare il report venerdì»),
«Elimina la nota 99» che dà un errore senza cancellare nulla, persistenza dopo la riapertura.

## Strumenti MCP e traccia nei log

All'avvio il programma lancia i server (`python -m server_mcp.meteo`, `python -m server_mcp.note`) e
chiede a ciascuno il suo catalogo. Il nome, la descrizione e i parametri dei tool arrivano **solo**
da lì: nell'agente non sono scritti. Su stderr compaiono, per ogni server, la riga del catalogo e,
a ogni uso, una riga `strumento=...`; l'intestazione della chat elenca gli strumenti disponibili.

```
... INFO  agente.mcp_ponte | server MCP meteo: catalogo [meteo_attuale, previsioni_meteo]
Tu> Che tempo fa a Udine?
... INFO  agente.graph | strumento=meteo_attuale origine=mcp:meteo call_id=... argomenti={"citta": "Udine"} esito=ok risultato=...
... INFO  agente.graph | strumento=elimina_nota origine=mcp:note call_id=... argomenti={"id_nota": 99} esito=errore risultato=Errore dallo strumento elimina_nota: ... nessuna nota con ID 99
```

| Campo | Significato |
|---|---|
| `strumento` | nome del tool richiesto dal modello |
| `origine` | `locale` per `ora_corrente`, `mcp:<server>` per i tool MCP |
| `call_id` | l'identificativo della tool_call (modello ↔ cronologia), non quello di JSON-RPC |
| `argomenti` | gli argomenti scelti dal modello |
| `esito` | `ok`, oppure `errore` quando il testo comincia con «Errore» |
| `risultato` | il testo che il modello legge nel `ToolMessage` (a capo sostituiti da ` | `) |

Il modello legge tre tipi di esito: il testo del risultato, `Errore dallo strumento <nome>: <messaggio>`
(il server ha rifiutato la richiesta: argomenti sbagliati, ID inesistente, città non trovata) oppure
`Errore di collegamento MCP con il server <server>: <dettaglio>` (il server non risponde o è morto).
Un server che non parte non blocca l'agente: compare un WARNING e la chat prosegue con gli altri strumenti.

I log del framework dei server sono tenuti a `WARNING` (`FASTMCP_LOG_LEVEL`), così la riga con il
banner non si mescola alla chat.

### Diagnosi per livelli

Quando «non funziona», si risale la catena dal basso: ogni livello presuppone che il precedente sia a posto.

| Livello | Sintomo | Che cosa guardare |
|---|---|---|
| 1. Processo non avviato | `WARNING ... server MCP meteo non disponibile: ...`; nessuna riga di catalogo | `MCP_TIMEOUT`, `NOTE_DB` scrivibile, errori di import nel server (`WARNING` con il dettaglio) |
| 2. Catalogo assente | il server parte ma il tool non è nel `catalogo [...]` né nell'intestazione della chat | `SERVER_MCP` (il server è nell'elenco?), decoratore `@mcp.tool` del tool; il catalogo è letto con `list_tools()` |
| 3. Chiamata assente | il modello risponde senza usare lo strumento: nessuna riga `strumento=...` | prompt di sistema e descrizione del tool: vedi il caso della nota «salvata» qui sotto |
| 4. Risultato corretto, risposta errata | la riga `strumento=... esito=ok` mostra il dato giusto, ma la risposta dice altro | il problema è nel modello (o nel prompt), non nel server: confronta `risultato=` con la risposta |

Caso incontrato: con `google/gemma-4-e2b` la richiesta «Ricordami di comprare il pane» ricevette in un
primo momento la risposta «Ho salvato la nota» **senza** che `aggiungi_nota` fosse chiamato (livello 3:
un successo falso). Si è corretto con una riga esplicita nel prompt di sistema («DEVI chiamare
`aggiungi_nota`: non dire mai che una nota è salvata se non l'ha confermato») e una descrizione del tool
più chiara. Per distinguere un salvataggio vero da una risposta plausibile servono i log: cerca
`strumento=aggiungi_nota ... esito=ok`.

### MCP Inspector (facoltativo)

Strumento ufficiale per provare un server MCP da solo, senza modello. Richiede Node.js. **Comando non
verificato in questo progetto**:

```powershell
npx @modelcontextprotocol/inspector python -m server_mcp.meteo
```

## Diagnosi

Messaggi verificati provocando ciascun errore. In tutti i casi il programma esce con codice 1, senza
traceback. (Il `WARNING ... server MCP ... non disponibile` non è un errore fatale: vedi «Diagnosi per livelli».)

| Sintomo | Causa | Soluzione |
|---|---|---|
| `Errore di configurazione: Variabile d'ambiente obbligatoria mancante: LM_BASE_URL (vedi .env.example).` | manca `.env` (o la variabile) | `Copy-Item .env.example .env` e completa i valori |
| `Errore: LM Studio non risponde su http://localhost:1234/v1 (Connection error.).` | LM Studio o il suo server spenti, oppure `LM_BASE_URL` sbagliato | avvia il server in LM Studio e controlla l'indirizzo; il messaggio arriva dopo circa 15 s di tentativi |
| `Errore: Il modello '...' non è disponibile su ...` seguito da `Modelli disponibili: ...` | `LM_MODEL` non corrisponde a un modello del server | carica il modello in LM Studio o copia in `.env` uno degli `id` elencati |
| `Errore di configurazione: FUSO_ORARIO_PREDEFINITO: fuso orario 'Roma' non riconosciuto. ...` | nome del fuso non IANA | usa un nome come `Europe/Rome` |
| `Errore di configurazione: MAX_PASSI_STRUMENTO deve essere almeno 1, non 0.` | valore numerico fuori intervallo | correggi il valore in `.env` |
| `Assistente> [errore] Non riesco a contattare LM Studio su ...` durante la chat | LM Studio si è fermato a sessione avviata | riavvia LM Studio e ripeti la domanda: la sessione e la cronologia restano valide |
| Dal container: `LM Studio non risponde su http://host.docker.internal:1234/v1` | il container non raggiunge l'host | [docs/GUIDA_DOCKER.md](docs/GUIDA_DOCKER.md), sezione 6 |
| `Errore di configurazione: SERVER_MCP contiene server sconosciuti: ...` | nome diverso da `meteo` o `note` | correggi `SERVER_MCP` in `.env` |
| `Errore di configurazione: MCP_TIMEOUT (...) deve essere maggiore del doppio di METEO_TIMEOUT (...)` | timeout incoerenti | alza `MCP_TIMEOUT` o abbassa `METEO_TIMEOUT` |

Se il modello sbaglia il fuso (per esempio passa `"Roma"`), lo strumento gli restituisce un messaggio
d'errore e il modello può riprovare entro `MAX_PASSI_STRUMENTO` giri: il programma non si ferma.

## Struttura

```
lab_llm/
├── agente/            codice: config, strumenti, mcp_ponte, graph, llm, client, main
├── server_mcp/        server MCP (processi separati): meteo.py, note.py
├── tests/             test automatici; tests/reale/ = prove con LM Studio (PROVA_REALE=1)
├── docs/              COME_FUNZIONA, GUIDA_DOCKER, GUIDA_PASSO_PASSO, PROSSIMA_SESSIONE, specifica e piano (superpowers/)
├── .env.example       variabili d'esempio (.env reale fuori da Git)
├── requirements.txt   requirements-dev.txt   pytest.ini
└── Dockerfile         compose.yaml           .dockerignore
```
