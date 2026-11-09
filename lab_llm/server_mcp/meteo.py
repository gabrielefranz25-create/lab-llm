"""Logica del server meteo: geocoding e previsioni di Open-Meteo, senza dipendere da MCP."""

import logging
import os
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

URL_GEOCODING = "https://geocoding-api.open-meteo.com/v1/search"
URL_PREVISIONI = "https://api.open-meteo.com/v1/forecast"
GIORNI_MAX = 7

# Codici WMO restituiti da Open-Meteo (weather_code), in italiano.
CODICI_WMO = {
    0: "cielo sereno",
    1: "prevalentemente sereno",
    2: "parzialmente nuvoloso",
    3: "cielo coperto",
    45: "nebbia",
    48: "nebbia con brina",
    51: "pioggerella leggera",
    52: "pioggerella moderata",
    53: "pioggerella intensa",
    54: "pioggerella gelata leggera",
    55: "pioggerella gelata intensa",
    56: "pioggerella gelata leggera",
    57: "pioggerella gelata intensa",
    61: "pioggia debole",
    62: "pioggia moderata",
    63: "pioggia forte",
    64: "pioggia gelata debole",
    65: "pioggia gelata forte",
    66: "pioggia gelata debole",
    67: "pioggia gelata forte",
    71: "neve debole",
    72: "neve moderata",
    73: "neve forte",
    74: "neve debole",
    75: "neve forte",
    76: "neve intensa",
    77: "granelli di neve",
    80: "rovesci deboli",
    81: "rovesci moderati",
    82: "rovesci violenti",
    85: "rovesci di neve deboli",
    86: "rovesci di neve forti",
    95: "temporale",
    96: "temporale con grandine leggera",
    99: "temporale con grandine forte",
}


class ErroreMeteo(Exception):
    """Errore atteso (argomenti, rete, servizio, risposta) con un messaggio leggibile dal modello."""


@dataclass(frozen=True)
class Localita:
    """Un risultato del geocoding."""

    nome: str
    regione: str | None
    paese: str | None
    latitudine: float
    longitudine: float

    def descrizione(self) -> str:
        """Nome con regione e paese, omettendo quelli mancanti: «Udine (Friuli-Venezia Giulia, Italia)»."""
        dettagli = ", ".join(parte for parte in (self.regione, self.paese) if parte)
        return f"{self.nome} ({dettagli})" if dettagli else self.nome


def descrivi_codice(codice: int | None) -> str:
    """Descrizione in italiano di un codice WMO; per i codici ignoti lo dichiara."""
    if codice is None:
        return "condizioni non disponibili"
    return CODICI_WMO.get(codice, f"condizioni non classificate (codice {codice})")


def crea_client() -> httpx.Client:
    """Client HTTP con timeout da METEO_TIMEOUT (secondi, default 10)."""
    try:
        timeout = float(os.environ.get("METEO_TIMEOUT", "10"))
    except ValueError:
        timeout = 10.0
    return httpx.Client(timeout=timeout)


def _errore(messaggio: str) -> ErroreMeteo:
    logger.warning("meteo: %s", messaggio)
    return ErroreMeteo(messaggio)


def _richiedi(client: httpx.Client, url: str, parametri: dict) -> dict:
    """GET con conversione degli errori di rete, di stato HTTP e di JSON in ErroreMeteo."""
    try:
        risposta = client.get(url, params=parametri)
    except (httpx.TimeoutException, httpx.TransportError) as errore:
        raise _errore("servizio meteo non raggiungibile") from errore
    if risposta.status_code >= 400:
        raise _errore(f"servizio meteo non disponibile (HTTP {risposta.status_code})")
    try:
        dati = risposta.json()
    except ValueError as errore:
        raise _errore("risposta del servizio meteo non valida") from errore
    if not isinstance(dati, dict):
        raise _errore("risposta del servizio meteo non valida")
    logger.info("meteo: richiesta riuscita a %s", url)
    return dati


def cerca_localita(client: httpx.Client, citta: str) -> tuple[Localita, list[Localita]]:
    """Prima località trovata per `citta` e le alternative con lo stesso nome."""
    nome = (citta or "").strip()
    if not nome:
        raise _errore("nome della città mancante")
    dati = _richiedi(client, URL_GEOCODING,
                     {"name": nome, "count": 5, "language": "it", "format": "json"})
    risultati = dati.get("results")
    if not risultati:
        raise _errore(f"città non trovata: {nome}")
    try:
        trovate = [Localita(nome=r["name"], regione=r.get("admin1"), paese=r.get("country"),
                            latitudine=float(r["latitude"]), longitudine=float(r["longitude"]))
                   for r in risultati]
    except (KeyError, TypeError, ValueError) as errore:
        raise _errore("risposta del servizio meteo non valida") from errore
    return trovate[0], trovate[1:]


def _intestazione(scelta: Localita, alternative: list[Localita]) -> list[str]:
    righe = [f"Località: {scelta.descrizione()}"]
    if alternative:
        righe.append("Altre località con questo nome:")
        righe.extend(f"- {altra.descrizione()}" for altra in alternative)
    return righe


def _valore(valore, unita: str) -> str:
    """Valore con unità, oppure «n.d.» se il servizio ha restituito null."""
    return "n.d." if valore is None else f"{valore} {unita}"


def testo_meteo_attuale(client: httpx.Client, citta: str) -> str:
    """Meteo attuale della città, con la località scelta e le eventuali alternative."""
    scelta, alternative = cerca_localita(client, citta)
    dati = _richiedi(client, URL_PREVISIONI, {
        "latitude": scelta.latitudine, "longitude": scelta.longitudine, "timezone": "auto",
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
    })
    try:
        attuale = dati["current"]
        righe = _intestazione(scelta, alternative) + [
            f"Rilevato alle: {attuale['time']} ({dati.get('timezone', 'fuso non indicato')})",
            f"Temperatura: {_valore(attuale['temperature_2m'], '°C')}",
            f"Umidità: {_valore(attuale['relative_humidity_2m'], '%')}",
            f"Vento: {_valore(attuale['wind_speed_10m'], 'km/h')}",
            f"Condizioni: {descrivi_codice(attuale['weather_code'])}",
        ]
    except (KeyError, IndexError, TypeError, ValueError) as errore:
        raise _errore("risposta del servizio meteo non valida") from errore
    logger.info("meteo attuale per %s", scelta.descrizione())
    return "\n".join(righe)


def testo_previsioni(client: httpx.Client, citta: str, giorni: int) -> str:
    """Previsioni giornaliere (una riga per giorno) per 1-7 giorni."""
    if not isinstance(giorni, int) or isinstance(giorni, bool) or not 1 <= giorni <= GIORNI_MAX:
        raise _errore(f"giorni deve essere un numero intero tra 1 e {GIORNI_MAX}")
    scelta, alternative = cerca_localita(client, citta)
    dati = _richiedi(client, URL_PREVISIONI, {
        "latitude": scelta.latitudine, "longitude": scelta.longitudine, "timezone": "auto",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "forecast_days": giorni,
    })
    try:
        giornaliero = dati["daily"]
        righe = _intestazione(scelta, alternative)
        for i, data in enumerate(giornaliero["time"]):
            righe.append(
                f"{data}: {descrivi_codice(giornaliero['weather_code'][i])}, "
                f"minima {_valore(giornaliero['temperature_2m_min'][i], '°C')}, "
                f"massima {_valore(giornaliero['temperature_2m_max'][i], '°C')}, "
                f"pioggia {_valore(giornaliero['precipitation_probability_max'][i], '%')}")
    except (KeyError, IndexError, TypeError, ValueError) as errore:
        raise _errore("risposta del servizio meteo non valida") from errore
    logger.info("previsioni a %d giorni per %s", giorni, scelta.descrizione())
    return "\n".join(righe)
