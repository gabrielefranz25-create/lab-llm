# Back-end: API e salvataggio delle chat in PostgreSQL (lezione 6, step 7)

Data: 2026-11-14. Fonte: `materiali/LLM_Lez_6.pdf`, «Step 7 · Back-end: API e salvataggio delle chat».
Parte dallo step 6 (agente come servizio HTTP senza stato). Modalità autonoma: le scelte sono di Claude.

## 1. Problema
Il futuro front-end (step 8) non deve conoscere l'agente. Serve un back-end, unico punto di contatto,
che gestisca le chat, le salvi in PostgreSQL (persistenti dopo il riavvio) e inoltri le domande
all'agente (`POST /chat` dello step 6), al quale passa cronologia e riassunto salvati.

## 2. Architettura
- Pacchetto **`backend/`**, indipendente da `agente/` (avrà il proprio container allo step 9):
  - `config.py`: `DATABASE_URL` (obbligatoria, es. `postgresql://lab:lab@localhost:5432/lab`),
    `AGENTE_URL` (default `http://127.0.0.1:8000`), `AGENTE_TIMEOUT` (default 600 s),
    `BACKEND_ASCOLTO`/`BACKEND_PORTA` (default `127.0.0.1:8080`), `LOG_LEVEL`.
  - `archivio.py`: interfaccia `Archivio` con due implementazioni: `ArchivioPostgres` (psycopg 3, nuova
    dipendenza `psycopg[binary]==3.3.9`, tabelle create all'avvio se mancano) e `ArchivioMemoria` (per i
    test automatici dell'API).
  - `agente_remoto.py`: `ClienteAgente` (httpx) verso `POST {AGENTE_URL}/chat`; errori → `AgenteNonDisponibile`.
  - `api.py`: FastAPI `crea_app(archivio, agente)`; `python -m backend` avvia uvicorn.
- **Tabelle**: `chat(id serial, titolo text, creata_il timestamptz, cronologia jsonb, riassunto text)`;
  `messaggi(id serial, chat_id → chat on delete cascade, ruolo text 'utente'|'assistente', testo text,
  strumenti jsonb, creato_il timestamptz)`. La cronologia completa per l'agente (formato LangChain, con
  tool_call e note del revisore) sta in `chat.cronologia`; `messaggi` contiene solo ciò che il front-end mostra.
- **Endpoint** (tabella della slide):

  | Operazione | Endpoint | Risposta |
  |---|---|---|
  | Creare una chat | `POST /chat` (corpo facoltativo `{"titolo"}`) | 201 `{"id", "titolo", "creata_il"}` |
  | Elencare le chat | `GET /chat` | `[{"id", "titolo", "ultimo_messaggio_il"}]`, la più recente prima |
  | Leggere una chat | `GET /chat/{id}` | `{"id", "titolo", "messaggi": [{"ruolo", "testo", "strumenti", "creato_il"}]}` in ordine cronologico |
  | Inviare un messaggio | `POST /chat/{id}/messaggi` `{"testo"}` | salva la domanda, chiama l'agente, salva e restituisce `{"domanda", "risposta"}` |
  | Eliminare una chat | `DELETE /chat/{id}` | 204, messaggi rimossi a cascata |
  | Stato | `GET /stato` | database e agente raggiungibili |

- **Titolo**: «Nuova chat» finché non arriva la prima domanda, poi i primi 60 caratteri della domanda.
- **Agente non raggiungibile** (comportamento documentato): risposta 503 `{"errore": "L'agente non è
  raggiungibile …"}`; la domanda **non** viene salvata (la chat resta com'era, si può riprovare). Errore
  dell'agente (es. 503 per LM Studio spento, 400 per testo non valido) → stesso codice e messaggio
  dell'agente, nulla salvato. Chat inesistente → 404; testo vuoto → 400 (422 da FastAPI per corpo non valido).
- **Log**: `backend: chat <id> messaggio inviato all'agente -> <codice> in <s> s`, `backend: chat <id> creata|eliminata`.
- OpenAPI su `/docs` e `/openapi.json`: sarà il contratto del front-end (step 8).

## 3. Test
- Automatici (agente simulato, `ArchivioMemoria`): tutte le operazioni, titolo, ordine, 404, 400, agente
  non raggiungibile (nulla salvato), errore dell'agente inoltrato, cronologia e riassunto passati
  all'agente al turno successivo, OpenAPI.
- PostgreSQL vero (`tests/test_archivio_postgres.py`, attivati con `POSTGRES_URL`, container `postgres:16`):
  stesse operazioni dell'archivio, cascata, persistenza tra due istanze dell'archivio (riavvio).
- Reale (`PROVA_REALE=1` + `POSTGRES_URL`): back-end con PostgreSQL e agente vero in-process; chat con
  domanda che usa uno strumento; dopo il riavvio del back-end la chat c'è ancora.

## 4. Non obiettivi
Utenti e autenticazione, rinomina delle chat, paginazione, streaming, front-end (step 8), Docker (step 9).
