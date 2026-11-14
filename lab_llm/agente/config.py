"""Lettura e validazione delle variabili d'ambiente (vedi .env.example)."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

LIVELLI_LOG = ("DEBUG", "INFO", "WARNING", "ERROR")
SERVER_MCP_NOTI = ("meteo", "note", "unita", "calcolatrice", "scadenze", "catalogo")
# Percorso dello strumento orologio (lezione 5, blocco B): una sola variante attiva per volta.
VARIANTI_OROLOGIO = ("locale", "fastapi", "mcp")
# Trasporto verso i server MCP (lezione 5, blocco C): sottoprocessi stdio o servizi Streamable HTTP.
TRASPORTI_MCP = ("stdio", "http")
# Ambito dell'agente usato dal router se AMBITO_AGENTE è assente o vuota: l'orologio e i saluti ci
# sono sempre, poi una frase per ogni server MCP attivo.
AMBITO_INIZIO = "data e ora attuali in qualsiasi fuso orario"
# Spiegazioni e riassunti: le richieste dei prompt MCP spiega e riassumi_conversazione (lezione 6, step 5).
AMBITO_FINE = ("spiegazioni di concetti di informatica e di intelligenza artificiale, riassunti della "
               "conversazione, saluti e domande sull'assistente stesso")
AMBITO_PER_SERVER = {
    "meteo": "meteo attuale e previsioni",
    "note": "note personali dell'utente (aggiungere, elencare, eliminare)",
    "unita": "conversioni tra unità di misura",
    "calcolatrice": "calcoli aritmetici",
    "scadenze": "giorni, giorni lavorativi e scadenze tra date",
    "catalogo": "catalogo dei corsi (ricerca e dettagli dei corsi)",
}


def ambito_predefinito(server: tuple[str, ...]) -> str:
    """Ambito del router per i server MCP indicati."""
    return ", ".join([AMBITO_INIZIO, *(AMBITO_PER_SERVER[s] for s in server), AMBITO_FINE])


AMBITO_PREDEFINITO = ambito_predefinito(SERVER_MCP_NOTI)


class ErroreConfigurazione(Exception):
    """Variabile d'ambiente mancante o con un valore non valido."""


@dataclass(frozen=True)
class Config:
    lm_base_url: str
    lm_model: str
    fuso_orario_predefinito: str
    max_passi_strumento: int
    max_messaggi_contesto: int
    messaggi_da_tenere: int
    lm_timeout: float
    log_level: str
    mcp_timeout: float
    meteo_timeout: float
    note_db: str
    server_mcp: tuple[str, ...]
    ambito: str
    variante_orologio: str = "locale"
    orologio_api_url: str = "http://localhost:8001"
    orologio_api_timeout: float = 5.0
    trasporto_mcp: str = "stdio"
    mcp_http_host: str = "127.0.0.1"
    max_revisioni: int = 2
    preferenze_file: str = "server_mcp/risorse/preferenze.json"


def _leggi(ambiente: Mapping[str, str], nome: str, default: str | None = None) -> str:
    """Restituisce il valore della variabile; una stringa vuota conta come assente."""
    valore = (ambiente.get(nome) or "").strip()
    if valore:
        return valore
    if default is None:
        raise ErroreConfigurazione(
            f"Variabile d'ambiente obbligatoria mancante: {nome} (vedi .env.example)."
        )
    return default


def _intero(ambiente: Mapping[str, str], nome: str, default: int, minimo: int) -> int:
    testo = _leggi(ambiente, nome, str(default))
    try:
        valore = int(testo)
    except ValueError:
        raise ErroreConfigurazione(f"{nome} deve essere un numero intero, non '{testo}'.") from None
    if valore < minimo:
        raise ErroreConfigurazione(f"{nome} deve essere almeno {minimo}, non {valore}.")
    return valore


def _secondi(ambiente: Mapping[str, str], nome: str, default: float) -> float:
    testo = _leggi(ambiente, nome, str(default))
    try:
        valore = float(testo)
    except ValueError:
        raise ErroreConfigurazione(f"{nome} deve essere un numero di secondi, non '{testo}'.") from None
    if valore <= 0:
        raise ErroreConfigurazione(f"{nome} deve essere maggiore di zero, non {valore}.")
    return valore


def _fuso(ambiente: Mapping[str, str], nome: str, default: str) -> str:
    testo = _leggi(ambiente, nome, default)
    try:
        ZoneInfo(testo)
    except (ZoneInfoNotFoundError, ValueError):
        raise ErroreConfigurazione(
            f"{nome}: fuso orario '{testo}' non riconosciuto. Usa un nome IANA come 'Europe/Rome'."
        ) from None
    return testo


def _livello_log(ambiente: Mapping[str, str], nome: str, default: str) -> str:
    testo = _leggi(ambiente, nome, default).upper()
    if testo not in LIVELLI_LOG:
        raise ErroreConfigurazione(f"{nome} deve essere uno tra {', '.join(LIVELLI_LOG)}, non '{testo}'.")
    return testo


def _scelta(ambiente: Mapping[str, str], nome: str, ammessi: tuple[str, ...]) -> str:
    """Valore (in minuscolo) tra quelli ammessi; il primo è il default."""
    testo = _leggi(ambiente, nome, ammessi[0]).lower()
    if testo not in ammessi:
        raise ErroreConfigurazione(f"{nome} deve essere uno tra {', '.join(ammessi)}, non '{testo}'.")
    return testo


def _elenco_server(ambiente: Mapping[str, str]) -> tuple[str, ...]:
    """Legge SERVER_MCP: assente = tutti i server noti, vuota = nessun server."""
    grezzo = ambiente.get("SERVER_MCP")  # non _leggi: la stringa vuota è un valore valido
    if grezzo is None:
        return SERVER_MCP_NOTI
    nomi = tuple(dict.fromkeys(n.strip() for n in grezzo.split(",") if n.strip()))
    sconosciuti = [n for n in nomi if n not in SERVER_MCP_NOTI]
    if sconosciuti:
        raise ErroreConfigurazione(
            f"SERVER_MCP contiene server sconosciuti: {', '.join(sconosciuti)}. "
            f"Server noti: {', '.join(SERVER_MCP_NOTI)}."
        )
    return nomi


def carica_config(ambiente: Mapping[str, str] | None = None) -> Config:
    """Costruisce la Config. Senza argomenti carica .env (senza sovrascrivere) e legge os.environ."""
    if ambiente is None:
        load_dotenv(override=False)
        ambiente = os.environ
    max_messaggi = _intero(ambiente, "MAX_MESSAGGI_CONTESTO", 20, minimo=2)
    da_tenere = _intero(ambiente, "MESSAGGI_DA_TENERE", 6, minimo=2)
    if da_tenere >= max_messaggi:  # altrimenti la compattazione non accorcerebbe mai la cronologia
        raise ErroreConfigurazione(
            f"MESSAGGI_DA_TENERE ({da_tenere}) deve essere minore di MAX_MESSAGGI_CONTESTO ({max_messaggi})."
        )
    mcp_timeout = _secondi(ambiente, "MCP_TIMEOUT", 30.0)
    meteo_timeout = _secondi(ambiente, "METEO_TIMEOUT", 10.0)
    if mcp_timeout <= 2 * meteo_timeout:  # il server meteo fa due chiamate HTTP in sequenza
        raise ErroreConfigurazione(
            f"MCP_TIMEOUT ({mcp_timeout:g}) deve essere maggiore del doppio di METEO_TIMEOUT ({meteo_timeout:g})."
        )
    server_mcp = _elenco_server(ambiente)
    return Config(
        lm_base_url=_leggi(ambiente, "LM_BASE_URL"),
        lm_model=_leggi(ambiente, "LM_MODEL"),
        fuso_orario_predefinito=_fuso(ambiente, "FUSO_ORARIO_PREDEFINITO", "Europe/Rome"),
        max_passi_strumento=_intero(ambiente, "MAX_PASSI_STRUMENTO", 3, minimo=1),
        max_messaggi_contesto=max_messaggi,
        messaggi_da_tenere=da_tenere,
        lm_timeout=_secondi(ambiente, "LM_TIMEOUT", 60.0),
        log_level=_livello_log(ambiente, "LOG_LEVEL", "INFO"),
        mcp_timeout=mcp_timeout,
        meteo_timeout=meteo_timeout,
        note_db=_leggi(ambiente, "NOTE_DB", "dati/note.sqlite3"),
        server_mcp=server_mcp,
        ambito=_leggi(ambiente, "AMBITO_AGENTE", ambito_predefinito(server_mcp)),
        variante_orologio=_scelta(ambiente, "VARIANTE_OROLOGIO", VARIANTI_OROLOGIO),
        orologio_api_url=_leggi(ambiente, "OROLOGIO_API_URL", "http://localhost:8001"),
        orologio_api_timeout=_secondi(ambiente, "OROLOGIO_API_TIMEOUT", 5.0),
        trasporto_mcp=_scelta(ambiente, "TRASPORTO_MCP", TRASPORTI_MCP),
        mcp_http_host=_leggi(ambiente, "MCP_HTTP_HOST", "127.0.0.1"),
        max_revisioni=_intero(ambiente, "MAX_REVISIONI", 2, minimo=0),
        preferenze_file=_leggi(ambiente, "PREFERENZE_FILE", "server_mcp/risorse/preferenze.json"),
    )
