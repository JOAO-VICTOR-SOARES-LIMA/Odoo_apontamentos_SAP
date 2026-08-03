import pytest

from src.retry import com_retry


def test_com_retry_sucesso_na_primeira_tentativa():
    chamadas = []

    def func():
        chamadas.append(1)
        return "ok"

    assert com_retry(func, tentativas=3, espera_inicial=0.001) == "ok"
    assert len(chamadas) == 1


def test_com_retry_falha_e_depois_da_certo():
    chamadas = []

    def func():
        chamadas.append(1)
        if len(chamadas) < 3:
            raise ConnectionError("falha transitoria")
        return "ok"

    resultado = com_retry(func, tentativas=3, espera_inicial=0.001, excecoes=(ConnectionError,))
    assert resultado == "ok"
    assert len(chamadas) == 3


def test_com_retry_esgota_tentativas_e_propaga():
    def func():
        raise ConnectionError("sempre falha")

    with pytest.raises(ConnectionError):
        com_retry(func, tentativas=2, espera_inicial=0.001, excecoes=(ConnectionError,))


def test_com_retry_nao_retenta_excecao_fora_da_lista():
    chamadas = []

    def func():
        chamadas.append(1)
        raise ValueError("erro de negocio, nao deve ter retry")

    with pytest.raises(ValueError):
        com_retry(func, tentativas=3, espera_inicial=0.001, excecoes=(ConnectionError,))
    assert len(chamadas) == 1
