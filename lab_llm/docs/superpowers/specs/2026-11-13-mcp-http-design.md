# Streamable HTTP in locale al posto di stdio (lezione 5, blocco C)

Data: 2026-11-13. Fonte: `materiali/LLM_Lez_5.pdf`, slide «Stdio e Streamable HTTP trasportano gli
stessi concetti MCP» e «Estensioni dopo la prima integrazione», punto 02: «Streamable HTTP in locale
al posto di stdio, verificando che il catalogo resti identico». Parte dal blocco B
(`2026-11-12-varianti-orologio-design.md`) senza riscriverlo. Modalità autonoma («fai tutto»): le
scelte sono di Claude.

## 1. Problema
Oggi ogni server MCP è un sottoprocesso stdio avviato dall'agente. Con Streamable HTTP lo stesso
server diventa un servizio avviato a parte e raggiunto con un URL. La lezione chiede di mostrare che
cambia il trasporto (avvio, collegamento, diagnosi), non il significato: catalogo e invocazione sono
identici.

## 2. Comportamento
- **Server**: ogni server (`meteo`, `note`, `unita`, `calcolatrice`, `scadenze`, `catalogo`,
  `orologio`) parte con `avvia(server, nome)` di `server_mcp/avvio.py`:
  - `MCP_TRASPORTO` assente o `stdio` → come oggi (`run(show_banner=False)`);
  - `MCP_TRASPORTO=http` → `run(transport="http", host=MCP_HTTP_ASCOLTO, port=..., path="/mcp")`.
    Indirizzo di ascolto `MCP_HTTP_ASCOLTO` (default `127.0.0.1`, solo questo PC); porta fissa per
    server (`PORTE_HTTP`: meteo 8101, note 8102, unita 8103, calcolatrice 8104, scadenze 8105,
    catalogo 8106, orologio 8107), sovrascrivibile con `MCP_HTTP_PORTA` (serve ai test).
    Log su stderr: `server <nome>: Streamable HTTP su http://<host>:<porta>/mcp`.
  - valore diverso → messaggio d'errore su stderr e uscita con codice 2.
- **Avvio di tutti i server HTTP**: `python -m server_mcp.avvia_http` avvia come sottoprocessi i
  server di `SERVER_MCP` (stessa regola dell'agente: assente = tutti) più `orologio`, con
  `MCP_TRASPORTO=http`, e resta in attesa; Ctrl+C li termina tutti. Passa le stesse variabili
  dell'agente (`LOG_LEVEL`, `FASTMCP_LOG_LEVEL=WARNING`, `METEO_TIMEOUT`, `NOTE_DB`, `FUSO_ORARIO`).
- **Agente**: `TRASPORTO_MCP` (`stdio` | `http`, default `stdio`) e `MCP_HTTP_HOST` (default
  `127.0.0.1`). Con `http`, `server_da_config` dà a ogni `ServerMCP` l'URL
  `http://<MCP_HTTP_HOST>:<porta>/mcp` e `ConnessioneMCP` usa `StreamableHttpTransport` invece di
  `StdioTransport`; non avvia sottoprocessi. Tutto il resto (catalogo con `list_tools()`, tool
  sincroni, esiti `Errore dallo strumento …`/`Errore di collegamento MCP …`) è invariato. Con la
  variante `mcp` dell'orologio vale lo stesso.
- **Log (evidenze)**: `server MCP <nome>: catalogo [...] via <stdio | http://…/mcp>`; all'avvio
  `trasporto MCP: <stdio|http>`. Server HTTP spento → `server MCP <nome> non disponibile: …` e
  l'agente prosegue senza quel server (come oggi con stdio).
- **Sicurezza**: i server ascoltano su `127.0.0.1` per default; HTTP in locale non è pubblicazione
  su Internet. Nessuna autenticazione (non richiesta). In Docker ascoltano su `0.0.0.0` nella rete
  di compose, porte non pubblicate sull'host.

## 3. Test
- Automatici: `avvia` (stdio, http con porta e host, porta sovrascritta, trasporto sconosciuto) con
  un server finto che registra la chiamata a `run`; config (`TRASPORTO_MCP`, `MCP_HTTP_HOST`);
  `server_da_config` con URL; **catalogo identico**: per ogni server, catalogo letto via stdio e via
  HTTP (sottoprocesso su porta libera) con `ConnessioneMCP`, confronto di nome, descrizione e
  schema; una chiamata via HTTP (`calcola("2+3")`); server HTTP spento → nessun tool e warning.
  Non usano il modello.
- Reali (`PROVA_REALE=1`): «Che ore sono a Tokyo?» e «Quanto fa 15 per 12?» con
  `TRASPORTO_MCP=http` (server avviati dal test con `avvia_http`), tool chiamati e risultato usato.
- Docker: servizio `server-mcp` (profilo `http`), chat via pipe con `TRASPORTO_MCP=http`.

## 4. Non obiettivi
Autenticazione, TLS, server remoti, SSE legacy (`HTTP+SSE`), resource e prompt MCP (lezione 6),
avvio automatico dei server HTTP dall'agente.
