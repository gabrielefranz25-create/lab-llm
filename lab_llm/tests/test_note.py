"""Test dell'archivio note su SQLite (file temporanei) e dell'involucro FastMCP in memoria."""

import asyncio
import sqlite3

import pytest
from fastmcp import Client

from server_mcp import note
from server_mcp.note import ArchivioNote, ErroreNote


@pytest.fixture
def archivio(tmp_path):
    return ArchivioNote(tmp_path / "n.sqlite3")


def test_aggiungi_restituisce_id_e_data(archivio):
    prima = archivio.aggiungi("comprare il latte")
    seconda = archivio.aggiungi("chiamare Anna")
    assert (prima.id, seconda.id) == (1, 2)
    assert prima.testo == "comprare il latte"
    assert len(prima.creata) == 16 and prima.creata[10] == "T"  # AAAA-MM-GGTHH:MM


def test_elenca_dalla_piu_recente_e_limite(archivio):
    for testo in ("a", "b", "c"):
        archivio.aggiungi(testo)
    assert [n.testo for n in archivio.elenca(10)] == ["c", "b", "a"]
    assert [n.testo for n in archivio.elenca(2)] == ["c", "b"]


def test_elenco_vuoto(tmp_path, monkeypatch):
    monkeypatch.setenv("NOTE_DB", str(tmp_path / "vuoto.sqlite3"))

    async def operazione():
        async with Client(note.mcp) as c:
            return await c.call_tool("elenca_note", {})
    assert asyncio.run(operazione()).content[0].text == "Nessuna nota salvata."


def test_elimina_per_id(archivio):
    archivio.aggiungi("a")
    archivio.aggiungi("b")
    eliminata = archivio.elimina(1)
    assert eliminata.testo == "a"
    assert [n.testo for n in archivio.elenca(10)] == ["b"]


def test_id_inesistente_non_cancella_niente(archivio):
    archivio.aggiungi("a")
    archivio.aggiungi("b")
    with pytest.raises(ErroreNote, match="nessuna nota con ID 99"):
        archivio.elimina(99)
    assert len(archivio.elenca(10)) == 2


def test_testo_vuoto_o_troppo_lungo(archivio):
    for testo in ("   ", "x" * 501):
        with pytest.raises(ErroreNote):
            archivio.aggiungi(testo)
    assert archivio.aggiungi("x" * 500).testo == "x" * 500
    assert len(archivio.elenca(10)) == 1


@pytest.mark.parametrize("limite", [0, 51])
def test_limite_fuori_intervallo(archivio, limite):
    with pytest.raises(ErroreNote):
        archivio.elenca(limite)


def test_persistenza_dopo_riapertura(tmp_path):
    percorso = tmp_path / "n.sqlite3"
    ArchivioNote(percorso).aggiungi("resta")
    assert [n.testo for n in ArchivioNote(percorso).elenca(10)] == ["resta"]


def test_testo_con_apostrofi_e_sql_salvato_letteralmente(archivio):
    testo = "l'esame; DROP TABLE note"
    archivio.aggiungi(testo)
    assert [n.testo for n in archivio.elenca(10)] == [testo]
    with sqlite3.connect(archivio.percorso) as conn:
        assert conn.execute("SELECT count(*) FROM note").fetchone() == (1,)


def test_archivio_non_accessibile(tmp_path):
    with pytest.raises(ErroreNote, match="archivio note non accessibile"):
        ArchivioNote(tmp_path)


def test_catalogo_note(tmp_path, monkeypatch):
    monkeypatch.setenv("NOTE_DB", str(tmp_path / "c.sqlite3"))

    async def operazione():
        async with Client(note.mcp) as c:
            return await c.list_tools()
    strumenti = {s.name: s for s in asyncio.run(operazione())}
    assert set(strumenti) == {"aggiungi_nota", "elenca_note", "elimina_nota"}
    assert "modifica" in strumenti["aggiungi_nota"].description
    assert "modifica" in strumenti["elimina_nota"].description
