# Piano: resource `utente://preferenze` (lezione 6, step 4)

Specifica: `docs/superpowers/specs/2026-11-14-preferenze-design.md`. Branch `feat/preferenze` da `dev`.
Modalità autonoma; TDD, un commit per task.

- [ ] **1. `feat(utente)`: server con la resource** — `tests/test_utente.py`, poi `server_mcp/utente.py`,
  `risorse/preferenze.json`, porta 8108 e `avvia_http`.
- [ ] **2. `feat(mcp)`: `leggi_risorsa` nel ponte** — test con il server `utente` via stdio.
- [ ] **3. `feat(preferenze)`: lettura e interpretazione nell'host** — `tests/test_preferenze.py`, poi
  `agente/preferenze.py` e `PREFERENZE_FILE` in config.
- [ ] **4. `feat(grafo)`: preferenze in cima al prompt** — test nel grafo; `PROMPT_SISTEMA` senza lingua e
  stile fissi.
- [ ] **5. `feat(main)`: preferenze lette all'avvio** — test di `main`; fuso effettivo per tutta la sessione.
- [ ] **6. `test(reale)`** — `tests/reale/test_preferenze_reale.py`.
- [ ] **7. `docs`** — guide; **8.** verifica completa (suite reale) e merge in `dev`.
