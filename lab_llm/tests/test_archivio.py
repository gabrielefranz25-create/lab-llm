"""Test dell'archivio delle chat: stessi test per la memoria e per PostgreSQL vero.

PostgreSQL solo con POSTGRES_URL impostata, per esempio con un container di prova:
docker run -d --name lab-postgres-test -e POSTGRES_USER=lab -e POSTGRES_PASSWORD=lab -e POSTGRES_DB=lab -p 55432:5432 postgres:16
$env:POSTGRES_URL="postgresql://lab:lab@localhost:55432/lab"
"""

import os

import pytest

from backend.archivio import ArchivioMemoria, ArchivioPostgres

POSTGRES_URL = os.environ.get("POSTGRES_URL")


@pytest.fixture(params=["memoria", "postgres"])
def archivio(request):
    if request.param == "memoria":
        return ArchivioMemoria()
    if not POSTGRES_URL:
        pytest.skip("PostgreSQL: imposta POSTGRES_URL")
    archivio = ArchivioPostgres(POSTGRES_URL)
    archivio.svuota()  # solo per i test: database di prova
    return archivio


def _turno(archivio, chat_id, domanda, risposta="ok"):
    return archivio.registra_turno(chat_id, domanda, risposta, [{"nome": "ora_corrente", "argomenti": {},
                                                                 "esito": "ok"}],
                                   cronologia=[{"type": "human", "data": {"content": domanda}}],
                                   riassunto=f"dopo {domanda}")


def test_crea_e_leggi_chat_vuota(archivio):
    chat = archivio.crea_chat()
    assert chat["titolo"] == "Nuova chat" and chat["creata_il"]
    letta = archivio.leggi_chat(chat["id"])
    assert letta["titolo"] == "Nuova chat" and letta["messaggi"] == []
    assert archivio.stato_agente(chat["id"]) == ([], "")


def test_turno_salva_messaggi_in_ordine_e_titolo(archivio):
    chat_id = archivio.crea_chat()["id"]
    _turno(archivio, chat_id, "Che ore sono a Tokyo? " + "x" * 80, "Sono le 10.")
    _turno(archivio, chat_id, "E a Roma?", "Sono le 2.")
    letta = archivio.leggi_chat(chat_id)
    assert [(m["ruolo"], m["testo"][:9]) for m in letta["messaggi"]] == [
        ("utente", "Che ore s"), ("assistente", "Sono le 1"), ("utente", "E a Roma?"), ("assistente", "Sono le 2")]
    assert letta["messaggi"][1]["strumenti"] == [{"nome": "ora_corrente", "argomenti": {}, "esito": "ok"}]
    assert letta["messaggi"][0]["strumenti"] == []
    assert letta["titolo"] == ("Che ore sono a Tokyo? " + "x" * 80)[:60]
    cronologia, riassunto = archivio.stato_agente(chat_id)
    assert cronologia == [{"type": "human", "data": {"content": "E a Roma?"}}] and riassunto == "dopo E a Roma?"


def test_titolo_scelto_alla_creazione_resta(archivio):
    chat_id = archivio.crea_chat("Orari")["id"]
    _turno(archivio, chat_id, "Che ore sono?")
    assert archivio.leggi_chat(chat_id)["titolo"] == "Orari"


def test_elenco_con_la_chat_piu_recente_prima(archivio):
    prima = archivio.crea_chat()["id"]
    seconda = archivio.crea_chat()["id"]
    _turno(archivio, prima, "aggiornata dopo")
    elenco = archivio.elenca_chat()
    assert [c["id"] for c in elenco] == [prima, seconda]
    assert elenco[0]["titolo"] == "aggiornata dopo" and elenco[0]["ultimo_messaggio_il"]


def test_elimina_chat_e_messaggi(archivio):
    chat_id = archivio.crea_chat()["id"]
    _turno(archivio, chat_id, "ciao")
    assert archivio.elimina_chat(chat_id) is True
    assert archivio.leggi_chat(chat_id) is None and archivio.stato_agente(chat_id) is None
    assert archivio.elimina_chat(chat_id) is False and archivio.elenca_chat() == []


def test_chat_inesistente(archivio):
    assert archivio.leggi_chat(999999) is None
    with pytest.raises(KeyError):
        _turno(archivio, 999999, "ciao")


def test_verifica(archivio):
    archivio.verifica()


@pytest.mark.skipif(not POSTGRES_URL, reason="PostgreSQL: imposta POSTGRES_URL")
def test_postgres_dati_presenti_dopo_il_riavvio():
    primo = ArchivioPostgres(POSTGRES_URL)
    primo.svuota()
    chat_id = primo.crea_chat()["id"]
    _turno(primo, chat_id, "resto qui?")
    riavviato = ArchivioPostgres(POSTGRES_URL)  # nuova istanza: come un back-end riavviato
    assert riavviato.leggi_chat(chat_id)["messaggi"][0]["testo"] == "resto qui?"


def test_postgres_non_raggiungibile():
    with pytest.raises(Exception):
        ArchivioPostgres("postgresql://lab:lab@127.0.0.1:1/lab", timeout=2)
