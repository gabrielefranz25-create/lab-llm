"""Test della logica dell'orologio condivisa dalle tre varianti (locale, FastAPI, FastMCP)."""

from datetime import datetime, timezone

import pytest

from servizio_orologio.logica import FusoNonValido, descrivi_ora

INVERNO = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)


def test_descrivi_ora_tokyo():
    risultato = descrivi_ora("Asia/Tokyo", INVERNO)
    assert "Fuso orario: Asia/Tokyo (JST, UTC+09:00)" in risultato
    assert "Data: giovedì 15 gennaio 2026" in risultato
    assert "Ora: 19:00:00" in risultato
    assert "ISO 8601: 2026-01-15T19:00:00+09:00" in risultato


def test_fuso_non_valido_solleva_con_motivo_comune():
    with pytest.raises(FusoNonValido) as info:
        descrivi_ora("Mars/Olympus", INVERNO)
    assert str(info.value) == "fuso orario 'Mars/Olympus' non riconosciuto. Usa un nome IANA come 'Europe/Rome'."


def test_fuso_vuoto_non_valido():
    with pytest.raises(FusoNonValido):
        descrivi_ora("", INVERNO)


def test_senza_istante_usa_ora_attuale():
    prima = datetime.now(timezone.utc).replace(microsecond=0)
    iso = descrivi_ora("UTC").rsplit("ISO 8601: ", 1)[1]
    assert datetime.fromisoformat(iso) >= prima
