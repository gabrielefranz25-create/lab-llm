"""Stdio e Streamable HTTP trasportano gli stessi concetti: catalogo identico, stessa invocazione.

Avvia davvero i server (sottoprocessi), ma non usa il modello: è un test automatico.
"""

import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager

import pytest

from agente.mcp_ponte import CARTELLA_PROGETTO, ConnessioneMCP, ServerMCP

SERVER = ("meteo", "note", "unita", "calcolatrice", "scadenze", "catalogo", "orologio")


def _porta_libera() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _in_ascolto(porta: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", porta)) == 0


@contextmanager
def server_http(nome: str, env: dict):
    """Avvia `server_mcp.<nome>` con MCP_TRASPORTO=http su una porta libera; restituisce l'URL."""
    porta = _porta_libera()
    processo = subprocess.Popen(
        [sys.executable, "-m", f"server_mcp.{nome}"], cwd=str(CARTELLA_PROGETTO),
        env={**os.environ, **env, "MCP_TRASPORTO": "http", "MCP_HTTP_PORTA": str(porta),
             "FASTMCP_LOG_LEVEL": "WARNING"},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        limite = time.monotonic() + 20
        while not _in_ascolto(porta):
            assert processo.poll() is None, f"il server {nome} è terminato"
            assert time.monotonic() < limite, f"il server {nome} non è in ascolto"
            time.sleep(0.1)
        yield f"http://127.0.0.1:{porta}/mcp"
    finally:
        processo.terminate()
        processo.wait(10)


def _voci(catalogo) -> list[tuple]:
    return [(v.name, v.description, v.input_schema) for v in catalogo]


@pytest.mark.parametrize("nome", SERVER)
def test_catalogo_identico_tra_stdio_e_http(nome, tmp_path):
    env = {"NOTE_DB": str(tmp_path / "note.sqlite3")}
    stdio = ServerMCP(nome, ("-m", f"server_mcp.{nome}"), env)
    with ConnessioneMCP([stdio], timeout=30) as connessione:
        catalogo_stdio = connessione.cataloghi[nome]
    with server_http(nome, env) as url, \
            ConnessioneMCP([ServerMCP(nome, (), url=url)], timeout=30) as connessione:
        catalogo_http = connessione.cataloghi[nome]
    assert catalogo_stdio  # almeno un tool
    assert _voci(catalogo_http) == _voci(catalogo_stdio)


def test_chiamata_via_http_come_via_stdio():
    with server_http("calcolatrice", {}) as url, \
            ConnessioneMCP([ServerMCP("calcolatrice", (), url=url)], timeout=30) as connessione:
        (calcola,) = connessione.strumenti
        assert calcola.metadata == {"origine": "mcp:calcolatrice"}
        assert calcola.invoke({"espressione": "2+3"}) == "2+3 = 5"
        assert calcola.invoke({"espressione": "__import__('os')"}).startswith(
            "Errore dallo strumento calcola: ")
