"""Prova del back-end con PostgreSQL vero e l'agente vero (PROVA_REALE=1 e POSTGRES_URL).

Back-end e servizio dell'agente girano in-process (TestClient): il back-end chiama `POST /chat`
dell'agente come farebbe in rete. Dopo il «riavvio» (nuovo archivio, nuova app) la chat c'è ancora.
"""

import os
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from agente.config import carica_config
from agente.main import costruisci_agente
from agente.servizio import crea_app as crea_app_agente
from backend.agente_remoto import ClienteAgente
from backend.api import crea_app
from backend.archivio import ArchivioPostgres

POSTGRES_URL = os.environ.get("POSTGRES_URL")

pytestmark = [
    pytest.mark.reale,
    pytest.mark.skipif(os.environ.get("PROVA_REALE") != "1" or not POSTGRES_URL,
                       reason="prova reale: imposta PROVA_REALE=1 e POSTGRES_URL"),
]


@pytest.fixture(scope="module")
def agente_remoto():
    config = replace(carica_config(), server_mcp=("calcolatrice",), variante_orologio="locale",
                     trasporto_mcp="stdio")
    with costruisci_agente(config) as (agente, _intestazione):
        yield ClienteAgente("http://testserver", http=TestClient(crea_app_agente(agente)))


def test_chat_persistente_dopo_il_riavvio(agente_remoto):
    archivio = ArchivioPostgres(POSTGRES_URL)
    archivio.svuota()  # database di prova
    client = TestClient(crea_app(archivio, agente_remoto))
    chat_id = client.post("/chat").json()["id"]
    primo = client.post(f"/chat/{chat_id}/messaggi", json={"testo": "Che ore sono a Tokyo?"})
    assert primo.status_code == 200, primo.text
    assert primo.json()["risposta"]["strumenti"][0]["nome"] == "ora_corrente"
    secondo = client.post(f"/chat/{chat_id}/messaggi", json={"testo": "Quanto fa 15 per 12?"})
    assert secondo.status_code == 200, secondo.text

    riavviato = TestClient(crea_app(ArchivioPostgres(POSTGRES_URL), agente_remoto))
    chat = riavviato.get(f"/chat/{chat_id}").json()
    assert chat["titolo"] == "Che ore sono a Tokyo?"
    assert [m["ruolo"] for m in chat["messaggi"]] == ["utente", "assistente"] * 2
    assert "Tokyo" in chat["messaggi"][1]["testo"]
    assert [c["id"] for c in riavviato.get("/chat").json()] == [chat_id]
