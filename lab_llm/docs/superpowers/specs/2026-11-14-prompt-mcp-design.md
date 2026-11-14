# Prompt MCP come comandi della CLI (lezione 6, step 5)

Data: 2026-11-14. Fonte: `materiali/LLM_Lez_6.pdf`, «Step 5 · Prompt: comandi riusabili nella CLI».
Parte dagli step 1–4. Modalità autonoma («fai tutto»): le scelte sono di Claude.

## 1. Problema
Un prompt MCP è un modello di istruzioni con argomenti, salvato sul server e richiamato **dall'utente**
(non dal modello, non dall'host da solo). MCP non prevede comandi standard: li definisce la CLI. Il
prompt richiamato deve passare dal grafo come ogni domanda (router, strumenti, revisore).

## 2. Comportamento
- **Server**: i due prompt stanno sul server `utente` (quello della resource delle preferenze):
  - `spiega(argomento: str, livello: str = "base")`: «Spiegami «<argomento>» a livello <livello>…»,
    con indicazioni diverse per `base`, `intermedio`, `avanzato` (un altro livello → errore del server);
  - `riassumi_conversazione(stile: str = "sintetico")`: chiede di riassumere i turni della sessione
    corrente (che il grafo ha nella cronologia e nel riassunto), `sintetico` o `dettagliato`.
- **Connessione**: dallo step 5 il server `utente` entra anche nella connessione dei tool (nessun tool nel
  catalogo, quindi nulla cambia per `bind_tools`); la lettura delle preferenze all'avvio resta quella
  dello step 4.
- **Ponte**: `ConnessioneMCP.elenca_prompt(server)` (`prompts/list`) e
  `ConnessioneMCP.ottieni_prompt(server, nome, argomenti)` (`prompts/get`) → lista di `(ruolo, testo)`.
- **Host** (`agente/comandi.py`, `ComandiPrompt`): all'avvio della chat legge `prompts/list` una volta
  (log INFO `prompt: catalogo del server utente [spiega, riassumi_conversazione]`). Comandi della CLI:
  - `/prompts`: per ogni prompt nome, descrizione e argomenti (con «obbligatorio» o «facoltativo»).
  - `/prompt nome arg=valore arg2="valore con spazi"` (sintassi `shlex`): controllo **nell'host** rispetto
    a `prompts/list`: prompt sconosciuto, argomento sconosciuto, argomento obbligatorio mancante, token
    senza `=` → messaggio d'errore, **nessuna chiamata al server né al modello**. Se valido: `prompts/get`,
    i messaggi ottenuti (user → `HumanMessage`, assistant → `AIMessage`) si aggiungono alla cronologia e
    il grafo parte come per una domanda. Errore del server (es. livello non valido) → messaggio, nessun
    modello chiamato.
  - Log INFO `prompt: richiamato <nome> argomenti=<json> dal server utente: <n> messaggi` e una riga
    per messaggio `prompt: messaggio <i> (<ruolo>): <testo>`.
  - Senza server `utente` (non disponibile): `/prompts` e `/prompt` rispondono che i prompt non sono
    disponibili.
- **Client**: `rispondi` accetta, oltre al testo, una lista di messaggi già pronti (quelli del prompt).
  Le righe che iniziano con `/` non vanno mai al modello come testo: un comando sconosciuto dà un errore.
- **Ambito del router**: l'ambito predefinito aggiunge «spiegazioni di concetti di informatica e di
  intelligenza artificiale, riassunti della conversazione», così le richieste dei prompt non vengono
  rifiutate (un prompt passa comunque dal router, come chiede lo step).

## 3. Test
- Automatici: server in memoria (elenco con argomenti obbligatori e facoltativi, testo compilato per
  livello, livello non valido → errore); ponte (`elenca_prompt`, `ottieni_prompt` via stdio); comandi
  (`/prompts` formattato, parsing con virgolette, tutti i casi d'errore senza chiamare server o grafo,
  messaggi del prompt in cronologia e grafo invocato una volta, log con nome, argomenti e messaggi);
  client (comando sconosciuto, `/prompt` che non manda testo grezzo al grafo).
- Reali (`PROVA_REALE=1`): `/prompt spiega argomento="Model Context Protocol" livello=base` → risposta
  semplice che parla di MCP; dopo due domande, `/prompt riassumi_conversazione` → riassunto che cita i
  turni della sessione.

## 4. Non obiettivi
Prompt richiamati dal modello, completamento automatico dei comandi, altri prompt.
