"""Test dell'interfaccia da terminale: cronologia, uscita, errori, avvio di main()."""

import logging

import httpx
import openai
import pytest
from langchain_core.messages import AIMessage, HumanMessage

import agente.config
from agente.client import avvia_sessione
from agente.graph import costruisci_grafo
from agente.main import configura_logging, main
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


@pytest.mark.parametrize("nome", ["httpx", "httpx2", "httpcore", "openai"])
def test_configura_logging_silenzia_librerie_http(nome):
    configura_logging("INFO")
    assert logging.getLogger(nome).level == logging.WARNING
