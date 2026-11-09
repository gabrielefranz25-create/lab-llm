"""Avvio dell'applicazione: log, configurazione, verifica del modello, grafo, chat."""

import logging
import sys

from agente.client import avvia_sessione
from agente.config import ErroreConfigurazione, carica_config
from agente.graph import costruisci_grafo, limite_ricorsione
from agente.llm import ErroreModello, crea_modello, crea_riassuntore, verifica_modello
from agente.strumenti import crea_ora_corrente

logger = logging.getLogger(__name__)


def configura_logging(livello: str) -> None:
    """Log su stderr (la chat resta su stdout); librerie HTTP silenziate a WARNING."""
    logging.basicConfig(
        level=livello, stream=sys.stderr, force=True,
        format="%(asctime)s %(levelname)-5s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # httpx2 è il nome del logger HTTP usato dalla versione installata di openai.
    for rumoroso in ("httpx", "httpx2", "httpcore", "openai"):
        logging.getLogger(rumoroso).setLevel(logging.WARNING)


def main() -> int:
    """0 a sessione conclusa, 1 se configurazione o modello non sono utilizzabili."""
    try:
        config = carica_config()
    except ErroreConfigurazione as errore:
        print(f"Errore di configurazione: {errore}", file=sys.stderr)
        return 1
    configura_logging(config.log_level)
    logger.info("avvio: modello=%s server=%s max_passi=%d contesto=%d da_tenere=%d", config.lm_model,
                config.lm_base_url, config.max_passi_strumento, config.max_messaggi_contesto,
                config.messaggi_da_tenere)
    try:
        verifica_modello(config)
    except ErroreModello as errore:
        print(f"Errore: {errore}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:  # Ctrl+C durante l'attesa di LM Studio all'avvio
        print("Interrotto.", file=sys.stderr)
        return 130

    strumenti = [crea_ora_corrente(config.fuso_orario_predefinito)]
    grafo = costruisci_grafo(
        crea_modello(config, strumenti), strumenti,
        max_passi=config.max_passi_strumento,
        max_messaggi_contesto=config.max_messaggi_contesto,
        fuso_predefinito=config.fuso_orario_predefinito,
        riassuntore=crea_riassuntore(config),
        messaggi_da_tenere=config.messaggi_da_tenere,
    )
    avvia_sessione(
        grafo,
        intestazione=(f"Modello: {config.lm_model}  |  Server: {config.lm_base_url}  |  "
                      f"Fuso predefinito: {config.fuso_orario_predefinito}"),
        server=config.lm_base_url,
        recursion_limit=limite_ricorsione(config.max_passi_strumento),
    )
    return 0
