# Grafo e strumenti

Spiegazione del grafo LangGraph dell'agente e degli strumenti che usa.
**Da aggiornare a ogni modifica del grafo, dello stato o degli strumenti.**
Per i dettagli di funzionamento vedi anche `COME_FUNZIONA.md`.

Stato al 2026-11-14: lezione 5 completa; lezione 6 step 1–5 (router, revisore, riassunto, resource, prompt) fatti.

## 1. Il grafo di oggi

Costruito da `costruisci_grafo` in `agente/graph.py`.

```
START
  │
  ▼
compatta ── riassume i messaggi vecchi se la cronologia supera la soglia
  │
  ▼
router ── decide se la domanda rientra nell'ambito (AMBITO_AGENTE)
  │
  ├─ fuori_ambito ─► rifiuto ──► END        l'agente non viene eseguito
  │
  ▼ conversazione
 llm  ◄──────────────┐   il modello (con gli strumenti collegati) decide: risposta o tool_call
  │                  │
  ├─ tool_call, passi < limite ─► strumenti ─┘   esegue le tool_call, poi torna a llm
  ├─ tool_call, limite raggiunto ─► limite ──► END     (messaggio fisso, non revisionato)
  └─ nessuna tool_call
       ▼
revisore ── la risposta tratta tutte le parti della domanda?
  ├─ non coerente, revisioni < MAX_REVISIONI ─► nota del revisore ─► llm
  └─ coerente, oppure limite di revisioni ──► END
```

### Nodi

| Nodo | Funzione | Cosa fa |
|---|---|---|
| `compatta` | `nodo_compatta` | Se `len(messages) > MAX_MESSAGGI_CONTESTO`, divide la cronologia (`dividi_cronologia`) in vecchi e recenti (gli ultimi `MESSAGGI_DA_TENERE`, a partire da un `HumanMessage`). Fa riassumere i vecchi (più il riassunto precedente) al **riassuntore** (lo stesso modello senza strumenti), toglie i vecchi da `messages` e scrive il nuovo testo nel campo `riassunto`, che **sostituisce** il precedente. Log `riassunto: messaggi prima=N dopo=M (riassunti K, tenuti M)`. Sotto la soglia non chiama il modello (log DEBUG). |
| `router` | `nodo_router` | Manda al **router** (lo stesso modello senza strumenti, con output strutturato `DecisioneRouter`: `categoria` e `motivo`) un prompt con l'ambito, l'eventuale `riassunto` e la trascrizione degli ultimi 4 messaggi; l'ultimo è la domanda da classificare. Le domande su ciò che l'utente ha detto prima (es. il nome) rientrano nell'ambito. Non conosce gli strumenti. Scrive `router: categoria=… motivo=… -> agente\|rifiuto` e salva la categoria nello stato. Se il router fallisce (errore di LM Studio o output non valido) scrive un warning e passa all'agente. Senza router (`router=None`) passa sempre all'agente. |
| `rifiuto` | `nodo_rifiuto` | Aggiunge un `AIMessage` fisso: «Mi dispiace, posso aiutarti solo con: {ambito}.». Non chiama il modello. |
| `llm` | `nodo_llm` | Mette il prompt di sistema (con le `ISTRUZIONI_PER_STRUMENTO` dei soli strumenti collegati, più l'eventuale riassunto) in cima, prende gli ultimi messaggi con `finestra_contesto` e chiama il modello. Scrive `agente: invio N messaggi al modello`: se questa riga manca, l'agente non è stato eseguito. |
| `strumenti` | `nodo_strumenti` | Esegue ogni tool_call dell'ultimo `AIMessage` e risponde con un `ToolMessage` per ciascuna. Gli errori diventano testo per il modello. Scrive nei log `strumento=… origine=… call_id=… esito=…`. |
| `limite` | `nodo_limite` | Chiude le tool_call rimaste in sospeso con un `ToolMessage` «Non eseguito» e aggiunge un messaggio di scuse. |
| `revisore` | `nodo_revisore` | Manda al **revisore** (lo stesso modello senza strumenti, output strutturato `DecisioneRevisore`: `motivo` e `coerente`) la domanda del turno (`domanda_del_turno`: l'ultimo `HumanMessage` che non è una nota del revisore) e la risposta proposta. Controlla solo che la risposta tratti tutte le parti della domanda senza deviare; non verifica i dati. Se non è coerente e `revisioni < MAX_REVISIONI` aggiunge un `HumanMessage` di nome `revisore` («Nota del revisore: … <motivo>. Rispondi di nuovo …») e incrementa `revisioni`; al limite scrive un WARNING e lascia l'ultima risposta. Log `revisore: coerente=si\|no motivo=… -> fine\|agente (revisione k di N)`. Errore o output non valido → WARNING e risposta accettata; senza revisore (`revisore=None`) approva sempre. |

### Archi
- `START → compatta → router`: fissi.
- Dopo `router` si passa da `instrada_dopo_router`, un **arco condizionale**: verso `llm` se la categoria è `conversazione`, verso `rifiuto` se è `fuori_ambito`.
- `rifiuto → END`.
- Dopo `llm` si passa da `instrada_dopo_llm`, un **arco condizionale**: verso `revisore` se non ci sono tool_call, verso `strumenti` se `passi_strumento < MAX_PASSI_STRUMENTO`, altrimenti verso `limite`.
- Dopo `revisore` si passa da `instrada_dopo_revisore`: verso `llm` se l'ultimo messaggio è una nota del revisore, altrimenti verso `END`.
- `strumenti → llm`: è il ciclo dell'agente.
- `limite → END`.

### Stato (`AgentState`)

| Campo | Tipo | Come si aggiorna |
|---|---|---|
| `messages` | lista di messaggi | Reducer `add_messages`: i messaggi restituiti dai nodi si **accodano**. `RemoveMessage(REMOVE_ALL_MESSAGES)` svuota la lista: lo usa `compatta`. |
| `passi_strumento` | `int` | Nessun reducer: il nuovo valore **sostituisce** quello vecchio. Il client lo rimette a 0 a ogni turno. |
| `categoria` | `str` | Nessun reducer: lo scrive `router` a ogni turno (`conversazione` o `fuori_ambito`). Lo legge `instrada_dopo_router`. Il motivo resta solo nel log. |
| `riassunto` | `str` | Nessun reducer: lo scrive `compatta` (il nuovo sostituisce il vecchio); lo leggono `llm` (in coda al prompt di sistema) e `router`. Il client lo conserva e lo ripassa a ogni turno. |
| `revisioni` | `int` | Nessun reducer: revisioni chieste dal revisore nel turno. Il client lo rimette a 0 a ogni domanda; il nodo lo legge con `.get(..., 0)`. I `passi_strumento` restano cumulativi nel turno, anche tra una revisione e l'altra. |

### Regola importante
Un `AIMessage` con tool_call deve sempre essere seguito dai rispettivi `ToolMessage`. Per questo `finestra_contesto` e `dividi_cronologia` tagliano solo all'inizio di un `HumanMessage`, e `limite` risponde anche alle tool_call che non esegue.

## 2. Gli strumenti

Il modello vede tutti gli strumenti allo stesso modo (nome, descrizione, schema degli argomenti). L'unica differenza è da dove arrivano.

| Strumento | Origine | Dove | Cosa fa |
|---|---|---|---|
| `ora_corrente(fuso_orario)` | una variante per volta (`VARIANTE_OROLOGIO`) | vedi sotto | Data e ora in un fuso IANA. Il default è `FUSO_ORARIO_PREDEFINITO`. |
| `meteo_attuale(citta)` | MCP `meteo` | `server_mcp/meteo.py` | Meteo di adesso da Open-Meteo, con geocoding. |
| `previsioni_meteo(citta, giorni=3)` | MCP `meteo` | `server_mcp/meteo.py` | Previsioni per alcuni giorni. |
| `aggiungi_nota(testo)` | MCP `note` | `server_mcp/note.py` | Salva una nota su SQLite (`NOTE_DB`). |
| `elenca_note(limite=10)` | MCP `note` | `server_mcp/note.py` | Elenca le note. |
| `elimina_nota(id_nota)` | MCP `note` | `server_mcp/note.py` | Elimina una nota per ID. |
| `converti_unita(valore, da, a)` | MCP `unita` | `server_mcp/unita.py` | Conversione tra unità della stessa grandezza (elenco chiuso). |
| `calcola(espressione)` | MCP `calcolatrice` | `server_mcp/calcolatrice.py` | Aritmetica con `ast`, senza `eval`; rifiuta tutto il resto. |
| `giorni_tra(data_inizio, data_fine)` | MCP `scadenze` | `server_mcp/scadenze.py` | Giorni di calendario e lavorativi tra due date. |
| `aggiungi_giorni(data, giorni, solo_lavorativi=False)` | MCP `scadenze` | `server_mcp/scadenze.py` | Data spostata di N giorni (anche solo lavorativi). |
| `cerca_corsi(testo, max_risultati=5)` | MCP `catalogo` | `server_mcp/catalogo.py` | Ricerca per parole nel catalogo dei corsi. |
| `dettaglio_corso(codice)` | MCP `catalogo` | `server_mcp/catalogo.py` | Tutti i campi di un corso dato il codice. |

I server scelti in `SERVER_MCP` (default: tutti) decidono anche l'ambito predefinito del router:
`ambito_predefinito` in `agente/config.py` unisce ora e saluti a una frase per ogni server attivo
(`AMBITO_PER_SERVER`).

### Le tre varianti dell'orologio (lezione 5, blocco B)
Stesso contratto (`ora_corrente(fuso_orario)`, stesso testo del risultato, stesso motivo d'errore),
stessa logica (`servizio_orologio/logica.py`); cambia solo il percorso. Una sola variante è attiva,
scelta con `VARIANTE_OROLOGIO` (default `locale`).

| Variante | Dove gira | Chi scrive il contratto | `origine` nel log | Errore di trasporto |
|---|---|---|---|---|
| `locale` | nel processo dell'agente (`agente/strumenti.py`, `crea_ora_corrente`) | la funzione `@tool` | `locale` | — |
| `fastapi` | servizio `python -m servizio_orologio.api` (`GET /ora`) | il wrapper scritto a mano `crea_ora_corrente_http` | `http:orologio` | `Errore di collegamento HTTP con il servizio orologio: …` |
| `mcp` | server `server_mcp/orologio.py` (stdio, avviato dall'agente) | il server, letto con `list_tools()` | `mcp:orologio` | `Errore di collegamento MCP con il server orologio: …` |

All'avvio il log mostra `orologio: variante=<v> percorso=<…>`. Dopo `bind_tools` il grafo è identico
nelle tre varianti: il nodo `strumenti` non sa che dietro c'è HTTP o MCP.

### Trasporto MCP (lezione 5, blocco C)
`TRASPORTO_MCP=stdio` (default): l'agente avvia i server come sottoprocessi. `TRASPORTO_MCP=http`: i
server sono servizi Streamable HTTP già avviati (`python -m server_mcp.avvia_http`, porte 8101–8107) e
l'agente si collega a `http://<MCP_HTTP_HOST>:<porta>/mcp`. Catalogo e invocazione sono identici.

### Percorso di uno strumento MCP
1. All'avvio, `main.py` apre `ConnessioneMCP` (`agente/mcp_ponte.py`), che lancia i server scelti in `SERVER_MCP` come sottoprocessi **stdio** oppure, con `TRASPORTO_MCP=http`, si collega ai server già avviati.
2. Il ponte legge il catalogo (`list_tools()`) e crea per ogni voce un `StructuredTool` **sincrono**. Nome, descrizione e schema arrivano dal server e non sono mai scritti nell'agente.
3. `unisci_strumenti` unisce strumenti locali e MCP; `crea_modello` li collega al modello (`bind_tools`).
4. Quando il modello chiede uno strumento, `nodo_strumenti` lo invoca e il ponte esegue `call_tool` sul proprio thread asincrono.
5. Il modello legge uno di tre esiti: il risultato, `Errore dallo strumento <nome>: …` oppure `Errore di collegamento MCP con il server <server>: …`.

## 3. Tool, resource e prompt (MCP)

| Primitiva | Chi la attiva | Quando | Stato nel progetto |
|---|---|---|---|
| Tool | il modello | durante il ciclo, quando serve un'azione o un dato | fatto (lezione 5) |
| Resource | l'applicazione (host) | prima di chiamare il modello, per preparare il contesto | fatto (lezione 6, step 4): `utente://preferenze` |
| Prompt | l'utente | quando sceglie esplicitamente un compito (`/prompt`) | fatto (lezione 6, step 5): `spiega`, `riassumi_conversazione` |

Errore comune: esporre tutto come tool. Così le decisioni che spettano all'applicazione o all'utente passano al modello.

### La resource `utente://preferenze` (step 4)
- Server `server_mcp/utente.py`: nessun tool, una resource (`application/json`) con il contenuto di
  `PREFERENZE_FILE` (default `server_mcp/risorse/preferenze.json`), riletto a ogni richiesta.
- Host: `main.py` chiama `leggi_preferenze` (`agente/preferenze.py`) **prima** di aprire la connessione dei
  tool, con una connessione dedicata al solo server `utente` (`resources/read` una volta, poi chiusa).
- Il fuso delle preferenze diventa il fuso predefinito della sessione (orologio, `scadenze`, prompt); lingua
  e stile completano la prima riga del prompt di sistema (`Sei l'assistente del laboratorio. Rispondi sempre in …`).
- Campo non valido → valore predefinito per quel campo; resource non disponibile → tutti i predefiniti.
  Entrambi i casi con un WARNING.

### I prompt MCP (step 5)
- Server `utente`: `spiega(argomento, livello="base")` (base, intermedio, avanzato) e
  `riassumi_conversazione(stile="sintetico")` (sintetico, dettagliato). Descrizioni degli argomenti dalla
  docstring (sezione `Args:`), lette da FastMCP.
- Host: `agente/comandi.py` (`ComandiPrompt`) legge `prompts/list` una volta all'avvio della chat e
  gestisce `/prompts` e `/prompt nome arg=valore`; gli argomenti si controllano nell'host. Il server
  `utente` è anche nella connessione dei tool (senza tool, quindi nulla cambia per `bind_tools`).
- I messaggi del prompt entrano nella cronologia al posto della domanda e il grafo non sa che vengono
  da un prompt: router, strumenti e revisore lavorano come sempre. L'ambito predefinito del router
  comprende «spiegazioni di concetti di informatica e di intelligenza artificiale, riassunti della
  conversazione».

## 4. Il grafo che vogliamo (lezione 6)

```
START → riassunto → router ─ fuori ambito ─► rifiuto → END
                       │
                   in ambito
                       ▼
                   agente (llm) ◄──► strumenti
                       │
                   nessuna tool_call
                       ▼
                   revisore ─ non coerente + motivo ─► agente
                       │
                    coerente
                       ▼
                      END
```

- **Router** (step 1, **fatto**): un LLM con output strutturato (categoria e motivo) decide se la domanda rientra nell'ambito dichiarato in configurazione. Non decide sugli strumenti.
- **Revisore** (step 2, **fatto**): un LLM controlla che la risposta sia coerente con la domanda. Se non lo è, rimanda all'agente il motivo (nota del revisore nella cronologia), con il limite `MAX_REVISIONI`.
- **Riassunto** (step 3, **fatto**): il nodo `compatta` scrive il riassunto nel campo `riassunto` dello stato (aggiornato, non accumulato) e registra nei log il numero di messaggi prima e dopo.
