# Piano: tre varianti dello stesso orologio (lezione 5, blocco B)

Specifica: `../specs/2026-11-12-varianti-orologio-design.md`. TDD (test prima, poi codice), un
commit per task, branch `feat/varianti-orologio` creato da `dev`. Dopo ogni task:
`python -m pytest` tutto verde prima del commit. Eseguito in autonomia (richiesta «fai tutto»).

- [ ] **Task 1 – logica condivisa.** `tests/test_logica_orologio.py` (`descrivi_ora` con istanti
  fissi, `FusoNonValido` con il motivo comune, `adesso=None`), poi `servizio_orologio/__init__.py`,
  `servizio_orologio/logica.py`; `agente/strumenti.py` importa da lì (`calcola_ora` invariata, test
  esistenti verdi). Commit `refactor(strumenti): logica dell'orologio in un pacchetto condiviso`.
- [ ] **Task 2 – variante FastAPI.** `fastapi==0.162.5` e `uvicorn==0.54.0` in `requirements.txt`
  (installati nel venv). `tests/test_api_orologio.py` (`TestClient`: 200 con testo, 400 con
  motivo, default del fuso, `/salute`, log `api orologio:`), poi `servizio_orologio/api.py`.
  Commit `feat(orologio): servizio FastAPI dell'orologio`.
- [ ] **Task 3 – wrapper HTTP.** Test in `tests/test_strumenti.py` (`httpx.MockTransport`: ok, 400,
  500, JSON non valido, `ConnectError`, `TimeoutException`; nome, descrizione e schema uguali alla
  variante locale; metadati `origine`), poi `crea_ora_corrente_http` in `agente/strumenti.py` e
  `origine=locale` sulla variante locale. Commit `feat(strumenti): wrapper HTTP dell'orologio`.
- [ ] **Task 4 – variante FastMCP.** `tests/test_orologio_mcp.py` (catalogo in memoria con un tool
  `ora_corrente`, schema con `fuso_orario`, chiamata ok, `ToolError` su `Mars/Olympus`, default da
  `FUSO_ORARIO`), poi `server_mcp/orologio.py`. Commit `feat(orologio): server FastMCP dell'orologio`.
- [ ] **Task 5 – scelta della variante.** Test in `tests/test_config.py` (`VARIANTE_OROLOGIO`
  default/valori/errore, `OROLOGIO_API_URL`, `OROLOGIO_API_TIMEOUT`) e in `tests/test_client.py`
  (`server_da_config` con e senza server orologio; `strumenti_orologio` per variante; log
  `orologio: variante=`), poi `agente/config.py`, `agente/main.py`, `.env.example`.
  Commit `feat(config): variante dell'orologio scelta con VARIANTE_OROLOGIO`.
- [ ] **Task 6 – prove reali.** `tests/reale/test_varianti_orologio_reale.py`: le tre varianti con
  «Che ore sono a Tokyo?», errori con chiamata diretta. Eseguita con LM Studio, esiti annotati.
  Commit `test(reale): tre varianti dell'orologio con LM Studio`.
- [ ] **Task 7 – Docker.** `Dockerfile` (copia `servizio_orologio/`), `compose.yaml` (servizio
  `orologio-api` nel profilo `fastapi`, `OROLOGIO_API_URL` per l'assistente). `docker compose build`,
  prova via pipe con le varianti `locale`, `fastapi`, `mcp`. Commit `build(docker): servizio
  FastAPI dell'orologio nel profilo fastapi`.
- [ ] **Task 8 – documentazione.** `README.md`, `docs/GRAFO_E_STRUMENTI.md`,
  `docs/PERCORSO_PROGETTO.md`, `docs/COME_FUNZIONA.md`, `docs/GUIDA_DOCKER.md`,
  `docs/PROSSIMA_SESSIONE.md`, `CLAUDE.md` (struttura e comandi).
  Commit `docs: tre varianti dell'orologio del blocco B`.
- [ ] **Task 9 – verifiche e merge.** `python -m pytest`; prove reali; revisione con
  `superpowers:requesting-code-review`; merge di `feat/varianti-orologio` in `dev` (niente push).
