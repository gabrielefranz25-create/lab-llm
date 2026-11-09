# Prossima sessione

## Stato al 2026-11-09
- Lezione 4 **completata**: piano del 26/10 (task 1–10) e aggiunta del nodo `compatta`
  (specifica e piano `docs/superpowers/*/2026-11-09-nodo-compatta*.md`), richiesto dagli appunti
  del docente («nodi compact»).
- 71 test automatici verdi + 4 prove reali con `PROVA_REALE=1` (compresa la compattazione con
  `google/gemma-4-e2b`). Docker verificato (build, rete container→LM Studio, chat con input via pipe).
- Documentazione: `README.md`, `docs/COME_FUNZIONA.md`, `docs/GUIDA_DOCKER.md`,
  `docs/GUIDA_PASSO_PASSO.md`.
- Resta da provare a mano: `docker compose run --rm assistente` con la tty interattiva.
- Branch `dev`; la chiusura della lezione è il merge in `main` con il tag `lezione-4`.

## Lezione successiva
- Materiale: `materiali/LLM_Lez_5.pdf`.
- Si parte con brainstorming → specifica → piano in `docs/superpowers/`, come per la lezione 4.

## Prima di iniziare
- Aprire Claude Code nella cartella `repo-lab-llm_l4` (oppure `lab_llm`).
- Avere LM Studio acceso con `google/gemma-4-e2b` caricato.
- Avviare Docker Desktop se servono le prove in container.
