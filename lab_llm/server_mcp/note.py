"""Logica del server delle note: archivio SQLite, senza dipendere da MCP."""

import logging
import os
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

logger = logging.getLogger(__name__)

TESTO_MAX = 500
LIMITE_MAX = 50


class ErroreNote(Exception):
    """Errore atteso (argomenti, ID inesistente, archivio) con un messaggio leggibile dal modello."""


@dataclass(frozen=True)
class Nota:
    """Una nota salvata."""

    id: int
    testo: str
    creata: str


class ArchivioNote:
    """Note su un file SQLite; ogni operazione apre e chiude la propria connessione."""

    def __init__(self, percorso: Path):
        self.percorso = Path(percorso)
        try:
            self.percorso.parent.mkdir(parents=True, exist_ok=True)
            with self._connetti() as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS note ("
                             "id INTEGER PRIMARY KEY AUTOINCREMENT, testo TEXT NOT NULL, creata TEXT NOT NULL)")
        except (OSError, sqlite3.Error) as errore:
            raise self._non_accessibile(errore) from errore

    @staticmethod
    def _non_accessibile(errore: Exception) -> ErroreNote:
        logger.warning("note: archivio non accessibile: %s", errore)
        return ErroreNote("archivio note non accessibile")

    def _connetti(self):
        """Connessione che il blocco `with` chiude alla fine (il commit è esplicito)."""
        return closing(sqlite3.connect(self.percorso))

    def aggiungi(self, testo: str) -> Nota:
        pulito = (testo or "").strip()
        if not pulito:
            raise ErroreNote("testo della nota mancante")
        if len(pulito) > TESTO_MAX:
            raise ErroreNote(f"testo della nota troppo lungo (massimo {TESTO_MAX} caratteri)")
        creata = datetime.now().isoformat(timespec="minutes")
        try:
            with self._connetti() as conn:
                cursore = conn.execute("INSERT INTO note (testo, creata) VALUES (?, ?)", (pulito, creata))
                conn.commit()
                id_nota = cursore.lastrowid
        except sqlite3.Error as errore:
            raise self._non_accessibile(errore) from errore
        logger.info("note: aggiunta la nota %d", id_nota)
        return Nota(id_nota, pulito, creata)

    def elenca(self, limite: int) -> list[Nota]:
        if not isinstance(limite, int) or isinstance(limite, bool) or not 1 <= limite <= LIMITE_MAX:
            raise ErroreNote(f"limite deve essere un numero intero tra 1 e {LIMITE_MAX}")
        try:
            with self._connetti() as conn:
                righe = conn.execute("SELECT id, testo, creata FROM note ORDER BY id DESC LIMIT ?",
                                     (limite,)).fetchall()
        except sqlite3.Error as errore:
            raise self._non_accessibile(errore) from errore
        return [Nota(*riga) for riga in righe]

    def elimina(self, id_nota: int) -> Nota:
        try:
            with self._connetti() as conn:
                riga = conn.execute("SELECT id, testo, creata FROM note WHERE id = ?", (id_nota,)).fetchone()
                if riga is None:
                    raise ErroreNote(f"nessuna nota con ID {id_nota}")
                conn.execute("DELETE FROM note WHERE id = ?", (id_nota,))
                conn.commit()
        except sqlite3.Error as errore:
            raise self._non_accessibile(errore) from errore
        logger.info("note: eliminata la nota %d", id_nota)
        return Nota(*riga)


def _archivio() -> ArchivioNote:
    """Archivio sul percorso di NOTE_DB, riletto a ogni chiamata."""
    return ArchivioNote(Path(os.environ.get("NOTE_DB", "dati/note.sqlite3")))


mcp = FastMCP("Note")


@mcp.tool
def aggiungi_nota(testo: str) -> str:
    """Salva una nota di testo (massimo 500 caratteri). Da usare per richieste come "ricordami di...", "annota...", "segna...". Operazione di modifica: scrive nell'archivio."""
    try:
        nota = _archivio().aggiungi(testo)
    except ErroreNote as errore:
        raise ToolError(str(errore)) from errore
    return f"Nota {nota.id} salvata il {nota.creata.replace('T', ' ')}: {nota.testo}"


@mcp.tool
def elenca_note(limite: int = 10) -> str:
    """Elenca le note salvate, dalla più recente, da 1 a 50 (con il loro ID)."""
    try:
        trovate = _archivio().elenca(limite)
    except ErroreNote as errore:
        raise ToolError(str(errore)) from errore
    if not trovate:
        return "Nessuna nota salvata."
    return "\n".join(f"Nota {n.id} salvata il {n.creata.replace('T', ' ')}: {n.testo}" for n in trovate)


@mcp.tool
def elimina_nota(id_nota: int) -> str:
    """Elimina definitivamente la nota con l'ID indicato. Operazione di modifica: non si può annullare."""
    try:
        nota = _archivio().elimina(id_nota)
    except ErroreNote as errore:
        raise ToolError(str(errore)) from errore
    return f"Nota {nota.id} eliminata: {nota.testo}"


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "INFO").upper())
    mcp.run(show_banner=False)
