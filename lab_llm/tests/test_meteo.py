"""Test della logica meteo con httpx.MockTransport: nessuna richiesta di rete."""

import httpx
import pytest

from server_mcp import meteo
from server_mcp.meteo import ErroreMeteo, Localita, cerca_localita, descrivi_codice

# `testo_*` si importa dal modulo: pytest raccoglierebbe come test i nomi che iniziano per "test".

UDINE = {"name": "Udine", "admin1": "Friuli-Venezia Giulia", "country": "Italia",
         "latitude": 46.06, "longitude": 13.24}
UDINE_USA = {"name": "Udine", "admin1": "Ohio", "country": "Stati Uniti",
             "latitude": 40.0, "longitude": -81.0}
ATTUALE = {"timezone": "Europe/Rome",
           "current": {"time": "2026-11-09T10:00", "temperature_2m": 12.3,
                       "relative_humidity_2m": 80, "weather_code": 3, "wind_speed_10m": 9.4}}
PREVISIONI = {"timezone": "Europe/Rome",
              "daily": {"time": ["2026-11-09", "2026-11-10", "2026-11-11"],
                        "weather_code": [3, 61, 0],
                        "temperature_2m_max": [12.0, 10.5, 14.0],
                        "temperature_2m_min": [5.0, 6.5, 4.0],
                        "precipitation_probability_max": [10, 40, 0]}}


def _client(risposte, richieste=None):
    """Client con trasporto finto: `risposte` mappa host -> JSON, oppure un'eccezione/status."""
    registro = richieste if richieste is not None else []

    def gestore(request: httpx.Request) -> httpx.Response:
        registro.append(request)
        esito = risposte[request.url.host]
        if isinstance(esito, Exception):
            raise esito
        if isinstance(esito, int):
            return httpx.Response(esito)
        return httpx.Response(200, json=esito)

    return httpx.Client(transport=httpx.MockTransport(gestore))


def _geo(*risultati):
    return {"results": list(risultati)}


def test_meteo_attuale_formattato():
    client = _client({"geocoding-api.open-meteo.com": _geo(UDINE),
                      "api.open-meteo.com": ATTUALE})
    testo = meteo.testo_meteo_attuale(client, "Udine")
    assert "Località: Udine (Friuli-Venezia Giulia, Italia)" in testo
    assert "12.3 °C" in testo
    assert "80 %" in testo
    assert "9.4 km/h" in testo
    assert "cielo coperto" in testo


def test_previsioni_una_riga_per_giorno():
    richieste = []
    client = _client({"geocoding-api.open-meteo.com": _geo(UDINE),
                      "api.open-meteo.com": PREVISIONI}, richieste)
    testo = meteo.testo_previsioni(client, "Udine", 3)
    righe = [r for r in testo.splitlines() if r.startswith("2026-")]
    assert len(righe) == 3
    assert righe[0].startswith("2026-11-09")
    previsione = [r for r in richieste if r.url.host == "api.open-meteo.com"][0]
    assert previsione.url.params["forecast_days"] == "3"


def test_citta_ambigua_dichiarata():
    client = _client({"geocoding-api.open-meteo.com": _geo(UDINE, UDINE_USA),
                      "api.open-meteo.com": ATTUALE})
    testo = meteo.testo_meteo_attuale(client, "Udine")
    assert "Località: Udine (Friuli-Venezia Giulia, Italia)" in testo
    assert "Altre località con questo nome:" in testo
    assert testo.index("Altre località con questo nome:") < testo.index("Udine (Ohio, Stati Uniti)")


def test_citta_non_trovata():
    richieste = []
    client = _client({"geocoding-api.open-meteo.com": {}}, richieste)
    with pytest.raises(ErroreMeteo, match="città non trovata: Atlantide"):
        meteo.testo_meteo_attuale(client, "Atlantide")
    assert all(r.url.host != "api.open-meteo.com" for r in richieste)


def test_timeout_distinto_da_http_500():
    timeout = _client({"geocoding-api.open-meteo.com": httpx.ConnectTimeout("lento")})
    with pytest.raises(ErroreMeteo, match="servizio meteo non raggiungibile"):
        meteo.testo_meteo_attuale(timeout, "Udine")
    errore = _client({"geocoding-api.open-meteo.com": 500})
    with pytest.raises(ErroreMeteo, match=r"servizio meteo non disponibile \(HTTP 500\)"):
        meteo.testo_meteo_attuale(errore, "Udine")


def test_risposta_non_valida():
    client = _client({"geocoding-api.open-meteo.com": _geo(UDINE),
                      "api.open-meteo.com": {"timezone": "Europe/Rome"}})
    with pytest.raises(ErroreMeteo, match="risposta del servizio meteo non valida"):
        meteo.testo_meteo_attuale(client, "Udine")


@pytest.mark.parametrize("citta, giorni", [("  ", 3), ("Udine", 0), ("Udine", 8)])
def test_argomenti_non_validi(citta, giorni):
    richieste = []
    client = _client({}, richieste)
    with pytest.raises(ErroreMeteo):
        meteo.testo_previsioni(client, citta, giorni)
    assert richieste == []


def test_citta_vuota_nel_meteo_attuale():
    richieste = []
    with pytest.raises(ErroreMeteo):
        meteo.testo_meteo_attuale(_client({}, richieste), "  ")
    assert richieste == []


def test_codice_sconosciuto():
    assert descrivi_codice(42) == "condizioni non classificate (codice 42)"


def test_citta_con_spazi_e_accenti_arriva_intatta():
    richieste = []
    client = _client({"geocoding-api.open-meteo.com": _geo(
        {"name": "São Paulo", "admin1": "San Paolo", "country": "Brasile",
         "latitude": -23.5, "longitude": -46.6})}, richieste)
    cerca_localita(client, "São Paulo")
    assert richieste[0].url.params["name"] == "São Paulo"
    assert " " not in str(richieste[0].url)


def test_localita_senza_regione():
    client = _client({"geocoding-api.open-meteo.com": _geo(
        {"name": "Tokyo", "country": "Giappone", "latitude": 35.7, "longitude": 139.7}),
        "api.open-meteo.com": ATTUALE})
    testo = meteo.testo_meteo_attuale(client, "Tokyo")
    assert "Località: Tokyo (Giappone)" in testo
    assert "None" not in testo
    assert Localita("Udine", None, "Italia", 0, 0).descrizione() == "Udine (Italia)"


def test_previsioni_con_valori_nulli():
    dati = {"timezone": "Europe/Rome",
            "daily": {**PREVISIONI["daily"], "precipitation_probability_max": [None, 40, 0]}}
    client = _client({"geocoding-api.open-meteo.com": _geo(UDINE), "api.open-meteo.com": dati})
    righe = [r for r in meteo.testo_previsioni(client, "Udine", 3).splitlines() if r.startswith("2026-")]
    assert "pioggia n.d." in righe[0]
    assert "pioggia 40 %" in righe[1]
