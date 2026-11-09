# Nodo `compatta`: riassunto della cronologia (aggiunta alla lezione 4)

Data: 2026-11-09. Integra la specifica `2026-10-26-assistente-orologio-design.md`, dove il
"riassunto della cronologia generato dal modello" era un non obiettivo. Gli appunti del docente
(`materiali/altre_info.txt`: "nodi llm, nodi compact") lo richiedono: diventa un obiettivo.

## 1. Problema
Oggi il contesto è controllato solo dalla finestra scorrevole (`finestra_contesto`): i messaggi
oltre `MAX_MESSAGGI_CONTESTO` non vengono più inviati al modello e il loro contenuto si perde
(es. "mi chiamo Gabriele" detto all'inizio). La cronologia in memoria invece cresce senza limite.

## 2. Comportamento
Grafo: `START → compatta → llm → (strumenti | limite | END)`; `strumenti → llm`, `limite → END`.
Il nodo `compatta` gira una volta per turno, prima del modello.

- **Quando**: se `len(messages) > max_messaggi_contesto` (stessa soglia di oggi, default 20).
- **Taglio**: `recenti` = ultimi `messaggi_da_tenere` messaggi (default 6), spostando l'inizio in
  avanti fino al primo `HumanMessage` (stessa regola di `finestra_contesto`: nessuna tool_call
  orfana). Se non c'è un taglio valido, non compatta. `vecchi` = tutto ciò che precede.
- **Riassunto**: un modello **senza strumenti** (`riassuntore`) riceve un prompt di sistema
  ("riassumi in italiano, conserva nomi, preferenze, fatti e richieste dell'utente") e i messaggi
  `vecchi`; un eventuale riassunto precedente è già in testa a `vecchi` e quindi viene incluso.
- **Nuova cronologia**: `RemoveMessage(id=REMOVE_ALL_MESSAGES)` + `[SystemMessage(riassunto,
  name="riassunto")] + recenti` (schema di LangGraph per riscrivere i messaggi con `add_messages`).
  Il client riceve la cronologia già compattata e non cambia.
- **Errori**: `openai.APIError` dal riassuntore → log WARNING, cronologia invariata (la finestra
  scorrevole resta la rete di sicurezza).
- **Log**: INFO `compattati N messaggi, tenuti M`. Print didattici `[passo]` commentati.
- **Nodo `llm`**: se il primo messaggio è il riassunto lo invia subito dopo il prompt di sistema,
  poi `finestra_contesto` sul resto.

## 3. Interfacce
- `costruisci_grafo(..., riassuntore: Runnable | None = None, messaggi_da_tenere: int = 6)`:
  con `riassuntore=None` il nodo esiste ma non compatta mai (test esistenti invariati).
- `agente/llm.py`: `crea_riassuntore(config)` = stesso `ChatOpenAI` di `crea_modello`, senza
  `bind_tools` (parte comune in `_chat(config)`).
- `agente/config.py`: `messaggi_da_tenere` da `MESSAGGI_DA_TENERE` (intero >= 2, default 6,
  deve essere minore di `MAX_MESSAGGI_CONTESTO`); documentata in `.env.example`.
- `agente/main.py`: passa `crea_riassuntore(config)` e `config.messaggi_da_tenere`.

## 4. Test
- Automatici (`tests/test_compatta.py`, modello finto): sotto soglia nulla cambia; sopra soglia
  riassunto in testa + recenti intatti con taglio su HumanMessage; riassunto precedente incluso;
  il riassunto arriva al modello `llm`; `APIError` → cronologia invariata; `riassuntore=None` →
  nessuna compattazione. Config e `crea_riassuntore` nei rispettivi file di test.
- Reale (`tests/reale/`, `PROVA_REALE=1`): conversazione oltre soglia con un nome detto
  all'inizio; dopo la compattazione il modello lo ricorda ancora.

## 5. Non obiettivi
Persistenza su disco, soglie in token invece che in messaggi, riassunto in streaming.
