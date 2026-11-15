"""Test delle immagini Docker (step 9): il back-end installa le stesse versioni del progetto."""

from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]


def _versioni(file: Path) -> dict[str, str]:
    righe = (r.split("#")[0].strip() for r in file.read_text(encoding="utf-8").splitlines())
    return dict(r.split("==", 1) for r in righe if "==" in r)


def test_backend_usa_le_versioni_di_requirements():
    progetto, backend = _versioni(RADICE / "requirements.txt"), _versioni(RADICE / "backend" / "requirements.txt")
    assert set(backend) == {"fastapi", "uvicorn", "httpx", "psycopg[binary]", "python-dotenv"}
    for pacchetto, versione in backend.items():
        assert progetto[pacchetto] == versione, pacchetto
