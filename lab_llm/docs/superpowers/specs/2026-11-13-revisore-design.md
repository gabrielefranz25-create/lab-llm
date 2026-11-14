# Revisore: la risposta è coerente con la domanda? (lezione 6, step 2)

Data: 2026-11-13. Fonte: `materiali/LLM_Lez_6.pdf`, «Step 2 · Revisore». Parte dal grafo con il
router (step 1) e dalla lezione 5 completa (blocchi A, B, C), senza riscriverli. Modalità autonoma
(«fai tutto»): le scelte sono di Claude.

## 1. Problema
L'agente può dare una risposta parziale (domanda in due parti, una sola risolta) o fuori tema, e
nessuno se ne accorge. Lo step chiede un secondo nodo LLM dopo l'agente che controlli la coerenza
tra domanda e risposta e, se serve, rimandi all'agente il motivo, con un limite di revisioni.

## 2. Comportamento
Grafo: `START → compatta → router → (llm | rifiuto)`; `llm` senza tool_call → **`revisore`** (prima
andava a `END`); `revisore → END` se coerente o al limite, altrimenti `revisore → llm`. `strumenti`,
`limite` e `rifiuto` come prima (il messaggio fisso del limite e il rifiuto non vengono revisionati).

- **Revisore**: stesso modello, senza strumenti, con output strutturato
  `DecisioneRevisore{coerente: bool, motivo: str}` (`with_structured_output`). Riceve un prompt di
  sistema (`PROMPT_REVISORE`) e un solo messaggio con la domanda dell'utente del turno e la risposta
  proposta. Controlla solo la coerenza: tutte le parti della domanda trattate, nessuna deviazione dal
  tema. Non verifica i dati (orari, meteo, calcoli vengono dagli strumenti).
- **Domanda del turno**: l'ultimo `HumanMessage` che non sia una nota del revisore.
- **Risposta non coerente**: il revisore aggiunge alla cronologia
  `HumanMessage(name="revisore", content="Nota del revisore: la risposta precedente non è completa
  o coerente con la domanda: <motivo>. Rispondi di nuovo alla domanda dell'utente, completa.")` e il
  grafo torna a `llm`. Un `HumanMessage` (e non un `SystemMessage`) perché alcuni modelli accettano un
  solo messaggio di sistema in testa. La bozza scartata resta nella cronologia (serve all'agente per
  capire cosa correggere); `trascrivi` mostra la nota come `Revisore: …`.
- **Stato**: nuovo campo `revisioni: int` (revisioni fatte nel turno), azzerato dal client a ogni
  domanda come `passi_strumento`. I passi di strumento restano cumulativi nel turno.
- **Limite**: `MAX_REVISIONI` (configurazione, intero >= 0, default 2). Con `revisioni ==
  MAX_REVISIONI` e risposta non coerente: log WARNING `revisore: limite di N revisioni raggiunto,
  restituita l'ultima risposta` e fine. `MAX_REVISIONI=0` = revisore solo osservatore (giudica e
  registra, non rimanda mai).
- **Errori del revisore** (`openai.APIError`, output non valido): log WARNING e risposta accettata.
- **Log (evidenze)**: INFO `revisore: coerente=si|no motivo=<m> -> fine|agente (revisione k di N)`.
- **Limite di ricorsione**: `limite_ricorsione(max_passi, max_revisioni)` = `2*max_passi +
  2*max_revisioni + 6`.

## 3. Interfacce
- `agente/graph.py`: `DecisioneRevisore`, `PROMPT_REVISORE`, `NOME_REVISORE`, `instrada_dopo_revisore`,
  `costruisci_grafo(..., revisore: Runnable | None = None, max_revisioni: int = 2)`; con
  `revisore=None` il nodo esiste e approva sempre (test esistenti invariati).
- `agente/llm.py`: `crea_revisore(config)`.
- `agente/config.py`: `max_revisioni` da `MAX_REVISIONI`; `.env.example`.
- `agente/client.py`: stato iniziale con `revisioni: 0`; `agente/main.py`: passa revisore e limite.

## 4. Test
- Automatici (revisore e modello finti): risposta coerente → approvata al primo passaggio, una sola
  chiamata all'agente; risposta parziale → nota con il motivo nella cronologia, seconda risposta
  approvata; revisore che rifiuta sempre → si ferma a `MAX_REVISIONI`, log del limite, ultima risposta
  restituita; revisore in errore → risposta accettata; il revisore riceve domanda e risposta, non gli
  strumenti; rifiuto del router e messaggio del limite non revisionati; `MAX_REVISIONI=0`.
- Reali (`PROVA_REALE=1`): revisore vero con risposta parziale scritta a mano a una domanda in due
  parti → `coerente=false` con motivo; risposta completa → `coerente=true`; grafo vero con «Che ore
  sono a Tokyo e quanto fa 15 per 12?» → risposta finale con entrambe le parti, approvata.

## 5. Non obiettivi
Riassunto come campo dello stato (step 3), resource e prompt MCP, verifica dei dati delle risposte,
revisione del rifiuto e del messaggio di limite, streaming.
