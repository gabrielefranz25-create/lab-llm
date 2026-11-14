# Piano: riassunto come campo dello stato (lezione 6, step 3)

Specifica: `docs/superpowers/specs/2026-11-14-riassunto-design.md`. Branch `feat/riassunto` da `dev`.
Modalità autonoma; TDD (test prima, poi codice), un commit per task.

- [ ] **1. `feat(grafo)`: campo `riassunto`** — test in `tests/test_compatta.py` riscritti sul campo
  (sotto soglia, sopra soglia con log prima/dopo, riassunto precedente sostituito, prompt di sistema,
  errore, taglio); poi `AgentState.riassunto`, `nodo_compatta` e `nodo_llm` aggiornati, `trascrivi`
  senza il caso del `SystemMessage`.
- [ ] **2. `feat(client)`: riassunto della sessione** — test in `tests/test_client.py` (riassunto
  restituito dal grafo ripassato al turno dopo); `rispondi` e `avvia_sessione` aggiornati.
- [ ] **3. `test(reale)`** — `tests/reale/test_lm_studio.py`: il nome del primo turno usato dopo la
  compressione, con il campo `riassunto` e il log prima/dopo.
- [ ] **4. `docs`** — README, `GRAFO_E_STRUMENTI.md`, `COME_FUNZIONA.md`, `PERCORSO_PROGETTO.md`,
  `PROSSIMA_SESSIONE.md`.
- [ ] **5. Verifica e merge** — `python -m pytest`, prove reali, merge in `dev`.
