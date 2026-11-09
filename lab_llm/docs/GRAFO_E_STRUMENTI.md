# Grafo e strumenti

Spiegazione del grafo LangGraph dell'agente e degli strumenti che usa.
**Da aggiornare a ogni modifica del grafo, dello stato o degli strumenti.**
Per i dettagli di funzionamento vedi anche `COME_FUNZIONA.md`.

Stato al 2026-11-09: fine lezione 5 (tag `lezione-5`).

## 1. Il grafo di oggi

Costruito da `costruisci_grafo` in `agente/graph.py`.

```
START
  │
  ▼
compatta ── riassume i messaggi vecchi se la cronologia supera la soglia
  │
  ▼
 llm  ◄──────────────┐   il modello (con gli strumenti collegati) decide: risposta o tool_call
  │                  │
  ├─ nessuna tool_call ───────────────► END
  ├─ tool_call, passi < limite ─► strumenti ─┘   esegue le tool_call, poi torna a llm
  └─ tool_call, limite raggiunto ─► limite ──► END
```

### Nodi

| Nodo | Funzione | Cosa fa |
|---|---|---|
| `compatta` | `nodo_compatta` | Se `len(messages) > MAX_MESSAGGI_CONTESTO`, divide la cronologia (`dividi_cronologia`) in vecchi e recenti (gli ultimi `MESSAGGI_DA_TENERE`, a partire da un `HumanMessage`). Fa riassumere i vecchi al **riassuntore** (lo stesso modello senza strumenti) e li sostituisce con un `SystemMessage` di nome `riassunto`. Sotto la soglia non chiama il modello. |
| `llm` | `nodo_llm` | Mette il prompt di sistema (più l'eventuale riassunto) in cima, prende gli ultimi messaggi con `finestra_contesto` e chiama il modello. |
| `strumenti` | `nodo_strumenti` | Esegue ogni tool_call dell'ultimo `AIMessage` e risponde con un `ToolMessage` per ciascuna. Gli errori diventano testo per il modello. Scrive nei log `strumento=… origine=… call_id=… esito=…`. |
| `limite` | `nodo_limite` | Chiude le tool_call rimaste in sospeso con un `ToolMessage` «Non eseguito» e aggiunge un messaggio di scuse. |

### Archi
- `START → compatta → llm`: fissi.
- Dopo `llm` si passa da `instrada_dopo_llm`, un **arco condizionale**: verso `END` se non ci sono tool_call, verso `strumenti` se `passi_strumento < MAX_PASSI_STRUMENTO`, altrimenti verso `limite`.
- `strumenti → llm`: è il ciclo dell'agente.
- `limite → END`.

### Stato (`AgentState`)

| Campo | Tipo | Come si aggiorna |
|---|---|---|
| `messages` | lista di messaggi | Reducer `add_messages`: i messaggi restituiti dai nodi si **accodano**. `RemoveMessage(REMOVE_ALL_MESSAGES)` svuota la lista: lo usa `compatta`. |
| `passi_strumento` | `int` | Nessun reducer: il nuovo valore **sostituisce** quello vecchio. Il client lo rimette a 0 a ogni turno. |

### Regola importante
Un `AIMessage` con tool_call deve sempre essere seguito dai rispettivi `ToolMessage`. Per questo `finestra_contesto` e `dividi_cronologia` tagliano solo all'inizio di un `HumanMessage`, e `limite` risponde anche alle tool_call che non esegue.

## 2. Gli strumenti

Il modello vede tutti gli strumenti allo stesso modo (nome, descrizione, schema degli argomenti). L'unica differenza è da dove arrivano.

| Strumento | Origine | Dove | Cosa fa |
|---|---|---|---|
| `ora_corrente(fuso_orario)` | locale | `agente/strumenti.py` | Data e ora in un fuso IANA. Il default è `FUSO_ORARIO_PREDEFINITO`. |
| `meteo_attuale(citta)` | MCP `meteo` | `server_mcp/meteo.py` | Meteo di adesso da Open-Meteo, con geocoding. |
| `previsioni_meteo(citta, giorni=3)` | MCP `meteo` | `server_mcp/meteo.py` | Previsioni per alcuni giorni. |
| `aggiungi_nota(testo)` | MCP `note` | `server_mcp/note.py` | Salva una nota su SQLite (`NOTE_DB`). |
| `elenca_note(limite=10)` | MCP `note` | `server_mcp/note.py` | Elenca le note. |
| `elimina_nota(id_nota)` | MCP `note` | `server_mcp/note.py` | Elimina una nota per ID. |

### Percorso di uno strumento MCP
1. All'avvio, `main.py` apre `ConnessioneMCP` (`agente/mcp_ponte.py`), che lancia i server scelti in `SERVER_MCP` come sottoprocessi **stdio**.
2. Il ponte legge il catalogo (`list_tools()`) e crea per ogni voce un `StructuredTool` **sincrono**. Nome, descrizione e schema arrivano dal server e non sono mai scritti nell'agente.
3. `unisci_strumenti` unisce strumenti locali e MCP; `crea_modello` li collega al modello (`bind_tools`).
4. Quando il modello chiede uno strumento, `nodo_strumenti` lo invoca e il ponte esegue `call_tool` sul proprio thread asincrono.
5. Il modello legge uno di tre esiti: il risultato, `Errore dallo strumento <nome>: …` oppure `Errore di collegamento MCP con il server <server>: …`.

## 3. Tool, resource e prompt (MCP)

| Primitiva | Chi la attiva | Quando | Stato nel progetto |
|---|---|---|---|
| Tool | il modello | durante il ciclo, quando serve un'azione o un dato | fatto (lezione 5) |
| Resource | l'applicazione (host) | prima di chiamare il modello, per preparare il contesto | da fare (lezione 6, step 4) |
| Prompt | l'utente | quando sceglie esplicitamente un compito (`/prompt`) | da fare (lezione 6, step 5) |

Errore comune: esporre tutto come tool. Così le decisioni che spettano all'applicazione o all'utente passano al modello.

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

- **Router** (step 1): un LLM con output strutturato (categoria e motivo) decide se la domanda rientra nell'ambito dichiarato in configurazione. Non decide sugli strumenti.
- **Revisore** (step 2): un LLM controlla che la risposta sia coerente con la domanda. Se non lo è, rimanda all'agente il motivo, con un limite di revisioni.
- **Riassunto** (step 3): è il nodo `compatta` di oggi. Va adattato perché il riassunto diventi un campo dello stato e perché registri nei log il numero di messaggi prima e dopo.
