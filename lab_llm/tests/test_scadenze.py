"""Test di giorni e scadenze (date ISO, festività da file locale) e dell'involucro FastMCP in memoria."""

import asyncio
from datetime import date

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from server_mcp import scadenze
from server_mcp.scadenze import (ErroreScadenze, carica_festivita, conta_giorni, descrivi_intervallo,
                                 descrivi_spostamento, leggi_data, sposta)


@pytest.fixture(scope="module")
def festivita():
    return carica_festivita()


def test_file_delle_festivita(festivita):
    assert festivita.nome(date(2026, 12, 25)) == "Natale"
    assert festivita.nome(date(2026, 4, 6)) == "Lunedì dell'Angelo"
    assert festivita.nome(date(2026, 4, 7)) is None
    assert festivita.anni_mobili == set(range(2024, 2031))


def test_leggi_data():
    assert leggi_data("2024-02-29") == date(2024, 2, 29)
    assert leggi_data(" oggi ", oggi=date(2026, 11, 11)) == date(2026, 11, 11)
    assert leggi_data("OGGI", oggi=date(2026, 11, 11)) == date(2026, 11, 11)


@pytest.mark.parametrize("testo", ["2023-02-29", "28/02/2024", "2024-2-3", "domani", "", "2024-13-01"])
def test_data_non_valida(testo):
    with pytest.raises(ErroreScadenze, match="data non valida"):
        leggi_data(testo)


def test_conta_giorni_con_festivita_e_fine_settimana(festivita):
    # Dal 20/12/2026 (domenica) al 10/01/2027: 15 feriali, meno Natale, Capodanno ed Epifania.
    calendario, lavorativi, scoperti = conta_giorni(date(2026, 12, 20), date(2027, 1, 10), festivita)
    assert (calendario, lavorativi, scoperti) == (21, 12, [])


def test_conta_giorni_stesso_giorno(festivita):
    assert conta_giorni(date(2026, 5, 4), date(2026, 5, 4), festivita) == (0, 0, [])


def test_fine_prima_dell_inizio(festivita):
    with pytest.raises(ErroreScadenze, match="precede"):
        conta_giorni(date(2026, 5, 4), date(2026, 5, 1), festivita)


def test_intervallo_troppo_ampio(festivita):
    with pytest.raises(ErroreScadenze, match="intervallo troppo ampio"):
        conta_giorni(date(2020, 1, 1), date(2035, 1, 1), festivita)


def test_anno_senza_festivita_mobili(festivita):
    _, _, scoperti = conta_giorni(date(2030, 12, 20), date(2031, 1, 10), festivita)
    assert scoperti == [2031]


def test_sposta_di_calendario(festivita):
    assert sposta(date(2024, 2, 28), 1, False, festivita) == (date(2024, 2, 29), [])
    assert sposta(date(2023, 2, 28), 1, False, festivita) == (date(2023, 3, 1), [])
    assert sposta(date(2026, 3, 10), -10, False, festivita) == (date(2026, 2, 28), [])


def test_sposta_lavorativi_salta_ponte_di_natale(festivita):
    # Giovedì 24/12/2026 + 1 lavorativo: Natale (ven), sabato e domenica saltati.
    assert sposta(date(2026, 12, 24), 1, True, festivita) == (date(2026, 12, 28), [])
    assert sposta(date(2026, 12, 28), -1, True, festivita) == (date(2026, 12, 24), [])
    assert sposta(date(2026, 12, 24), 0, True, festivita) == (date(2026, 12, 24), [])


def test_sposta_dichiara_anni_scoperti(festivita):
    assert sposta(date(2031, 1, 1), 1, True, festivita) == (date(2031, 1, 2), [2031])


@pytest.mark.parametrize("giorni", [3651, -3651])
def test_giorni_fuori_intervallo(festivita, giorni):
    with pytest.raises(ErroreScadenze, match="tra -3650 e 3650"):
        sposta(date(2026, 1, 1), giorni, False, festivita)


def test_testi(festivita):
    intervallo = descrivi_intervallo("2026-12-20", "2027-01-10", festivita)
    assert intervallo.startswith("Dal 2026-12-20 al 2027-01-10: 21 giorni di calendario, 12 giorni lavorativi")
    assert intervallo.endswith("Calcolo indicativo, non normativo.")
    spostamento = descrivi_spostamento("2026-12-24", 1, True, festivita)
    assert spostamento.startswith("2026-12-24 + 1 giorni lavorativi = 2026-12-28 (lunedì).")
    assert "Festività mobili non note per: 2031" in descrivi_spostamento("2031-01-01", 1, True, festivita)


def _esegui(operazione):
    async def corpo():
        async with Client(scadenze.mcp) as c:
            return await operazione(c)
    return asyncio.run(corpo())


def test_catalogo_scadenze():
    strumenti = {s.name: s for s in _esegui(lambda c: c.list_tools())}
    assert set(strumenti) == {"giorni_tra", "aggiungi_giorni"}
    assert strumenti["aggiungi_giorni"].input_schema["required"] == ["data", "giorni"]


def test_chiamata_giorni_tra():
    risultato = _esegui(lambda c: c.call_tool("giorni_tra", {"data_inizio": "2026-12-20",
                                                              "data_fine": "2027-01-10"}))
    assert "12 giorni lavorativi" in risultato.content[0].text


def test_chiamata_con_errore_diventa_tool_error():
    with pytest.raises(ToolError, match="data non valida"):
        _esegui(lambda c: c.call_tool("aggiungi_giorni", {"data": "31/12/2026", "giorni": 3}))
