"""Test del collegamento a LM Studio con un client finto: nessuna chiamata di rete."""

from types import SimpleNamespace

import httpx
import openai
import pytest

from agente.config import carica_config
from agente.llm import ErroreModello, crea_modello, verifica_modello
from agente.strumenti import crea_ora_corrente

URL = "http://localhost:1234/v1"


class ClientFinto:
    """Imita `OpenAI`: `.models.list()` restituisce oggetti con `.id`, oppure solleva `errore`."""

    def __init__(self, ids: list[str] | None = None, errore: Exception | None = None):
        self.models = self
        self._ids = ids or []
        self._errore = errore

    def list(self):
        if self._errore:
            raise self._errore
        return [SimpleNamespace(id=i) for i in self._ids]


def _config(modello: str = "m"):
    return carica_config({"LM_BASE_URL": URL, "LM_MODEL": modello})


def test_verifica_modello_presente():
    verifica_modello(_config(), ClientFinto(["altro", "m"]))


def test_verifica_modello_assente_elenca_disponibili():
    with pytest.raises(ErroreModello) as info:
        verifica_modello(_config("mancante"), ClientFinto(["google/gemma-4-e2b", "qwen"]))
    testo = str(info.value)
    assert "mancante" in testo
    assert "google/gemma-4-e2b" in testo and "qwen" in testo
    assert "carica il modello o correggi LM_MODEL" in testo


def test_verifica_server_irraggiungibile():
    errore = openai.APIConnectionError(request=httpx.Request("GET", "http://x"))
    with pytest.raises(ErroreModello) as info:
        verifica_modello(_config(), ClientFinto(errore=errore))
    testo = str(info.value)
    assert URL in testo
    assert "avvia LM Studio e il server" in testo


def test_crea_modello_parametri():
    modello = crea_modello(_config(), [crea_ora_corrente()])
    assert modello.bound.model_name == "m"
    assert modello.bound.temperature == 0
    assert modello.bound.openai_api_base == URL
    assert modello.kwargs["tools"][0]["function"]["name"] == "ora_corrente"
