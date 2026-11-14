# L'agente come servizio HTTP (lezione 6, step 6)

Data: 2026-11-14. Fonte: `materiali/LLM_Lez_6.pdf`, «Step 6 · L'agente come servizio HTTP». Parte dagli
step 1–5. Modalità autonoma («fai tutto»): le scelte sono di Claude.

## 1. Problema
L'agente è un'applicazione da terminale: grafo, server MCP e chat vivono nello stesso processo. Per
servire un'interfaccia web (step 7–8) deve esporre un'API che riceve la conversazione e restituisce la
risposta, **senza stato** (cronologia e riassunto arrivano dal chiamante e tornano aggiornati) e senza
duplicare la logica: lo stesso grafo risponde alla CLI e alle chiamate HTTP.

## 2. Architettura
- **Nucleo** `agente/nucleo.py`: `Agente` riunisce ciò che oggi prepara `main()` (preferenze, server MCP,
  strumenti, grafo, comandi dei prompt). `avvia_agente(config)` è un context manager usato sia dalla CLI
  locale sia dal servizio. Metodi:
  - `turno(cronologia, riassunto, testo=None, prompt=None) -> Esito` (messaggi, riassunto, risposta,
    strumenti usati nel turno: nome, argomenti, esito `ok`/`errore`); `prompt=(nome, argomenti)` passa da
    `ComandiPrompt.compila` (controllo degli argomenti come allo step 5);
  - `prompt_disponibili()` (catalogo per `/prompts`), `stato()` (modello, server MCP).
  La logica del turno resta in `client.rispondi`; il nucleo aggiunge solo la traccia degli strumenti.
- **Servizio** `agente/servizio.py` (FastAPI, già tra le dipendenze): `crea_app(agente)`;
  `python -m agente.servizio` avvia uvicorn su `AGENTE_ASCOLTO:AGENTE_PORTA` (default `127.0.0.1:8000`).
  - `POST /chat` — corpo `{"messaggio": str | null, "prompt": {"nome", "argomenti"} | null,
    "cronologia": [...], "riassunto": str}` (esattamente uno tra messaggio e prompt); risposta
    `{"risposta", "cronologia", "riassunto", "strumenti": [{"nome", "argomenti", "esito"}]}`. La
    cronologia viaggia nel formato JSON di LangChain (`messages_to_dict`), così tool_call e
    `ToolMessage` restano validi tra un turno e l'altro.
  - `GET /prompts` — catalogo dei prompt MCP; `GET /stato` — `{"agente": "ok", "modello": {...},
    "server_mcp": {...}}`, 200 se il modello risponde, altrimenti 503.
  - Errori comprensibili, sempre `{"errore": "<messaggio>"}`: LM Studio non raggiungibile → 503;
    prompt o argomenti non validi, richiesta senza messaggio né prompt → 400 (422 per corpo non valido,
    da FastAPI); limite di ricorsione → 500 con messaggio. Uno strumento non disponibile resta un esito
    `errore` nella traccia (il modello lo riferisce), non un errore HTTP.
  - Log: `api: POST /chat cronologia=<n> -> 200 strumenti=[...] in <s> s`, oltre ai log del grafo.
  - Documentazione OpenAPI automatica: `/docs` e `/openapi.json`.
- **CLI client dell'API** `agente/cli.py`: `python -m agente.cli` (indirizzo da `AGENTE_URL`, default
  `http://127.0.0.1:8000`): stessa chat, stessi comandi `/prompts` e `/prompt`, ma ogni turno è una
  `POST /chat` (la CLI tiene cronologia e riassunto, il servizio no). Errori del servizio → messaggio
  `[errore] …` e la sessione continua. `python -m agente` resta la chat locale (stesso nucleo, nessun HTTP).

## 3. Configurazione
`AGENTE_ASCOLTO` (default `127.0.0.1`), `AGENTE_PORTA` (default 8000), `AGENTE_URL` per la CLI.

## 4. Test
- Automatici: nucleo con grafo finto (traccia strumenti, prompt, errori); servizio con `TestClient` e un
  agente finto (risposta e traccia, cronologia restituita e riletta, prompt valido e non valido, 503 con
  LM Studio giù, 400 senza messaggio, `/stato`, `/prompts`, `/openapi.json`); CLI con
  `httpx.MockTransport` (turni, cronologia ripassata, errori del servizio).
- Reali (`PROVA_REALE=1`): servizio vero in-process (`TestClient` su `avvia_agente`) con «Che ore sono a
  Tokyo?» → `ora_corrente` nella traccia; la stessa domanda alla chat locale dà lo stesso strumento con gli
  stessi argomenti; `/stato` 200.

## 5. Non obiettivi
Autenticazione, streaming, persistenza delle chat (step 7), Docker del servizio (step 9).
