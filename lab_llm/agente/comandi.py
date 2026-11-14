"""Comandi della CLI per i prompt MCP: /prompts elenca, /prompt nome arg=valore richiama.

Un prompt lo sceglie l'utente. MCP non prevede comandi standard: questi li definisce la nostra CLI.
Gli argomenti vengono controllati qui, nell'host, rispetto a `prompts/list`: una richiesta non valida
non arriva né al server né al modello. I messaggi ottenuti con `prompts/get` vanno poi al grafo come
una domanda qualsiasi (router, strumenti, revisore).
"""

import json
import logging
import shlex

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage

from agente.mcp_ponte import ErroreMCP

logger = logging.getLogger(__name__)

ESEMPIO = '/prompt spiega argomento="Model Context Protocol" livello=base'
USO = f"Uso: /prompt nome argomento=valore ... (per esempio {ESEMPIO})"


class ErroreComando(Exception):
    """Comando non valido o non eseguibile: il messaggio è per l'utente."""


class ComandiPrompt:
    """Catalogo dei prompt del server (letto una volta) e richiamo dei prompt dalla CLI."""

    def __init__(self, connessione, server: str = "utente"):
        self.connessione, self.server = connessione, server
        try:
            self.catalogo = {p.name: p for p in connessione.elenca_prompt(server)}
        except ErroreMCP as errore:
            logger.warning("prompt non disponibili: %s", errore)
            self.catalogo = None
            return
        logger.info("prompt: catalogo del server %s [%s]", server, ", ".join(self.catalogo))

    @property
    def disponibili(self) -> bool:
        return self.catalogo is not None

    def elenco(self) -> str:
        """Testo di /prompts: nome, descrizione e argomenti di ogni prompt."""
        if not self.disponibili:
            return f"Prompt non disponibili: server {self.server} non raggiungibile."
        return formatta_catalogo(self.catalogo_json(), self.server)

    def catalogo_json(self) -> list[dict]:
        """Catalogo come dati semplici (per GET /prompts del servizio HTTP)."""
        return [{"nome": p.name, "descrizione": p.description or "",
                 "argomenti": [{"nome": a.name, "descrizione": a.description or "", "obbligatorio": bool(a.required)}
                               for a in p.arguments or []]}
                for p in (self.catalogo or {}).values()]

    def richiama(self, riga: str) -> list[AnyMessage]:
        """Da `/prompt nome a=b ...` ai messaggi compilati dal server. Solleva ErroreComando."""
        if not self.disponibili:
            raise ErroreComando(f"Prompt non disponibili: server {self.server} non raggiungibile.")
        return self.compila(*interpreta_riga(riga))

    def compila(self, nome: str, argomenti: dict[str, str]) -> list[AnyMessage]:
        """Controlla nome e argomenti rispetto al catalogo (prompts/list), poi chiede i messaggi al server."""
        if not self.disponibili:
            raise ErroreComando(f"Prompt non disponibili: server {self.server} non raggiungibile.")
        self._controlla(nome, argomenti)
        try:
            messaggi = self.connessione.ottieni_prompt(self.server, nome, argomenti)
        except ErroreMCP as errore:
            logger.warning("prompt %s non riuscito: %s", nome, errore)
            raise ErroreComando(f"Il server non ha compilato il prompt {nome}: {errore}") from errore
        logger.info("prompt: richiamato %s argomenti=%s dal server %s: %d messaggi", nome,
                    json.dumps(argomenti, ensure_ascii=False), self.server, len(messaggi))
        for i, (ruolo, testo) in enumerate(messaggi, start=1):
            logger.info("prompt: messaggio %d (%s): %s", i, ruolo, testo.replace("\n", " "))
        return [AIMessage(testo) if ruolo == "assistant" else HumanMessage(testo) for ruolo, testo in messaggi]

    def _controlla(self, nome: str, argomenti: dict[str, str]) -> None:
        prompt = self.catalogo.get(nome)
        if prompt is None:
            raise ErroreComando(f"Prompt sconosciuto: {nome}. Disponibili: {', '.join(self.catalogo)}.")
        ammessi = {a.name: a for a in prompt.arguments or []}
        sconosciuti = [chiave for chiave in argomenti if chiave not in ammessi]
        if sconosciuti:
            raise ErroreComando(f"Argomento sconosciuto: {', '.join(sconosciuti)}. Ammessi: {', '.join(ammessi)}.")
        mancanti = [n for n, a in ammessi.items() if a.required and n not in argomenti]
        if mancanti:
            raise ErroreComando(f"Argomento obbligatorio mancante: {', '.join(mancanti)}.")


def formatta_catalogo(catalogo: list[dict], server: str = "utente") -> str:
    """Testo di /prompts dal catalogo in forma di dati (catalogo_json o GET /prompts del servizio)."""
    righe = [f"Prompt del server {server}:"]
    for prompt in catalogo:
        righe.append(f"- {prompt['nome']}: {prompt['descrizione']}".rstrip())
        for argomento in prompt["argomenti"]:
            tipo = "obbligatorio" if argomento["obbligatorio"] else "facoltativo"
            righe.append(f"    {argomento['nome']} ({tipo}): {argomento['descrizione']}".rstrip())
    righe.append(USO)
    return "\n".join(righe)


def interpreta_riga(riga: str) -> tuple[str, dict[str, str]]:
    """`/prompt nome a=b c="d e"` → (nome, argomenti), senza catalogo: usata anche dalla CLI remota."""
    try:
        parti = shlex.split(riga)
    except ValueError:
        raise ErroreComando(f"Virgolette non chiuse. {USO}") from None
    if len(parti) < 2:
        raise ErroreComando(USO)
    nome, *coppie = parti[1:]
    argomenti: dict[str, str] = {}
    for coppia in coppie:
        chiave, uguale, valore = coppia.partition("=")
        if not uguale or not chiave:
            raise ErroreComando(f"'{coppia}': atteso nome=valore. {USO}")
        argomenti[chiave] = valore
    return nome, argomenti
