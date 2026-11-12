"""Test dello strumento orologio con istanti fissi in UTC."""

import logging
from datetime import datetime, timezone

import httpx
import pytest

from agente.strumenti import calcola_ora, crea_ora_corrente, crea_ora_corrente_http

INVERNO = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
ESTATE = datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc)


def test_roma_inverno():
    risultato = calcola_ora("Europe/Rome", INVERNO)
    assert "Europe/Rome (CET, UTC+01:00)" in risultato
    assert "Data: giovedì 15 gennaio 2026" in risultato
    assert "Ora: 11:00:00" in risultato
    assert "ISO 8601: 2026-01-15T11:00:00+01:00" in risultato


def test_roma_estate():
    risultato = calcola_ora("Europe/Rome", ESTATE)
    assert "(CEST, UTC+02:00)" in risultato
    assert "mercoledì 15 luglio 2026" in risultato
    assert "Ora: 12:00:00" in risultato


def test_tokyo_cambia_giorno():
    risultato = calcola_ora("Asia/Tokyo", datetime(2026, 10, 26, 16, 42, tzinfo=timezone.utc))
    assert "(JST, UTC+09:00)" in risultato
    assert "martedì 27 ottobre 2026" in risultato
    assert "Ora: 01:42:00" in risultato


def test_new_york_offset_negativo():
    assert "UTC-05:00" in calcola_ora("America/New_York", INVERNO)


def test_fuso_non_valido_restituisce_errore():
    risultato = calcola_ora("Roma", INVERNO)
    assert risultato.startswith("Errore: fuso orario 'Roma' non riconosciuto")


def test_fuso_non_valido_registra_warning(caplog):
    with caplog.at_level(logging.WARNING):
        calcola_ora("Roma", INVERNO)
    assert any(r.levelno == logging.WARNING and "Roma" in r.getMessage() for r in caplog.records)


def test_ora_corrente_senza_argomenti_usa_predefinito():
    assert "Europe/Rome" in crea_ora_corrente(orologio=lambda: INVERNO).invoke({})


def test_ora_corrente_con_fuso():
    strumento = crea_ora_corrente(orologio=lambda: INVERNO)
    assert "Asia/Tokyo" in strumento.invoke({"fuso_orario": "Asia/Tokyo"})


def test_schema_strumento():
    strumento = crea_ora_corrente()
    assert strumento.name == "ora_corrente"
    assert "Europe/Rome" in strumento.description
    assert "fuso_orario" in strumento.args


# --- variante 02: wrapper HTTP verso il servizio FastAPI -----------------------------------------

URL = "http://orologio.test:8001"


def _wrapper(gestore):
    """Wrapper con un client httpx che non usa la rete: `gestore(request) -> Response`."""
    client = httpx.Client(transport=httpx.MockTransport(gestore))
    return crea_ora_corrente_http(URL, timeout=5.0, fuso_predefinito="Europe/Rome", client=client)


def test_http_ok_restituisce_il_risultato_del_servizio():
    richieste = []

    def gestore(request):
        richieste.append(request)
        return httpx.Response(200, json={"fuso_orario": "Asia/Tokyo", "risultato": "Ora: 19:00:00"})

    assert _wrapper(gestore).invoke({"fuso_orario": "Asia/Tokyo"}) == "Ora: 19:00:00"
    assert str(richieste[0].url) == f"{URL}/ora?fuso_orario=Asia%2FTokyo"


def test_http_senza_argomenti_invia_il_fuso_predefinito():
    richieste = []

    def gestore(request):
        richieste.append(request)
        return httpx.Response(200, json={"risultato": "ok"})

    _wrapper(gestore).invoke({})
    assert richieste[0].url.params["fuso_orario"] == "Europe/Rome"


def test_http_400_e_errore_dello_strumento():
    motivo = "fuso orario 'Mars/Olympus' non riconosciuto. Usa un nome IANA come 'Europe/Rome'."
    risultato = _wrapper(lambda r: httpx.Response(400, json={"detail": motivo})).invoke(
        {"fuso_orario": "Mars/Olympus"})
    assert risultato == f"Errore dallo strumento ora_corrente: {motivo}"


@pytest.mark.parametrize("gestore, dettaglio", [
    (lambda r: httpx.Response(500, text="boom"), "stato HTTP 500"),
    (lambda r: httpx.Response(200, text="non json"), "risposta non valida"),
    (lambda r: httpx.Response(200, json={"altro": 1}), "risposta non valida"),
])
def test_http_risposte_inattese_sono_errori_di_collegamento(gestore, dettaglio):
    risultato = _wrapper(gestore).invoke({"fuso_orario": "Asia/Tokyo"})
    assert risultato.startswith("Errore di collegamento HTTP con il servizio orologio: ")
    assert dettaglio in risultato


def test_http_servizio_spento_e_errore_di_collegamento():
    def gestore(request):
        raise httpx.ConnectError("Connection refused", request=request)

    risultato = _wrapper(gestore).invoke({"fuso_orario": "Asia/Tokyo"})
    assert risultato.startswith("Errore di collegamento HTTP con il servizio orologio: ")
    assert "Connection refused" in risultato


def test_http_timeout_e_errore_di_collegamento():
    def gestore(request):
        raise httpx.ReadTimeout("lento", request=request)

    risultato = _wrapper(gestore).invoke({"fuso_orario": "Asia/Tokyo"})
    assert risultato == ("Errore di collegamento HTTP con il servizio orologio: "
                         "nessuna risposta entro 5.0 secondi")


def test_http_stesso_contratto_della_variante_locale():
    locale = crea_ora_corrente("Europe/Rome")
    http = crea_ora_corrente_http(URL, timeout=5.0, fuso_predefinito="Europe/Rome")
    assert http.name == locale.name
    assert http.description == locale.description
    assert http.args == locale.args
    assert http.metadata == {"origine": "http:orologio"}


def test_http_log_della_chiamata(caplog):
    with caplog.at_level(logging.INFO, logger="agente.strumenti"):
        _wrapper(lambda r: httpx.Response(200, json={"risultato": "ok"})).invoke({"fuso_orario": "UTC"})
    assert f"orologio http: GET {URL}/ora fuso_orario=UTC -> 200" in [r.getMessage() for r in caplog.records]
