"""Avvio dell'applicazione: log, configurazione, verifica del modello, grafo, chat."""

import logging
import sys

from agente.client import avvia_sessione
from agente.config import Config, ErroreConfigurazione, carica_config
from agente.graph import costruisci_grafo, limite_ricorsione
from agente.llm import ErroreModello, crea_modello, crea_riassuntore, verifica_modello
from agente.mcp_ponte import ConnessioneMCP, ServerMCP, unisci_strumenti
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


def server_da_config(config: Config) -> list[ServerMCP]:
    """Server MCP da avviare, secondo SERVER_MCP. Ai sottoprocessi passano il livello di log
    dell'agente (per i log del server) e FASTMCP_LOG_LEVEL=WARNING (per tacere la riga
    "Starting MCP server" del framework, che finirebbe sul terminale della chat)."""
    comuni = {"LOG_LEVEL": config.log_level, "FASTMCP_LOG_LEVEL": "WARNING"}
    disponibili = {
        "meteo": ServerMCP("meteo", ("-m", "server_mcp.meteo"),
                           {**comuni, "METEO_TIMEOUT": str(config.meteo_timeout)}),
        "note": ServerMCP("note", ("-m", "server_mcp.note"), {**comuni, "NOTE_DB": config.note_db}),
    }
    return [disponibili[nome] for nome in config.server_mcp]


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

    try:
        with ConnessioneMCP(server_da_config(config), config.mcp_timeout) as connessione:
            strumenti = unisci_strumenti([crea_ora_corrente(config.fuso_orario_predefinito)],
                                         connessione.strumenti)
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
                              f"Fuso predefinito: {config.fuso_orario_predefinito}  |  "
                              f"Strumenti: {', '.join(s.name for s in strumenti)}"),
                server=config.lm_base_url,
                recursion_limit=limite_ricorsione(config.max_passi_strumento),
            )
    except KeyboardInterrupt:  # Ctrl+C durante l'avvio dei server MCP
        print("Interrotto.", file=sys.stderr)
        return 130
    return 0
