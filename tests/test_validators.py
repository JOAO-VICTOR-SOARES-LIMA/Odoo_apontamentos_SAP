from src.validators import validar_linha

_LINHA_BASE = {
    "employee_id_sap": 123,
    "idsap": "456",
    "data": "2026-07-30",
    "horas": 2.0,
    "origem": "odoo",  # nao exige start_time/end_time precalculado (so linha vinda do excel exige)
}


def test_linha_valida_passa():
    resultado = validar_linha(_LINHA_BASE, enviar_linhas_zero_hora=False)
    assert resultado.valido is True


def test_employee_id_sap_ausente():
    row = {**_LINHA_BASE, "employee_id_sap": None}
    resultado = validar_linha(row, enviar_linhas_zero_hora=False)
    assert (resultado.valido, resultado.status) == (False, "erro_dados_ausentes")


def test_idsap_ausente():
    row = {**_LINHA_BASE, "idsap": None}
    resultado = validar_linha(row, enviar_linhas_zero_hora=False)
    assert (resultado.valido, resultado.status) == (False, "erro_dados_ausentes")


def test_data_ausente():
    row = {**_LINHA_BASE, "data": None}
    resultado = validar_linha(row, enviar_linhas_zero_hora=False)
    assert (resultado.valido, resultado.status) == (False, "erro_dados_ausentes")


def test_horas_zero_e_pulado_quando_flag_desligada():
    row = {**_LINHA_BASE, "horas": 0}
    resultado = validar_linha(row, enviar_linhas_zero_hora=False)
    assert (resultado.valido, resultado.status) == (False, "pulado_zero_horas")


def test_horas_zero_passa_quando_flag_ligada():
    row = {**_LINHA_BASE, "horas": 0}
    resultado = validar_linha(row, enviar_linhas_zero_hora=True)
    assert resultado.valido is True


def test_local_campo_sem_horario_preenchido():
    row = {**_LINHA_BASE, "local": "Campo", "hora_inicio_campo": None, "hora_fim_campo": None}
    resultado = validar_linha(row, enviar_linhas_zero_hora=False)
    assert (resultado.valido, resultado.status) == (False, "erro_dados_ausentes")


def test_local_campo_hora_fim_antes_da_hora_inicio():
    row = {**_LINHA_BASE, "local": "Campo", "hora_inicio_campo": 14.0, "hora_fim_campo": 13.0}
    resultado = validar_linha(row, enviar_linhas_zero_hora=False)
    assert (resultado.valido, resultado.status) == (False, "erro_horario_invalido")


def test_local_campo_hora_fim_ultrapassa_24h():
    row = {**_LINHA_BASE, "local": "Campo", "hora_inicio_campo": 22.0, "hora_fim_campo": 24.5}
    resultado = validar_linha(row, enviar_linhas_zero_hora=False)
    assert (resultado.valido, resultado.status) == (False, "erro_horario_invalido")


def test_local_campo_horario_valido_passa():
    row = {**_LINHA_BASE, "local": "Campo", "hora_inicio_campo": 8.0, "hora_fim_campo": 12.0}
    resultado = validar_linha(row, enviar_linhas_zero_hora=False)
    assert resultado.valido is True


def test_excel_com_end_time_ultrapassando_24h_bug_n8n():
    row = {**_LINHA_BASE, "origem": "excel", "start_time": "20:00", "end_time": "25:00"}
    resultado = validar_linha(row, enviar_linhas_zero_hora=False)
    assert (resultado.valido, resultado.status) == (False, "erro_horario_invalido")


def test_excel_sem_start_end_time():
    row = {**_LINHA_BASE, "origem": "excel", "start_time": None, "end_time": None}
    resultado = validar_linha(row, enviar_linhas_zero_hora=False)
    assert (resultado.valido, resultado.status) == (False, "erro_dados_ausentes")


def test_linha_do_odoo_nao_exige_start_end_time_precalculado():
    row = {**_LINHA_BASE, "origem": "odoo"}
    resultado = validar_linha(row, enviar_linhas_zero_hora=False)
    assert resultado.valido is True
