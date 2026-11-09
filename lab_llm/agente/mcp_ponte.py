"""Ponte MCP: avvia i server stdio e ne espone il catalogo come tool LangChain sincroni.

È l'unico modulo asincrono dell'agente. Un thread dedicato esegue un event loop asyncio in cui
restano aperte le sessioni con i server; il grafo, sincrono, chiama i tool, che inviano la
richiesta a quel loop e attendono la risposta.
"""

import asyncio
import logging
import os
import sys
import threading
from collections.abc import Mapping, Sequence
from concurrent.futures import Future
from dataclasses import dataclass, field
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from fastmcp.exceptions import ToolError
from langchain_core.tools import BaseTool, StructuredTool
from mcp.types import TextContent

logger = logging.getLogger(__name__)

# Cartella `lab_llm/`: è la cartella di lavoro dei sottoprocessi (così `-m server_mcp.meteo` funziona).
CARTELLA_PROGETTO = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ServerMCP:
    """Un server MCP da avviare come `sys.executable <argomenti>`, per esempio `-m server_mcp.meteo`."""

    nome: str
    argomenti: tuple[str, ...]
    env: Mapping[str, str] = field(default_factory=dict)


@dataclass
class _Custode:
    """Ciò che serve per tenere aperta, usare e poi chiudere la sessione con un server."""

    server: ServerMCP
    chiusura: asyncio.Event
    pronto: Future
    finito: threading.Event = field(default_factory=threading.Event)
    compito: Future | None = None
    client: Client | None = None


class ConnessioneMCP:
    """Context manager: all'ingresso apre i server e crea i tool, all'uscita chiude tutto.

    Attributi: `strumenti` (tool LangChain, nell'ordine dei server) e `cataloghi`
    (catalogo grezzo di `list_tools()` per nome di server, utile per la diagnosi).
    """

    def __init__(self, servers: Sequence[ServerMCP], timeout: float):
        self.servers = list(servers)
        self.timeout = timeout
        self.strumenti: list[BaseTool] = []
        self.cataloghi: dict[str, list] = {}
        self._custodi: list[_Custode] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None

    # --- ingresso e uscita -------------------------------------------------------------------

    def __enter__(self) -> "ConnessioneMCP":
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, name="ponte-mcp", daemon=True)
        self._thread.start()
        try:
            for server in self.servers:
                self._apri(server)
        except BaseException:
            self._chiudi()
            raise
        return self

    def __exit__(self, *dettagli) -> None:
        self._chiudi()

    def _apri(self, server: ServerMCP) -> None:
        """Avvia il custode del server e attende il catalogo; se non arriva, prosegue senza."""
        # print(f"[passo] avvio del server MCP {server.nome}: {server.argomenti}")
        custode = _Custode(server=server, chiusura=asyncio.Event(), pronto=Future())
        self._custodi.append(custode)
        custode.compito = asyncio.run_coroutine_threadsafe(self._custodisci(custode), self._loop)
        try:
            client, catalogo = custode.pronto.result(self.timeout)
        except TimeoutError:
            logger.warning("server MCP %s non disponibile: nessuna risposta entro %s secondi",
                           server.nome, self.timeout)
            custode.compito.cancel()
            return
        except Exception as errore:
            logger.warning("server MCP %s non disponibile: %s", server.nome, _dettaglio(errore))
            return

        custode.client = client
        self.cataloghi[server.nome] = catalogo
        self.strumenti.extend(self._crea_strumento(server, client, voce) for voce in catalogo)
        logger.info("server MCP %s: catalogo [%s]", server.nome,
                    ", ".join(voce.name for voce in catalogo))

    async def _custodisci(self, custode: _Custode) -> None:
        """Coroutine «custode»: apre la sessione, legge il catalogo e la tiene aperta fino alla chiusura.

        La sessione si apre e si chiude nello stesso task, come richiede anyio.
        """
        server = custode.server
        trasporto = StdioTransport(
            command=sys.executable,
            args=list(server.argomenti),
            env={**os.environ, **server.env},
            cwd=str(CARTELLA_PROGETTO),
            keep_alive=False,  # all'uscita dal client il sottoprocesso viene terminato
        )
        try:
            async with Client(trasporto) as client:
                catalogo = await client.list_tools()
                # print(f"[passo] {server.nome}: catalogo con {len(catalogo)} tool")
                custode.pronto.set_result((client, catalogo))
                await custode.chiusura.wait()
        except BaseException as errore:
            if not custode.pronto.done():
                custode.pronto.set_exception(errore)
            raise
        finally:
            # Qui la sessione è già chiusa e il sottoprocesso terminato: lo si segnala al thread
            # principale (il Future di `compito`, se annullato, risulta concluso subito, prima della
            # pulizia, quindi non basta per sapere quando fermare il loop).
            custode.finito.set()

    def _chiudi(self) -> None:
        """Segnala la chiusura ai custodi, li attende, poi ferma il loop e il thread."""
        if self._loop is None:
            return
        for custode in self._custodi:
            self._loop.call_soon_threadsafe(custode.chiusura.set)
        for custode in self._custodi:
            if not custode.finito.wait(self.timeout):
                logger.warning("server MCP %s: chiusura non completata entro %s secondi",
                               custode.server.nome, self.timeout)
                custode.compito.cancel()
            elif (custode.compito.done() and not custode.compito.cancelled()
                  and custode.compito.exception() is not None):
                # Per esempio un server morto durante la sessione: era già stato segnalato.
                logger.debug("server MCP %s: chiusura con errore: %s",
                             custode.server.nome, _dettaglio(custode.compito.exception()))
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(self.timeout)
        if not self._thread.is_alive():
            self._loop.close()
        # print("[passo] ponte MCP chiuso")

    # --- tool sincroni -----------------------------------------------------------------------

    def _crea_strumento(self, server: ServerMCP, client: Client, voce) -> StructuredTool:
        """Tool LangChain sincrono per una voce del catalogo: nome, descrizione e schema dal server."""
        nome = voce.name

        def esegui(**argomenti) -> str:
            return self._chiama(server.nome, client, nome, argomenti)

        return StructuredTool.from_function(
            func=esegui,
            name=nome,
            description=voce.description or "",
            # Schema JSON come dizionario: LangChain non valida, gli argomenti arrivano al server.
            args_schema=voce.input_schema,
            metadata={"origine": f"mcp:{server.nome}"},
        )

    def _chiama(self, nome_server: str, client: Client, nome: str, argomenti: dict) -> str:
        """Invia `call_tool` al loop del thread, attende l'esito e lo converte in testo."""
        # print(f"[passo] MCP {nome_server}.{nome}({argomenti})")
        chiamata = client.call_tool(nome, argomenti)
        futuro = None
        try:
            futuro = asyncio.run_coroutine_threadsafe(chiamata, self._loop)
            risultato = futuro.result(self.timeout)
        except ToolError as errore:
            logger.warning("strumento %s: errore dal server: %s", nome, errore)
            return f"Errore dallo strumento {nome}: {errore}"
        except Exception as errore:
            if futuro is None:
                chiamata.close()  # loop già chiuso: la coroutine non partirà mai
            else:
                futuro.cancel()
            dettaglio = (f"nessuna risposta entro {self.timeout} secondi"
                         if isinstance(errore, TimeoutError) else _dettaglio(errore))
            logger.warning("server MCP %s: errore di collegamento: %s", nome_server, dettaglio)
            return f"Errore di collegamento MCP con il server {nome_server}: {dettaglio}"
        return "\n".join(blocco.text for blocco in risultato.content
                         if isinstance(blocco, TextContent))


def _dettaglio(errore: BaseException) -> str:
    """Messaggio dell'eccezione, o il suo tipo se il messaggio è vuoto."""
    return str(errore) or type(errore).__name__


def unisci_strumenti(*gruppi: Sequence[BaseTool]) -> list[BaseTool]:
    """Unisce i gruppi di tool tenendo il primo per ogni nome; i duplicati vengono scartati."""
    uniti: list[BaseTool] = []
    nomi: set[str] = set()
    for gruppo in gruppi:
        for strumento in gruppo:
            if strumento.name in nomi:
                logger.warning("strumento duplicato scartato: %s", strumento.name)
                continue
            nomi.add(strumento.name)
            uniti.append(strumento)
    return uniti
