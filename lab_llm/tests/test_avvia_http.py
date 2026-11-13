"""Test di `python -m server_mcp.avvia_http`: quali server parte e con quali variabili."""

import sys

import pytest

from server_mcp import avvia_http
from server_mcp.avvia_http import processi_da_avviare


def test_tutti_i_server_piu_orologio_se_server_mcp_assente():
    processi = processi_da_avviare({})
    assert [nome for nome, _, _ in processi] == [
        "meteo", "note", "unita", "calcolatrice", "scadenze", "catalogo", "orologio"]
    nome, comando, env = processi[0]
    assert comando == [sys.executable, "-m", "server_mcp.meteo"]
    assert env["MCP_TRASPORTO"] == "http"
    assert env["FASTMCP_LOG_LEVEL"] == "WARNING"


def test_server_scelti_con_server_mcp():
    processi = processi_da_avviare({"SERVER_MCP": "note, calcolatrice"})
    assert [nome for nome, _, _ in processi] == ["note", "calcolatrice", "orologio"]


def test_server_mcp_vuota_avvia_solo_l_orologio():
    assert [nome for nome, _, _ in processi_da_avviare({"SERVER_MCP": ""})] == ["orologio"]


def test_server_sconosciuto():
    with pytest.raises(SystemExit, match="server sconosciuti: posta"):
        processi_da_avviare({"SERVER_MCP": "meteo,posta"})


def test_fuso_dell_agente_passato_come_fuso_orario():
    (_, _, env), = [p for p in processi_da_avviare({"FUSO_ORARIO_PREDEFINITO": "Asia/Tokyo"})
                    if p[0] == "orologio"]
    assert env["FUSO_ORARIO"] == "Asia/Tokyo"


def test_variabili_dell_ambiente_conservate():
    (_, _, env), *_ = processi_da_avviare({"NOTE_DB": "x.sqlite3", "MCP_HTTP_ASCOLTO": "0.0.0.0"})
    assert env["NOTE_DB"] == "x.sqlite3"
    assert env["MCP_HTTP_ASCOLTO"] == "0.0.0.0"


def test_main_termina_tutti_i_processi(monkeypatch):
    avviati = []

    class ProcessoFinto:
        def __init__(self, comando, **_):
            self.comando, self.terminato = comando, False
            avviati.append(self)

        def wait(self, timeout=None):
            if not self.terminato:
                raise KeyboardInterrupt  # Ctrl+C mentre si aspetta il primo server
            return 0

        def terminate(self):
            self.terminato = True

        def poll(self):
            return 0 if self.terminato else None

    monkeypatch.setattr(avvia_http.subprocess, "Popen", ProcessoFinto)
    monkeypatch.setattr(avvia_http, "load_dotenv", lambda **_: None)
    monkeypatch.setenv("SERVER_MCP", "unita")
    assert avvia_http.main() == 0
    assert [p.comando[-1] for p in avviati] == ["server_mcp.unita", "server_mcp.orologio"]
    assert all(p.terminato for p in avviati)
