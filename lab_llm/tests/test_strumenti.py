"""Test dello strumento orologio con istanti fissi in UTC."""

import logging
from datetime import datetime, timezone

from agente.strumenti import calcola_ora, crea_ora_corrente

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
