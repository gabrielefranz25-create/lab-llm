# Tre varianti dello stesso orologio (lezione 5, blocco B)

Data: 2026-11-12. Fonte: `materiali/LLM_Lez_5.pdf`, blocco 4 «Confronto nell'agente» (slide 17–23).
Parte dal progetto con il blocco A completato (`2026-11-11-strumenti-proposte-design.md`) e dal
router della lezione 6 (step 1), senza riscriverli.

Modalità: l'utente ha chiesto di procedere in autonomia («fai tutto»), un blocco alla volta, con
spec e piano salvati qui e resoconto a fine blocco. Le scelte qui sotto sono di Claude.

## 1. Problema
L'orologio `ora_corrente` oggi è solo una funzione locale registrata con `@tool`. La lezione chiede
di confrontare lo stesso strumento raggiunto per tre percorsi diversi, a parità di domanda, modello
e contratto, con una sola variante esposta al modello per volta:

| Variante | Dove gira la logica | Chi scrive il contratto |
|---|---|---|
| `locale` | nel processo dell'agente | funzione `@tool` nell'agente |
| `fastapi` | servizio HTTP FastAPI separato | wrapper HTTP scritto a mano nell'agente |
| `mcp` | server FastMCP (stdio) | il server, letto con `list_tools()` |

Dopo `bind_tools` il percorso nel grafo è identico: il modello propone, il nodo `strumenti` esegue,
il risultato rientra come `ToolMessage` con lo stesso `tool_call_id`.

## 2. Contratto comune
- Nome `ora_corrente`, argomento `fuso_orario` (stringa IANA, es. `Asia/Tokyo`), facoltativo con
  default `FUSO_ORARIO_PREDEFINITO`.
- Risultato: il testo attuale di `calcola_ora` (fuso con sigla e offset, data in italiano, ora,
  ISO 8601).
- Errore osservabile: fuso non riconosciuto, senza un'ora inventata. Il testo del motivo è lo stesso
  nelle tre varianti: `fuso orario 'X' non riconosciuto. Usa un nome IANA come 'Europe/Rome'.`
  - `locale`: `Errore: <motivo>` (come oggi);
  - `fastapi`: `Errore dallo strumento ora_corrente: <motivo>` (HTTP 400);
  - `mcp`: `Errore dallo strumento ora_corrente: <motivo>` (`ToolError` dal server, già gestito dal ponte).
- Errore di trasporto distinto dal fuso non valido:
  - `fastapi`: `Errore di collegamento HTTP con il servizio orologio: <dettaglio>` (servizio spento,
    timeout, stato HTTP inatteso, JSON non valido);
  - `mcp`: `Errore di collegamento MCP con il server orologio: <dettaglio>` (già esistente).

## 3. Componenti
- **`servizio_orologio/logica.py`** (nuovo pacchetto, non dipende da `agente/`): `GIORNI`, `MESI`,
  `FusoNonValido(ValueError)`, `descrivi_ora(fuso, adesso=None) -> str` che solleva
  `FusoNonValido`. È la logica condivisa dalle tre varianti; `agente/strumenti.py` la importa e
  `calcola_ora` mantiene il comportamento attuale (stringa `Errore: ...`, warning nel log).
- **`servizio_orologio/api.py`**: app FastAPI con `GET /ora?fuso_orario=...` →
  `200 {"fuso_orario": ..., "risultato": "<testo>"}`, oppure `400 {"detail": "<motivo>"}`;
  `GET /salute` → `{"stato": "ok"}`. Avvio `python -m servizio_orologio.api` con uvicorn su
  `OROLOGIO_API_HOST` (default `127.0.0.1`) e `OROLOGIO_API_PORTA` (default `8001`). Log su stderr:
  `api orologio: fuso=<f> esito=ok|errore`.
- **`server_mcp/orologio.py`**: FastMCP «Orologio» con il tool `ora_corrente(fuso_orario)`; il
  default è letto da `FUSO_ORARIO` (passato dall'agente); descrizione uguale a quella locale;
  fuso non valido → `ToolError`. Non è in `SERVER_MCP`: lo avvia `main` solo con la variante `mcp`.
- **`agente/strumenti.py`**: oltre a `crea_ora_corrente` (variante locale, invariata) aggiunge
  `crea_ora_corrente_http(url_base, timeout, fuso_predefinito, client=None)`: tool scritto a mano con
  lo stesso nome, la stessa descrizione e lo stesso argomento della variante locale, che chiama
  `GET {url_base}/ora` con `httpx` e traduce gli errori (§2). `client` serve ai test
  (`httpx.MockTransport`). Metadati `origine`: `locale` per la locale, `http:orologio` per il wrapper
  (quella MCP resta `mcp:orologio`), così la riga di log del nodo `strumenti` mostra il percorso.
- **`agente/config.py`**: `VARIANTE_OROLOGIO` (`locale` | `fastapi` | `mcp`, default `locale`,
  valori diversi → `ErroreConfigurazione`); `OROLOGIO_API_URL` (default `http://localhost:8001`);
  `OROLOGIO_API_TIMEOUT` (secondi, default 5, come nella slide) per il wrapper.
- **`agente/main.py`**: `strumenti_orologio(config)` sceglie la variante; con `mcp`
  aggiunge `ServerMCP("orologio", ("-m", "server_mcp.orologio"), {..., "FUSO_ORARIO": ...})` in
  testa ai server da avviare e il tool arriva dal catalogo. Log di avvio:
  `orologio: variante=<v> percorso=<funzione locale | GET <url>/ora | server MCP orologio (stdio)>`.
  Se il server MCP orologio non parte l'agente prosegue senza orologio (come per gli altri server).
  Con `fastapi` il servizio non viene controllato all'avvio: se è spento, l'errore compare alla
  prima chiamata come errore di collegamento (diagnosi per livelli della slide 23).
- **Docker**: `Dockerfile` copia anche `servizio_orologio/`; `compose.yaml` aggiunge il servizio
  `orologio-api` (stessa immagine, comando `python -m servizio_orologio.api`,
  `OROLOGIO_API_HOST=0.0.0.0`) nel profilo `fastapi`; l'assistente riceve
  `OROLOGIO_API_URL=http://orologio-api:8001`.
- **Dipendenze**: `fastapi==0.162.5` (nuova, serve alla variante 02); `uvicorn==0.54.0` già presente
  come dipendenza di fastmcp, ora fissata esplicitamente perché usata dal nostro codice.

## 4. Evidenze (log)
Stessa domanda «Che ore sono a Tokyo?» con le tre varianti:
- avvio: `orologio: variante=...`;
- nodo strumenti: `strumento=ora_corrente origine=locale|http:orologio|mcp:orologio call_id=...
  argomenti={'fuso_orario': 'Asia/Tokyo'} esito=ok ...`;
- `fastapi`: riga del servizio `api orologio: fuso=Asia/Tokyo esito=ok`;
- `mcp`: riga del server `orologio: fuso=Asia/Tokyo esito=ok` (stderr del sottoprocesso).

## 5. Test
- Automatici: `descrivi_ora` e `FusoNonValido`; test esistenti di `calcola_ora` invariati; API con
  `fastapi.testclient.TestClient` (200, 400, default, `/salute`); wrapper con `httpx.MockTransport`
  (ok, 400 → errore dello strumento, 500/JSON non valido/connessione rifiutata/timeout → errore di
  collegamento, stesso nome/descrizione/schema della locale); server MCP in memoria con
  `fastmcp.Client` (catalogo, chiamata, `ToolError`); config (`VARIANTE_OROLOGIO`, URL, timeout);
  `main.strumenti_orologio` e i server avviati per variante.
- Reali (`tests/reale/test_varianti_orologio_reale.py`, `PROVA_REALE=1`): per ogni variante,
  «Che ore sono a Tokyo?» → una chiamata `ora_corrente` con `Asia/Tokyo`, `ToolMessage` correlato,
  risposta con l'ora; la variante `fastapi` avvia uvicorn come sottoprocesso su una porta libera.
  Errori con chiamata diretta: `Mars/Olympus` → errore del fuso, servizio spento → errore di
  collegamento.
- Docker: `docker compose --profile fastapi up -d orologio-api` e
  `docker compose run --rm -e VARIANTE_OROLOGIO=fastapi assistente` con una domanda via pipe.

## 6. Non obiettivi
Streamable HTTP (blocco C), resource e prompt MCP (lezione 6), più varianti attive insieme, avvio
automatico del servizio FastAPI dall'agente, autenticazione del servizio.
