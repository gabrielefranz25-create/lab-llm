"""Test di `server_mcp.avvio.avvia`: stesso server, trasporto stdio o Streamable HTTP."""

import logging

import pytest

from server_mcp.avvio import PORTE_HTTP, avvia


class ServerFinto:
    """Registra gli argomenti di `run` invece di avviare davvero il server."""

    def __init__(self):
        self.chiamate = []

    def run(self, **argomenti):
        self.chiamate.append(argomenti)


@pytest.fixture(autouse=True)
def ambiente_pulito(monkeypatch):
    for nome in ("MCP_TRASPORTO", "MCP_HTTP_ASCOLTO", "MCP_HTTP_PORTA"):
        monkeypatch.delenv(nome, raising=False)


def test_porte_fisse_per_ogni_server():
    assert PORTE_HTTP == {"meteo": 8101, "note": 8102, "unita": 8103, "calcolatrice": 8104,
                          "scadenze": 8105, "catalogo": 8106, "orologio": 8107}


def test_stdio_predefinito():
    server = ServerFinto()
    avvia(server, "meteo")
    assert server.chiamate == [{"show_banner": False}]


def test_stdio_esplicito(monkeypatch):
    monkeypatch.setenv("MCP_TRASPORTO", "stdio")
    server = ServerFinto()
    avvia(server, "note")
    assert server.chiamate == [{"show_banner": False}]


def test_http_con_porta_del_server(monkeypatch, caplog):
    monkeypatch.setenv("MCP_TRASPORTO", "http")
    server = ServerFinto()
    with caplog.at_level(logging.INFO, logger="server_mcp.avvio"):
        avvia(server, "calcolatrice")
    assert server.chiamate == [{"transport": "http", "host": "127.0.0.1", "port": 8104,
                                "path": "/mcp", "show_banner": False}]
    assert "server calcolatrice: Streamable HTTP su http://127.0.0.1:8104/mcp" in caplog.text


def test_http_con_host_e_porta_sovrascritti(monkeypatch):
    monkeypatch.setenv("MCP_TRASPORTO", "HTTP")
    monkeypatch.setenv("MCP_HTTP_ASCOLTO", "0.0.0.0")
    monkeypatch.setenv("MCP_HTTP_PORTA", "9999")
    server = ServerFinto()
    avvia(server, "unita")
    assert server.chiamate[0]["host"] == "0.0.0.0"
    assert server.chiamate[0]["port"] == 9999


def test_trasporto_sconosciuto_esce_con_codice_2(monkeypatch, capsys):
    monkeypatch.setenv("MCP_TRASPORTO", "sse")
    server = ServerFinto()
    with pytest.raises(SystemExit) as uscita:
        avvia(server, "meteo")
    assert uscita.value.code == 2
    assert server.chiamate == []
    assert "MCP_TRASPORTO deve essere stdio o http, non 'sse'" in capsys.readouterr().err
