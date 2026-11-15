"""Test dell'API dell'agente (FastAPI) con un agente finto: niente modello, niente server MCP."""

import httpx
import openai
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, messages_to_dict
from langgraph.errors import GraphRecursionError

from agente.comandi import ErroreComando
from agente.nucleo import Esito
from agente.servizio import crea_app


class AgenteFinto:
    def __init__(self, errore=None, stato_modello=True):
        self.errore, self.stato_modello = errore, stato_modello
        self.turni = []

    def turno(self, cronologia, riassunto, testo=None, prompt=None):
        self.turni.append((cronologia, riassunto, testo, prompt))
        if self.errore:
            raise self.errore
        if prompt and prompt[0] != "spiega":
            raise ErroreComando(f"Prompt sconosciuto: {prompt[0]}.")
        domanda = HumanMessage(testo or f"prompt {prompt[0]}", id=f"h{len(self.turni)}")
        risposta = AIMessage("Sono le 10.", id=f"a{len(self.turni)}")
        return Esito(messaggi=cronologia + [domanda, risposta], riassunto=riassunto + "r",
                     risposta="Sono le 10.",
                     strumenti=[{"nome": "ora_corrente", "argomenti": {}, "esito": "ok"}])

    def prompt_disponibili(self):
        return [{"nome": "spiega", "descrizione": "d", "argomenti": []}]

    def stato(self):
        return {"agente": "ok", "modello": {"id": "m", "raggiungibile": self.stato_modello}, "server_mcp": {}}


def _client(agente=None):
    return TestClient(crea_app(agente or AgenteFinto()))


def test_chat_restituisce_risposta_cronologia_e_strumenti(caplog):
    import logging
    with caplog.at_level(logging.INFO, logger="agente.servizio"):
        risposta = _client().post("/chat", json={"messaggio": "Che ore sono?"})
    assert risposta.status_code == 200
    corpo = risposta.json()
    assert corpo["risposta"] == "Sono le 10." and corpo["riassunto"] == "r"
    assert corpo["strumenti"] == [{"nome": "ora_corrente", "argomenti": {}, "esito": "ok"}]
    assert [m["type"] for m in corpo["cronologia"]] == ["human", "ai"]
    assert "api: POST /chat cronologia=0 -> 200 strumenti=[ora_corrente]" in caplog.text


def test_cronologia_restituita_viene_riletta_al_turno_dopo():
    agente = AgenteFinto()
    client = _client(agente)
    primo = client.post("/chat", json={"messaggio": "uno"}).json()
    client.post("/chat", json={"messaggio": "due", "cronologia": primo["cronologia"],
                               "riassunto": primo["riassunto"]})
    cronologia, riassunto, testo, _ = agente.turni[1]
    assert [m.content for m in cronologia] == ["uno", "Sono le 10."] and isinstance(cronologia[1], AIMessage)
    assert riassunto == "r" and testo == "due"


def test_chat_con_prompt():
    agente = AgenteFinto()
    risposta = _client(agente).post("/chat", json={"prompt": {"nome": "spiega", "argomenti": {"argomento": "MCP"}}})
    assert risposta.status_code == 200
    assert agente.turni[0][3] == ("spiega", {"argomento": "MCP"})


def test_prompt_non_valido_400():
    risposta = _client().post("/chat", json={"prompt": {"nome": "ignoto"}})
    assert risposta.status_code == 400 and risposta.json() == {"errore": "Prompt sconosciuto: ignoto."}


def test_serve_messaggio_o_prompt_400():
    for corpo in ({}, {"messaggio": "x", "prompt": {"nome": "spiega"}}, {"messaggio": "  "}):
        risposta = _client().post("/chat", json=corpo)
        assert risposta.status_code == 400 and "messaggio" in risposta.json()["errore"]


def test_cronologia_non_valida_400():
    risposta = _client().post("/chat", json={"messaggio": "x", "cronologia": [{"type": "boh"}]})
    assert risposta.status_code == 400 and "cronologia" in risposta.json()["errore"]


def test_modello_non_raggiungibile_503():
    errore = openai.APIConnectionError(request=httpx.Request("POST", "http://h"))
    risposta = _client(AgenteFinto(errore=errore)).post("/chat", json={"messaggio": "x"})
    assert risposta.status_code == 503
    assert risposta.json()["errore"].startswith("Il modello non è raggiungibile")


def test_limite_di_ricorsione_500():
    risposta = _client(AgenteFinto(errore=GraphRecursionError("x"))).post("/chat", json={"messaggio": "x"})
    assert risposta.status_code == 500 and "passaggi" in risposta.json()["errore"]


def test_prompts_e_stato():
    client = _client()
    assert client.get("/prompts").json() == [{"nome": "spiega", "descrizione": "d", "argomenti": []}]
    assert client.get("/stato").status_code == 200
    assert _client(AgenteFinto(stato_modello=False)).get("/stato").status_code == 503


def test_documentazione_openapi():
    schema = _client().get("/openapi.json").json()
    assert {"/chat", "/prompts", "/stato"} <= set(schema["paths"])
    assert schema["info"]["title"] == "Agente del laboratorio"


def test_cronologia_in_formato_langchain():
    cronologia = messages_to_dict([HumanMessage("ciao", id="x"), AIMessage("salve", id="y")])
    agente = AgenteFinto()
    _client(agente).post("/chat", json={"messaggio": "x", "cronologia": cronologia})
    assert [m.id for m in agente.turni[0][0]] == ["x", "y"]
