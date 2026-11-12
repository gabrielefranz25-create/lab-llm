"""Test del servizio FastAPI dell'orologio (variante 02), senza rete: TestClient in memoria."""

import logging

import pytest
from fastapi.testclient import TestClient

from servizio_orologio.api import crea_app


@pytest.fixture
def client():
    return TestClient(crea_app(fuso_predefinito="Europe/Rome"))


def test_ora_con_fuso(client):
    risposta = client.get("/ora", params={"fuso_orario": "Asia/Tokyo"})
    assert risposta.status_code == 200
    corpo = risposta.json()
    assert corpo["fuso_orario"] == "Asia/Tokyo"
    assert "Fuso orario: Asia/Tokyo (JST, UTC+09:00)" in corpo["risultato"]


def test_ora_senza_fuso_usa_predefinito(client):
    corpo = client.get("/ora").json()
    assert corpo["fuso_orario"] == "Europe/Rome"
    assert "Fuso orario: Europe/Rome" in corpo["risultato"]


def test_fuso_non_valido_400_con_motivo(client):
    risposta = client.get("/ora", params={"fuso_orario": "Mars/Olympus"})
    assert risposta.status_code == 400
    assert risposta.json() == {
        "detail": "fuso orario 'Mars/Olympus' non riconosciuto. Usa un nome IANA come 'Europe/Rome'."
    }


def test_salute(client):
    assert client.get("/salute").json() == {"stato": "ok"}


def test_log_della_richiesta(client, caplog):
    with caplog.at_level(logging.INFO, logger="servizio_orologio.api"):
        client.get("/ora", params={"fuso_orario": "Asia/Tokyo"})
        client.get("/ora", params={"fuso_orario": "Mars/Olympus"})
    messaggi = [r.getMessage() for r in caplog.records]
    assert "api orologio: fuso=Asia/Tokyo esito=ok" in messaggi
    assert "api orologio: fuso=Mars/Olympus esito=errore" in messaggi
