from dataclasses import dataclass


@dataclass
class ResultadoValidacao:
    valido: bool
    status: str
    motivo: str | None = None


def _hora_para_minutos(texto: str) -> int:
    h, m = str(texto).split(":")
    return int(h) * 60 + int(m)


def validar_linha(row: dict, enviar_linhas_zero_hora: bool) -> ResultadoValidacao:
    """Replica as checagens que faltavam no fluxo n8n original antes de enviar ao SAP."""

    if not row.get("employee_id_sap"):
        return ResultadoValidacao(False, "erro_dados_ausentes", "employeeId_sap ausente")
    if not row.get("idsap"):
        return ResultadoValidacao(False, "erro_dados_ausentes", "idsap (ActivityType) ausente")
    if not row.get("data"):
        return ResultadoValidacao(False, "erro_dados_ausentes", "data ausente")

    if (row.get("horas") or 0) == 0 and not enviar_linhas_zero_hora:
        return ResultadoValidacao(False, "pulado_zero_horas", "horas=0 (config ENVIAR_LINHAS_ZERO_HORA=false)")

    # local == "Campo": o colaborador preenche o horario de inicio/fim reais no Odoo (nao
    # confia no encadeamento por horas) - StartTime/EndTime de verdade sao resolvidos em
    # core.py::resolver_horario, aqui so valida que os dados existem e fazem sentido.
    if row.get("local") == "Campo":
        hora_inicio, hora_fim = row.get("hora_inicio_campo"), row.get("hora_fim_campo")
        if hora_inicio is None or hora_fim is None:
            return ResultadoValidacao(
                False, "erro_dados_ausentes",
                f"local='Campo' mas hora inicio/fim nao preenchidas no Odoo (apontamento id "
                f"{row.get('odoo_id')}) - corrija manualmente no Odoo antes de reenviar",
            )
        if hora_fim <= hora_inicio or hora_fim >= 24:
            return ResultadoValidacao(
                False, "erro_horario_invalido",
                f"local='Campo': hora fim ({hora_fim}) invalida em relacao a hora inicio "
                f"({hora_inicio}) no apontamento id {row.get('odoo_id')} - corrija manualmente no Odoo",
            )

    # StartTime/EndTime pre-calculado so existe em linhas vindas do Excel (o node "Calcular
    # Horario Envio SAP" do n8n) - serve so pra pegar o bug legado de encadeamento do n8n
    # (EndTime >= 24:00). Linhas vindas do Odoo nao tem esse campo: o horario e sempre
    # recalculado do zero por AgendaHorarios.alocar() dentro de enviar_linha, entao essa
    # checagem nao se aplica.
    if row.get("origem", "excel") == "excel":
        if row.get("start_time") is None or row.get("end_time") is None:
            return ResultadoValidacao(False, "erro_dados_ausentes", "StartTime/EndTime ausente")

        fim_minutos = _hora_para_minutos(row["end_time"])
        if fim_minutos >= 24 * 60:
            return ResultadoValidacao(
                False, "erro_horario_invalido",
                f"EndTime {row['end_time']} ultrapassa 24:00 (bug de encadeamento do n8n) - requer correcao manual",
            )

    return ResultadoValidacao(True, "valido")
