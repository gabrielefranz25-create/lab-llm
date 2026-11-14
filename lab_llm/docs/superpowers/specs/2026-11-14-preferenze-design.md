# Resource `utente://preferenze` (lezione 6, step 4)

Data: 2026-11-14. Fonte: `materiali/LLM_Lez_6.pdf`, «Step 4 · Resource: preferenze dell'utente». Parte
dagli step 1–3. Modalità autonoma («fai tutto»): le scelte sono di Claude.

## 1. Problema
Lingua, stile e fuso predefinito delle risposte sono scritti nel codice (prompt di sistema) o nella
configurazione. Lo step chiede che un server MCP li esponga come **resource** e che sia l'host (non il
modello) a leggerli a inizio sessione e a metterli in cima al prompt di sistema: cambiando il file, la
sessione successiva si comporta diversamente senza toccare il codice.

## 2. Comportamento
- **Server `utente`** (`server_mcp/utente.py`, FastMCP): resource `utente://preferenze`
  (`name="preferenze"`, `mime_type="application/json"`) che restituisce il contenuto del file
  `PREFERENZE_FILE` (default `server_mcp/risorse/preferenze.json`, letto a ogni richiesta). Nessun tool.
  Porta HTTP 8108; `avvia_http` lo avvia sempre, come l'orologio. Log su stderr della lettura.
- **File**: `{"lingua": "italiano", "fuso_orario": "Europe/Rome", "stile": "sintetico"}`; `stile` è
  `sintetico` o `dettagliato`.
- **Host** (`agente/preferenze.py`): `leggi_preferenze(server, timeout, predefinite)` apre una
  connessione MCP con il solo server `utente`, chiama `resources/read` una volta, prima della prima
  domanda, e interpreta il JSON. Campo mancante o non valido (lingua vuota, fuso IANA sconosciuto, stile
  fuori elenco) → valore predefinito per quel campo e WARNING. Resource non disponibile (server spento,
  file mancante, JSON non valido) → tutti i valori predefiniti e WARNING `preferenze: resource
  utente://preferenze non disponibile, uso i valori predefiniti (…): <motivo>`.
- **Valori predefiniti**: lingua `italiano`, stile `sintetico`, fuso `FUSO_ORARIO_PREDEFINITO`.
- **Log (evidenza)**: INFO `resource: utente://preferenze letta dal server utente: lingua=… fuso_orario=…
  stile=…` (diverso dalle righe `strumento=…` dei tool).
- **Effetti**: il fuso delle preferenze diventa il fuso predefinito della sessione
  (`replace(config, fuso_orario_predefinito=…)` prima di creare strumenti, server e grafo: orologio nelle
  tre varianti, `scadenze`, prompt). Lingua e stile completano la prima riga del prompt di sistema:
  `Sei l'assistente del laboratorio. Rispondi sempre in <lingua>, <stile>.` (il fuso arriva al prompt come
  fuso predefinito). Sonde reali del 2026-11-14 (3 tentativi per variante): con l'URI della resource, lo stile tra
  parentesi e il fuso nella riga gemma-4-e2b inventava l'ora (0 chiamate a `ora_corrente` su 3); con
  l'etichetta «Preferenze dell'utente:» o con le preferenze prima di «Sei l'assistente del
  laboratorio.» non chiamava `calcola` per «15 per 12» (0 su 3), e lo stesso togliendo «(ora
  italiana)». Con la forma attuale 3 su 3. «(ora italiana)» resta solo con `Europe/Rome`.
- La resource **non** è un tool: il server `utente` non ha voci in `list_tools()` e nulla passa a
  `bind_tools`. La connessione per le preferenze è separata da quella dei tool (si chiude subito):
  serve leggere il fuso prima di avviare gli altri server.

## 3. Interfacce
- `server_mcp/utente.py`, `server_mcp/risorse/preferenze.json`, `PORTE_HTTP["utente"] = 8108`.
- `agente/mcp_ponte.py`: `ConnessioneMCP.leggi_risorsa(nome_server, uri) -> str`.
- `agente/preferenze.py`: `Preferenze`, `URI_PREFERENZE`, `predefinite`, `interpreta`, `istruzioni`,
  `leggi_preferenze`.
- `agente/config.py`: `preferenze_file` da `PREFERENZE_FILE`.
- `agente/graph.py`: `costruisci_grafo(..., preferenze: str = ISTRUZIONI_PREDEFINITE)`, in cima al prompt.
- `agente/main.py`: `server_utente(config)`, lettura prima della connessione dei tool.

## 4. Test
- Automatici: server in memoria (resource elencata con URI e MIME, contenuto del file, file cambiato →
  contenuto nuovo, file mancante → errore, catalogo dei tool vuoto); `interpreta` e `istruzioni`;
  `leggi_preferenze` con il server vero via stdio (file temporaneo) e con un server inesistente
  (predefinite e WARNING); grafo con le preferenze in cima al prompt; `main` che applica il fuso.
- Reali (`PROVA_REALE=1`): preferenze con `America/New_York` → «Che ore sono?» usa New York senza
  chiederlo; preferenze con lingua `inglese` e stile `dettagliato` → risposta in inglese.

## 5. Non obiettivi
Modifica delle preferenze dalla chat (non è un tool), rilettura durante la sessione, prompt MCP (step 5).
