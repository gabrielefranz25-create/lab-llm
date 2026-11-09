# Piano: nodo `compatta`

Specifica: `../specs/2026-11-09-nodo-compatta-design.md`. TDD, un commit per task, branch `dev`.

- [x] **Task 1 – configurazione.** Test in `tests/test_config.py` (default 6, override, minimo 2,
  deve essere < `MAX_MESSAGGI_CONTESTO`), poi `messaggi_da_tenere` in `agente/config.py` e in
  `.env.example`. Commit `feat(config): MESSAGGI_DA_TENERE per la compattazione`.
- [x] **Task 2 – riassuntore.** Test in `tests/test_llm.py` (nessuno strumento collegato), poi
  `_chat` + `crea_riassuntore` in `agente/llm.py`. Commit `feat(llm): modello riassuntore senza strumenti`.
- [x] **Task 3 – nodo compatta.** `tests/test_compatta.py` (casi della spec §4), poi nodo,
  prompt del riassunto, taglio e invio del riassunto nel nodo `llm` in `agente/graph.py`.
  Tutti i test precedenti devono restare verdi. Commit `feat(grafo): nodo compatta che riassume la cronologia`.
- [x] **Task 4 – avvio.** `agente/main.py` passa riassuntore e soglia; prova reale in
  `tests/reale/test_lm_studio.py`. Commit `feat(main): collega il riassuntore al grafo`.
- [x] **Task 5 – documentazione.** Diagramma Mermaid e tabella nodi in `docs/COME_FUNZIONA.md`,
  `README.md`, `docs/GUIDA_PASSO_PASSO.md`, non obiettivi della specifica del 26/10,
  `docs/PROSSIMA_SESSIONE.md`. Commit `docs: nodo compatta`.
- [ ] **Task 6 – verifiche e chiusura.** `python -m pytest`; prove reali con LM Studio;
  chat con `MAX_MESSAGGI_CONTESTO=6`; prova Docker interattiva (utente); merge `dev` → `main`,
  tag `lezione-4` (push solo su richiesta).
