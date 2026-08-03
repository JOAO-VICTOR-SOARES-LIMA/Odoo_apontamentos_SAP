from src.reconciler import SapIndex, normalizar_projeto


def test_normalizar_projeto_mantem_so_codigo_numerico_inicial():
    assert normalizar_projeto("81.25.0150 / 81.25.0852") == "81.25.0150"


def test_normalizar_projeto_sem_pontos_a_mais():
    assert normalizar_projeto("81.25.0150") == "81.25.0150"


def test_normalizar_projeto_none_vira_string_vazia():
    assert normalizar_projeto(None) == ""


def test_normalizar_projeto_sem_codigo_numerico_mantem_texto():
    assert normalizar_projeto("SEM-CODIGO") == "SEM-CODIGO"


def test_normalizar_projeto_aceita_valor_nao_string():
    assert normalizar_projeto(8125) == "8125"


def _linha_hana(user_id=123, data="2026-07-30", idsap="456", fi_project="81.25.0150", effect_tm=200):
    return {
        "user_id": user_id, "data": data, "idsap": idsap,
        "fi_project": fi_project, "effect_tm": effect_tm,
    }


def test_ja_existe_dentro_da_tolerancia():
    indice = SapIndex([_linha_hana(effect_tm=200)], tolerancia_horas=0.1)  # 200 = 02:00 = 2h
    assert indice.ja_existe(123, "456", "81.25.0150", "2026-07-30", horas=2.0) is True


def test_ja_existe_fora_da_tolerancia():
    indice = SapIndex([_linha_hana(effect_tm=200)], tolerancia_horas=0.01)
    assert indice.ja_existe(123, "456", "81.25.0150", "2026-07-30", horas=3.0) is False


def test_ja_existe_normaliza_projeto_na_consulta():
    indice = SapIndex([_linha_hana(fi_project="81.25.0150")], tolerancia_horas=0.1)
    assert indice.ja_existe(123, "456", "81.25.0150 / 81.25.0852", "2026-07-30", horas=2.0) is True


def test_ja_existe_chave_diferente_nao_bate():
    indice = SapIndex([_linha_hana()], tolerancia_horas=0.1)
    assert indice.ja_existe(999, "456", "81.25.0150", "2026-07-30", horas=2.0) is False
