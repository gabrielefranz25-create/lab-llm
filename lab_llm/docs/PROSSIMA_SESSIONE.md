# Prossima sessione

## Stato al 2026-11-09 (lezione 5 chiusa)
- Lezione 5 **chiusa**: `main` portato avanti fino a `dev` (fast-forward) e tag `lezione-5`. Push non ancora fatto
  (`git push origin main dev lezione-5`, solo su richiesta).
- Ultimi esiti: `python -m pytest` → `122 passed, 10 skipped`; prove reali MCP → `6 passed`.
- Nuovi documenti da **aggiornare a ogni modifica**: `docs/GRAFO_E_STRUMENTI.md` (grafo, stato,
  strumenti) e `docs/PERCORSO_PROGETTO.md` (passi in ordine con skill, prompt e modalità).
- Flusso dei branch (in `CLAUDE.md`): feature branch da `dev` → merge in `dev` → a fine sessione
  `dev` → `main` + tag `lezione-N`.
- Resta da provare a mano: `docker compose run --rm assistente` con la tty interattiva; facoltativo
  MCP Inspector (`npx @modelcontextprotocol/inspector python -m server_mcp.meteo`).

## Stato al 2026-11-09 (lezione 6, step 1 fatto)
- Step 1 (router) completato su `feat/router`: spec `docs/superpowers/specs/2026-11-09-router-design.md`,
  piano `docs/superpowers/plans/2026-11-09-router.md`. Esiti: `132 passed, 12 skipped`; prove reali del
  router `2 passed`; prova a mano con domanda in ambito, seguito «e domani?» e domanda fuori ambito.
- Prossimo: step 2 (revisore). Il prompt di partenza è quello del PDF (vedi `docs/PERCORSO_PROGETTO.md`).

## Stato al 2026-11-11 (completamento della lezione 5, blocco A fatto)
- Branch `feat/strumenti-proposte`, **verificato ma non ancora unito in `dev`** (il merge va confermato):
  server `unita`, `calcolatrice`, `scadenze`, `catalogo`; ambito del router composto dai server attivi;
  istruzione sui conti nel prompt solo con `calcola` collegato.
- Esiti: `python -m pytest` → 253 passed, 17 skipped; prove reali (`-m reale`) → 17 passed;
  `docker compose build` ok e chat nel container via pipe ok; revisione finale fatta (rilievi minori
  rimandati, elencati in `docs/PERCORSO_PROGETTO.md`).
- Se il PC va in sospensione durante i test, le esecuzioni durano ore: tenerlo sveglio.
- Tabella di marcia della lezione 5: dopo il blocco A, blocco B (tre varianti dell'orologio: locale,
  FastAPI + wrapper HTTP, FastMCP, una attiva con `VARIANTE_OROLOGIO`) e blocco C (Streamable HTTP in
  locale, catalogo identico a stdio). Poi si riprende la lezione 6 dallo step 2 (revisore).

## Stato al 2026-11-13 (blocco B fatto)
- Blocco A unito in `dev`. Blocco B (tre varianti dell'orologio, `VARIANTE_OROLOGIO`) su
  `feat/varianti-orologio`, unito in `dev` dopo la verifica.
- Modalità concordata il 2026-11-12: **autonomia** («fai tutto»): per ogni blocco/step spec e piano
  scritti e committati senza attendere l'approvazione, resoconto a fine blocco. Push solo su richiesta.
- Blocco C (Streamable HTTP, `TRASPORTO_MCP`) fatto su `feat/mcp-http`. Lezione 5 completa.
- Ordine rimasto: lezione 6 dallo step 2 (revisore) allo step 9.
- Step 2 avviato sul branch `feat/revisore` (da `dev`): specifica scritta
  (`docs/superpowers/specs/2026-11-13-revisore-design.md`); mancano piano e implementazione.

## Stato al 2026-11-14 (step 2 fatto)
- Step 2 (revisore) su `feat/revisore`, unito in `dev`: nodo `revisore` dopo l'agente, `MAX_REVISIONI`
  (default 2), nota del revisore nella cronologia. Prove reali in `tests/reale/test_revisore_reale.py`.
- Prossimo: step 3 (riassunto come campo dello stato), poi 4–9.

## Prompt da incollare (ripartenza)
```
Leggi il CLAUDE.md e docs/PROSSIMA_SESSIONE.md e controlla lo stato della repository.
Continuiamo in autonomia dal primo step non fatto della lezione 6: spec e piano in docs/superpowers/, feature branch da dev, test, prove reali con LM Studio,
Docker, documenti aggiornati, merge in dev (niente push).
```

## Lezione 6: evolvere l'agente
Materiale: `materiali/LLM_Lez_6.pdf` e gli appunti `materiali/grafo, mcp, interfaccia ed architet.txt`,
`materiali/altre info.txt`. Nove step, uno alla volta (tabella in `docs/PERCORSO_PROGETTO.md`):
1 Router · 2 Revisore · 3 Riassunto · 4 Resource · 5 Prompt MCP · 6 Agente HTTP · 7 Back-end +
PostgreSQL · 8 Front-end · 9 Docker Compose con 4 container.

- Per ogni step servono spec e piano approvati, test con il modello simulato, prova reale, README e i due
  documenti aggiornati, e un commit (Conventional Commits).
- Lo step 3 è già in parte coperto dal nodo `compatta`. Mancano il riassunto come campo dello stato
  (non un `SystemMessage` dentro `messages`) e il log con il numero di messaggi prima e dopo.

## Prompt da incollare (step 1)
```
Leggi il CLAUDE.md e controlla lo stato della repository.
Vogliamo realizzare lo step 1 della lezione 6 (materiali/LLM_Lez_6.pdf) – Router: conversazione o
fuori ambito. L'agente ha un ambito dichiarato in configurazione; un nodo LLM prima dell'agente,
con output strutturato (categoria e motivo), decide se la domanda rientra nell'ambito; arco
condizionale: conversazione → agente, fuori ambito → nodo di rifiuto → fine. Il router non valuta
gli strumenti. Evidenze: log con categoria, motivo e passaggio all'agente; domanda fuori ambito
rifiutata senza esecuzione del nodo agente; test con router simulato per entrambi i percorsi.
Il progetto attuale funziona fino alla lezione 5: estendilo senza riscriverlo e non anticipare gli
step successivi. Lavora su un feature branch creato da dev.
Chiariscimi le decisioni mancanti e proponi una soluzione semplice. Distingui i test con il modello
simulato dalle prove reali con LM Studio. Le evidenze richieste devono essere verificabili nei log o
nei test.
Non iniziare l'implementazione prima dell'approvazione della specifica e del piano.
A fine step aggiorna docs/GRAFO_E_STRUMENTI.md e docs/PERCORSO_PROGETTO.md.
```

## Prima di iniziare
- Aprire Claude Code nella cartella `repo-lab-llm_l4` (oppure `lab_llm`).
- Avere LM Studio acceso con `google/gemma-4-e2b` caricato e la rete attiva (il meteo usa Open-Meteo).
- Avviare Docker Desktop se servono le prove in container.
