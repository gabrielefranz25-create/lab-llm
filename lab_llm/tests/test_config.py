"""Test della lettura e validazione delle variabili d'ambiente."""

import pytest

from agente.config import ErroreConfigurazione, carica_config

MINIMO = {"LM_BASE_URL": "http://h:1/v1", "LM_MODEL": "m"}


def test_valori_minimi_e_default():
    config = carica_config(MINIMO)
    assert config.lm_base_url == "http://h:1/v1"
    assert config.lm_model == "m"
    assert config.fuso_orario_predefinito == "Europe/Rome"
    assert config.max_passi_strumento == 3
    assert config.max_messaggi_contesto == 20
    assert config.lm_timeout == 60.0
    assert config.log_level == "INFO"


@pytest.mark.parametrize("nome", ["LM_BASE_URL", "LM_MODEL"])
def test_variabile_obbligatoria_mancante(nome):
    ambiente = {k: v for k, v in MINIMO.items() if k != nome}
    with pytest.raises(ErroreConfigurazione, match=nome):
        carica_config(ambiente)


def test_variabile_obbligatoria_vuota_conta_come_assente():
    with pytest.raises(ErroreConfigurazione, match="LM_MODEL"):
        carica_config({**MINIMO, "LM_MODEL": ""})


def test_valori_personalizzati():
    config = carica_config({
        **MINIMO,
        "FUSO_ORARIO_PREDEFINITO": "Asia/Tokyo",
        "MAX_PASSI_STRUMENTO": "5",
        "MAX_MESSAGGI_CONTESTO": "8",
        "LM_TIMEOUT": "12.5",
        "LOG_LEVEL": "debug",
    })
    assert config.fuso_orario_predefinito == "Asia/Tokyo"
    assert config.max_passi_strumento == 5
    assert config.max_messaggi_contesto == 8
    assert config.lm_timeout == 12.5
    assert config.log_level == "DEBUG"


@pytest.mark.parametrize("nome, valore", [
    ("MAX_PASSI_STRUMENTO", "0"),
    ("MAX_PASSI_STRUMENTO", "tre"),
    ("MAX_MESSAGGI_CONTESTO", "1"),
    ("LM_TIMEOUT", "-5"),
    ("FUSO_ORARIO_PREDEFINITO", "Roma"),
    ("LOG_LEVEL", "CHIACCHIERA"),
])
def test_valori_non_validi(nome, valore):
    with pytest.raises(ErroreConfigurazione, match=nome):
        carica_config({**MINIMO, nome: valore})
