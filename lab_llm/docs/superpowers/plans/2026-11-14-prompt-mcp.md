# Piano: prompt MCP come comandi della CLI (lezione 6, step 5)

Specifica: `docs/superpowers/specs/2026-11-14-prompt-mcp-design.md`. Branch `feat/prompt-mcp` da `dev`.
Modalità autonoma; TDD, un commit per task.

- [ ] **1. `feat(utente)`: prompt `spiega` e `riassumi_conversazione`** — test in `tests/test_utente.py`.
- [ ] **2. `feat(mcp)`: `elenca_prompt` e `ottieni_prompt` nel ponte** — test in `tests/test_mcp_ponte.py`.
- [ ] **3. `feat(comandi)`: `/prompts` e `/prompt` con controllo degli argomenti** — `tests/test_comandi.py`,
  poi `agente/comandi.py`.
- [ ] **4. `feat(client)`: comandi nella chat** — `rispondi` con messaggi già pronti, `avvia_sessione`
  con i comandi; test in `tests/test_client.py`.
- [ ] **5. `feat(main)`: server `utente` nella connessione e ambito** — `server_da_config` include
  `utente`; ambito predefinito con spiegazioni e riassunti; test di config e main.
- [ ] **6. `test(reale)`** — `tests/reale/test_prompt_reale.py`.
- [ ] **7. `docs`**, verifica completa e merge in `dev`.
