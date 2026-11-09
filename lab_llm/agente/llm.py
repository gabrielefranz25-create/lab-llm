"""Collegamento al modello servito da LM Studio sull'host (API compatibile con OpenAI)."""

import logging

import openai
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from openai import OpenAI

from agente.config import Config

logger = logging.getLogger(__name__)

# LM Studio non verifica la chiave: valore fittizio, non una credenziale.
CHIAVE_FITTIZIA = "lm-studio"


class ErroreModello(Exception):
    """LM Studio non raggiungibile, oppure modello non disponibile sul server."""


def _chat(config: Config) -> ChatOpenAI:
    """ChatOpenAI verso LM Studio, senza strumenti."""
    return ChatOpenAI(
        base_url=config.lm_base_url,
        model=config.lm_model,
        api_key=CHIAVE_FITTIZIA,
        temperature=0,  # risposte più stabili, tool calling più affidabile
        timeout=config.lm_timeout,
        max_retries=1,
    )


def crea_modello(config: Config, strumenti: list[BaseTool]) -> Runnable:
    """ChatOpenAI verso LM Studio, con gli strumenti già collegati (bind_tools)."""
    return _chat(config).bind_tools(strumenti)


def crea_riassuntore(config: Config) -> Runnable:
    """Stesso modello senza strumenti: per il riassunto della cronologia non deve chiamarne."""
    return _chat(config)


def elenca_modelli(config: Config, client: OpenAI | None = None) -> list[str]:
    """Identificativi dei modelli restituiti da GET {LM_BASE_URL}/models."""
    if client is None:
        client = OpenAI(base_url=config.lm_base_url, api_key=CHIAVE_FITTIZIA,
                        timeout=config.lm_timeout)
    return [m.id for m in client.models.list()]


def verifica_modello(config: Config, client: OpenAI | None = None) -> None:
    """Controlla all'avvio che il server risponda e che LM_MODEL sia tra i modelli disponibili."""
    try:
        disponibili = elenca_modelli(config, client)
    except openai.APIError as errore:
        logger.error("LM Studio non raggiungibile su %s: %s", config.lm_base_url, errore)
        raise ErroreModello(
            f"LM Studio non risponde su {config.lm_base_url} ({errore}).\n"
            "Suggerimento: avvia LM Studio e il server, poi controlla LM_BASE_URL."
        ) from errore
    if config.lm_model not in disponibili:
        elenco = ", ".join(disponibili) if disponibili else "(nessuno)"
        raise ErroreModello(
            f"Il modello '{config.lm_model}' non è disponibile su {config.lm_base_url}.\n"
            f"Modelli disponibili: {elenco}\n"
            "Suggerimento: carica il modello o correggi LM_MODEL."
        )
