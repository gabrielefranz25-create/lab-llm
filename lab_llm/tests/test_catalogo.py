"""Test del catalogo locale dei corsi (ricerca e dettaglio sullo stesso file) e dell'involucro FastMCP."""

import asyncio
import json

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from server_mcp import catalogo
from server_mcp.catalogo import (ErroreCatalogo, carica_corsi, cerca, descrivi_dettaglio,
                                 descrivi_ricerca, dettaglio)


@pytest.fixture
def corsi(tmp_path):
    percorso = tmp_path / "corsi.json"
    percorso.write_text(json.dumps([
        {"codice": "AA-1", "titolo": "Python di base", "sede": "Pordenone", "durata_ore": 20,
         "descrizione": "Primi passi."},
        {"codice": "AA-2", "titolo": "Python avanzato", "sede": "Udine", "durata_ore": 30,
         "descrizione": "Decoratori e generatori."},
        {"codice": "BB-1", "titolo": "Docker", "sede": "Pordenone", "durata_ore": 10,
         "descrizione": "Container con Python."},
    ]), encoding="utf-8")
    return carica_corsi(percorso)


def test_file_del_catalogo_reale():
    corsi = carica_corsi()
    assert len(corsi) >= 8
    assert {"codice", "titolo", "sede", "durata_ore", "descrizione"} <= set(corsi[0])
    assert len({c["codice"] for c in corsi}) == len(corsi)


def test_ricerca_per_una_parola_senza_maiuscole(corsi):
    assert [c["codice"] for c in cerca(corsi, "PYTHON", 10)] == ["AA-1", "AA-2", "BB-1"]


def test_ricerca_richiede_tutte_le_parole(corsi):
    assert [c["codice"] for c in cerca(corsi, "python pordenone", 10)] == ["AA-1", "BB-1"]


def test_ricerca_sul_codice(corsi):
    assert [c["codice"] for c in cerca(corsi, "bb-1", 10)] == ["BB-1"]


def test_max_risultati(corsi):
    assert len(cerca(corsi, "python", 2)) == 2


@pytest.mark.parametrize("massimo", [0, 11])
def test_max_risultati_fuori_intervallo(corsi, massimo):
    with pytest.raises(ErroreCatalogo, match="tra 1 e 10"):
        cerca(corsi, "python", massimo)


def test_testo_vuoto(corsi):
    with pytest.raises(ErroreCatalogo, match="testo di ricerca mancante"):
        cerca(corsi, "  ", 5)


def test_nessun_risultato_dichiarato(corsi):
    assert descrivi_ricerca(corsi, "cucina", 5) == "Nessun corso trovato per «cucina»."


def test_testo_della_ricerca(corsi):
    assert descrivi_ricerca(corsi, "pordenone", 5) == (
        "Trovati 2 corsi per «pordenone»:\nAA-1 – Python di base (Pordenone)\nBB-1 – Docker (Pordenone)")


def test_dettaglio_senza_maiuscole(corsi):
    assert dettaglio(corsi, " aa-2 ")["titolo"] == "Python avanzato"
    testo = descrivi_dettaglio(corsi, "AA-2")
    assert "Codice: AA-2" in testo and "Sede: Udine" in testo and "Durata: 30 ore" in testo


def test_codice_inesistente(corsi):
    with pytest.raises(ErroreCatalogo, match="nessun corso con codice «XX-99»"):
        dettaglio(corsi, "XX-99")


def _esegui(operazione):
    async def corpo():
        async with Client(catalogo.mcp) as c:
            return await operazione(c)
    return asyncio.run(corpo())


def test_catalogo_mcp_con_due_tool_distinti():
    strumenti = {s.name: s for s in _esegui(lambda c: c.list_tools())}
    assert set(strumenti) == {"cerca_corsi", "dettaglio_corso"}
    assert strumenti["cerca_corsi"].description != strumenti["dettaglio_corso"].description
    assert strumenti["dettaglio_corso"].input_schema["required"] == ["codice"]


def test_chiamata_cerca_corsi():
    risultato = _esegui(lambda c: c.call_tool("cerca_corsi", {"testo": "Pordenone"}))
    assert risultato.content[0].text.startswith("Trovati ")


def test_chiamata_con_errore_diventa_tool_error():
    with pytest.raises(ToolError, match="nessun corso con codice"):
        _esegui(lambda c: c.call_tool("dettaglio_corso", {"codice": "XX-99"}))
