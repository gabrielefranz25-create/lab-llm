"""Avvia con Streamable HTTP i server MCP scelti in SERVER_MCP (assente = tutti) più l'orologio.

Uso: `python -m server_mcp.avvia_http`, poi l'agente con TRASPORTO_MCP=http. Ctrl+C li ferma tutti.
Ogni server ascolta sulla propria porta (`server_mcp.avvio.PORTE_HTTP`).
"""

import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from dotenv import load_dotenv

from server_mcp.avvio import PORTE_HTTP

# Cartella `lab_llm/`: i server si avviano con `-m server_mcp.<nome>` da qui.
CARTELLA_PROGETTO = Path(__file__).resolve().parents[1]
SERVER_SCEGLIBILI = tuple(nome for nome in PORTE_HTTP if nome != "orologio")


def processi_da_avviare(ambiente: Mapping[str, str]) -> list[tuple[str, list[str], dict[str, str]]]:
    """(nome, comando, variabili) di ogni server da avviare, nell'ordine di PORTE_HTTP."""
    grezzo = ambiente.get("SERVER_MCP")
    if grezzo is None:
        scelti = list(SERVER_SCEGLIBILI)
    else:
        scelti = [n.strip() for n in grezzo.split(",") if n.strip()]
        sconosciuti = [n for n in scelti if n not in SERVER_SCEGLIBILI]
        if sconosciuti:
            raise SystemExit(f"SERVER_MCP contiene server sconosciuti: {', '.join(sconosciuti)}.")
    env = {**ambiente, "MCP_TRASPORTO": "http", "FASTMCP_LOG_LEVEL": "WARNING"}
    env.setdefault("FUSO_ORARIO", ambiente.get("FUSO_ORARIO_PREDEFINITO") or "Europe/Rome")
    return [(nome, [sys.executable, "-m", f"server_mcp.{nome}"], dict(env))
            for nome in PORTE_HTTP if nome in scelti or nome == "orologio"]


def main() -> int:
    load_dotenv(override=False)
    processi = []
    try:
        for nome, comando, env in processi_da_avviare(os.environ):
            print(f"avvio {nome} su porta {PORTE_HTTP[nome]}", file=sys.stderr)
            processi.append(subprocess.Popen(comando, env=env, cwd=CARTELLA_PROGETTO))
        for processo in processi:
            processo.wait()
    except KeyboardInterrupt:
        print("Arresto dei server MCP.", file=sys.stderr)
    finally:
        for processo in processi:
            if processo.poll() is None:
                processo.terminate()
        for processo in processi:
            processo.wait(10)
    return 0


if __name__ == "__main__":
    sys.exit(main())
