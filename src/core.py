import copy
import time
from dataclasses import dataclass, field

from src.agenda import AgendaHorarios, hhmm_para_horas_decimais, horas_decimais_para_hhmm
from src.config import Config
from src.db import Historico
from src.excel_loader import carregar_linhas
from src.hana_client import HanaClient
from src.reconciler import SapIndex, normalizar_projeto
from src.sap_client import SapClient, SapError
from src.validators import validar_linha


def projeto_efetivo(row: dict) -> str:
    """Prefere o codigo de projeto autoritativo (coluna opcional 'projeto_sap' do Excel),
    cai pra coluna de exibicao 'projeto' se essa coluna nao existir. Sempre normalizado
    (mantem so o codigo numerico inicial, ex: '81.25.0150 / 81.25.0852' -> '81.25.0150') -
    'projeto_sap' pode vir com mais de um projeto concatenado quando a tarefa do Odoo
    tem mais de um projeto vinculado."""
    valor = row.get("projeto_sap") or row["projeto"]
    return normalizar_projeto(valor)


@dataclass
class Contexto:
    config: Config
    linhas: list
    indice_sap: SapIndex
    agenda: AgendaHorarios
    funcionarios_ativos: set
    projetos_validos: set
    hana: HanaClient
    sap: SapClient = None


def montar_contexto(config: Config, abrir_sap: bool = False) -> Contexto:
    linhas = carregar_linhas(config.excel_path)
    return montar_contexto_com_linhas(config, linhas, abrir_sap)


def montar_contexto_com_linhas(config: Config, linhas: list, abrir_sap: bool = False) -> Contexto:
    """Mesmo bootstrap de montar_contexto (HANA/SapIndex/AgendaHorarios/SapClient), mas recebe
    as linhas prontas em vez de ler do Excel - usado pelo fluxo de importacao direto do Odoo
    (src/odoo_import.py), que monta as linhas por outra via."""
    hana = HanaClient(config.hana.host, config.hana.port, config.hana.user,
                       config.hana.password, config.hana.schema,
                       config.hana.ssl_validate_certificate)

    datas_validas = [l["data"] for l in linhas if l.get("data")]
    data_min = min(datas_validas) if datas_validas else None
    linhas_hana = hana.buscar_lancamentos_existentes(data_min) if data_min else []

    indice_sap = SapIndex(linhas_hana, config.tolerancia_horas)
    agenda = AgendaHorarios(linhas_hana)
    funcionarios_ativos = hana.buscar_funcionarios_ativos()
    projetos_validos = hana.buscar_projetos_validos()

    sap = SapClient(config.sap) if abrir_sap else None

    return Contexto(config, linhas, indice_sap, agenda, funcionarios_ativos, projetos_validos, hana, sap)


def fechar_contexto(ctx: Contexto):
    ctx.hana.close()


def avaliar_linha(ctx: Contexto, row: dict) -> tuple[str, str | None]:
    """So leitura - avalia o status de uma linha sem nenhum efeito colateral (seguro pra preview)."""
    resultado = validar_linha(row, ctx.config.enviar_linhas_zero_hora)
    if not resultado.valido:
        return resultado.status, resultado.motivo

    if row["employee_id_sap"] not in ctx.funcionarios_ativos:
        return "erro_dados_ausentes", f"employeeId_sap {row['employee_id_sap']} nao esta ativo no SAP [{ctx.config.sap.nome}]"

    projeto = projeto_efetivo(row)
    if normalizar_projeto(projeto) not in ctx.projetos_validos:
        return "erro_projeto_invalido", f"projeto '{projeto}' nao encontrado/ativo no SAP [{ctx.config.sap.nome}]"

    if ctx.indice_sap.ja_existe(row["employee_id_sap"], row["idsap"], projeto, row["data"], row["horas"]):
        return "ja_existe_sap", "encontrado no SAP dentro da tolerancia de horas"

    return "pronto_para_envio", None


def gerar_preview(ctx: Contexto) -> list[dict]:
    """Lista todas as linhas do Excel com o status calculado - nao envia nada."""
    preview = []
    for row in ctx.linhas:
        status, motivo = avaliar_linha(ctx, row)
        preview.append({**row, "status": status, "motivo": motivo})
    return preview


def _montar_payload(row: dict, projeto: str, start_time: str, end_time: str) -> dict:
    idsap = row["idsap"]
    activity_type = int(idsap) if str(idsap).isdigit() else idsap
    return {
        "DateFrom": row["data"],
        "DateTo": row["data"],
        "PM_TimeSheetLineDataCollection": [
            {
                "Date": row["data"],
                "ActivityType": activity_type,
                "StartTime": start_time,
                "EndTime": end_time,
                "FinancialProject": projeto,
                "Break": row.get("break_time") or "00:00",
                "NonBillableTime": "00:00",
                "U_Local": row.get("local") or "",
                "U_EASY_Obs": row.get("descricao") or "",
            }
        ],
        "UserID": row["employee_id_sap"],
    }


def _motivo_horario_invalido(row: dict, start_time: str, end_time: str, horas_ja_lancadas: float | None) -> str:
    if horas_ja_lancadas is not None:
        return (
            f"horario invalido: este funcionario ja tem {horas_ja_lancadas:.2f}h lancadas no dia "
            f"{row['data']} (em outro(s) lancamento(s)/projeto(s) - o encadeamento e por "
            f"funcionario+dia, nao por projeto), ocupando das 08:00 ate {start_time}. Encadeando "
            f"esta linha a partir dai (+{row['horas']:.2f}h desta linha), o horario calculado "
            f"chegaria a {end_time} - que bate ou passa da meia-noite (24:00), horario invalido "
            f"pro SAP. Precisa correcao manual (revisar se esta linha e desse dia/funcionario "
            f"mesmo, dividir entre dias, ou verificar duplicidade)"
        )
    return f"horario calculado ultrapassa 24:00 ({start_time} -> {end_time}) - precisa correcao manual"


def resolver_horario(agenda: AgendaHorarios, row: dict) -> tuple[str, str, bool, str | None]:
    """Decide StartTime/EndTime pra uma linha 'pronto_para_envio'. Se local == 'Campo' (Odoo),
    usa o horario real que o colaborador preencheu (hora_inicio_campo/hora_fim_campo) em vez do
    encadeamento por horas - so atualiza a agenda (via registrar_fixo) pra que um proximo
    lancamento nao-Campo do mesmo funcionario/dia comece depois desse horario real, sem
    sobrepor. Caso contrario, usa o encadeamento de sempre (AgendaHorarios.alocar).
    Retorna (start_time, end_time, valido, motivo_se_invalido)."""
    if row.get("local") == "Campo":
        hora_inicio, hora_fim = row["hora_inicio_campo"], row["hora_fim_campo"]
        start_time = horas_decimais_para_hhmm(hora_inicio)
        end_time = horas_decimais_para_hhmm(hora_fim)
        agenda.registrar_fixo(row["employee_id_sap"], row["data"], hora_fim)
        return start_time, end_time, True, None

    projeto = projeto_efetivo(row)
    intervalo_horas = hhmm_para_horas_decimais(row.get("break_time"))
    start_time, end_time, valido, horas_ja_lancadas = agenda.alocar(
        row["employee_id_sap"], row["data"], projeto, row["horas"], intervalo_horas,
    )
    motivo = None if valido else _motivo_horario_invalido(row, start_time, end_time, horas_ja_lancadas)
    return start_time, end_time, valido, motivo


def gerar_payloads_preview(ctx: Contexto, preview: list[dict]) -> tuple[dict[int, dict], dict[int, str]]:
    """So leitura - simula, numa copia isolada da agenda, o payload que seria enviado ao SAP
    para cada linha 'pronto_para_envio' do preview, na mesma ordem em que "enviar todas" as
    processaria. Nao afeta ctx.agenda (usada de verdade no envio), entao pode ser chamada
    quantas vezes quiser sem interferir num envio real subsequente.

    Como o horario de cada linha depende do encadeamento com as anteriores, o resultado so
    e uma previsao fiel se as linhas forem de fato enviadas nessa mesma ordem e nada mudar no
    SAP entre o preview e o envio.

    Retorna (payloads, erros): payloads e linha_excel->payload pras linhas simuladas com sucesso;
    erros e linha_excel->motivo pras linhas que estourariam 24:00 na simulacao (mesmo motivo
    detalhado que apareceria de verdade em enviar_linha)."""
    agenda_simulada = copy.deepcopy(ctx.agenda)
    payloads = {}
    erros = {}
    for row in preview:
        if row["status"] != "pronto_para_envio":
            continue
        projeto = projeto_efetivo(row)
        start_time, end_time, horario_valido, motivo = resolver_horario(agenda_simulada, row)
        if not horario_valido:
            erros[row["linha_excel"]] = motivo
            continue
        payloads[row["linha_excel"]] = _montar_payload(row, projeto, start_time, end_time)
    return payloads, erros


def enviar_linha(ctx: Contexto, hist: Historico, execucao_id: int, row: dict) -> dict:
    """Efeito colateral: pode gravar no SAP (POST) e sempre grava no Postgres.
    So chamar isso a partir de uma acao manual explicita (botao do frontend / --send da CLI)."""
    status, motivo = avaliar_linha(ctx, row)

    if status != "pronto_para_envio":
        hist.registrar_linha(execucao_id, row["linha_excel"], row, status, motivo)
        return {"status": status, "motivo": motivo}

    projeto = projeto_efetivo(row)
    start_time, end_time, horario_valido, motivo_invalido = resolver_horario(ctx.agenda, row)
    if not horario_valido:
        hist.registrar_linha(execucao_id, row["linha_excel"], row, "erro_horario_invalido", motivo_invalido)
        return {"status": "erro_horario_invalido", "motivo": motivo_invalido}

    payload = _montar_payload(row, projeto, start_time, end_time)
    try:
        resposta = ctx.sap.post_timesheet(payload)
        hist.registrar_linha(execucao_id, row["linha_excel"], row, "enviado", None, resposta, payload)
        return {"status": "enviado"}
    except SapError as exc:
        hist.registrar_linha(execucao_id, row["linha_excel"], row, "erro_envio", str(exc), exc.response_body, payload)
        return {"status": "erro_envio", "motivo": str(exc)}


def enviar_em_lotes(ctx: Contexto, hist: Historico, execucao_id: int, linhas: list[dict],
                     tamanho_lote: int, pausa_segundos: float, callback_progresso=None) -> dict:
    """Envia uma lista de linhas ja selecionadas, em lotes, com pausa entre lotes.
    callback_progresso(pos, total, row, resultado) e chamado apos cada linha - use pra atualizar
    barra de progresso/log no frontend. Retorna resumo final da execucao."""
    total = len(linhas)
    for pos, row in enumerate(linhas, start=1):
        resultado = enviar_linha(ctx, hist, execucao_id, row)
        if callback_progresso:
            callback_progresso(pos, total, row, resultado)
        if pos % tamanho_lote == 0 and pos < total:
            time.sleep(pausa_segundos)

    hist.finalizar_execucao(execucao_id)
    return hist.resumo_execucao(execucao_id)
