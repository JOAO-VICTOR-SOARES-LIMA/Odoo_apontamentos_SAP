from src.agenda import AgendaHorarios, hhmm_para_horas_decimais, horas_decimais_para_hhmm


def test_horas_decimais_para_hhmm():
    assert horas_decimais_para_hhmm(8.0) == "08:00"
    assert horas_decimais_para_hhmm(8.5) == "08:30"
    assert horas_decimais_para_hhmm(17.25) == "17:15"


def test_hhmm_para_horas_decimais():
    assert hhmm_para_horas_decimais("08:00") == 8.0
    assert hhmm_para_horas_decimais("08:30") == 8.5
    assert hhmm_para_horas_decimais(None) == 0.0
    assert hhmm_para_horas_decimais("") == 0.0


def test_alocar_comeca_as_08h_quando_nao_ha_lancamento_anterior():
    agenda = AgendaHorarios(linhas_hana=[])
    start, end, valido, horas_ja_lancadas = agenda.alocar(
        employee_id_sap=1, data="2026-07-30", projeto="81.25.0150", horas=2.0,
    )
    assert (start, end, valido, horas_ja_lancadas) == ("08:00", "10:00", True, None)


def test_alocar_encadeia_a_partir_do_fim_do_lancamento_anterior_mesmo_dia_mesmo_funcionario():
    agenda = AgendaHorarios(linhas_hana=[])
    agenda.alocar(employee_id_sap=1, data="2026-07-30", projeto="81.25.0150", horas=2.0)
    start, end, valido, horas_ja_lancadas = agenda.alocar(
        employee_id_sap=1, data="2026-07-30", projeto="81.25.0999", horas=1.0,
    )
    # encadeamento e por funcionario+dia, NAO por projeto - a segunda linha continua de onde
    # a primeira parou mesmo estando em outro projeto
    assert (start, end, valido, horas_ja_lancadas) == ("10:00", "11:00", True, 2.0)


def test_alocar_estourando_24h_fica_invalido_e_nao_atualiza_a_agenda():
    agenda = AgendaHorarios(linhas_hana=[])
    agenda.alocar(employee_id_sap=1, data="2026-07-30", projeto="81.25.0150", horas=15.0)
    _, _, valido, _ = agenda.alocar(
        employee_id_sap=1, data="2026-07-30", projeto="81.25.0150", horas=2.0,
    )
    assert valido is False

    # como a linha invalida nao deve ter sido registrada, um proximo alocar valido continua
    # de onde a ULTIMA linha valida parou (23:00), nao do estouro anterior
    start, end, valido, _ = agenda.alocar(
        employee_id_sap=1, data="2026-07-30", projeto="81.25.0150", horas=0.5,
    )
    assert (start, end, valido) == ("23:00", "23:30", True)


def test_alocar_e_independente_por_funcionario_e_por_dia():
    agenda = AgendaHorarios(linhas_hana=[])
    agenda.alocar(employee_id_sap=1, data="2026-07-30", projeto="81.25.0150", horas=4.0)

    start_outro_funcionario, *_ = agenda.alocar(
        employee_id_sap=2, data="2026-07-30", projeto="81.25.0150", horas=1.0,
    )
    start_outro_dia, *_ = agenda.alocar(
        employee_id_sap=1, data="2026-07-31", projeto="81.25.0150", horas=1.0,
    )
    assert start_outro_funcionario == "08:00"
    assert start_outro_dia == "08:00"


def test_registrar_fixo_evita_sobreposicao_de_um_lancamento_campo_seguinte():
    agenda = AgendaHorarios(linhas_hana=[])
    agenda.registrar_fixo(employee_id_sap=1, data="2026-07-30", hora_fim_horas=12.5)

    start, end, valido, horas_ja_lancadas = agenda.alocar(
        employee_id_sap=1, data="2026-07-30", projeto="81.25.0150", horas=2.0,
    )
    assert (start, end, valido) == ("12:30", "14:30", True)
    assert horas_ja_lancadas == 4.5


def test_registrar_fixo_nao_retrocede_se_horario_informado_for_menor_que_o_atual():
    agenda = AgendaHorarios(linhas_hana=[])
    agenda.alocar(employee_id_sap=1, data="2026-07-30", projeto="81.25.0150", horas=4.0)  # ate 12:00
    agenda.registrar_fixo(employee_id_sap=1, data="2026-07-30", hora_fim_horas=9.0)

    start, *_ = agenda.alocar(employee_id_sap=1, data="2026-07-30", projeto="81.25.0150", horas=1.0)
    assert start == "12:00"


def test_intervalo_horas_entra_na_largura_da_janela():
    agenda = AgendaHorarios(linhas_hana=[])
    start, end, valido, _ = agenda.alocar(
        employee_id_sap=1, data="2026-07-30", projeto="81.25.0150", horas=4.0, intervalo_horas=1.0,
    )
    assert (start, end, valido) == ("08:00", "13:00", True)
