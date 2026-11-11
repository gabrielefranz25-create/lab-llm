"""Test della calcolatrice sicura (logica con ast, senza eval) e dell'involucro FastMCP in memoria."""

import asyncio

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from server_mcp import calcolatrice
from server_mcp.calcolatrice import ErroreCalcolo, formatta, valuta


@pytest.mark.parametrize("espressione, atteso", [
    ("17*23", 391),
    ("2 + 3 * 4", 14),
    ("(2 + 3) * 4", 20),
    ("7 / 2", 3.5),
    ("7 // 2", 3),
    ("7 % 3", 1),
    ("2 ** 10", 1024),
    ("-2 ** 2", -4),
    ("+5 - -3", 8),
    ("1.5 * 4", 6.0),
])
def test_espressioni_valide(espressione, atteso):
    assert valuta(espressione) == atteso


def test_simboli_alternativi():
    assert valuta("2^3") == 8
    assert valuta("6 × 7") == 42
    assert valuta("9 ÷ 2") == 4.5


@pytest.mark.parametrize("valore, testo", [(391, "391"), (3.5, "3.5"), (2.0, "2"), (1 / 3, "0.3333333333")])
def test_formatta(valore, testo):
    assert formatta(valore) == testo


@pytest.mark.parametrize("espressione, messaggio", [
    ("", "espressione mancante"),
    ("   ", "espressione mancante"),
    ("1+" * 101 + "1", "troppo lunga"),
    ("2 +", "espressione non valida"),
    ("__import__('os')", "chiamata di funzione"),
    ("x + 1", "nome «x»"),
    ("(1).real", "attributo"),
    ("1 < 2", "confronto"),
    ("3,5 * 2", "usa il punto per i decimali"),
    ("'a' * 3", "elemento non consentito"),
    ("True + 1", "elemento non consentito"),
    ("2j * 2", "elemento non consentito"),
    ("1 / 0", "divisione per zero"),
    ("5 % 0", "divisione per zero"),
    ("0 ** -1", "divisione per zero"),
    ("2 ** 1000", "esponente troppo grande"),
    ("10 ** 60 * 10 ** 60", "risultato troppo grande"),
    ("1e300 * 1e300", "risultato troppo grande"),
    ("(-8) ** 0.5", "risultato non reale"),
])
def test_errori(espressione, messaggio):
    with pytest.raises(ErroreCalcolo, match=messaggio):
        valuta(espressione)


def _esegui(operazione):
    async def corpo():
        async with Client(calcolatrice.mcp) as c:
            return await operazione(c)
    return asyncio.run(corpo())


def test_catalogo_calcolatrice():
    strumenti = _esegui(lambda c: c.list_tools())
    assert [s.name for s in strumenti] == ["calcola"]
    assert strumenti[0].input_schema["required"] == ["espressione"]
    assert "calcol" in strumenti[0].description.lower()


def test_chiamata_calcola():
    risultato = _esegui(lambda c: c.call_tool("calcola", {"espressione": "17*23"}))
    assert risultato.content[0].text == "17*23 = 391"


def test_chiamata_con_errore_diventa_tool_error():
    with pytest.raises(ToolError, match="chiamata di funzione"):
        _esegui(lambda c: c.call_tool("calcola", {"espressione": "__import__('os')"}))
