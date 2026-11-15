# Docker Compose: un container per componente (lezione 6, step 9)

Data: 2026-11-15. Fonte: `materiali/LLM_Lez_6.pdf`, «Step 9 · Docker Compose: un container per componente».
Parte dagli step 6–8. Modalità autonoma: le scelte sono di Claude.

## 1. Obiettivo
`docker compose up` avvia l'applicazione completa, pronta all'uso dal browser: front-end, back-end, agente
e PostgreSQL, ognuno nel proprio container. LM Studio resta sull'host.

## 2. Servizi in `compose.yaml`
| Servizio | Immagine | Porta sull'host | Note |
|---|---|---|---|
| `frontend` | `frontend/Dockerfile` (nginx 1.27) | **8090** → 80 | file statici; `/config.js` con `backend = "/api"`; proxy `/api/` → `http://backend:8080/` (timeout 600 s) |
| `backend` | `backend/Dockerfile` (python 3.13, solo le dipendenze del back-end) | nessuna | `DATABASE_URL` composta dalle credenziali; `AGENTE_URL=http://agente:8000`; avviato a database pronto (`depends_on: db: condition: service_healthy`) |
| `agente` | `Dockerfile` esistente, `python -m agente.servizio` | **nessuna** (non esposto) | `LM_BASE_URL=http://host.docker.internal:1234/v1`; server MCP stdio nel suo container; volumi `note` e preferenze come prima |
| `db` | `postgres:16` ufficiale | nessuna | volume `postgres`; healthcheck `pg_isready` |

- Il browser raggiunge solo il front-end; le chiamate API arrivano al back-end tramite il **proxy** di nginx
  (stessa origine: niente CORS, `BACKEND_ORIGINI` vuota). Agente e back-end non hanno porte pubblicate.
- **Credenziali** `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` nel `.env` (fuori da Git), obbligatorie
  (`${VAR:?messaggio}`); `.env.example` le documenta senza valori reali. L'agente non le riceve.
- La chat da terminale nel container (`assistente`) passa al profilo `cli`, così `up` avvia esattamente i
  quattro servizi; `docker compose run --rm assistente` continua a funzionare. Profili `fastapi` e `http` invariati.

## 3. Verifiche
- Automatiche: le versioni in `backend/requirements.txt` coincidono con quelle di `requirements.txt`;
  `docker compose config` valido.
- Docker (manuali, evidenze della slide): `docker compose up -d --build` → `docker compose ps` con quattro
  servizi attivi e porta pubblicata solo dal front-end; chat via `http://localhost:8090` (proxy `/api`) con
  uno strumento, visibile nei log dell'agente; `down` e `up` → chat ancora presente; agente non raggiungibile
  dall'host.

## 4. Non obiettivi
HTTPS, utenti, immagini pubblicate su un registro, streaming.
