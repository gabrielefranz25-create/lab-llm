"""Configurazione del back-end, solo da variabili d'ambiente (in locale anche da `.env`)."""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import load_dotenv


class ErroreConfigurazione(Exception):
    """Variabile mancante o non valida: il messaggio dice quale."""


@dataclass(frozen=True)
class ConfigBackend:
    database_url: str
    agente_url: str = "http://127.0.0.1:8000"
    agente_timeout: float = 600.0
    ascolto: str = "127.0.0.1"
    porta: int = 8080
    log_level: str = "INFO"


def carica_config(ambiente: Mapping[str, str] | None = None) -> ConfigBackend:
    if ambiente is None:
        load_dotenv(override=False)
        ambiente = os.environ

    def leggi(nome: str, default: str | None = None) -> str:
        valore = (ambiente.get(nome) or "").strip()
        if valore:
            return valore
        if default is None:
            raise ErroreConfigurazione(f"Manca la variabile {nome} (es. postgresql://lab:lab@localhost:5432/lab).")
        return default

    def numero(nome: str, default: str, tipo):
        testo = leggi(nome, default)
        try:
            valore = tipo(testo)
        except ValueError:
            raise ErroreConfigurazione(f"{nome} deve essere un numero, non '{testo}'.") from None
        if valore <= 0:
            raise ErroreConfigurazione(f"{nome} deve essere maggiore di zero, non {testo}.")
        return valore

    return ConfigBackend(
        database_url=leggi("DATABASE_URL"),
        agente_url=leggi("AGENTE_URL", "http://127.0.0.1:8000").rstrip("/"),
        agente_timeout=numero("AGENTE_TIMEOUT", "600", float),
        ascolto=leggi("BACKEND_ASCOLTO", "127.0.0.1"),
        porta=numero("BACKEND_PORTA", "8080", int),
        log_level=leggi("LOG_LEVEL", "INFO").upper(),
    )
