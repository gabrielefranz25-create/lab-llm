# Percorso del progetto

Cosa è il progetto e tutti i passi fatti, in ordine, con skill, prompt e modalità usati.
**Da aggiornare a ogni modifica del progetto** (nuovo step, nuova lezione, cambio di metodo).

## Il progetto in breve
Un agente in Python che conversa con un modello locale (`google/gemma-4-e2b` in LM Studio) tramite un grafo LangGraph. Usa strumenti locali e MCP (orologio, meteo, note) e si avvia anche in Docker. Il codice è in `lab_llm/`; i materiali del docente sono in `materiali/` (fuori da Git); il codice della lezione 3 è in `archivio/`.

## Metodo di lavoro (vale per ogni step)

### Flusso dei branch
```
dev ──► feature branch (es. feat/router) ──► merge in dev ──► a fine sessione merge in main + tag lezione-N
```
- Ogni step o modifica parte da un feature branch creato da `dev`.
- Finito e verificato lo step, il feature branch si unisce in `dev`.
- A fine sessione (lezione chiusa) `dev` si unisce in `main` e si crea il tag `lezione-N`.
- Push solo su richiesta.

### Sequenza di skill (Superpowers)
| Fase | Skill | Prodotto |
|---|---|---|
| 1. Idea e domande | `superpowers:brainstorming` | decisioni chiarite |
| 2. Specifica | (dentro brainstorming) | `docs/superpowers/specs/AAAA-MM-GG-<nome>-design.md`, da approvare |
| 3. Piano | `superpowers:writing-plans` | `docs/superpowers/plans/AAAA-MM-GG-<nome>.md`, da approvare |
| 4. Implementazione | `superpowers:subagent-driven-development` oppure `superpowers:executing-plans` | un commit per task, con TDD (`superpowers:test-driven-development`) |
| 5. Errori | `superpowers:systematic-debugging` | causa trovata prima della correzione |
| 6. Verifica | `superpowers:verification-before-completion`, `superpowers:requesting-code-review` | test e prove reali eseguiti, revisione |
| 7. Chiusura | `superpowers:finishing-a-development-branch` | merge in `dev` |

### Modalità di Claude Code
- **Plan mode**: per capire cosa fare e decidere, senza modificare nulla.
- **Modalità normale o auto**: per eseguire un piano già approvato.
- `/clear` tra una sessione e l'altra; `docs/PROSSIMA_SESSIONE.md` contiene lo stato e il prompt per ripartire.

### Prompt di partenza per uno step (dal PDF della lezione 6)
```
Leggi il CLAUDE.md e controlla lo stato della repository.
Vogliamo realizzare lo step [numero e nome]: [obiettivo e requisiti dello step].
Il progetto attuale funziona fino allo step precedente: estendilo senza riscriverlo e non anticipare
gli step successivi.
Chiariscimi le decisioni mancanti e proponi una soluzione semplice. Distingui i test con il modello
simulato dalle prove reali con LM Studio. Le evidenze richieste devono essere verificabili nei log o
nei test.
Non iniziare l'implementazione prima dell'approvazione della specifica e del piano.
```

### Prompt per eseguire un piano approvato (usato nella lezione 4)
```
Riprendiamo il progetto in lab_llm/ seguendo lab_llm/CLAUDE.md.
Leggi la specifica approvata <spec> e il piano <piano>.
Ho riletto il piano: [lo approvo / vorrei cambiare: ...].
Esegui il piano con superpowers:executing-plans, partendo dal primo task non completato, un task
alla volta, con verifica e commit a ogni task (push solo su mia richiesta).
Spunta le caselle - [x] nel piano man mano.
```

### Comandi di verifica (PowerShell, da `lab_llm/` con il venv attivo)
- Test automatici: `python -m pytest`
- Prove reali: `$env:PROVA_REALE="1"; python -m pytest -m reale -v`
- Avvio: `python -m agente`. Docker: `docker compose build`, poi `docker compose run --rm assistente`.

## Passi fatti, in ordine

### Lezione 3 (19/10): client LM Studio. Codice in `archivio/`
1. Client minimo verso l'API compatibile con OpenAI di LM Studio (configurazione, messaggi, payload).
2. Ciclo da terminale (uscita con `esci`), streaming della risposta, gestione degli errori.
3. Cronologia mantenuta in memoria durante la sessione.

### Lezione 4 (26/10 – 9/11): agente con grafo LangGraph. Tag `lezione-4`
- Specifica `specs/2026-10-26-assistente-orologio-design.md` e piano `plans/2026-10-26-assistente-orologio.md`, eseguito con `superpowers:executing-plans` (10 task).
1. `feat(config)`: venv, impalcatura, variabili d'ambiente (`.env.example`).
2. `feat(strumenti)`: strumento `ora_corrente` con fuso esplicito.
3. `feat(grafo)`: stato, finestra di contesto, instradamento; poi i nodi `llm`, `strumenti` e `limite`.
4. `feat(llm)`: collegamento a LM Studio e verifica del modello all'avvio.
5. `feat(client)`: chat da terminale e `main`.
6. `test(reale)`: prove con il modello vero, attivate da `PROVA_REALE`.
7. `build(docker)`: Dockerfile e compose, con LM Studio sull'host (`host.docker.internal`).
8. `docs`: README, `COME_FUNZIONA.md`, `GUIDA_DOCKER.md`, `GUIDA_PASSO_PASSO.md`.
9. Revisione finale e correzioni (tool_call non JSON, Ctrl+C).
10. Aggiunta del nodo `compatta` (spec e piano `2026-11-09-nodo-compatta*`): riassunto della cronologia con un modello senza strumenti.

### Lezione 5 (9/11): strumenti MCP. Tag `lezione-5`
- Specifica `specs/2026-11-09-strumenti-mcp-design.md` e piano `plans/2026-11-09-strumenti-mcp.md` (consigliato `superpowers:subagent-driven-development`).
1. `feat(meteo)`: logica Open-Meteo e server FastMCP (`meteo_attuale`, `previsioni_meteo`).
2. `feat(config)`: variabili per server MCP, timeout e archivio delle note.
3. `feat(mcp)`: ponte sincrono `agente/mcp_ponte.py` con discovery stdio.
4. `feat(grafo)`: tool MCP nel grafo, con log di origine, `call_id` ed esito.
5. `feat(note)`: server MCP delle note su SQLite; `fix(note)`: prompt più esplicito, perché il modello diceva «salvato» senza chiamare `aggiungi_nota`.
6. `build(docker)`: server MCP nel container e volume `note`.
7. `docs`: guide aggiornate. Esiti: 122 test passati, 6 prove reali MCP passate.
8. Chiusura: merge `dev → main` e tag `lezione-5`.
9. Creati `docs/GRAFO_E_STRUMENTI.md` e questo file, da aggiornare a ogni modifica.

### Lezione 6: evolvere l'agente. Da fare
Materiale: `materiali/LLM_Lez_6.pdf`. Uno step alla volta, ciascuno con spec, piano, test, prova reale, README e commit.

| Step | Cosa | Evidenza minima | Stato |
|---|---|---|---|
| 1 | Router: in ambito o fuori ambito | domanda fuori ambito rifiutata senza passare dall'agente | da fare |
| 2 | Revisore: risposta coerente | risposta incompleta corretta entro il limite | da fare |
| 3 | Riassunto della cronologia | info del primo turno usata dopo la compressione | in parte (nodo `compatta`) |
| 4 | Resource MCP `utente://preferenze` | preferenze applicate; si cambia il file, non il codice | da fare |
| 5 | Prompt MCP `/prompts`, `/prompt` | comandi funzionanti con argomenti validati | da fare |
| 6 | Agente come servizio HTTP | stessa risposta da CLI e da API | da fare |
| 7 | Back-end + PostgreSQL | chat persistenti dopo il riavvio; OpenAPI | da fare |
| 8 | Front-end di chat | conversazione completa dal browser, errori mostrati | da fare |
| 9 | Docker Compose con 4 container | un comando avvia tutto; agente non esposto | da fare |
