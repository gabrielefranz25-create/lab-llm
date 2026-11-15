# Piano: l'agente come servizio HTTP (lezione 6, step 6)

Specifica: `docs/superpowers/specs/2026-11-14-agente-http-design.md`. Branch `feat/agente-http` da `dev`.
Modalità autonoma; TDD, un commit per task.

- [x] **1. `refactor(comandi)`: `compila(nome, argomenti)`** separato dal parsing della riga.
- [x] **2. `feat(nucleo)`: `Agente`, `avvia_agente`, `Esito`, traccia degli strumenti** — `tests/test_nucleo.py`;
  `main.py` usa il nucleo (la chat locale non cambia comportamento).
- [x] **3. `feat(servizio)`: API FastAPI `/chat`, `/prompts`, `/stato`** — `tests/test_servizio.py`; config
  `AGENTE_ASCOLTO`, `AGENTE_PORTA`, `AGENTE_URL`.
- [x] **4. `feat(cli)`: CLI client dell'API** — `tests/test_cli.py`.
- [x] **5. `test(reale)`** — `tests/reale/test_servizio_reale.py`.
- [x] **6. `docs`**, verifica completa e merge in `dev`.
