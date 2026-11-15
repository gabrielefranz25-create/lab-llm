"""L'agente come servizio HTTP (lezione 6, step 6): lo stesso nucleo della chat, esposto con FastAPI.

L'agente è senza stato: cronologia e riassunto arrivano con ogni richiesta e tornano aggiornati. La
cronologia viaggia nel formato JSON di LangChain (`messages_to_dict`), così tool_call e ToolMessage
restano validi tra un turno e l'altro. Documentazione OpenAPI su /docs e /openapi.json.

Avvio: `python -m agente.servizio` (host e porta da AGENTE_ASCOLTO e AGENTE_PORTA).
"""

import logging
import sys
import time

import openai
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from langchain_core.messages import messages_from_dict, messages_to_dict
from langgraph.errors import GraphRecursionError
from pydantic import BaseModel, Field

from agente.comandi import ErroreComando

logger = logging.getLogger("agente.servizio")  # anche se avviato con python -m


class RichiestaPrompt(BaseModel):
    nome: str = Field(description="nome del prompt MCP (vedi GET /prompts)")
    argomenti: dict[str, str] = Field(default_factory=dict, description="argomenti del prompt")


class RichiestaChat(BaseModel):
    messaggio: str | None = Field(None, description="domanda dell'utente (oppure `prompt`)")
    prompt: RichiestaPrompt | None = Field(None, description="prompt MCP da richiamare (oppure `messaggio`)")
    cronologia: list[dict] = Field(default_factory=list,
                                   description="cronologia restituita dal turno precedente (formato LangChain)")
    riassunto: str = Field("", description="riassunto restituito dal turno precedente")


class StrumentoUsato(BaseModel):
    nome: str
    argomenti: dict | str
    esito: str = Field(description="ok oppure errore")


class RispostaChat(BaseModel):
    risposta: str
    cronologia: list[dict] = Field(description="da rimandare al turno successivo")
    riassunto: str = Field(description="da rimandare al turno successivo")
    strumenti: list[StrumentoUsato] = Field(description="strumenti chiamati in questo turno")


class Errore(BaseModel):
    errore: str


def _errore(codice: int, testo: str) -> JSONResponse:
    return JSONResponse(status_code=codice, content={"errore": testo})


def crea_app(agente) -> FastAPI:
    """App FastAPI sopra un `agente.nucleo.Agente` (o un oggetto con gli stessi metodi)."""
    app = FastAPI(title="Agente del laboratorio",
                  description="Il grafo LangGraph dell'assistente come servizio HTTP senza stato.")
    errori = {400: {"model": Errore}, 500: {"model": Errore}, 503: {"model": Errore}}

    @app.post("/chat", response_model=RispostaChat, responses=errori)
    def chat(richiesta: RichiestaChat):
        """Un turno: messaggio (o prompt MCP) più cronologia e riassunto; restituisce risposta e traccia."""
        inizio = time.monotonic()
        messaggio = (richiesta.messaggio or "").strip() or None
        if (messaggio is None) == (richiesta.prompt is None):
            return _errore(400, "Serve un messaggio non vuoto oppure un prompt, non entrambi.")
        try:
            cronologia = messages_from_dict(richiesta.cronologia)
        except (KeyError, ValueError, TypeError) as errore:
            return _errore(400, f"La cronologia non è valida: {errore}")
        prompt = (richiesta.prompt.nome, richiesta.prompt.argomenti) if richiesta.prompt else None
        # print(f"[passo] servizio: POST /chat con {len(cronologia)} messaggi di cronologia")
        try:
            esito = agente.turno(cronologia, richiesta.riassunto, testo=messaggio, prompt=prompt)
        except ErroreComando as errore:
            codice, risposta = 400, _errore(400, str(errore))
        except openai.APIError as errore:
            logger.error("api: modello non raggiungibile: %s", errore)
            codice, risposta = 503, _errore(503, f"Il modello non è raggiungibile ({type(errore).__name__}). "
                                                 "Controlla che LM Studio sia acceso.")
        except GraphRecursionError as errore:
            logger.error("api: limite di ricorsione del grafo superato: %s", errore)
            codice, risposta = 500, _errore(500, "Il grafo ha superato il numero massimo di passaggi per "
                                                 "questa domanda. Prova a riformularla.")
        else:
            codice = 200
            risposta = RispostaChat(risposta=esito.risposta, cronologia=messages_to_dict(esito.messaggi),
                                    riassunto=esito.riassunto, strumenti=esito.strumenti)
        nomi = [s["nome"] for s in esito.strumenti] if codice == 200 else []
        logger.info("api: POST /chat cronologia=%d -> %d strumenti=[%s] in %.1f s", len(cronologia), codice,
                    ", ".join(nomi), time.monotonic() - inizio)
        return risposta

    @app.get("/prompts")
    def prompts() -> list[dict]:
        """Prompt MCP disponibili (nome, descrizione, argomenti obbligatori e facoltativi)."""
        return agente.prompt_disponibili()

    @app.get("/stato", responses={503: {"description": "modello non raggiungibile"}})
    def stato():
        """Agente, modello di LM Studio e server MCP: 200 se il modello risponde, altrimenti 503."""
        dati = agente.stato()
        return JSONResponse(status_code=200 if dati["modello"]["raggiungibile"] else 503, content=dati)

    return app


def main() -> int:
    """Costruisce l'agente (come la chat locale) e avvia uvicorn."""
    import uvicorn

    from agente.config import ErroreConfigurazione, carica_config
    from agente.main import configura_logging, costruisci_agente

    try:
        config = carica_config()
    except ErroreConfigurazione as errore:
        print(f"Errore di configurazione: {errore}", file=sys.stderr)
        return 1
    configura_logging(config.log_level)
    logger.info("servizio: http://%s:%d (documentazione su /docs)", config.agente_ascolto, config.agente_porta)
    with costruisci_agente(config) as (agente, intestazione):
        logger.info("servizio: %s", intestazione)
        uvicorn.run(crea_app(agente), host=config.agente_ascolto, port=config.agente_porta,
                    log_level=config.log_level.lower())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
