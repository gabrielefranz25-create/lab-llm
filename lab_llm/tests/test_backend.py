"""Test del back-end: API con archivio in memoria e agente simulato, cliente dell'agente, configurazione."""

import json
import logging

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.agente_remoto import AgenteNonDisponibile, ClienteAgente
from backend.api import crea_app
from backend.archivio import ArchivioMemoria
from backend.config import ErroreConfigurazione, carica_config


class AgenteFinto:
    """Come ClienteAgente: accoda domanda e risposta alla cronologia; può fallire con un errore."""

    def __init__(self, errore=None):
        self.errore = errore
        self.richieste = []

    def chat(self, messaggio, cronologia, riassunto):
        self.richieste.append((messaggio, cronologia, riassunto))
        if self.errore:
            raise self.errore
        return {"risposta": f"risposta a {messaggio}", "riassunto": riassunto + "+",
                "cronologia": cronologia + [{"type": "human", "data": {"content": messaggio}}],
                "strumenti": [{"nome": "ora_corrente", "argomenti": {"fuso_orario": "Asia/Tokyo"}, "esito": "ok"}]}

    def stato(self):
        return {"raggiungibile": self.errore is None}


def _client(agente=None, archivio=None):
    return TestClient(crea_app(archivio or ArchivioMemoria(), agente or AgenteFinto()))


def test_crea_elenca_leggi_ed_elimina():
    client = _client()
    creata = client.post("/chat")
    assert creata.status_code == 201 and creata.json()["titolo"] == "Nuova chat"
    chat_id = creata.json()["id"]
    assert [c["id"] for c in client.get("/chat").json()] == [chat_id]
    assert client.get(f"/chat/{chat_id}").json()["messaggi"] == []
    assert client.delete(f"/chat/{chat_id}").status_code == 204
    assert client.get(f"/chat/{chat_id}").status_code == 404 and client.get("/chat").json() == []


def test_titolo_scelto_alla_creazione():
    assert _client().post("/chat", json={"titolo": "Orari"}).json()["titolo"] == "Orari"


def test_invio_salva_domanda_e_risposta(caplog):
    client = _client()
    chat_id = client.post("/chat").json()["id"]
    with caplog.at_level(logging.INFO, logger="backend.api"):
        scambio = client.post(f"/chat/{chat_id}/messaggi", json={"testo": "Che ore sono a Tokyo?"})
    assert scambio.status_code == 200
    corpo = scambio.json()
    assert corpo["domanda"]["ruolo"] == "utente" and corpo["domanda"]["testo"] == "Che ore sono a Tokyo?"
    assert corpo["risposta"]["testo"] == "risposta a Che ore sono a Tokyo?"
    assert corpo["risposta"]["strumenti"][0]["nome"] == "ora_corrente"
    chat = client.get(f"/chat/{chat_id}").json()
    assert chat["titolo"] == "Che ore sono a Tokyo?" and len(chat["messaggi"]) == 2
    assert f"backend: chat {chat_id} messaggio inviato all'agente -> 200" in caplog.text


def test_cronologia_e_riassunto_ripassati_all_agente():
    agente = AgenteFinto()
    client = _client(agente)
    chat_id = client.post("/chat").json()["id"]
    client.post(f"/chat/{chat_id}/messaggi", json={"testo": "uno"})
    client.post(f"/chat/{chat_id}/messaggi", json={"testo": "due"})
    messaggio, cronologia, riassunto = agente.richieste[1]
    assert messaggio == "due" and cronologia == [{"type": "human", "data": {"content": "uno"}}] and riassunto == "+"


def test_agente_non_raggiungibile_nulla_salvato(caplog):
    errore = AgenteNonDisponibile(503, "L'agente non è raggiungibile su http://agente:8000 (ConnectError).")
    client = _client(AgenteFinto(errore))
    chat_id = client.post("/chat").json()["id"]
    with caplog.at_level(logging.WARNING, logger="backend.api"):
        risposta = client.post(f"/chat/{chat_id}/messaggi", json={"testo": "ciao"})
    assert risposta.status_code == 503 and risposta.json()["errore"].startswith("L'agente non è raggiungibile")
    assert client.get(f"/chat/{chat_id}").json()["messaggi"] == []
    assert "-> 503" in caplog.text


def test_errore_dell_agente_diventa_502():
    client = _client(AgenteFinto(AgenteNonDisponibile(500, "Errore dell'agente: troppi passaggi")))
    chat_id = client.post("/chat").json()["id"]
    risposta = client.post(f"/chat/{chat_id}/messaggi", json={"testo": "ciao"})
    assert risposta.status_code == 502 and "troppi passaggi" in risposta.json()["errore"]


def test_messaggio_vuoto_e_chat_inesistente():
    client = _client()
    chat_id = client.post("/chat").json()["id"]
    assert client.post(f"/chat/{chat_id}/messaggi", json={"testo": "  "}).status_code == 400
    assert client.post("/chat/999/messaggi", json={"testo": "ciao"}).status_code == 404
    assert client.delete("/chat/999").status_code == 404
    assert client.get("/chat/999").json() == {"errore": "La chat 999 non esiste."}


def test_stato():
    assert _client().get("/stato").status_code == 200
    risposta = _client(AgenteFinto(AgenteNonDisponibile(503, "x"))).get("/stato")
    assert risposta.status_code == 503 and risposta.json()["agente"] == {"raggiungibile": False}


def test_openapi_con_tutte_le_operazioni():
    schema = _client().get("/openapi.json").json()
    assert schema["info"]["title"] == "Back-end delle chat"
    percorsi = schema["paths"]
    assert set(percorsi["/chat"]) == {"get", "post"}
    assert set(percorsi["/chat/{chat_id}"]) == {"get", "delete"}
    assert "post" in percorsi["/chat/{chat_id}/messaggi"]


# --- cliente dell'agente ---------------------------------------------------------------------

def _cliente(gestisci):
    return ClienteAgente("http://agente:8000", http=httpx.Client(base_url="http://agente:8000",
                                                                 transport=httpx.MockTransport(gestisci)))


def test_cliente_agente_inoltra_cronologia_e_riassunto():
    ricevute = []

    def gestisci(request):
        ricevute.append(json.loads(request.content))
        return httpx.Response(200, json={"risposta": "ok", "cronologia": [], "riassunto": "", "strumenti": []})

    assert _cliente(gestisci).chat("ciao", [{"type": "human"}], "r")["risposta"] == "ok"
    assert ricevute == [{"messaggio": "ciao", "cronologia": [{"type": "human"}], "riassunto": "r"}]


def test_cliente_agente_errori():
    def spento(request):
        raise httpx.ConnectError("rifiutata", request=request)
    with pytest.raises(AgenteNonDisponibile, match="non è raggiungibile") as info:
        _cliente(spento).chat("ciao", [], "")
    assert info.value.codice == 503
    with pytest.raises(AgenteNonDisponibile, match="modello giù") as info:
        _cliente(lambda r: httpx.Response(503, json={"errore": "modello giù"})).chat("ciao", [], "")
    assert info.value.codice == 503
    assert _cliente(spento).stato()["raggiungibile"] is False


# --- configurazione --------------------------------------------------------------------------

def test_config_backend():
    config = carica_config({"DATABASE_URL": "postgresql://a:b@db:5432/lab"})
    assert (config.agente_url, config.ascolto, config.porta) == ("http://127.0.0.1:8000", "127.0.0.1", 8080)
    with pytest.raises(ErroreConfigurazione, match="DATABASE_URL"):
        carica_config({})
    with pytest.raises(ErroreConfigurazione, match="BACKEND_PORTA"):
        carica_config({"DATABASE_URL": "x", "BACKEND_PORTA": "zero"})
