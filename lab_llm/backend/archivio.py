"""Archivio delle chat: PostgreSQL in esercizio, memoria nei test automatici dell'API.

Due tabelle: `chat` (titolo, data, e lo stato da ripassare all'agente: cronologia in formato LangChain
e riassunto) e `messaggi` (solo ciò che il front-end mostra: ruolo, testo, strumenti usati, data).
"""

import copy
import itertools
import logging
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

logger = logging.getLogger(__name__)

TITOLO_INIZIALE = "Nuova chat"
LUNGHEZZA_TITOLO = 60

SCHEMA = """
CREATE TABLE IF NOT EXISTS chat (
    id          SERIAL PRIMARY KEY,
    titolo      TEXT NOT NULL,
    creata_il   TIMESTAMPTZ NOT NULL DEFAULT now(),
    cronologia  JSONB NOT NULL DEFAULT '[]'::jsonb,
    riassunto   TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS messaggi (
    id          SERIAL PRIMARY KEY,
    chat_id     INTEGER NOT NULL REFERENCES chat(id) ON DELETE CASCADE,
    ruolo       TEXT NOT NULL CHECK (ruolo IN ('utente', 'assistente')),
    testo       TEXT NOT NULL,
    strumenti   JSONB NOT NULL DEFAULT '[]'::jsonb,
    creato_il   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS messaggi_chat ON messaggi (chat_id, id);
"""


def titolo_da(domanda: str) -> str:
    return domanda.strip()[:LUNGHEZZA_TITOLO]


class ArchivioPostgres:
    """Chat e messaggi in PostgreSQL; le tabelle si creano all'avvio se mancano."""

    def __init__(self, url: str, timeout: float = 10):
        self.url, self.timeout = url, timeout
        with self._connessione() as conn:
            conn.execute(SCHEMA)
        logger.info("archivio: PostgreSQL pronto (tabelle chat e messaggi)")

    def _connessione(self):
        return psycopg.connect(self.url, connect_timeout=int(self.timeout), row_factory=dict_row)

    def verifica(self) -> None:
        with self._connessione() as conn:
            conn.execute("SELECT 1")

    def crea_chat(self, titolo: str = TITOLO_INIZIALE) -> dict:
        with self._connessione() as conn:
            return conn.execute("INSERT INTO chat (titolo) VALUES (%s) RETURNING id, titolo, creata_il",
                                (titolo,)).fetchone()

    def elenca_chat(self) -> list[dict]:
        with self._connessione() as conn:
            return conn.execute("""
                SELECT c.id, c.titolo, COALESCE(MAX(m.creato_il), c.creata_il) AS ultimo_messaggio_il
                FROM chat c LEFT JOIN messaggi m ON m.chat_id = c.id
                GROUP BY c.id ORDER BY ultimo_messaggio_il DESC, c.id DESC""").fetchall()

    def leggi_chat(self, chat_id: int) -> dict | None:
        with self._connessione() as conn:
            chat = conn.execute("SELECT id, titolo, creata_il FROM chat WHERE id = %s", (chat_id,)).fetchone()
            if chat is None:
                return None
            chat["messaggi"] = conn.execute(
                "SELECT ruolo, testo, strumenti, creato_il FROM messaggi WHERE chat_id = %s ORDER BY id",
                (chat_id,)).fetchall()
            return chat

    def stato_agente(self, chat_id: int) -> tuple[list, str] | None:
        with self._connessione() as conn:
            riga = conn.execute("SELECT cronologia, riassunto FROM chat WHERE id = %s", (chat_id,)).fetchone()
        return None if riga is None else (riga["cronologia"], riga["riassunto"])

    def registra_turno(self, chat_id: int, domanda: str, risposta: str, strumenti: list[dict], *,
                       cronologia: list, riassunto: str) -> None:
        """Domanda e risposta insieme, in una transazione, con lo stato aggiornato dell'agente."""
        with self._connessione() as conn, conn.transaction():
            aggiornata = conn.execute("""
                UPDATE chat SET cronologia = %s, riassunto = %s,
                    titolo = CASE WHEN titolo = %s AND NOT EXISTS (SELECT 1 FROM messaggi WHERE chat_id = %s)
                                  THEN %s ELSE titolo END
                WHERE id = %s""",
                (Jsonb(cronologia), riassunto, TITOLO_INIZIALE, chat_id, titolo_da(domanda), chat_id))
            if aggiornata.rowcount == 0:
                raise KeyError(chat_id)
            conn.execute("INSERT INTO messaggi (chat_id, ruolo, testo) VALUES (%s, 'utente', %s)",
                         (chat_id, domanda))
            conn.execute("INSERT INTO messaggi (chat_id, ruolo, testo, strumenti) VALUES (%s, 'assistente', %s, %s)",
                         (chat_id, risposta, Jsonb(strumenti)))

    def elimina_chat(self, chat_id: int) -> bool:
        with self._connessione() as conn:
            return conn.execute("DELETE FROM chat WHERE id = %s", (chat_id,)).rowcount > 0

    def svuota(self) -> None:
        """Solo per i test: cancella tutte le chat."""
        with self._connessione() as conn:
            conn.execute("TRUNCATE messaggi, chat RESTART IDENTITY")


class ArchivioMemoria:
    """Stessa interfaccia, in memoria: per i test automatici dell'API (nessun database)."""

    def __init__(self):
        self._chat: dict[int, dict] = {}
        self._id = itertools.count(1)

    def verifica(self) -> None:
        return None

    def crea_chat(self, titolo: str = TITOLO_INIZIALE) -> dict:
        chat = {"id": next(self._id), "titolo": titolo, "creata_il": datetime.now(timezone.utc),
                "messaggi": [], "cronologia": [], "riassunto": ""}
        self._chat[chat["id"]] = chat
        return {k: chat[k] for k in ("id", "titolo", "creata_il")}

    def elenca_chat(self) -> list[dict]:
        righe = [{"id": c["id"], "titolo": c["titolo"],
                  "ultimo_messaggio_il": c["messaggi"][-1]["creato_il"] if c["messaggi"] else c["creata_il"]}
                 for c in self._chat.values()]
        return sorted(righe, key=lambda r: (r["ultimo_messaggio_il"], r["id"]), reverse=True)

    def leggi_chat(self, chat_id: int) -> dict | None:
        chat = self._chat.get(chat_id)
        if chat is None:
            return None
        return {"id": chat["id"], "titolo": chat["titolo"], "creata_il": chat["creata_il"],
                "messaggi": copy.deepcopy(chat["messaggi"])}

    def stato_agente(self, chat_id: int) -> tuple[list, str] | None:
        chat = self._chat.get(chat_id)
        return None if chat is None else (copy.deepcopy(chat["cronologia"]), chat["riassunto"])

    def registra_turno(self, chat_id: int, domanda: str, risposta: str, strumenti: list[dict], *,
                       cronologia: list, riassunto: str) -> None:
        chat = self._chat[chat_id]  # KeyError se la chat non esiste
        if chat["titolo"] == TITOLO_INIZIALE and not chat["messaggi"]:
            chat["titolo"] = titolo_da(domanda)
        adesso = datetime.now(timezone.utc)
        chat["messaggi"] += [{"ruolo": "utente", "testo": domanda, "strumenti": [], "creato_il": adesso},
                             {"ruolo": "assistente", "testo": risposta, "strumenti": copy.deepcopy(strumenti),
                              "creato_il": adesso}]
        chat["cronologia"], chat["riassunto"] = copy.deepcopy(cronologia), riassunto

    def elimina_chat(self, chat_id: int) -> bool:
        return self._chat.pop(chat_id, None) is not None
