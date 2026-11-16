# Prossima sessione (handoff)

Riscritto da capo a ogni fine sessione; le versioni precedenti sono nella cronologia Git
(`git log -p docs/PROSSIMA_SESSIONE.md`), il percorso completo in `docs/PERCORSO_PROGETTO.md`.

## 1. Data e punto del corso
2026-11-16. Lezione 6 **chiusa** (step 1–9). Prossima: lezione 7, non ancora iniziata.

## 2. Fatto in questa sessione
- Branch `docs/guida-test`, unito in `dev`: nuova guida `docs/GUIDA_TEST.md` (prove a mano passo per passo:
  LM Studio, Docker Desktop, PowerShell, test automatici, chat locale, pagina nel browser, chat Docker,
  checklist, consigli su skill e token).
- Questo file trasformato in handoff a sezioni fisse; regola in `CLAUDE.md` (sezione Documentazione).
- Nessuna modifica al codice.

## 3. Esiti delle verifiche
- Ultima suite completa (2026-11-16, chiusura lezione 6): `python -m pytest` → 449 passed, 45 skipped.
- Compose (quattro container, LM Studio acceso): risposta con strumento dal proxy `/api/`, chat presente
  dopo `down`/`up`, agente fermato → 503 leggibile e nulla salvato. Prova a vista con Chrome headless.
- In questa sessione solo documenti: nessun test rieseguito.

## 4. Stato Git
- Branch di lavoro: `dev`. `main` è fermo al tag `lezione-6` (`d9872d3`); `dev` ha in più i commit della guida.
- Tag locali: `lezione-3`, `lezione-4`, `lezione-5`, `lezione-6`.
- **Non pushato**: tutta la lezione 6 e questa guida. Sul remoto `origin/main` = `lezione-5`,
  `origin/dev` = `6d5109d`, tag `lezione-3` e `lezione-5`. Quando richiesto:
  `git push origin main dev lezione-4 lezione-6` (prima, se si vuole la guida anche su `main`,
  fast-forward di `main` a `dev`).
- Feature branch locali tutti già uniti in `dev` (si possono cancellare con `git branch -d`).

## 5. Da provare a mano / aperti
- Pagina nel browser vero: `docs/GUIDA_TEST.md`, sezione 4 (conversazione, più chat, eliminazione,
  persistenza, banner con agente spento).
- `docker compose run --rm assistente` con la tastiera (sezione 5 della guida).
- Facoltativi: streaming della risposta al browser (non fatto); MCP Inspector.

## 6. Prossimo passo
Fare le prove della guida e spuntare la checklist (sezione 9). Poi, su richiesta, push. Poi lezione 7.

## 7. Prompt di ripartenza
```
Leggi CLAUDE.md e docs/PROSSIMA_SESSIONE.md, poi git status. Step: <nome> della lezione N
(materiali/LLM_Lez_N.pdf, slide X–Y). Spec e piano brevi in docs/superpowers/, branch da dev,
test con modello simulato + una prova reale mirata, documenti aggiornati solo a fine step, merge in dev, niente push.
A fine sessione riscrivi docs/PROSSIMA_SESSIONE.md (handoff).
```

## Prima di iniziare
- LM Studio acceso con `google/gemma-4-e2b` e «Serve on Local Network»; rete attiva (meteo).
- Docker Desktop avviato se servono le prove in container. PC sveglio durante le prove reali.
