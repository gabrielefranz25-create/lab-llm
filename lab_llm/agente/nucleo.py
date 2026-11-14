"""Nucleo dell'agente: un turno di conversazione, senza stato, per la chat locale e per il servizio HTTP.

`Agente` tiene ciò che serve per rispondere (grafo, comandi dei prompt, connessione MCP) ma non la
conversazione: cronologia e riassunto arrivano dal chiamante a ogni turno e tornano aggiornati. Lo
costruisce `agente.main.costruisci_agente`.
"""

import logging
from dataclasses import dataclass, field

import openai
from langchain_core.messages import AIMessage, AnyMessage, ToolMessage

from agente.client import rispondi
from agente.comandi import ErroreComando
from agente.config import Config
from agente.llm import elenca_modelli

logger = logging.getLogger(__name__)


@dataclass
class Esito:
    """Risultato di un turno: cronologia e riassunto aggiornati, testo della risposta, strumenti usati."""
    messaggi: list[AnyMessage]
    riassunto: str
    risposta: str
    strumenti: list[dict] = field(default_factory=list)


def traccia_strumenti(nuovi: list[AnyMessage]) -> list[dict]:
    """Strumenti chiamati nei messaggi del turno: nome, argomenti ed esito (`ok` o `errore`)."""
    risultati = {m.tool_call_id: m.content for m in nuovi if isinstance(m, ToolMessage)}
    traccia = []
    for m in nuovi:
        for tc in (m.tool_calls if isinstance(m, AIMessage) else []):
            testo = str(risultati.get(tc["id"], ""))
            errore = testo.startswith(("Errore", "Non eseguito")) or tc["id"] not in risultati
            traccia.append({"nome": tc["name"], "argomenti": tc["args"], "esito": "errore" if errore else "ok"})
    return traccia


@dataclass
class Agente:
    config: Config
    grafo: object
    comandi: object
    connessione: object
    recursion_limit: int

    def turno(self, cronologia: list[AnyMessage], riassunto: str, testo: str | None = None,
              prompt: tuple[str, dict[str, str]] | None = None) -> Esito:
        """Un turno con una domanda (`testo`) o un prompt MCP (`prompt` = nome, argomenti).

        Solleva ValueError (né testo né prompt, o entrambi), ErroreComando (prompt non valido),
        openai.APIError (LM Studio) e GraphRecursionError, come la chat.
        """
        if (testo is None) == (prompt is None):
            raise ValueError("serve un messaggio oppure un prompt, non entrambi")
        nuovi = None
        if prompt is not None:
            if self.comandi is None:
                raise ErroreComando("Prompt non disponibili: server utente non raggiungibile.")
            nuovi = self.comandi.compila(*prompt)
        prima = {m.id for m in cronologia if m.id}
        messaggi, riassunto, risposta = rispondi(self.grafo, cronologia, testo or "", self.recursion_limit,
                                                 riassunto, nuovi)
        strumenti = traccia_strumenti([m for m in messaggi if m.id not in prima])
        return Esito(messaggi=messaggi, riassunto=riassunto, risposta=risposta, strumenti=strumenti)

    def prompt_disponibili(self) -> list[dict]:
        if self.comandi is None or not self.comandi.disponibili:
            return []
        return self.comandi.catalogo_json()

    def stato(self) -> dict:
        """Agente, modello (GET /models di LM Studio) e server MCP collegati."""
        try:
            modelli = elenca_modelli(self.config)
            modello = {"id": self.config.lm_model, "raggiungibile": True,
                       "caricato": self.config.lm_model in modelli}
        except openai.APIError as errore:
            modello = {"id": self.config.lm_model, "raggiungibile": False, "errore": str(errore)}
        server = {s.nome: "ok" if s.nome in self.connessione.cataloghi else "non disponibile"
                  for s in self.connessione.servers}
        return {"agente": "ok", "modello": modello, "server_mcp": server}
