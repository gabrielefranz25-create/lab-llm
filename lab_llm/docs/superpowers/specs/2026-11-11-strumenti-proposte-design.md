# Strumenti MCP delle proposte del blocco 5 (lezione 5, completamento)

Data: 2026-11-11. Fonte: `materiali/LLM_Lez_5.pdf`, slide 25 e 28 («Funzionalità da aggiungere al
proprio agente», «Catalogo locale»). Parte dal progetto attuale (lezione 5 + router della lezione 6)
senza riscriverlo. Meteo e note sono già fatti (`2026-11-09-strumenti-mcp-design.md`).

## 1. Problema
Delle sei proposte del blocco 5 mancano le tre di livello base (convertitore di unità, calcolatrice
sicura, giorni e scadenze) e quella intermedia «catalogo locale». Ognuna allena un aspetto diverso:
elenco chiuso e validazione, rifiuto di input non validi, formati e casi limite, scelta tra più tool
sullo stesso dato e risultati vuoti.

## 2. Scelte comuni
- **Un server FastMCP per proposta** in `server_mcp/` (`unita`, `calcolatrice`, `scadenze`,
  `catalogo`), sullo schema di `meteo.py` e `note.py`: logica pura testabile senza MCP, funzioni
  `@mcp.tool` sottili, errori attesi come eccezione del modulo trasformata in `ToolError` (il ponte
  produce già `Errore dallo strumento <nome>: ...`), log su stderr, nessuna scrittura su stdout,
  `mcp.run(show_banner=False)` nel `__main__`. I server non importano `agente/`.
- **Dati locali** in `server_mcp/risorse/` (non `dati/`, che è in `.gitignore` e `.dockerignore`):
  `festivita.json`, `corsi.json`. Letti a ogni chiamata, percorso relativo al modulo.
- **Nomi e descrizioni** in italiano, nella docstring (è ciò che arriva al modello tramite
  `list_tools()`); descrizioni nettamente distinguibili tra loro.
- Nessuna resource MCP (catalogo come resource è lo step 4 della lezione 6) e nessun prompt MCP.

## 3. Server e contratti

### 3.1 `unita` – `converti_unita(valore: float, da: str, a: str) -> str`
- Grandezze con elenco chiuso di unità (simboli e nomi italiani come alias, senza distinzione di
  maiuscole):
  lunghezza `mm cm m km in ft yd mi`; massa `mg g kg t oz lb`; volume `ml cl l m3 gal`;
  velocità `m/s km/h mph kn`; temperatura `C F K` (formule, non fattori).
- Risultato: `10 mi = 16.0934 km (lunghezza)`, 6 cifre significative.
- Errori: unità sconosciuta (con l'elenco delle unità ammesse per quella grandezza o di tutte),
  grandezze diverse (`km` → `kg`), valore non finito, temperatura sotto lo zero assoluto.

### 3.2 `calcolatrice` – `calcola(espressione: str) -> str`
- Valutazione con `ast.parse(..., mode="eval")` e visita esplicita dei nodi, **mai `eval`**.
  Ammessi: numeri `int`/`float` (non `bool`, non complessi), `+ - * / // % **`, segno unario,
  parentesi. `^` è accettato come potenza, `×`/`÷` come `*` e `/`.
- Limiti: espressione al massimo 200 caratteri; esponente con valore assoluto ≤ 100; risultato con
  valore assoluto ≤ 1e100.
- Risultato: `17*23 = 391` (interi senza decimali, float con al massimo 10 cifre significative).
- Errori, tutti con messaggio esplicito: espressione vuota o troppo lunga, sintassi non valida,
  elemento non consentito (nomi, chiamate, attributi, confronti…: il messaggio dice quale),
  divisione per zero, esponente o risultato troppo grande.

### 3.3 `scadenze` – due tool
- `giorni_tra(data_inizio: str, data_fine: str) -> str`: giorni di calendario e giorni lavorativi
  (lunedì–venerdì escluse le festività) tra le due date, estremo iniziale escluso.
- `aggiungi_giorni(data: str, giorni: int, solo_lavorativi: bool = False) -> str`: data risultante
  con il giorno della settimana; con `solo_lavorativi` salta sabati, domeniche e festività.
- Date in ISO `AAAA-MM-GG`; `oggi` è accettato e usa la data locale del server. `giorni` tra
  -3650 e 3650.
- Festività da `risorse/festivita.json`: `fisse` (`MM-GG` → nome, le dieci nazionali italiane) e
  `mobili` (data ISO → nome, Lunedì dell'Angelo 2024–2030). Se il calcolo tocca un anno senza
  festività mobili note, il risultato lo dichiara.
- Ogni risultato termina con «Calcolo indicativo, non normativo.».
- Errori: data non valida o nel formato sbagliato, `giorni` fuori intervallo.

### 3.4 `catalogo` – due tool sullo stesso dato
- Dati: `risorse/corsi.json`, una decina di corsi **fittizi** con `codice`, `titolo`, `sede`,
  `durata_ore`, `descrizione`.
- `cerca_corsi(testo: str, max_risultati: int = 5) -> str`: ricerca senza distinzione di maiuscole;
  un corso corrisponde se **tutte** le parole del testo compaiono in codice, titolo, sede o
  descrizione. Restituisce righe `CODICE – titolo (sede)`. Nessun risultato →
  `Nessun corso trovato per «testo».` (lista vuota dichiarata, nessun elemento inventato).
- `dettaglio_corso(codice: str) -> str`: tutti i campi del corso.
- Errori: testo di ricerca vuoto, `max_risultati` fuori da 1–10, codice inesistente.
- Le descrizioni dicono quando usare l'uno o l'altro («per sapere quali corsi ci sono» /
  «per i dettagli di un corso di cui conosci il codice»).

## 4. Collegamento all'agente
- `agente/config.py`: `SERVER_MCP_NOTI = ("meteo", "note", "unita", "calcolatrice", "scadenze",
  "catalogo")`; il default di `SERVER_MCP` resta «tutti i server noti».
- **Ambito del router**: il default diventa composto. `AMBITO_BASE` (data e ora, saluti e domande
  sull'assistente) più una frase per ogni server attivo, da `AMBITO_PER_SERVER`. Nuova funzione
  `ambito_predefinito(server)`; `AMBITO_PREDEFINITO` resta come ambito con tutti i server.
  `AMBITO_AGENTE` continua a sovrascrivere tutto. Così, togliendo un server da `SERVER_MCP`, il router
  smette di accettare le domande che lo riguardano.
- `agente/main.py` → `server_da_config`: quattro voci nuove, con le variabili comuni (`LOG_LEVEL`,
  `FASTMCP_LOG_LEVEL`). Nessuna nuova variabile d'ambiente.
- `.env.example`: elenco dei nomi validi aggiornato. `Dockerfile` copia già tutto `server_mcp/`,
  `risorse/` compresa: nessuna modifica attesa (da verificare con la build).
- Grafo invariato: il log `strumento=... origine=mcp:<server> call_id=... esito=...` vale anche per i
  nuovi tool.

## 5. Test
**Simulati** (`python -m pytest`, nessun modello né rete):
- `tests/test_unita.py`, `test_calcolatrice.py`, `test_scadenze.py`, `test_catalogo.py`: logica
  (casi validi, ogni errore della §3, casi limite: `-2**2`, `2**1000`, `__import__('os')`,
  `1/0`, 29 febbraio, ponte con festività, anno senza festività mobili, ricerca vuota) e
  catalogo/chiamata via `fastmcp.Client` in memoria, come `tests/test_note.py` (nomi dei tool,
  schema degli argomenti, `ToolError` sugli errori).
- `tests/test_config.py`: nuovi nomi validi, ambito composto dai server attivi, override.
- `tests/test_client.py` (dove già si prova `server_da_config`): le nuove voci.

**Reali** (`PROVA_REALE=1`, LM Studio): `tests/reale/test_proposte_reale.py`, un server alla volta
(stabile) più una prova con tutti i server attivi:
- «Quanto fa 17*23?» → chiamata a `calcola`, risultato 391 nel ToolMessage correlato.
- «Quanti chilometri sono 10 miglia?» → `converti_unita`.
- «Quanti giorni lavorativi ci sono tra il 2026-12-20 e il 2027-01-10?» → `giorni_tra`.
- «Che corsi ci sono a Pordenone? Dammi i dettagli del primo» → `cerca_corsi` poi `dettaglio_corso`.
- Errore controllato chiamando direttamente lo strumento (`calcola("__import__('os')")`,
  `dettaglio_corso("XX-99")`): `Errore dallo strumento ...`, nessun falso successo.
- Con tutti i server: la domanda sulla calcolatrice sceglie ancora `calcola` e il router la accetta.
  Se gemma-4-e2b sbaglia con il catalogo completo, si registra nei log e si valuta un default di
  `SERVER_MCP` più piccolo, senza dichiarare completato il percorso.

## 6. Fuori ambito
Resource e prompt MCP (lezione 6, step 4 e 5), Streamable HTTP (blocco C), varianti dell'orologio
(blocco B), persistenza della cronologia.
