"""Test del convertitore di unità (elenco chiuso, alias italiani, temperatura) e dell'involucro FastMCP."""

import asyncio
import math

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from server_mcp import unita
from server_mcp.unita import ErroreUnita, converti, descrivi_conversione


@pytest.mark.parametrize("valore, da, a, atteso", [
    (10, "mi", "km", 16.09344),
    (1, "km", "m", 1000),
    (12, "in", "cm", 30.48),
    (1, "lb", "g", 453.59237),
    (2, "t", "kg", 2000),
    (1, "gal", "l", 3.785411784),
    (1, "m3", "l", 1000),
    (36, "km/h", "m/s", 10),
    (1, "kn", "km/h", 1.852),
    (0, "C", "F", 32),
    (212, "F", "C", 100),
    (0, "K", "C", -273.15),
    (25, "C", "K", 298.15),
])
def test_conversioni(valore, da, a, atteso):
    risultato, _ = converti(valore, da, a)
    assert math.isclose(risultato, atteso, rel_tol=1e-9, abs_tol=1e-9)


@pytest.mark.parametrize("da, a", [
    ("miglia", "chilometri"), ("MI", "KM"), ("Miglio", " km "), ("celsius", "fahrenheit"),
    ("°C", "°F"), ("libbre", "grammi"), ("nodi", "chilometri orari"), ("m³", "litri"),
])
def test_alias_e_maiuscole(da, a):
    converti(1, da, a)  # nessun errore


def test_grandezza_restituita():
    assert converti(1, "km", "m")[1] == "lunghezza"
    assert converti(1, "C", "K")[1] == "temperatura"


def test_testo_del_risultato():
    assert descrivi_conversione(10, "miglia", "km") == "10 mi = 16.0934 km (lunghezza)"
    assert descrivi_conversione(100, "celsius", "fahrenheit") == "100 °C = 212 °F (temperatura)"


def test_unita_sconosciuta_elenca_le_ammesse():
    with pytest.raises(ErroreUnita, match=r"unità «parsec» non riconosciuta.*lunghezza: mm, cm, m"):
        converti(1, "parsec", "km")


def test_grandezze_diverse():
    with pytest.raises(ErroreUnita, match=r"impossibile convertire km \(lunghezza\) in kg \(massa\)"):
        converti(1, "km", "kg")


def test_sotto_lo_zero_assoluto():
    with pytest.raises(ErroreUnita, match="sotto lo zero assoluto"):
        converti(-300, "C", "K")
    with pytest.raises(ErroreUnita, match="sotto lo zero assoluto"):
        converti(-1, "K", "C")


@pytest.mark.parametrize("valore", [math.inf, -math.inf, math.nan])
def test_valore_non_finito(valore):
    with pytest.raises(ErroreUnita, match="valore non valido"):
        converti(valore, "m", "km")


def _esegui(operazione):
    async def corpo():
        async with Client(unita.mcp) as c:
            return await operazione(c)
    return asyncio.run(corpo())


def test_catalogo_unita():
    strumenti = _esegui(lambda c: c.list_tools())
    assert [s.name for s in strumenti] == ["converti_unita"]
    assert set(strumenti[0].input_schema["required"]) == {"valore", "da", "a"}


def test_chiamata_converti_unita():
    risultato = _esegui(lambda c: c.call_tool("converti_unita", {"valore": 10, "da": "mi", "a": "km"}))
    assert risultato.content[0].text == "10 mi = 16.0934 km (lunghezza)"


def test_chiamata_con_errore_diventa_tool_error():
    with pytest.raises(ToolError, match="impossibile convertire"):
        _esegui(lambda c: c.call_tool("converti_unita", {"valore": 1, "da": "km", "a": "kg"}))
