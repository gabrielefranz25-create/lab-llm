# Percorso del progetto

Cosa è il progetto e tutti i passi fatti, in ordine, con skill, prompt e modalità usati.
**Da aggiornare a ogni modifica del progetto** (nuovo step, nuova lezione, cambio di metodo).

## Il progetto in breve
Un agente in Python che conversa con un modello locale (`google/gemma-4-e2b` in LM Studio) tramite un grafo LangGraph. Usa strumenti locali e MCP (orologio, meteo, note, unità, calcolatrice, scadenze, catalogo) e si avvia anche in Docker. Il codice è in `lab_llm/`; i materiali del docente sono in `materiali/` (fuori da Git); il codice della lezione 3 è in `archivio/`.

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

### Lezione 5, completamento (11/11): le altre proposte del blocco 5. Branch `feat/strumenti-proposte`
- Prompt: «continuiamo il progetto, dimmi a che punto siamo e cosa dobbiamo fare; della lezione 5 dobbiamo
  implementare anche gli altri task». Scelti con una domanda: le altre proposte del blocco 5, le tre
  varianti dell'orologio e le estensioni della slide 29.
- Skill e modalità: **plan mode** per lo stato e la tabella di marcia in tre blocchi (A proposte,
  B tre varianti dell'orologio, C Streamable HTTP), approvata con ExitPlanMode; poi spec e piano del
  blocco A approvati; esecuzione con `superpowers:executing-plans` (TDD, un commit per task, registro
  in `.superpowers/sdd/`).
- Specifica `specs/2026-11-11-strumenti-proposte-design.md` e piano `plans/2026-11-11-strumenti-proposte.md`.
1. `feat(calcolatrice)`: `calcola` con `ast`, mai `eval`.
2. `feat(unita)`: `converti_unita` su elenco chiuso con alias italiani.
3. `feat(scadenze)`: `giorni_tra`, `aggiungi_giorni`, festività da `server_mcp/risorse/festivita.json`
   (cartella `risorse/` e non `dati/`, che è esclusa da Git e da Docker).
4. `feat(catalogo)`: `cerca_corsi` e `dettaglio_corso` sullo stesso `corsi.json`.
5. `feat(config)`: nuovi nomi in `SERVER_MCP` (default tutti) e ambito del router composto dai server attivi.
6. `test(reale)`: `tests/reale/test_proposte_reale.py`.
7. `docs`: guide aggiornate.
8. Revisione finale (agente revisore): `fix(strumenti)` per la ricerca con parole vuote, «oggi» nel fuso
   dell'agente e il risultato infinito del convertitore; i rilievi minori sono rimandati.
9. Prove reali e Docker (LM Studio e Docker accesi): `docker compose build` ok, nel container 11 tool
   e chat via pipe ok. In chat «15 per 12» → `calcola("15/12")`: `fix(grafo)` con l'istruzione sui conti
   in `ISTRUZIONI_PER_STRUMENTO`, aggiunta solo se `calcola` è collegato (fissa nel prompt rompeva la
   prova reale dell'orologio, verificato 4 su 4 contro 4 su 4). Esiti finali: 253 test automatici,
   17 prove reali passate.
- Esiti: `python -m pytest` → 253 passati, 17 skipped; discovery stdio dei sei server → 11 tool MCP.
- Escluse di proposito: resource del catalogo (lezione 6, step 4) e prompt MCP (step 5).

### Lezione 5, blocco B (12–13/11): tre varianti dello stesso orologio. Branch `feat/varianti-orologio`
- Prompt: «COMPLETIAMO IL Progetto», poi «fai tutto» (completare blocchi B e C e gli step 2–9 della
  lezione 6). Scelta con una domanda: **autonomo, un blocco alla volta** (spec e piano scritti e
  committati senza attendere l'approvazione, resoconto a fine blocco); LM Studio e Docker accesi.
- Skill e modalità: `superpowers:brainstorming` (interrotto dalla scelta di autonomia),
  `superpowers:executing-plans` con `superpowers:test-driven-development`, modalità auto.
- Specifica `specs/2026-11-12-varianti-orologio-design.md` e piano `plans/2026-11-12-varianti-orologio.md`.
1. `refactor(strumenti)`: logica in `servizio_orologio/logica.py` (`descrivi_ora`, `FusoNonValido`), condivisa dalle tre varianti.
2. `feat(orologio)`: servizio FastAPI `servizio_orologio/api.py` (`GET /ora`, `GET /salute`); nuove dipendenze `fastapi==0.162.5`, `uvicorn==0.54.0`.
3. `feat(strumenti)`: wrapper HTTP `crea_ora_corrente_http`, stesso contratto scritto a mano; errori di trasporto distinti dal fuso non valido.
4. `feat(orologio)`: server FastMCP `server_mcp/orologio.py`.
5. `feat(config)`: `VARIANTE_OROLOGIO` (`locale`/`fastapi`/`mcp`), `OROLOGIO_API_URL`, `OROLOGIO_API_TIMEOUT`; log `orologio: variante=… percorso=…`.
6. `test(reale)`: `tests/reale/test_varianti_orologio_reale.py` (5 prove).
7. `build(docker)`: servizio `orologio-api` nel profilo `fastapi`.
8. `docs`: guide aggiornate.
- Esiti: `python -m pytest` → 288 passati, 22 skipped; prove reali (`-m reale`) → 22 passate (5 delle varianti);
  `python -m agente` e Docker via pipe con «Che ore sono a Tokyo?» nelle tre varianti → `origine=locale`,
  `http:orologio`, `mcp:orologio`; servizio spento → `Errore di collegamento HTTP …`.

### Lezione 5, blocco C (13/11): Streamable HTTP in locale. Branch `feat/mcp-http`
- Stesso prompt e stessa modalità autonoma del blocco B.
- Specifica `specs/2026-11-13-mcp-http-design.md` e piano `plans/2026-11-13-mcp-http.md`.
1. `feat(mcp)`: `server_mcp/avvio.py` (`MCP_TRASPORTO`, porte fisse 8101–8107, percorso `/mcp`) usato dai sette server.
2. `feat(mcp)`: agente con `TRASPORTO_MCP`/`MCP_HTTP_HOST`, `ServerMCP.url`, `crea_trasporto`, log `via …`.
3. `test(mcp)`: catalogo identico tra stdio e HTTP per i sette server (`tests/test_mcp_http.py`).
4. `feat(mcp)`: `python -m server_mcp.avvia_http` avvia tutti i server HTTP.
5. `test(reale)`: `tests/reale/test_mcp_http_reale.py` (orologio e calcolatrice via HTTP).
6. `build(docker)`: servizio `server-mcp` nel profilo `http`.
7. `docs`: guide aggiornate.
8. Revisione finale (agente revisore): `fix(mcp)` perché `avvia_http` segnali un server terminato (es. porta
   occupata) e fermi gli altri, gestisca SIGTERM (`docker compose down` in 2 s) e non passi `MCP_HTTP_PORTA`;
   i sottoprocessi stdio ricevono sempre `MCP_TRASPORTO=stdio`.
- Esiti: `python -m pytest` → 319 passati, 24 skipped; prove reali (`-m reale`) → 24 passate (2 via HTTP); a mano e in
  Docker 7 cataloghi `via http://…` e chiamate a `ora_corrente` e `calcola` riuscite. In Docker la
  prima prova usava l'immagine vecchia dell'assistente (stdio): ricostruita, poi verificata.

### Lezione 6: evolvere l'agente. In corso
Materiale: `materiali/LLM_Lez_6.pdf`. Uno step alla volta, ciascuno con spec, piano, test, prova reale, README e commit.

#### Step 1 (9/11): router. Branch `feat/router`
- Prompt: quello dello step 1 in `docs/PROSSIMA_SESSIONE.md` (prompt di partenza del PDF con i requisiti del router).
- Skill e modalità: `superpowers:brainstorming` per le decisioni (ambito stretto, router che legge gli ultimi 4 messaggi, rifiuto fisso, router in errore → agente); **plan mode** per la proposta, approvata con ExitPlanMode; poi modalità auto, un task alla volta con TDD (test prima, poi codice) e un commit per task.
- Specifica `specs/2026-11-09-router-design.md` e piano `plans/2026-11-09-router.md`.
1. `docs`: specifica e piano.
2. `feat(config)`: `AMBITO_AGENTE` con ambito predefinito stretto (ora, meteo, note, saluti).
3. `feat(grafo)`: `DecisioneRouter` (categoria, motivo), nodi `router` e `rifiuto`, arco condizionale `instrada_dopo_router`, campo `categoria` nello stato, log `agente: invio …` nel nodo `llm`.
4. `feat(main)`: `crea_router` (stesso modello, `with_structured_output`, nessuno strumento) collegato al grafo.
5. `test(reale)`: `tests/reale/test_router_reale.py`.
6. `docs`: questo file, `GRAFO_E_STRUMENTI.md`, README.
- Esiti: `python -m pytest` → 132 passati, 12 skipped. Prove reali del router → 2 passate; suite reale completa (`-m reale`) → 12 passate. Prova a mano: «Che tempo fa a Roma?» e il seguito «e domani?» vanno all'agente; «Chi era Garibaldi?» → `fuori_ambito`, rifiuto, nessuna riga `agente: invio`.
- Test simulati (router finto) e prove reali sono separati: i primi dimostrano il cablaggio del grafo, le seconde che gemma-4-e2b classifica davvero.

#### Step 2 (13–14/11): revisore. Branch `feat/revisore`
- Prompt: quello di ripartenza in `docs/PROSSIMA_SESSIONE.md` («Continuiamo in autonomia dal primo step non
  fatto della lezione 6…»), poi «riprendi il progetto e completalo». Modalità autonoma («fai tutto»): spec e
  piano scritti e committati senza attendere l'approvazione.
- Skill e modalità: `superpowers:executing-plans` con `superpowers:test-driven-development`, modalità auto.
- Specifica `specs/2026-11-13-revisore-design.md` e piano `plans/2026-11-14-revisore.md`.
1. `docs`: specifica e piano.
2. `feat(config)`: `MAX_REVISIONI` (intero ≥ 0, default 2; 0 = revisore solo osservatore).
3. `feat(grafo)`: `DecisioneRevisore` (motivo, coerente), nodo `revisore` dopo `llm` senza tool_call, nota
   del revisore come `HumanMessage(name="revisore")`, campo `revisioni` nello stato,
   `instrada_dopo_revisore`, `limite_ricorsione(max_passi, max_revisioni)`.
4. `feat(main)`: `crea_revisore` (stesso modello, `with_structured_output`), client che azzera `revisioni`.
5. `test(reale)`: `tests/reale/test_revisore_reale.py` (4 prove). Con il primo prompt gemma-4-e2b
   ricontrollava i conti («15 per 12» letto come divisione) e rifiutava risposte complete (4 giudizi giusti
   su 8); con il prompt che chiede di elencare le parti e di non verificare i dati, e il motivo prima del
   verdetto nello schema, 12 su 12.
6. `docs`: guide aggiornate.
- Evidenze: test simulati per risposta coerente al primo passaggio, risposta parziale corretta, limite con
  revisore che rifiuta sempre; prova reale con bozza parziale → `revisore: coerente=no … -> agente
  (revisione 1 di 2)`, poi `ora_corrente` e `calcola`, poi `coerente=si` e risposta con 180. A mano:
  `python -m agente` con «Che ore sono a Tokyo e quanto fa 15 per 12?» → entrambe le parti, `coerente=si`.
- Esiti: `python -m pytest` → 339 passati, 28 skipped; prove reali (`-m reale`) → 26 passate e 2 errori in
  `test_mcp_http_reale.py` (server HTTP non pronti entro 20 s durante la suite lunga); rilanciate da sole → 2 passate.

#### Step 3 (14/11): riassunto come campo dello stato. Branch `feat/riassunto`
- Prompt: «riprendi il progetto e completalo», modalità autonoma.
- Skill e modalità: `superpowers:executing-plans` con `superpowers:test-driven-development`, modalità auto.
- Specifica `specs/2026-11-14-riassunto-design.md` e piano `plans/2026-11-14-riassunto.md`.
1. `docs`: specifica e piano.
2. `feat(grafo)`: campo `riassunto` nello stato, aggiornato da `compatta`; log `riassunto: messaggi prima=… dopo=…`.
3. `feat(client)`: il client conserva il riassunto e lo ripassa al grafo.
4. `test(reale)`: il nome del primo turno usato dopo la compressione, solo dal campo `riassunto`.
5. Prova a mano con soglia 6: due problemi trovati e corretti. `fix(grafo)`: il revisore leggeva «7 per 8»
   come divisione e faceva cambiare all'agente 56 in 0.875 (esempio nel prompt; sonda 8 su 8, due volte).
   `feat(grafo)`: il router riceve il riassunto (prima «Come mi chiamo e dove vivo?» era fuori ambito).
   Tentata e tolta una riga sui saluti nel prompt del revisore: peggiorava la sonda (8 su 10). Limite noto:
   su un saluto il revisore può chiedere revisioni inutili, sempre entro `MAX_REVISIONI`.
6. `docs`: guide aggiornate.
- Esiti: `python -m pytest` → 343 passati, 28 skipped; prova reale del riassunto → 1 passata; a mano, dopo due
  compressioni, «Ti chiami Gabriele e vivi a Udine.».

#### Step 4 (14/11): resource `utente://preferenze`. Branch `feat/preferenze`
- Prompt: «riprendi il progetto e completalo», poi «continua»; modalità autonoma.
- Skill e modalità: `superpowers:executing-plans` con `superpowers:test-driven-development`, modalità auto.
- Specifica `specs/2026-11-14-preferenze-design.md` e piano `plans/2026-11-14-preferenze.md`.
1. `docs`: specifica e piano.
2. `feat(utente)`: server `server_mcp/utente.py` con la sola resource; file `risorse/preferenze.json`; porta 8108.
3. `feat(mcp)`: `ConnessioneMCP.leggi_risorsa` (stdio e HTTP), errori come `ErroreMCP`.
4. `feat(preferenze)`: `agente/preferenze.py` (lettura, controllo dei campi, predefiniti), `PREFERENZE_FILE`.
5. `feat(grafo)`: preferenze in cima al prompt; via «Rispondi in italiano» e «(ora italiana)» da `PROMPT_SISTEMA`.
6. `feat(main)`: preferenze lette prima della connessione dei tool; il loro fuso vale per tutta la sessione.
7. `test(reale)`: fuso America/New_York senza chiederlo; lingua inglese e stile dettagliato. Prima versione
   della riga del prompt con URI, stile tra parentesi e fuso: «Che ore sono?» senza chiamata a
   `ora_corrente` (0 su 3, la riga senza preferenze 3 su 3); riga asciutta: 3 su 3.
   La suite reale ha poi mostrato una regressione su `calcola` via HTTP (0 su 3): `fix(grafo)` con le
   preferenze dopo «Sei l'assistente del laboratorio.», senza etichetta, e «(ora italiana)» solo con
   `Europe/Rome` (sonde con tre varianti × due domande; ora 3 su 3).
8. `build(docker)` e `docs`: file delle preferenze montato in sola lettura; guide aggiornate.
- Esiti: `python -m pytest` → 370 passati, 30 skipped; suite reale (`-m reale`) → 28 su 30 (falliti
  `calcola` via HTTP e meteo attuale, che rilanciati insieme agli altri test MCP passano 8 su 8: risposte
  non deterministiche del modello nella suite lunga, da tenere d'occhio). In Docker, senza ricostruire:
  file con `Europe/Rome` → `ora_corrente({"fuso_orario": "Europe/Rome"})`; cambiato in
  `America/New_York` → `ora_corrente({})` e risposta con l'ora di New York.

#### Step 5 (14/11): prompt MCP come comandi della CLI. Branch `feat/prompt-mcp`
- Prompt: «riprendi il progetto e completalo», «continua»; modalità autonoma.
- Skill e modalità: `superpowers:executing-plans` con `superpowers:test-driven-development`, modalità auto.
- Specifica `specs/2026-11-14-prompt-mcp-design.md` e piano `plans/2026-11-14-prompt-mcp.md`.
1. `docs`: specifica e piano.
2. `feat(utente)`: prompt `spiega` e `riassumi_conversazione` sul server `utente`.
3. `feat(mcp)`: `elenca_prompt` e `ottieni_prompt` nel ponte.
4. `feat(comandi)`: `agente/comandi.py`, controllo degli argomenti nell'host rispetto a `prompts/list`.
5. `feat(client)`: `/prompts`, `/prompt`, comandi sconosciuti; `rispondi(..., nuovi=…)`.
6. `feat(main)`: server `utente` nella connessione, `ComandiPrompt` alla chat, ambito con spiegazioni e riassunti.
7. `test(reale)`: `tests/reale/test_prompt_reale.py` (3 prove, sessione completa).
8. `docs`: guide aggiornate.
- Esiti: `python -m pytest` → 393 passati, 33 skipped; suite reale (`-m reale`) → 33 passate su 33 in 20 minuti;
  prove reali dei prompt → 3 passate; a mano con
  `python -m agente`: `/prompts` con argomenti e descrizioni, `/prompt spiega` senza argomento bloccato,
  `/aiuto` sconosciuto.

#### Step 6 (14/11): l'agente come servizio HTTP. Branch `feat/agente-http`
- Prompt: «riprendi il progetto e completalo», «continua»; modalità autonoma.
- Skill e modalità: `superpowers:executing-plans` con `superpowers:test-driven-development`, modalità auto.
- Specifica `specs/2026-11-14-agente-http-design.md` e piano `plans/2026-11-14-agente-http.md`.
1. `docs`: specifica e piano.
2. `refactor(comandi)`: `compila(nome, argomenti)` separato dal parsing della riga; `catalogo_json`.
3. `feat(nucleo)`: `Agente` senza stato (turno, traccia degli strumenti, stato), `costruisci_agente` in `main.py`.
4. `feat(servizio)`: FastAPI con `/chat`, `/prompts`, `/stato`; `AGENTE_ASCOLTO`, `AGENTE_PORTA`, `AGENTE_URL`.
5. `feat(cli)`: `python -m agente.cli`, la chat come client dell'API.
6. `test(reale)`: `tests/reale/test_servizio_reale.py`. Il confronto API/locale con «15 per 12» falliva
   perché il modello a volte non chiama `calcola` senza cronologia (in entrambi i percorsi): confronto
   fatto con «Che ore sono a Tokyo?».
7. `fix(servizio)`: logger `agente.servizio` anche con `python -m`.
8. `docs`: guide aggiornate.
- Evidenze a mano (2026-11-14): servizio avviato, `curl /stato` 200, `/openapi.json` con `/chat`, `/prompts`,
  `/stato`; `POST /chat` «Che ore sono a Tokyo?» → `ora_corrente` nella traccia e nel log; `/prompt spiega`
  senza argomento → 400; CLI remota via pipe con le stesse risposte; con `LM_BASE_URL` sbagliato `/stato` e
  `/chat` → 503 con messaggio comprensibile.

#### Step 7 (14–15/11): back-end con PostgreSQL. Branch `feat/backend`
- Prompt: «completa il progetto»; modalità autonoma (sessione interrotta dopo il codice, ripresa il 15/11).
- Skill e modalità: `superpowers:executing-plans` con `superpowers:test-driven-development`, modalità auto.
- Specifica `specs/2026-11-14-backend-design.md` e piano `plans/2026-11-14-backend.md`.
1. `docs`: specifica e piano.
2. `build(backend)`: `psycopg[binary]==3.3.9`, `backend/config.py` (`DATABASE_URL` obbligatoria).
3. `feat(backend)`: archivio PostgreSQL e in memoria, stessi test (`tests/test_archivio.py`).
4. `feat(backend)`: API FastAPI (`/chat`, `/chat/{id}`, `/chat/{id}/messaggi`, `/stato`), `ClienteAgente`, `python -m backend`.
5. `test(reale)`: `tests/reale/test_backend_reale.py`, PostgreSQL e agente veri, chat ritrovata dopo il riavvio.
6. `docs`: guide aggiornate.
- Evidenze (2026-11-15): `tests/test_archivio.py` + `tests/test_backend.py` → 28 passed con PostgreSQL 16 in
  container; prova reale `1 passed`; a mano con l'agente spento `/stato` e invio → 503, chat rimasta vuota.

#### Step 8 (15/11): front-end di chat. Branch `feat/frontend`
- Prompt: «completa il progetto»; modalità autonoma.
- Skill e modalità: `superpowers:executing-plans` con `superpowers:test-driven-development`, modalità auto.
- Specifica `specs/2026-11-15-frontend-design.md` e piano `plans/2026-11-15-frontend.md`.
1. `docs`: specifica e piano. Scelte: HTML/CSS/JS senza framework, `python -m frontend` con la libreria
   standard, indirizzo del back-end in `/config.js` da `FRONTEND_BACKEND_URL`, CORS nel back-end.
2. `feat(backend)`: CORS da `BACKEND_ORIGINI`.
3. `feat(frontend)`: server dei file statici con `config.js`.
4. `feat(frontend)`: pagina di chat; test del contratto con l'OpenAPI del back-end.
5. `docs`: guide aggiornate.
- Evidenze (2026-11-15): test automatici verdi; catena vera (agente, back-end, PostgreSQL, front-end) provata
  via HTTP con l'header `Origin` della pagina: risposta con `ora_corrente`, chat presente dopo il riavvio
  del back-end, agente spento → 503 leggibile e nulla salvato. L'estensione di Chrome non era disponibile:
  la prova a vista nel browser resta da fare.

#### Step 9 (15/11): Docker Compose con quattro container. Branch `feat/compose`
- Prompt: «completa il progetto»; modalità autonoma.
- Skill e modalità: `superpowers:executing-plans`, modalità auto.
- Specifica `specs/2026-11-15-compose-design.md` e piano `plans/2026-11-15-compose.md`.
1. `docs`: specifica e piano.
2. `build(backend)`: `backend/Dockerfile` con le sole dipendenze del back-end (`tests/test_immagini.py`).
3. `build(frontend)`: nginx con `/config.js` e proxy `/api/`.
4. `build(compose)`: `db`, `agente`, `backend`, `frontend`; `assistente` nel profilo `cli`; credenziali in `.env`.
5. `fix(frontend)`: alla prima prova `down`/`up` nginx rispondeva 502 mentre il back-end si avviava →
   healthcheck del back-end, front-end avviato a back-end pronto, messaggio chiaro per 502-504.
6. `docs`: guide aggiornate.
- Evidenze (2026-11-15): `docker compose ps` con quattro servizi e solo la porta 8090; chat via proxy con
  `calcola` nei log dell'agente; chat presente dopo `down`/`up`; agente fermato → 503 leggibile.

#### Chiusura della lezione 6 (16/11). Branch `fix/banner-nascosto`
- Prompt: «puoi finire senza pusharlo»; modalità auto, piano breve approvato in plan mode.
- Skill e modalità: `superpowers:test-driven-development` per la correzione,
  `superpowers:verification-before-completion` per la chiusura.
1. Verifica completa in Compose: `python -m pytest` → 449 passed, 45 skipped; `docker compose up -d --build`;
   via proxy «Che ore sono adesso a Tokyo?» → `ora_corrente` con `Asia/Tokyo`, ora corretta; chat presente
   dopo `down`/`up`; `docker compose stop agente` → 503 leggibile, elenco chat ancora 200, nulla salvato.
2. Prova a vista con Chrome headless (screenshot): il banner d'errore rosso compariva **vuoto** anche senza
   errori, perché `display: flex` di `.errore` prevaleva sull'attributo `hidden`.
3. `fix(frontend)`: regola `[hidden] { display: none !important; }` e test su `stile.css`; dopo la
   ricostruzione la pagina mostra «pronto» e nessun banner.
4. `docs`: questo passo e `PROSSIMA_SESSIONE.md`; `dev` → `main` con il tag `lezione-6`, senza push.

#### Guida ai test e handoff (16/11). Branch `docs/guida-test`
- Prompt: stato del progetto, guida passo passo per testarlo (clic, tasti, testo), consigli su skill e
  token, documento di handoff a ogni fine sessione; plan mode, poi modalità auto.
1. `docs`: `docs/GUIDA_TEST.md` (preparazione di LM Studio, Docker e PowerShell; test automatici; chat
   locale; pagina nel browser con persistenza ed errore; chat Docker; checklist; uso di Claude Code).
2. `docs`: `PROSSIMA_SESSIONE.md` riscritto come handoff con sezioni fisse; regola in `CLAUDE.md`.

#### Prima prova a mano con la guida (16/11). Branch `fix/meteo-dettaglio`
- Prompt: output delle prove incollato dall'utente; plan mode, poi modalità auto.
- Skill: `superpowers:test-driven-development`.
1. Esiti: chat locale e browser ok; una volta il meteo ha dato `servizio meteo non raggiungibile`
   (Open-Meteo lento, 3,5–7 s a domanda).
2. `fix(meteo)`: il messaggio indica il tipo di errore (`ReadTimeout`, `ConnectError`), test
   `test_errore_di_rete_indica_il_tipo`; riga nella tabella dei problemi di `GUIDA_TEST.md`.

| Step | Cosa | Evidenza minima | Stato |
|---|---|---|---|
| 1 | Router: in ambito o fuori ambito | domanda fuori ambito rifiutata senza passare dall'agente | fatto (`feat/router`) |
| 2 | Revisore: risposta coerente | risposta incompleta corretta entro il limite | fatto (`feat/revisore`) |
| 3 | Riassunto della cronologia | info del primo turno usata dopo la compressione | fatto (`feat/riassunto`) |
| 4 | Resource MCP `utente://preferenze` | preferenze applicate; si cambia il file, non il codice | fatto (`feat/preferenze`) |
| 5 | Prompt MCP `/prompts`, `/prompt` | comandi funzionanti con argomenti validati | fatto (`feat/prompt-mcp`) |
| 6 | Agente come servizio HTTP | stessa risposta da CLI e da API | fatto (`feat/agente-http`) |
| 7 | Back-end + PostgreSQL | chat persistenti dopo il riavvio; OpenAPI | fatto (`feat/backend`) |
| 8 | Front-end di chat | conversazione completa dal browser, errori mostrati | fatto (`feat/frontend`) |
| 9 | Docker Compose con 4 container | un comando avvia tutto; agente non esposto | fatto (`feat/compose`) |
