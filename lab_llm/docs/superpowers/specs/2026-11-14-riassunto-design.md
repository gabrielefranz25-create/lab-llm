# Riassunto della cronologia come campo dello stato (lezione 6, step 3)

Data: 2026-11-14. Fonte: `materiali/LLM_Lez_6.pdf`, «Step 3 · Riassunto della cronologia». Parte dal
grafo con router (step 1) e revisore (step 2). Modalità autonoma («fai tutto»): le scelte sono di Claude.

## 1. Problema
Il nodo `compatta` (lezione 4) riassume già i messaggi vecchi oltre `MAX_MESSAGGI_CONTESTO`, ma mette il
riassunto **dentro `messages`** come `SystemMessage(name="riassunto")`. Lo step chiede che il riassunto
sia un **campo dello stato aggiornato, non accumulato**, e un log con il numero di messaggi prima e dopo.
Gli altri requisiti ci sono già: soglia configurabile (`MAX_MESSAGGI_CONTESTO`), ultimi N conservati
(`MESSAGGI_DA_TENERE`), taglio mai tra una tool_call e il suo `ToolMessage` (`dividi_cronologia`),
nessuna chiamata al modello sotto la soglia.

## 2. Comportamento
- **Stato**: nuovo campo `riassunto: str` (senza reducer: il valore nuovo sostituisce il vecchio).
  `messages` contiene solo Human/AI/Tool (e le note del revisore), mai il riassunto.
- **Nodo `compatta`** (nome invariato, all'inizio del turno): sopra la soglia divide la cronologia in
  vecchi e recenti; manda al riassuntore il riassunto precedente (se c'è) più la trascrizione dei vecchi;
  restituisce `{"messages": [RemoveMessage(REMOVE_ALL_MESSAGES), *recenti], "riassunto": nuovo}`. Il
  riassunto nuovo **sostituisce** il precedente, che il riassuntore ha già incorporato.
- **Log (evidenza)**: INFO `riassunto: messaggi prima=<n> dopo=<m> (riassunti <k>, tenuti <m>)`; sotto la
  soglia DEBUG `riassunto: <n> messaggi, sotto la soglia di <s>, nessuna chiamata al modello`.
- **Nodo `llm`**: se `riassunto` non è vuoto lo aggiunge al prompt di sistema (un solo `SystemMessage` in
  testa, come prima) con l'intestazione `INTESTAZIONE_RIASSUNTO`.
- **Router e revisore**: invariati (il router legge gli ultimi 4 messaggi; non serve il riassunto).
- **Client**: tiene `cronologia` e `riassunto` della sessione; li passa al grafo a ogni turno e salva
  quelli restituiti. `rispondi(grafo, cronologia, testo, recursion_limit, riassunto="")` restituisce
  `(messaggi, riassunto, testo_risposta)`. Così, allo step 6, cronologia e riassunto potranno arrivare
  dal chiamante e tornare aggiornati.
- **Errori del riassuntore**: come prima, WARNING e cronologia e riassunto lasciati invariati.
- `trascrivi` non gestisce più il `SystemMessage` del riassunto; il riassunto precedente entra nel testo
  per il riassuntore come riga `Riassunto precedente: …`.

## 3. Interfacce
- `agente/graph.py`: `AgentState.riassunto`; `nodo_compatta`, `nodo_llm` aggiornati; tolto
  `NOME_RIASSUNTO` e `_e_riassunto`.
- `agente/client.py`: `rispondi` e `avvia_sessione` con il riassunto della sessione.

## 4. Test
- Automatici (riassuntore e modello finti): sotto la soglia nessuna chiamata; sopra la soglia campo
  `riassunto` valorizzato, `messages` senza `SystemMessage`, recenti intatti, log prima/dopo; riassunto
  precedente passato al riassuntore e sostituito; riassunto nel prompt di sistema del modello (un solo
  `SystemMessage`); errore del riassuntore; taglio su un `HumanMessage`; client che conserva il riassunto
  tra i turni.
- Reale (`PROVA_REALE=1`): soglia bassa, nome detto al primo turno, più turni, poi «Come mi chiamo?» →
  risposta con il nome; stato con `riassunto` non vuoto e log `riassunto: messaggi prima=… dopo=…`.

## 5. Non obiettivi
Stima dei token (resta la soglia in messaggi), riassunto visibile al router, persistenza del riassunto.
