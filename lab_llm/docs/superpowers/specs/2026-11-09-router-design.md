# Router: conversazione o fuori ambito (lezione 6, step 1)

Data: 2026-11-09. Fonte: `materiali/LLM_Lez_6.pdf`, «Step 1 – Router». Parte dal grafo della
lezione 5 (`2026-11-09-strumenti-mcp-design.md`) senza riscriverlo.

## 1. Problema
L'agente risponde a qualsiasi domanda. Lo step chiede un ambito dichiarato in configurazione e un
nodo LLM, posto prima dell'agente, che rifiuti le domande fuori ambito senza raggiungere l'agente.
La scelta degli strumenti resta all'agente: il router non li conosce.

## 2. Comportamento
Grafo: `START → compatta → router → (llm | rifiuto)`; `rifiuto → END`; da `llm` in poi tutto come
prima (`strumenti`, `limite`, `END`).

- **Ambito**: testo libero da `AMBITO_AGENTE` (facoltativa). Default stretto in `config.py`:
  data e ora, meteo, note personali, saluti e domande sull'assistente.
- **Router**: stesso modello, senza strumenti, con output strutturato
  `DecisioneRouter{categoria: "conversazione" | "fuori_ambito", motivo: str}`
  (`with_structured_output`, schema Pydantic). Riceve un prompt di sistema con l'ambito (nessun
  nome di strumento) e la trascrizione (`trascrivi`) degli ultimi 4 messaggi della cronologia,
  così un seguito come «e domani?» viene giudicato nel suo contesto. La domanda da classificare è
  l'ultimo messaggio dell'utente.
- **Stato**: nuovo campo `categoria: str` in `AgentState`, scritto dal router a ogni turno e letto
  dall'arco condizionale `instrada_dopo_router`. Il motivo va solo nel log.
- **Rifiuto**: nodo senza modello che aggiunge
  `AIMessage("Mi dispiace, posso aiutarti solo con: {ambito}.")`. La cronologia resta valida.
- **Errori del router** (`openai.APIError`, output non valido o assente): log WARNING e la domanda
  passa all'agente (`categoria=conversazione`), come fa `compatta` quando il riassunto fallisce.
- **Log (evidenze)**: INFO `router: categoria=<c> motivo=<m> -> agente|rifiuto`; nuova riga INFO
  nel nodo `llm`: `agente: invio N messaggi al modello`. Su una domanda fuori ambito la seconda
  riga non compare. Print didattici `[passo]` commentati.
- **Limite di ricorsione**: il router aggiunge un super-step (2·max + 4 < `2*max_passi+5`).

## 3. Interfacce
- `costruisci_grafo(..., router: Runnable | None = None, ambito: str = "")`: con `router=None` il
  nodo esiste ma manda sempre all'agente (test esistenti invariati).
- `agente/graph.py`: `DecisioneRouter`, `PROMPT_ROUTER`, `MESSAGGIO_RIFIUTO`,
  `instrada_dopo_router`.
- `agente/llm.py`: `crea_router(config)` = `_chat(config).with_structured_output(DecisioneRouter)`.
- `agente/config.py`: campo `ambito` da `AMBITO_AGENTE` (default `AMBITO_PREDEFINITO`);
  documentata in `.env.example`.
- `agente/main.py`: passa `crea_router(config)` e `config.ambito`; l'ambito compare nel log di avvio.

## 4. Test
- Automatici (`tests/test_router.py`, router e modello finti): conversazione → agente con log di
  categoria, motivo e `-> agente` e riga `agente: invio`; fuori ambito → rifiuto, modello
  dell'agente mai chiamato, nessuna riga `agente: invio`; router in errore → agente; il router
  riceve l'ambito e la trascrizione, non gli strumenti; `router=None` → agente. Config in
  `tests/test_config.py`, `crea_router` in `tests/test_llm.py`.
- Reali (`tests/reale/test_router_reale.py`, `PROVA_REALE=1`): «Che ore sono a Tokyo?» →
  conversazione e risposta dell'agente; «Scrivimi la ricetta della carbonara» → fuori ambito,
  rifiuto, agente non eseguito. Più una prova a mano con `python -m agente`.
- Una risposta simulata dimostra il cablaggio del grafo, non che il modello reale classifichi bene.

## 5. Non obiettivi
Revisore (step 2), riassunto come campo dello stato (step 3), resource e prompt MCP, servizio HTTP,
più di due categorie, rifiuto generato dal modello.
