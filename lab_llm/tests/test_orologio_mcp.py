"""Test del server FastMCP dell'orologio (variante 03), con il client fastmcp in memoria."""

import asyncio

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from server_mcp.orologio import crea_server


def _esegui(azione, fuso_predefinito="Europe/Rome"):
    async def corpo():
        async with Client(crea_server(fuso_predefinito)) as client:
            return await azione(client)
    return asyncio.run(corpo())


def test_catalogo_con_un_solo_tool():
    strumenti = _esegui(lambda c: c.list_tools())
    assert [s.name for s in strumenti] == ["ora_corrente"]
    voce = strumenti[0]
    assert "fuso_orario" in voce.input_schema["properties"]
    assert "Europe/Rome" in voce.description


def test_chiamata_con_fuso():
    risultato = _esegui(lambda c: c.call_tool("ora_corrente", {"fuso_orario": "Asia/Tokyo"}))
    assert "Fuso orario: Asia/Tokyo (JST, UTC+09:00)" in risultato.content[0].text


def test_chiamata_senza_argomenti_usa_il_predefinito():
    risultato = _esegui(lambda c: c.call_tool("ora_corrente", {}), fuso_predefinito="America/New_York")
    assert "Fuso orario: America/New_York" in risultato.content[0].text


def test_fuso_non_valido_diventa_tool_error():
    with pytest.raises(ToolError, match="fuso orario 'Mars/Olympus' non riconosciuto"):
        _esegui(lambda c: c.call_tool("ora_corrente", {"fuso_orario": "Mars/Olympus"}))
