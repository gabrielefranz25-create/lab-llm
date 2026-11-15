"""Test del nucleo dell'agente (usato dalla chat locale e dal servizio HTTP), con grafo finto."""

from types import SimpleNamespace as NS

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agente.comandi import ErroreComando
from agente.config import carica_config
from agente.nucleo import Agente

CONFIG = carica_config({"LM_BASE_URL": "http://h:1/v1", "LM_MODEL": "m"})


class GrafoFinto:
    """Risponde con una tool_call di ora_corrente, il suo risultato e la risposta finale."""

    def __init__(self, esito_strumento="Fuso orario: Asia/Tokyo | Ora: 10:00"):
        self.esito = esito_strumento
        self.ricevuti = []

    def invoke(self, stato, config=None):
        self.ricevuti.append(stato)
        nuovi = [AIMessage("", tool_calls=[{"name": "ora_corrente", "args": {"fuso_orario": "Asia/Tokyo"},
                                            "id": f"c{len(self.ricevuti)}"}], id=f"a{len(self.ricevuti)}"),
                 ToolMessage(self.esito, tool_call_id=f"c{len(self.ricevuti)}", id=f"t{len(self.ricevuti)}"),
                 AIMessage("A Tokyo sono le 10.", id=f"r{len(self.ricevuti)}")]
        domanda = [m if m.id else m.model_copy(update={"id": f"h{len(self.ricevuti)}"})
                   for m in stato["messages"]]
        return {"messages": domanda + nuovi, "riassunto": stato["riassunto"] + "+"}


class ComandiFinti:
    disponibili = True

    def compila(self, nome, argomenti):
        if nome != "spiega":
            raise ErroreComando(f"Prompt sconosciuto: {nome}.")
        return [HumanMessage(f"Spiegami «{argomenti['argomento']}»")]

    def catalogo_json(self):
        return [{"nome": "spiega", "descrizione": "d", "argomenti": []}]


def _agente(grafo=None, comandi=None, connessione=None):
    return Agente(config=CONFIG, grafo=grafo or GrafoFinto(), comandi=comandi or ComandiFinti(),
                  connessione=connessione or NS(servers=[], cataloghi={}), recursion_limit=16)


def test_turno_con_traccia_degli_strumenti():
    esito = _agente().turno([], "", testo="Che ore sono a Tokyo?")
    assert esito.risposta == "A Tokyo sono le 10."
    assert esito.strumenti == [{"nome": "ora_corrente", "argomenti": {"fuso_orario": "Asia/Tokyo"},
                                "esito": "ok"}]
    assert esito.riassunto == "+" and len(esito.messaggi) == 4


def test_traccia_solo_del_turno_corrente_ed_esito_errore():
    agente = _agente(GrafoFinto("Errore dallo strumento ora_corrente: fuso non valido"))
    primo = agente.turno([], "", testo="uno")
    secondo = agente.turno(primo.messaggi, primo.riassunto, testo="due")
    assert len(secondo.strumenti) == 1 and secondo.strumenti[0]["esito"] == "errore"
    assert agente.grafo.ricevuti[1]["riassunto"] == "+"


def test_turno_con_prompt():
    grafo = GrafoFinto()
    _agente(grafo).turno([], "", prompt=("spiega", {"argomento": "MCP"}))
    assert grafo.ricevuti[0]["messages"][-1].content == "Spiegami «MCP»"


def test_prompt_non_valido_non_chiama_il_grafo():
    grafo = GrafoFinto()
    with pytest.raises(ErroreComando):
        _agente(grafo).turno([], "", prompt=("ignoto", {}))
    assert grafo.ricevuti == []


def test_serve_un_messaggio_o_un_prompt():
    with pytest.raises(ValueError):
        _agente().turno([], "")
    with pytest.raises(ValueError):
        _agente().turno([], "", testo="x", prompt=("spiega", {"argomento": "a"}))


def test_stato_con_modello_e_server(monkeypatch):
    import agente.nucleo
    monkeypatch.setattr(agente.nucleo, "elenca_modelli", lambda config: ["m", "altro"])
    connessione = NS(servers=[NS(nome="meteo"), NS(nome="utente")], cataloghi={"utente": []})
    stato = _agente(connessione=connessione).stato()
    assert stato == {"agente": "ok", "modello": {"id": "m", "raggiungibile": True, "caricato": True},
                     "server_mcp": {"meteo": "non disponibile", "utente": "ok"}}


def test_stato_con_modello_irraggiungibile(monkeypatch):
    import openai, httpx, agente.nucleo

    def guasto(config):
        raise openai.APIConnectionError(request=httpx.Request("GET", "http://h"))
    monkeypatch.setattr(agente.nucleo, "elenca_modelli", guasto)
    modello = _agente().stato()["modello"]
    assert modello["raggiungibile"] is False and "Connection error" in modello["errore"]


def test_prompt_disponibili():
    assert _agente().prompt_disponibili()[0]["nome"] == "spiega"
