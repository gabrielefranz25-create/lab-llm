"""Server FastMCP di prova per i test del ponte: un tool che risponde e uno che fa morire il processo."""

import logging
import os
import sys

from fastmcp import FastMCP

mcp = FastMCP("Morente")


@mcp.tool
def eco(testo: str) -> str:
    """Restituisce il testo ricevuto, senza modifiche."""
    return testo


@mcp.tool
def muori() -> str:
    """Termina subito il processo del server, simulando un crash durante la sessione."""
    os._exit(1)


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    mcp.run(show_banner=False)
