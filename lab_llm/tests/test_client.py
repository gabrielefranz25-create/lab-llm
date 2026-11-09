"""Test dell'interfaccia da terminale: cronologia, uscita, errori, avvio di main()."""

import logging

import httpx
import openai
import pytest
from langchain_core.messages import AIMessage, HumanMessage

import agente.config
import agente.main
from agente.client import avvia_sessione
from agente.graph import costruisci_grafo
from agente.config import carica_config
from agente.main import configura_logging, main, server_da_config
from agente.strumenti import crea_ora_corrente

SERVER = "http://h:1/v1"


class ModelloFinto:
    def __init__(self, risposte: list[AIMessage]):
        self.risposte = list(risposte)
        self.chiamate: list[list] = []

    def invoke(self, messaggi):
        self.chiamate.append(list(messaggi))
        return self.risposte.pop(0)


class GrafoFinto:
    """Al primo invoke solleva `errore`, poi risponde con un AIMessage fisso."""

    def __init__(self, errore: Exception):
        self.errore = errore
        self.ricevuti: list[list] = []

    def invoke(self, stato, config=None):
        self.ricevuti.append(list(stato["messages"]))
        if self.errore:
            errore, self.errore = self.errore, None
            raise errore
        return {"messages": stato["messages"] + [AIMessage("ok")], "passi_strumento": 0}


def _grafo(modello):
    return costruisci_grafo(modello, [crea_ora_corrente()], max_passi=3,
                            max_messaggi_contesto=20, fuso_predefinito="Europe/Rome")


def _sessione(grafo, ingressi: list):
    """Esegue la sessione con input da lista (EOF a fine lista) e restituisce l'output."""
    righe: list[str] = []
    coda = iter(ingressi)

    def leggi(_prompt):
        valore = next(coda, EOFError())
        if isinstance(valore, BaseException):
            raise valore
        return valore

    avvia_sessione(grafo, intestazione="Modello: m", server=SERVER, recursion_limit=11,
                   leggi=leggi, scrivi=righe.append)
    return "\n".join(righe)


def test_cronologia_mantenuta_tra_turni():
    modello = ModelloFinto([AIMessage("Ciao!"), AIMessage("Mi hai salutato")])
    _sessione(_grafo(modello), ["Ciao", "Di cosa abbiamo parlato?", "esci"])
    contenuti = [m.content for m in modello.chiamate[1]]
    assert "Ciao" in contenuti and "Ciao!" in contenuti
    assert contenuti[-1] == "Di cosa abbiamo parlato?"


@pytest.mark.parametrize("comando", ["esci", "ESCI", "quit"])
def test_uscita_con_comando(comando):
    uscita = _sessione(_grafo(ModelloFinto([])), [comando])
    assert "Sessione terminata. La cronologia non è stata salvata." in uscita


def test_uscita_con_bom_iniziale():
    # PowerShell 5.1 antepone il BOM UTF-8 all'input passato via pipe ("esci" | python -m agente).
    modello = ModelloFinto([])
    uscita = _sessione(_grafo(modello), ["﻿esci"])
    assert modello.chiamate == []
    assert "Sessione terminata" in uscita


def test_uscita_con_eof():
    uscita = _sessione(_grafo(ModelloFinto([])), [EOFError()])
    assert "Sessione terminata" in uscita


def test_uscita_con_ctrl_c():
    uscita = _sessione(_grafo(ModelloFinto([])), [KeyboardInterrupt()])
    assert "Sessione terminata" in uscita


def test_input_vuoto_ignorato():
    modello = ModelloFinto([])
    _sessione(_grafo(modello), ["", "   ", "esci"])
    assert modello.chiamate == []


def test_errore_collegamento_non_altera_cronologia():
    grafo = GrafoFinto(openai.APIConnectionError(request=httpx.Request("GET", SERVER)))
    uscita = _sessione(grafo, ["prima", "seconda", "esci"])
    assert f"[errore] Non riesco a contattare LM Studio su {SERVER}" in uscita
    assert [m.content for m in grafo.ricevuti[1]] == ["seconda"]
    assert isinstance(grafo.ricevuti[1][0], HumanMessage)


def test_risposta_vuota():
    uscita = _sessione(_grafo(ModelloFinto([AIMessage("")])), ["Ciao", "esci"])
    assert "Assistente> (il modello non ha restituito testo)" in uscita


def test_main_config_mancante(monkeypatch, capsys):
    monkeypatch.setattr(agente.config, "load_dotenv", lambda **_: None)
    monkeypatch.setenv("LM_BASE_URL", SERVER)
    monkeypatch.delenv("LM_MODEL", raising=False)
    assert main() == 1
    assert "LM_MODEL" in capsys.readouterr().err


def test_ctrl_c_durante_la_risposta_chiude_la_sessione():
    grafo = GrafoFinto(KeyboardInterrupt())
    uscita = _sessione(grafo, ["Che ore sono?", "seconda"])
    assert "Sessione terminata. La cronologia non è stata salvata." in uscita
    assert len(grafo.ricevuti) == 1


def test_main_ctrl_c_durante_la_verifica(monkeypatch, capsys):
    def interrotta(_config):
        raise KeyboardInterrupt
    monkeypatch.setattr(agente.config, "load_dotenv", lambda **_: None)
    monkeypatch.setenv("LM_BASE_URL", SERVER)
    monkeypatch.setenv("LM_MODEL", "m")
    monkeypatch.setattr(agente.main, "verifica_modello", interrotta)
    assert main() == 130
    assert "Interrotto" in capsys.readouterr().err


@pytest.mark.parametrize("nome", ["httpx", "httpx2", "httpcore", "openai"])
def test_configura_logging_silenzia_librerie_http(nome):
    configura_logging("INFO")
    assert logging.getLogger(nome).level == logging.WARNING


def _config(**extra):
    base = {"LM_BASE_URL": SERVER, "LM_MODEL": "m", "METEO_TIMEOUT": "4", "MCP_TIMEOUT": "30"}
    return carica_config({**base, **extra})


def test_server_da_config():
    (meteo,) = server_da_config(_config(SERVER_MCP="meteo"))
    assert meteo.nome == "meteo"
    assert meteo.argomenti == ("-m", "server_mcp.meteo")
    assert meteo.env["METEO_TIMEOUT"] == "4.0"
    assert server_da_config(_config(SERVER_MCP="")) == []


def test_server_da_config_log_server_e_framework():
    (meteo,) = server_da_config(_config(SERVER_MCP="meteo", LOG_LEVEL="DEBUG"))
    assert meteo.env["LOG_LEVEL"] == "DEBUG"  # i log del nostro server seguono l'agente
    assert meteo.env["FASTMCP_LOG_LEVEL"] == "WARNING"  # niente "Starting MCP server" nella chat


def _avvia_main_con_mcp(monkeypatch, connessione):
    monkeypatch.setattr(agente.config, "load_dotenv", lambda **_: None)
    monkeypatch.setenv("LM_BASE_URL", SERVER)
    monkeypatch.setenv("LM_MODEL", "m")
    monkeypatch.setattr(agente.main, "verifica_modello", lambda _config: None)
    monkeypatch.setattr(agente.main, "crea_modello", lambda _config, _strumenti: object())
    monkeypatch.setattr(agente.main, "crea_riassuntore", lambda _config: object())
    monkeypatch.setattr(agente.main, "ConnessioneMCP", connessione)
    return main()


def test_main_ctrl_c_durante_l_avvio_dei_server(monkeypatch, capsys):
    class Interrotta:
        def __init__(self, *_):
            pass

        def __enter__(self):
            raise KeyboardInterrupt

        def __exit__(self, *_):
            return False

    assert _avvia_main_con_mcp(monkeypatch, Interrotta) == 130
    assert "Interrotto" in capsys.readouterr().err


def test_main_intestazione_con_strumenti_mcp(monkeypatch):
    from langchain_core.tools import StructuredTool
    finto = StructuredTool.from_function(func=lambda: "x", name="meteo_attuale", description="d")
    visto = {}

    class Finta:
        def __init__(self, servers, timeout):
            visto["servers"] = servers
            self.strumenti = [finto]

        def __enter__(self):
            return self

        def __exit__(self, *_):
            visto["chiusa"] = True
            return False

    monkeypatch.setattr(agente.main, "avvia_sessione",
                        lambda grafo, intestazione, server, recursion_limit: visto.update(testata=intestazione))
    assert _avvia_main_con_mcp(monkeypatch, Finta) == 0
    assert "Strumenti: ora_corrente, meteo_attuale" in visto["testata"]
    assert visto["servers"][0].nome == "meteo" and visto["chiusa"]
