"""Test di `python -m server_mcp.avvia_http`: quali server parte e con quali variabili."""

import sys

import pytest

from server_mcp import avvia_http
from server_mcp.avvia_http import processi_da_avviare


def test_tutti_i_server_piu_orologio_e_utente_se_server_mcp_assente():
    processi = processi_da_avviare({})
    assert [nome for nome, _, _ in processi] == [
        "meteo", "note", "unita", "calcolatrice", "scadenze", "catalogo", "orologio", "utente"]
    nome, comando, env = processi[0]
    assert comando == [sys.executable, "-m", "server_mcp.meteo"]
    assert env["MCP_TRASPORTO"] == "http"
    assert env["FASTMCP_LOG_LEVEL"] == "WARNING"


def test_server_scelti_con_server_mcp():
    processi = processi_da_avviare({"SERVER_MCP": "note, calcolatrice"})
    assert [nome for nome, _, _ in processi] == ["note", "calcolatrice", "orologio", "utente"]


def test_server_mcp_vuota_avvia_solo_orologio_e_utente():
    assert [nome for nome, _, _ in processi_da_avviare({"SERVER_MCP": ""})] == ["orologio", "utente"]


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


class ProcessoFinto:
    """Processo che termina da solo dopo `vita` controlli (None = mai) o quando viene terminato."""

    def __init__(self, comando, vita=None):
        self.comando, self.vita, self.terminato, self.controlli = comando, vita, False, 0

    def poll(self):
        if self.terminato:
            return 0
        self.controlli += 1
        return 1 if self.vita is not None and self.controlli > self.vita else None

    def wait(self, timeout=None):
        return self.poll()

    def terminate(self):
        self.terminato = True

    def kill(self):
        self.terminato = True


def _main_con(monkeypatch, vite, interrompi_dopo=None):
    """Esegue main() con processi finti; `vite` per nome di server; Ctrl+C dopo N attese."""
    avviati = []
    attese = {"n": 0}

    def popen(comando, **_):
        avviati.append(ProcessoFinto(comando, vite.get(comando[-1].rsplit(".", 1)[1])))
        return avviati[-1]

    def attendi(_secondi):
        attese["n"] += 1
        if interrompi_dopo is not None and attese["n"] > interrompi_dopo:
            raise KeyboardInterrupt

    monkeypatch.setattr(avvia_http.subprocess, "Popen", popen)
    monkeypatch.setattr(avvia_http, "load_dotenv", lambda **_: None)
    monkeypatch.setattr(avvia_http.time, "sleep", attendi)
    monkeypatch.setenv("SERVER_MCP", "unita")
    return avvia_http.main(), avviati


def test_main_ctrl_c_termina_tutti_i_processi(monkeypatch):
    codice, avviati = _main_con(monkeypatch, {}, interrompi_dopo=3)
    assert codice == 0
    assert [p.comando[-1] for p in avviati] == ["server_mcp.unita", "server_mcp.orologio", "server_mcp.utente"]
    assert all(p.terminato for p in avviati)


def test_main_server_terminato_ferma_gli_altri(monkeypatch, capsys):
    codice, avviati = _main_con(monkeypatch, {"orologio": 2})
    assert codice == 1
    assert "server orologio terminato (codice 1)" in capsys.readouterr().err
    assert avviati[0].terminato  # unita fermato


def test_porta_singola_non_passata_ai_server():
    (_, _, env), *_ = processi_da_avviare({"MCP_HTTP_PORTA": "9999"})
    assert "MCP_HTTP_PORTA" not in env
