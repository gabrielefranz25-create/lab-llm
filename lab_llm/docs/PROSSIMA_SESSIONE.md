# Prossima sessione

## Stato al 2026-11-03
- Specifica e piano **approvati**.
- Task 1–6 completati (config, strumento orologio, grafo, collegamento a LM Studio, chat da
  terminale): 55 test verdi. Prova manuale con LM Studio riuscita (gemma chiama `ora_corrente`).
  Venv creato in `lab_llm/.venv`, `.env` locale presente.
- Prossimo: **Task 7** (prove reali con LM Studio attivate da `PROVA_REALE`). Branch `dev`, commit
  locali non ancora inviati con push.

## Prima di iniziare
- Aprire Claude Code nella cartella `repo-lab-llm_l4` (oppure `lab_llm`).
- Avere LM Studio acceso con `google/gemma-4-e2b` caricato (serve dal Task 6).
- Avviare Docker Desktop (serve dal Task 8).

## Prompt da incollare
```
Riprendiamo il progetto in lab_llm/ seguendo lab_llm/CLAUDE.md.
Leggi la specifica approvata lab_llm/docs/superpowers/specs/2026-10-26-assistente-orologio-design.md
e il piano lab_llm/docs/superpowers/plans/2026-10-26-assistente-orologio.md.
Ho riletto il piano: [lo approvo / vorrei cambiare: ...].
Esegui il piano in modalità Native con superpowers:executing-plans, partendo dal primo task non
completato, un task alla volta, con verifica e commit a ogni task (push solo su mia richiesta).
Spunta le caselle - [x] nel piano man mano.
Ricordami di pulire o riavviare la sessione ai punti di pausa (dopo i task 3, 6 e 8).
```

## Per le sessioni successive
Basta sostituire la penultima riga del prompt con: «Continua dal primo task non completato del piano.»
