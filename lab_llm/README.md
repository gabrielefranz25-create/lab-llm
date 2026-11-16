# Assistente del laboratorio

Chat da terminale in Python che usa un grafo LangGraph esplicito per parlare con un modello servito da
**LM Studio** sull'host. Il modello può chiedere l'ora con lo strumento `ora_corrente`, che il
programma esegue davvero e che indica sempre il fuso orario (predefinito `Europe/Rome`).
La cronologia resta in memoria per la durata della sessione: non viene salvata. Quando diventa lunga,
il nodo `compatta` la fa riassumere al modello e tiene solo gli ultimi messaggi; il riassunto è un campo
dello stato (`riassunto`), aggiornato a ogni compressione, che il client ripassa al grafo a ogni turno.
Nel log: `riassunto: messaggi prima=N dopo=M (riassunti K, tenuti M)`.

Dalla lezione 5 l'assistente usa anche strumenti **MCP**: due server locali, avviati come
sottoprocessi, che l'agente scopre da sé leggendone il catalogo. Il server `meteo` offre
`meteo_attuale` e `previsioni_meteo` (dati di Open-Meteo, serve la rete); il server `note` offre
`aggiungi_nota`, `elenca_note` ed `elimina_nota` e salva le note in un file SQLite, quindi **le note
restano** anche dopo la chiusura del programma (la cronologia della chat no).

Completano la lezione 5 altri quattro server, uno per ciascuna delle proposte del blocco 5:
`unita` (`converti_unita`, elenco chiuso di unità), `calcolatrice` (`calcola`, espressioni valutate con
`ast`, mai con `eval`), `scadenze` (`giorni_tra`, `aggiungi_giorni`, con festività italiane lette da
`server_mcp/risorse/festivita.json`) e `catalogo` (`cerca_corsi`, `dettaglio_corso` su
`server_mcp/risorse/corsi.json`, corsi inventati).

Il blocco B della lezione 5 confronta **tre varianti dello stesso orologio**, scelte con
`VARIANTE_OROLOGIO`: `locale` (funzione nel processo dell'agente, default), `fastapi` (servizio HTTP
`servizio_orologio/api.py` chiamato da un wrapper scritto a mano) e `mcp` (server FastMCP
`server_mcp/orologio.py`, contratto letto dal catalogo). Il contratto `ora_corrente(fuso_orario)` è
lo stesso; nel log cambia `origine=locale|http:orologio|mcp:orologio`.

Dalla lezione 6 (step 1) un nodo **router** decide, prima dell'agente, se la domanda rientra
nell'ambito dichiarato in `AMBITO_AGENTE`. Le domande fuori ambito ricevono un rifiuto fisso e
l'agente non viene eseguito. Nel log compaiono `router: categoria=… motivo=… -> agente|rifiuto` e,
solo se l'agente viene eseguito, `agente: invio N messaggi al modello`.

Dallo step 2 un nodo **revisore** controlla, dopo l'agente, che la risposta tratti tutte le parti della
domanda. Se non è coerente il motivo torna all'agente come nota nella cronologia, al massimo
`MAX_REVISIONI` volte. Nel log compare `revisore: coerente=si|no motivo=… -> fine|agente (revisione k di N)`.

Dallo step 4 lingua, stile (`sintetico` o `dettagliato`) e fuso predefinito vengono dalle **preferenze
dell'utente**: il server MCP `utente` le espone come **resource** `utente://preferenze` (il file
`server_mcp/risorse/preferenze.json`) e l'agente le legge una volta all'avvio, prima della prima domanda,
mettendole in cima al prompt di sistema. La resource non è un tool: il modello non la vede e non la
sceglie. Cambiando il file, la sessione successiva risponde di conseguenza, senza toccare il codice. Nel
log: `resource: utente://preferenze letta dal server utente: lingua=… fuso_orario=… stile=…`; se la
resource manca, un WARNING e i valori predefiniti (italiano, sintetico, `FUSO_ORARIO_PREDEFINITO`).

Dallo step 5 lo stesso server `utente` espone due **prompt MCP**, che sceglie l'utente con due comandi
della chat (MCP non prevede comandi standard: li definisce la CLI):

```
Tu> /prompts
Tu> /prompt spiega argomento="Model Context Protocol" livello=base
Tu> /prompt riassumi_conversazione stile=dettagliato
```

`/prompts` mostra nome, descrizione e argomenti (obbligatori o facoltativi) letti con `prompts/list`.
`/prompt` controlla gli argomenti **nell'host**: prompt o argomento sconosciuto, argomento obbligatorio
mancante o virgolette non chiuse bloccano la richiesta senza chiamare né il server né il modello. Se è
valida, i messaggi ottenuti con `prompts/get` entrano nella cronologia e passano dal grafo come una
domanda (router, strumenti, revisore). Nel log: `prompt: richiamato spiega argomenti={…} dal server utente:
1 messaggi` e `prompt: messaggio 1 (user): …`.

Come funziona dentro (grafo, stato, nodi, strumenti, ponte MCP, log): [docs/COME_FUNZIONA.md](docs/COME_FUNZIONA.md).
Docker su Windows e risoluzione dei problemi: [docs/GUIDA_DOCKER.md](docs/GUIDA_DOCKER.md).
Prove a mano passo per passo (dove cliccare, che cosa scrivere, che cosa deve comparire):
[docs/GUIDA_TEST.md](docs/GUIDA_TEST.md).

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
| `SERVER_MCP` | no | tutti (`meteo,note,unita,calcolatrice,scadenze,catalogo`) | server MCP da avviare, separati da virgole; se la variabile è presente ma vuota non parte nessun server; un nome sconosciuto dà un errore di configurazione |
| `AMBITO_AGENTE` | no | ora e saluti + una frase per ogni server attivo | ambito dell'agente in linguaggio naturale, letto dal router; se manca si compone con `ambito_predefinito` in `agente/config.py` (`AMBITO_PER_SERVER`), così togliendo un server da `SERVER_MCP` il router smette di accettarne le domande; compare anche nel messaggio di rifiuto |
| `PREFERENZE_FILE` | no | `server_mcp/risorse/preferenze.json` | file JSON delle preferenze (`lingua`, `fuso_orario`, `stile`) letto dal server `utente`; relativo a `lab_llm/`; il suo fuso prevale su `FUSO_ORARIO_PREDEFINITO` |
| `AGENTE_ASCOLTO`, `AGENTE_PORTA` | no | `127.0.0.1`, `8000` | indirizzo su cui ascolta `python -m agente.servizio` |
| `AGENTE_URL` | no | `http://127.0.0.1:8000` | indirizzo del servizio per `python -m agente.cli` |
| `MAX_REVISIONI` | no | `2` | revisioni per domanda chieste dal revisore, intero ≥ 0; con `0` il revisore giudica e scrive nel log ma non rimanda mai la risposta all'agente |
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

### Le tre varianti dell'orologio

```powershell
# 01 locale (default)
python -m agente
# 02 FastAPI: prima il servizio, in un altro terminale (porta 8001), poi l'agente
python -m servizio_orologio.api
$env:VARIANTE_OROLOGIO="fastapi"; python -m agente
# 03 FastMCP: l'agente avvia da sé il server orologio via stdio
$env:VARIANTE_OROLOGIO="mcp"; python -m agente
```

Verificato il 2026-11-12 con «Che ore sono a Tokyo?»: nelle tre varianti il modello chiama
`ora_corrente` con `{"fuso_orario": "Asia/Tokyo"}` e la riga del nodo strumenti riporta
`origine=locale`, `origine=http:orologio` e `origine=mcp:orologio`. Con il servizio FastAPI spento
il modello riceve `Errore di collegamento HTTP con il servizio orologio: …`, distinto dal fuso non
valido (`Errore dallo strumento ora_corrente: fuso orario 'Mars/Olympus' non riconosciuto…`).
Il servizio si prova anche da solo: `curl "http://127.0.0.1:8001/ora?fuso_orario=Asia/Tokyo"`.

## L'agente come servizio HTTP (lezione 6, step 6)

Lo stesso agente (stesso nucleo `agente/nucleo.py`, stesso grafo) risponde anche via HTTP, **senza
stato**: cronologia e riassunto arrivano con ogni richiesta e tornano aggiornati.

```powershell
python -m agente.servizio                 # API su http://127.0.0.1:8000, documentazione su /docs
python -m agente.cli                      # in un altro terminale: la chat come client dell'API
```

| Endpoint | Cosa fa |
|---|---|
| `POST /chat` | `{"messaggio": "...", "cronologia": [...], "riassunto": ""}` (oppure `"prompt": {"nome", "argomenti"}` al posto di `messaggio`) → `{"risposta", "cronologia", "riassunto", "strumenti": [{"nome", "argomenti", "esito"}]}` |
| `GET /prompts` | prompt MCP disponibili, con gli argomenti |
| `GET /stato` | agente, modello (LM Studio) e server MCP; 200 se il modello risponde, altrimenti 503 |
| `GET /docs`, `GET /openapi.json` | documentazione OpenAPI generata da FastAPI |

La cronologia viaggia nel formato JSON di LangChain (`messages_to_dict`): il chiamante la rimanda così
com'è al turno dopo. Errori sempre come `{"errore": "..."}`: LM Studio non raggiungibile → 503; prompt o
argomenti non validi, né messaggio né prompt, cronologia non valida → 400; limite di passaggi → 500.

Prova con `curl` (in PowerShell usare `curl.exe`), verificata il 2026-11-14:

```powershell
curl.exe -s http://127.0.0.1:8000/stato
curl.exe -s -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d '{\"messaggio\": \"Che ore sono a Tokyo?\"}'
```

Risposta: `"risposta": "A Tokyo sono le 06:44:10 (fuso orario Asia/Tokyo)."`, `"strumenti": [{"nome":
"ora_corrente", "argomenti": {"fuso_orario": "Asia/Tokyo"}, "esito": "ok"}]`; nel log del servizio
`strumento=ora_corrente …` e `api: POST /chat cronologia=0 -> 200 strumenti=[ora_corrente] in 68.2 s`.
Con `LM_BASE_URL` sbagliato: `/stato` → 503 con `"raggiungibile": false`, `/chat` → 503 `{"errore": "Il
modello non è raggiungibile (OpenAIConnectionError). Controlla che LM Studio sia acceso."}`.

`python -m agente` resta la chat locale, senza HTTP; `python -m agente.cli` è la stessa chat (comandi
`/prompts` e `/prompt` compresi) ma passa dall'API, all'indirizzo `AGENTE_URL`.

## Back-end delle chat con PostgreSQL (lezione 6, step 7)

Il back-end (`backend/`, `python -m backend`) è l'unico punto di contatto del front-end: salva chat e
messaggi in PostgreSQL e inoltra le domande all'agente (`POST /chat` dello step 6), al quale passa la
cronologia e il riassunto salvati. Il front-end non conosce l'agente.

```powershell
# PostgreSQL (qui un container; la porta 55432 evita conflitti con un PostgreSQL già installato)
docker run -d --name lab-postgres -e POSTGRES_USER=lab -e POSTGRES_PASSWORD=lab -e POSTGRES_DB=lab -p 55432:5432 postgres:16
python -m agente.servizio                                            # terminale 1: l'agente (porta 8000)
$env:DATABASE_URL="postgresql://lab:lab@localhost:55432/lab"; python -m backend   # terminale 2: porta 8080, /docs
```

| Operazione | Endpoint | Risposta |
|---|---|---|
| Creare una chat | `POST /chat` (corpo facoltativo `{"titolo"}`) | 201 `{"id", "titolo", "creata_il"}` |
| Elencare le chat | `GET /chat` | `[{"id", "titolo", "ultimo_messaggio_il"}]`, la più recente prima |
| Leggere una chat | `GET /chat/{id}` | `{"id", "titolo", "creata_il", "messaggi": [{"ruolo", "testo", "strumenti", "creato_il"}]}` |
| Inviare un messaggio | `POST /chat/{id}/messaggi` `{"testo"}` | `{"domanda", "risposta"}` (due messaggi) |
| Eliminare una chat | `DELETE /chat/{id}` | 204, messaggi rimossi a cascata |
| Stato | `GET /stato` | database e agente; 200 se entrambi rispondono, altrimenti 503 |

- Tabelle create all'avvio se mancano: `chat` (titolo, data, cronologia LangChain in `jsonb`, riassunto)
  e `messaggi` (solo ciò che si mostra: ruolo, testo, strumenti usati, data).
- Titolo «Nuova chat» fino alla prima domanda, poi i suoi primi 60 caratteri.
- **Agente non raggiungibile**: 503 `{"errore": "L'agente non è raggiungibile su … Riprova più tardi."}` e la
  domanda **non** viene salvata (la chat resta com'era, si può riprovare). Un errore dell'agente (per
  esempio LM Studio spento) torna con il suo messaggio: 503 resta 503, gli altri codici diventano 502.
  Chat inesistente → 404, testo vuoto → 400.
- Variabili: `DATABASE_URL` (obbligatoria), `AGENTE_URL`, `AGENTE_TIMEOUT`, `BACKEND_ASCOLTO`, `BACKEND_PORTA`
  (vedi `.env.example`). Con PostgreSQL spento `python -m backend` esce con `Errore: PostgreSQL non raggiungibile (…)`.
- Verificato il 2026-11-15 con l'agente spento: `/stato` → 503 con `"agente": {"raggiungibile": false, …}`,
  invio → 503 e chat ancora vuota; nel log `backend: chat 2 creata`. OpenAPI su
  `http://127.0.0.1:8080/docs` con `/chat`, `/chat/{chat_id}`, `/chat/{chat_id}/messaggi`, `/stato`.

## Front-end di chat nel browser (lezione 6, step 8)

Pagina statica (HTML, CSS e JavaScript, senza framework) in `frontend/static/`, servita in locale da
`python -m frontend`; parla **solo** con il back-end, il cui indirizzo arriva da `/config.js`, generato dalla
variabile `FRONTEND_BACKEND_URL` (default `http://127.0.0.1:8080`).

```powershell
python -m agente.servizio                                                         # terminale 1: agente (8000)
$env:DATABASE_URL="postgresql://lab:lab@localhost:55432/lab"; python -m backend   # terminale 2: back-end (8080)
python -m frontend                                                                # terminale 3: http://127.0.0.1:8090
```

- Colonna a sinistra: stato (verde «pronto», rosso con ciò che manca), «+ Nuova chat», elenco delle chat
  con data dell'ultimo messaggio ed eliminazione con conferma. A destra i messaggi, con gli strumenti usati
  sotto ogni risposta (`ora_corrente(fuso_orario=Asia/Tokyo)`, in rosso se in errore).
- Durante la risposta casella e pulsanti sono disabilitati e compare «L'assistente sta rispondendo… (N s)».
- Errori in un banner con il messaggio del back-end; se l'invio fallisce la domanda torna nella casella
  (il back-end non l'ha salvata) e si può riprovare.
- Il back-end ammette le origini di `BACKEND_ORIGINI` (CORS; default `http://127.0.0.1:8090,http://localhost:8090`).
- Le chiamate di `app.js` sono scritte dall'OpenAPI del back-end; `tests/test_frontend.py` controlla che ogni
  `chiama("METODO", "/percorso")` esista con quel metodo in `/openapi.json`.
- Verificato il 2026-11-15 via HTTP con l'header `Origin` del front-end (stesse chiamate della pagina):
  «Che ore sono a Tokyo?» → `ora_corrente`, risposta in 84 s; dopo il riavvio del back-end la chat c'è
  ancora; con l'agente spento l'invio dà 503 `L'agente non è raggiungibile …` (con l'header CORS, quindi la
  pagina lo può mostrare) e la chat resta con due messaggi. **Da provare a vista nel browser.**

## Applicazione completa con Docker Compose (lezione 6, step 9)

Quattro container, un comando. LM Studio resta sull'host (con «Serve on Local Network» attivo).

```powershell
# una volta: nel file .env le credenziali di PostgreSQL (vedi .env.example)
#   POSTGRES_USER=lab   POSTGRES_PASSWORD=...   POSTGRES_DB=lab
docker compose up -d --build      # poi aprire http://localhost:8090
docker compose ps                 # quattro servizi attivi
docker compose logs -f agente     # strumenti usati, log del grafo
docker compose down               # le chat restano nel volume postgres (down -v le cancella)
```

| Servizio | Cosa fa | Porta sull'host |
|---|---|---|
| `frontend` | nginx: pagina di chat, `/config.js` con `backend = "/api"`, proxy `/api/` → `backend:8080` | **8090** |
| `backend` | `python -m backend` (immagine `backend/Dockerfile`), avviato a database pronto | nessuna |
| `agente` | `python -m agente.servizio`, server MCP stdio nel container, LM Studio su `host.docker.internal` | **nessuna** |
| `db` | `postgres:16` ufficiale, dati nel volume `postgres`, healthcheck `pg_isready` | nessuna |

- Il browser parla solo con il front-end; le API passano dal proxy (stessa origine, niente CORS). Il
  front-end parte solo quando il back-end è pronto (healthcheck), così nginx non risponde 502 all'avvio.
- Con `POSTGRES_*` mancanti `docker compose` si ferma con `imposta POSTGRES_PASSWORD nel file .env`.
- La chat da terminale resta disponibile: `docker compose run --rm assistente` (profilo `cli`, non parte con `up`).

Verificato il 2026-11-15: `docker compose ps` → `agente`, `backend`, `db` (healthy), `frontend`
(`0.0.0.0:8090->80/tcp`), nessun'altra porta pubblicata; dall'host `localhost:8000` e `localhost:8080` rifiutano
la connessione. Via `http://localhost:8090/api` «Quanto fa 15 per 12?» → «15 per 12 fa 180.», nel log
dell'agente `strumento=calcola origine=mcp:calcolatrice … esito=ok` e `api: POST /chat cronologia=0 -> 200
strumenti=[calcola] in 69.4 s`. Dopo `down` e `up` la chat c'è ancora. Con `docker compose stop agente`
l'invio dà 503 `L'agente non è raggiungibile su http://agente:8000 …` e la chat resta invariata.
**La prova a vista nel browser va ancora fatta.**

## Avvio con Docker (chat da terminale)

LM Studio resta sull'host; il container lo raggiunge su `http://host.docker.internal:1234/v1`.

```powershell
docker compose build assistente
docker compose run --rm assistente
```

- Il servizio `assistente` è nel profilo `cli`: `docker compose run` lo avvia lo stesso, `up` no.
- Si usa `run` e non `up`, perché la chat ha bisogno di uno stdin interattivo; `--rm` elimina il
  container all'uscita.
- Verificato su questo PC con LM Studio in ascolto su `0.0.0.0:1234` («Serve on Local Network»
  attivo). Il caso con l'opzione disattivata non è stato provato.
- La chat con la tty interattiva va ancora provata nel terminale; è stata verificata con l'input
  passato via pipe: `"Che ore sono?`nesci" | docker compose run --rm -T assistente`.
- Dal container la rete verso Open-Meteo funziona (verificato, codice HTTP 200):
  `docker compose run --rm assistente python -c "import httpx; print(httpx.get('https://api.open-meteo.com/v1/forecast?latitude=46&longitude=13&current=temperature_2m', timeout=10).status_code)"`.
- Variante FastAPI dell'orologio nel container (servizio `orologio-api`, profilo `fastapi`):
  `docker compose --profile fastapi up -d --build orologio-api`, poi
  `docker compose run --rm -e VARIANTE_OROLOGIO=fastapi assistente`; alla fine
  `docker compose --profile fastapi down`. Variante MCP: `docker compose run --rm -e VARIANTE_OROLOGIO=mcp assistente`.
  Verificate via pipe il 2026-11-12 (anche con il servizio spento: errore di collegamento).
- Prova con meteo e note (input via pipe):
  `"Che tempo fa a Udine?`nRicordami di comprare il pane`nesci" | docker compose run --rm -T assistente`
  ha chiamato `meteo_attuale` e `aggiungi_nota`. Le note stanno nel volume `note`: una seconda
  esecuzione con «Elenca le mie note» le ha ritrovate. Come svuotarle:
  [docs/GUIDA_DOCKER.md](docs/GUIDA_DOCKER.md), sezione 10.
- Preferenze: `compose.yaml` monta `server_mcp/risorse/preferenze.json` dell'host in sola lettura, quindi
  basta modificare il file e rilanciare `docker compose run --rm assistente`, senza ricostruire l'immagine.

## Test

```powershell
python -m pytest
```

Esito del 2026-11-15, con `POSTGRES_URL` impostata (test dell'archivio anche su PostgreSQL): `457 passed, 37 skipped`
(le prove reali risultano `skipped` senza `PROVA_REALE`). I test non richiedono
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

Prove reali del router: una domanda in ambito («Che ore sono a Tokyo?») va all'agente, una fuori
ambito («Scrivimi la ricetta della carbonara») viene rifiutata senza la riga `agente: invio`:

```powershell
$env:PROVA_REALE="1"; python -m pytest tests/reale/test_router_reale.py -v -o log_cli=true --log-cli-level=INFO
Remove-Item Env:PROVA_REALE
```

Esito del 2026-11-09: `2 passed` in circa un minuto e mezzo.

Prove reali del revisore: il revisore vero giudica una risposta parziale e una completa scritte a mano a
«Che ore sono a Tokyo e quanto fa 15 per 12?»; poi il grafo vero risponde alla stessa domanda e, in una
quarta prova, parte da una bozza parziale scritta a mano che il revisore rimanda all'agente:

```powershell
$env:PROVA_REALE="1"; python -m pytest tests/reale/test_revisore_reale.py -v -o log_cli=true --log-cli-level=INFO
Remove-Item Env:PROVA_REALE
```

Prova reale del riassunto (lezione 6, step 3): soglia 6, il nome detto al primo turno è ancora usato dopo
la compressione, ma sta solo nel campo `riassunto`:

```powershell
$env:PROVA_REALE="1"; python -m pytest tests/reale/test_lm_studio.py -k compattazione -v -o log_cli=true --log-cli-level=INFO
Remove-Item Env:PROVA_REALE
```

Esito del 2026-11-14: `1 passed` con `riassunto: messaggi prima=7 dopo=1 (riassunti 6, tenuti 1)`. A mano,
con `$env:MAX_MESSAGGI_CONTESTO="6"; $env:MESSAGGI_DA_TENERE="2"; python -m agente`, dopo due compressioni
«Come mi chiamo e dove vivo?» → «Ti chiami Gabriele e vivi a Udine.».

Esito delle prove del revisore del 2026-11-14: `4 passed` in circa 3 minuti e mezzo.

Prove reali delle preferenze (step 4): file temporaneo con `America/New_York` → «Che ore sono?» chiama
`ora_corrente` senza argomenti e ottiene New York; file con lingua `inglese` e stile `dettagliato` →
risposta in inglese:

```powershell
$env:PROVA_REALE="1"; python -m pytest tests/reale/test_preferenze_reale.py -v -o log_cli=true --log-cli-level=INFO
Remove-Item Env:PROVA_REALE
```

Esito del 2026-11-14: `2 passed` in circa un minuto.

Prove reali dei prompt MCP (step 5), con router, revisore, orologio e calcolatrice veri: `/prompts` e
`/prompt spiega argomento="Model Context Protocol" livello=base`; `/prompt spiega livello=base` bloccato
senza chiamare il modello; due domande e poi `/prompt riassumi_conversazione stile=dettagliato`:

```powershell
$env:PROVA_REALE="1"; python -m pytest tests/reale/test_prompt_reale.py -v -o log_cli=true --log-cli-level=INFO
Remove-Item Env:PROVA_REALE
```

Esito del 2026-11-14: `3 passed` in circa 6 minuti; il riassunto cita l'ora di Tokyo e 180. Nella quarta prova il log mostra
`revisore: coerente=no motivo=La risposta tratta solo la prima parte della domanda (l'ora a Tokyo) e
ignora completamente la seconda parte … -> agente (revisione 1 di 2)`, poi `ora_corrente` e
`calcola("15*12")`, poi `revisore: coerente=si`.

Prove reali del servizio HTTP (step 6), in-process con `TestClient` sopra l'agente vero: due turni via
API con la cronologia restituita (`ora_corrente`, poi `calcola`), la stessa domanda all'API e al nucleo
locale con gli stessi strumenti, `/stato` e `/prompts`:

```powershell
$env:PROVA_REALE="1"; python -m pytest tests/reale/test_servizio_reale.py -v -o log_cli=true --log-cli-level=INFO
Remove-Item Env:PROVA_REALE
```

Esito del 2026-11-14: `3 passed` in circa 7 minuti.

Prova reale del back-end (step 7), con PostgreSQL vero (`POSTGRES_URL`, database di prova: viene
svuotato) e l'agente vero dietro `POST /chat`: due domande (`ora_corrente`, `calcola`), poi un nuovo
archivio e una nuova app (il riavvio) ritrovano la chat con i quattro messaggi:

```powershell
docker run -d --name lab-postgres-test -e POSTGRES_USER=lab -e POSTGRES_PASSWORD=lab -e POSTGRES_DB=lab -p 55432:5432 postgres:16
$env:POSTGRES_URL="postgresql://lab:lab@localhost:55432/lab"
$env:PROVA_REALE="1"; python -m pytest tests/reale/test_backend_reale.py -v -o log_cli=true --log-cli-level=INFO
Remove-Item Env:PROVA_REALE
```

Esito del 2026-11-15: `1 passed` in circa 5 minuti; nel log `backend: chat 1 messaggio inviato all'agente -> 200
in 119.9 s strumenti=[ora_corrente]`. Con `POSTGRES_URL` impostata anche `tests/test_archivio.py` esegue gli
stessi test dell'archivio in memoria su PostgreSQL vero (cascata e persistenza tra due istanze compresi).

Prove reali dei server delle proposte: una domanda per server (calcolo, conversione, giorni lavorativi,
ricerca e poi dettaglio di un corso), un errore controllato per server con chiamata diretta e una
prova con **tutti** i server e il router, per vedere se il modello sceglie ancora `calcola` con il
catalogo completo:

```powershell
$env:PROVA_REALE="1"; python -m pytest tests/reale/test_proposte_reale.py -v -o log_cli=true --log-cli-level=INFO
Remove-Item Env:PROVA_REALE
```

Esito del 2026-11-11: `5 passed` in circa 4 minuti. Suite reale completa (`-m reale`): `17 passed` in
circa 9 minuti. In chat «Quanto fa 15 per 12?» → `calcola("15*12")` = 180 (vedi sotto, prompt di sistema).

## Strumenti MCP e traccia nei log

All'avvio il programma lancia i server scelti in `SERVER_MCP` (`python -m server_mcp.meteo`, `python -m server_mcp.note`, …) e
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

### Streamable HTTP al posto di stdio (blocco C)

Gli stessi server possono girare come servizi HTTP locali (porte 8101–8107, solo `127.0.0.1`):

```powershell
# terminale 1: avvia i server di SERVER_MCP (default tutti) più l'orologio, Ctrl+C per fermarli
python -m server_mcp.avvia_http
# terminale 2: l'agente si collega con un URL invece di avviare sottoprocessi
# (VARIANTE_OROLOGIO=mcp: anche l'orologio passa da HTTP, altrimenti resta la funzione locale)
$env:TRASPORTO_MCP="http"; $env:VARIANTE_OROLOGIO="mcp"; python -m agente
```

Il log dell'agente mostra `trasporto MCP: http` e `server MCP <nome>: catalogo [...] via
http://127.0.0.1:<porta>/mcp`. Il catalogo è identico a quello via stdio (nome, descrizione e schema di
ogni tool): lo verifica `tests/test_mcp_http.py` per tutti e sette i server. Se un server HTTP è
spento: `server MCP <nome> non disponibile: …` e l'agente prosegue senza quel server; se si spegne
durante la sessione, le chiamate restituiscono `Errore di collegamento MCP …` finché non si riavvia
l'agente (come con stdio). Se un server non parte (per esempio porta occupata) `avvia_http` lo
segnala (`server <nome> terminato (codice N)`) e ferma gli altri.
Un singolo server: `$env:MCP_TRASPORTO="http"; python -m server_mcp.calcolatrice` (porta 8104).
Verificato il 2026-11-13 con «Che ore sono a Tokyo?» e «Quanto fa 15 per 12?», anche in Docker:
`docker compose --profile http up -d --build server-mcp`, poi
`docker compose run --rm -e TRASPORTO_MCP=http -e VARIANTE_OROLOGIO=mcp assistente` (dopo `docker compose build`, perché anche
l'immagine dell'assistente deve essere aggiornata).

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
| `Errore di configurazione: SERVER_MCP contiene server sconosciuti: ...` | nome diverso da `meteo`, `note`, `unita`, `calcolatrice`, `scadenze`, `catalogo` | correggi `SERVER_MCP` in `.env` |
| `Errore di configurazione: MCP_TIMEOUT (...) deve essere maggiore del doppio di METEO_TIMEOUT (...)` | timeout incoerenti | alza `MCP_TIMEOUT` o abbassa `METEO_TIMEOUT` |

Se il modello sbaglia il fuso (per esempio passa `"Roma"`), lo strumento gli restituisce un messaggio
d'errore e il modello può riprovare entro `MAX_PASSI_STRUMENTO` giri: il programma non si ferma.

## Struttura

```
lab_llm/
├── agente/            codice: config, strumenti, mcp_ponte, preferenze, comandi, graph, llm, client, nucleo,
│                      main (chat locale), servizio (API HTTP), cli (chat client dell'API)
├── backend/           back-end delle chat (step 7): config, archivio (PostgreSQL), agente_remoto, api
├── compose.yaml       quattro servizi (frontend, backend, agente, db) + profili cli, fastapi, http
├── frontend/          front-end di chat (step 8): static/ (index.html, stile.css, app.js), __main__ = server locale,
│                      Dockerfile + nginx.conf.template (step 9)
├── servizio_orologio/ logica condivisa dell'orologio (logica.py) e servizio FastAPI (api.py)
├── server_mcp/        server MCP (processi separati): meteo, note, unita, calcolatrice, scadenze, catalogo, orologio,
│                      utente (resource utente://preferenze); avvio.py = stdio o Streamable HTTP;
│                      avvia_http.py = tutti i server in HTTP; risorse/ = festivita.json, corsi.json, preferenze.json
├── tests/             test automatici; tests/reale/ = prove con LM Studio (PROVA_REALE=1)
├── docs/              COME_FUNZIONA, GUIDA_DOCKER, GUIDA_PASSO_PASSO, GUIDA_TEST, PROSSIMA_SESSIONE, specifica e piano (superpowers/)
├── .env.example       variabili d'esempio (.env reale fuori da Git)
├── requirements.txt   requirements-dev.txt   pytest.ini
└── Dockerfile         compose.yaml           .dockerignore
```
