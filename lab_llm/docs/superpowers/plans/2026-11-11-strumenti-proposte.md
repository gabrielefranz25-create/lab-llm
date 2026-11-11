# Piano: strumenti MCP delle proposte del blocco 5 (lezione 5, completamento)

Specifica: `../specs/2026-11-11-strumenti-proposte-design.md`. TDD (test prima, poi codice), un
commit per task, branch `feat/strumenti-proposte` creato da `dev`. Dopo ogni task:
`python -m pytest` tutto verde prima del commit.

- [ ] **Task 1 – calcolatrice.** `tests/test_calcolatrice.py` (casi validi, `^`/`×`/`÷`, segno,
  ogni errore della spec §3.2, `__import__('os')`, `2**1000`, `1/0`; catalogo e `ToolError` via
  `fastmcp.Client` in memoria), poi `server_mcp/calcolatrice.py`.
  Commit `feat(calcolatrice): server MCP con valutazione sicura delle espressioni`.
- [ ] **Task 2 – convertitore di unità.** `tests/test_unita.py` (fattori, alias italiani, temperatura,
  grandezze diverse, unità sconosciuta, sotto lo zero assoluto, valore non finito; catalogo in
  memoria), poi `server_mcp/unita.py`. Commit `feat(unita): server MCP per convertire unità di misura`.
- [ ] **Task 3 – giorni e scadenze.** `server_mcp/risorse/festivita.json`, `tests/test_scadenze.py`
  (`giorni_tra`, `aggiungi_giorni` con e senza lavorativi, ponte con festività, 29 febbraio, `oggi`
  con data fissata, anno senza festività mobili, formati errati, intervallo di `giorni`), poi
  `server_mcp/scadenze.py`. Commit `feat(scadenze): server MCP per giorni e scadenze con festività locali`.
- [ ] **Task 4 – catalogo locale.** `server_mcp/risorse/corsi.json` (corsi fittizi),
  `tests/test_catalogo.py` (ricerca a più parole, maiuscole, nessun risultato dichiarato,
  `max_risultati` fuori intervallo, dettaglio, codice inesistente; catalogo in memoria con due tool
  distinti), poi `server_mcp/catalogo.py`. Commit `feat(catalogo): server MCP con ricerca e dettaglio dei corsi`.
- [ ] **Task 5 – collegamento all'agente.** Test in `tests/test_config.py` (nuovi nomi in
  `SERVER_MCP`, ambito composto dai server attivi, `AMBITO_AGENTE` che sovrascrive) e in
  `tests/test_client.py` (`server_da_config` con le nuove voci), poi `agente/config.py`
  (`SERVER_MCP_NOTI`, `AMBITO_BASE`, `AMBITO_PER_SERVER`, `ambito_predefinito`), `agente/main.py`,
  `.env.example`. Prova a mano dei cataloghi: `python -m agente` e riga `Strumenti: ...`.
  Commit `feat(config): nuovi server MCP e ambito del router composto dai server attivi`.
- [ ] **Task 6 – prove reali.** `tests/reale/test_proposte_reale.py` (marker `reale`, riusa
  `crea_chiedi` e `chiamate` di `test_mcp_reale.py`): un server alla volta, errori controllati con
  chiamata diretta, una prova con tutti i server. Eseguita con LM Studio; esiti annotati anche se
  qualcuna fallisce. Commit `test(reale): strumenti delle proposte con LM Studio`.
- [ ] **Task 7 – Docker.** `docker compose build` e `docker compose run --rm assistente` con una
  domanda per server; modifiche a `Dockerfile`/`compose.yaml` solo se servono.
  Commit `build(docker): ...` solo se è cambiato qualcosa.
- [ ] **Task 8 – documentazione.** `README.md`, `docs/GRAFO_E_STRUMENTI.md` (tabella strumenti),
  `docs/PERCORSO_PROGETTO.md` (passi, skill, modalità), `docs/COME_FUNZIONA.md` se elenca i server,
  `docs/PROSSIMA_SESSIONE.md`, `CLAUDE.md` (struttura: elenco dei server).
  Commit `docs: strumenti delle proposte del blocco 5`.
- [ ] **Task 9 – verifiche e merge.** `python -m pytest`; prove reali; chat a mano (una domanda per
  server, una fuori ambito); revisione con `superpowers:requesting-code-review`; merge
  `feat/strumenti-proposte` → `dev`. Push solo su richiesta. Poi blocco B (varianti dell'orologio).
