"""API del back-end per il front-end: chat salvate in PostgreSQL, domande inoltrate all'agente.

Il documento OpenAPI (/openapi.json, /docs) è il contratto del front-end (step 8).
Avvio: `python -m backend`.
"""

import logging
import time
from datetime import datetime

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.agente_remoto import AgenteNonDisponibile

logger = logging.getLogger("backend.api")


class NuovaChat(BaseModel):
    titolo: str | None = Field(None, description="titolo; se manca «Nuova chat», poi la prima domanda")


class Chat(BaseModel):
    id: int
    titolo: str
    creata_il: datetime


class VoceElenco(BaseModel):
    id: int
    titolo: str
    ultimo_messaggio_il: datetime


class Messaggio(BaseModel):
    ruolo: str = Field(description="utente oppure assistente")
    testo: str
    strumenti: list[dict] = Field(default_factory=list, description="strumenti usati dall'agente")
    creato_il: datetime


class ChatCompleta(Chat):
    messaggi: list[Messaggio] = Field(description="in ordine cronologico")


class NuovoMessaggio(BaseModel):
    testo: str = Field(description="domanda dell'utente")


class Scambio(BaseModel):
    domanda: Messaggio
    risposta: Messaggio


class Errore(BaseModel):
    errore: str


def _errore(codice: int, testo: str) -> JSONResponse:
    return JSONResponse(status_code=codice, content={"errore": testo})


NON_TROVATA = {404: {"model": Errore, "description": "chat inesistente"}}


def crea_app(archivio, agente, origini_consentite: tuple[str, ...] = ()) -> FastAPI:
    """App FastAPI sopra un archivio (PostgreSQL o memoria) e un ClienteAgente."""
    app = FastAPI(title="Back-end delle chat",
                  description="Chat e messaggi salvati in PostgreSQL; le domande vanno all'agente.")
    if origini_consentite:  # front-end servito da un'altra origine (sviluppo locale)
        app.add_middleware(CORSMiddleware, allow_origins=list(origini_consentite),
                           allow_methods=["*"], allow_headers=["*"])

    @app.post("/chat", status_code=201, response_model=Chat)
    def crea_chat(richiesta: NuovaChat | None = None):
        """Crea una chat e ne restituisce l'identificativo."""
        titolo = (richiesta.titolo or "").strip() if richiesta else ""
        chat = archivio.crea_chat(titolo) if titolo else archivio.crea_chat()
        logger.info("backend: chat %d creata", chat["id"])
        return chat

    @app.get("/chat", response_model=list[VoceElenco])
    def elenca_chat():
        """Chat con titolo e data dell'ultimo messaggio, la più recente prima."""
        return archivio.elenca_chat()

    @app.get("/chat/{chat_id}", response_model=ChatCompleta, responses=NON_TROVATA)
    def leggi_chat(chat_id: int):
        """Una chat con i messaggi in ordine cronologico."""
        chat = archivio.leggi_chat(chat_id)
        return chat if chat is not None else _errore(404, f"La chat {chat_id} non esiste.")

    @app.post("/chat/{chat_id}/messaggi", response_model=Scambio,
              responses={**NON_TROVATA, 400: {"model": Errore}, 503: {"model": Errore},
                         502: {"model": Errore, "description": "errore dell'agente"}})
    def invia_messaggio(chat_id: int, richiesta: NuovoMessaggio):
        """Salva la domanda, chiama l'agente, salva e restituisce la risposta.

        Se l'agente non risponde (o risponde con un errore) non si salva nulla: si può riprovare.
        """
        domanda = richiesta.testo.strip()
        if not domanda:
            return _errore(400, "Il messaggio è vuoto.")
        stato = archivio.stato_agente(chat_id)
        if stato is None:
            return _errore(404, f"La chat {chat_id} non esiste.")
        cronologia, riassunto = stato
        inizio = time.monotonic()
        try:
            esito = agente.chat(domanda, cronologia, riassunto)
        except AgenteNonDisponibile as errore:
            logger.warning("backend: chat %d messaggio inviato all'agente -> %d in %.1f s: %s", chat_id,
                           errore.codice, time.monotonic() - inizio, errore)
            # 503 (agente o modello irraggiungibili) resta 503; gli altri errori dell'agente diventano 502.
            return _errore(503 if errore.codice == 503 else 502, str(errore))
        archivio.registra_turno(chat_id, domanda, esito["risposta"], esito["strumenti"],
                                cronologia=esito["cronologia"], riassunto=esito["riassunto"])
        logger.info("backend: chat %d messaggio inviato all'agente -> 200 in %.1f s strumenti=[%s]", chat_id,
                    time.monotonic() - inizio, ", ".join(s["nome"] for s in esito["strumenti"]))
        messaggi = archivio.leggi_chat(chat_id)["messaggi"]
        return {"domanda": messaggi[-2], "risposta": messaggi[-1]}

    @app.delete("/chat/{chat_id}", status_code=204, responses=NON_TROVATA)
    def elimina_chat(chat_id: int):
        """Rimuove la chat e i suoi messaggi."""
        if not archivio.elimina_chat(chat_id):
            return _errore(404, f"La chat {chat_id} non esiste.")
        logger.info("backend: chat %d eliminata", chat_id)
        return Response(status_code=204)

    @app.get("/stato")
    def stato():
        """Database e agente: 200 se entrambi rispondono, altrimenti 503."""
        try:
            archivio.verifica()
            database = {"raggiungibile": True}
        except Exception as errore:  # qualunque errore del driver: lo si riporta
            database = {"raggiungibile": False, "errore": str(errore)}
        dati = {"backend": "ok", "database": database, "agente": agente.stato()}
        pronto = database["raggiungibile"] and dati["agente"]["raggiungibile"]
        return JSONResponse(status_code=200 if pronto else 503, content=dati)

    return app
