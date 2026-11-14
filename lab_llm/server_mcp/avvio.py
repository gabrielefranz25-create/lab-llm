"""Avvio di un server MCP con il trasporto scelto in MCP_TRASPORTO: stdio (default) o Streamable HTTP.

Il server è lo stesso: cambiano solo il modo in cui viaggiano i messaggi e chi lo avvia
(con stdio l'agente, con HTTP chi lancia il servizio, per esempio `python -m server_mcp.avvia_http`).
"""

import logging
import os
import sys

logger = logging.getLogger(__name__)

# Porta fissa di ogni server in HTTP: l'agente la usa per comporre l'URL `http://<host>:<porta>/mcp`.
PORTE_HTTP = {"meteo": 8101, "note": 8102, "unita": 8103, "calcolatrice": 8104,
              "scadenze": 8105, "catalogo": 8106, "orologio": 8107, "utente": 8108}
PERCORSO_HTTP = "/mcp"


def avvia(server, nome: str) -> None:
    """Avvia `server` (un FastMCP) via stdio o via Streamable HTTP, secondo MCP_TRASPORTO."""
    trasporto = (os.environ.get("MCP_TRASPORTO") or "stdio").strip().lower()
    if trasporto == "stdio":
        server.run(show_banner=False)
        return
    if trasporto != "http":
        print(f"MCP_TRASPORTO deve essere stdio o http, non '{trasporto}'.", file=sys.stderr)
        raise SystemExit(2)
    host = os.environ.get("MCP_HTTP_ASCOLTO") or "127.0.0.1"
    porta = int(os.environ.get("MCP_HTTP_PORTA") or PORTE_HTTP[nome])
    logger.info("server %s: Streamable HTTP su http://%s:%d%s", nome, host, porta, PERCORSO_HTTP)
    server.run(transport="http", host=host, port=porta, path=PERCORSO_HTTP, show_banner=False)
