from src.agenda import horas_decimais_para_hhmm
from src.config import Config
from src.core import enviar_em_lotes, fechar_contexto, gerar_preview, montar_contexto_com_linhas
from src.db import Historico
from src.de_para import normalizar_apontamento_odoo
from src.hana_client import HanaClient
from src.odoo_client import OdooClient


def _montar_linhas_de_apontamentos(hana: HanaClient, odoo: OdooClient, apontamentos: list[dict]) -> list[dict]:
    """Normaliza uma lista de apontamentos crus do Odoo (ja filtrados por data/validated por
    quem chama) no mesmo formato que src/excel_loader.py::carregar_linhas produz, pra serem
    processadas pelo pipeline existente (avaliar_linha/enviar_linha/gerar_preview/Historico) sem
    nenhuma mudanca nele - so 'start_time'/'end_time' ficam de fora (nao existem pra linha vinda
    do Odoo; sao recalculados do zero por AgendaHorarios.alocar() dentro de enviar_linha)."""
    empid_por_email = hana.buscar_funcionarios_ativos_com_email()
    usuarios_odoo = {u["id"]: u["login"] for u in odoo.buscar_usuarios()}

    task_ids = {ap["task_id"][0] for ap in apontamentos if ap.get("task_id")}
    id_sap_raiz_por_task = odoo.buscar_id_sap_tarefa_principal(list(task_ids))

    vistos = set()
    linhas = []
    for ap in apontamentos:
        linha = normalizar_apontamento_odoo(ap, usuarios_odoo, empid_por_email, id_sap_raiz_por_task)

        assinatura = (linha["colaborador"], linha["data"], linha["projeto_sap"], linha["idsap"],
                      linha["tarefa"], linha["descricao_apontamento"], round(linha["horas_apontadas"], 2))
        if assinatura in vistos:
            continue
        vistos.add(assinatura)

        break_time = (horas_decimais_para_hhmm(linha["intervalo_horas"])
                      if linha["intervalo_horas"] else "00:00")

        linhas.append({
            "linha_excel": len(linhas) + 1,
            "origem": "odoo",
            "odoo_id": linha["odoo_id"],
            "colaborador": linha["colaborador"],
            "data": linha["data"],
            "projeto": linha["projeto_odoo"],
            "projeto_sap": linha["projeto_sap"],
            "idsap": linha["idsap"],
            "tarefa": linha["tarefa"],
            "descricao": linha["descricao_apontamento"],
            "horas": linha["horas_apontadas"],
            "intervalo": linha["intervalo_horas"],
            "break_time": break_time,
            "employee_id_sap": linha["employee_id_sap"],
            # Local == "Campo": StartTime/EndTime vem exatamente do que o colaborador preencheu,
            # em vez do encadeamento por funcionario+dia - ver src/core.py::resolver_horario.
            "local": linha["local"],
            "hora_inicio_campo": linha["hora_inicio_campo"],
            "hora_fim_campo": linha["hora_fim_campo"],
        })

    return linhas


def montar_linhas_odoo(hana: HanaClient, odoo: OdooClient, data: str) -> list[dict]:
    """Busca apontamentos VALIDADOS no Odoo num dia exato (nao o dia trabalhado, o dia da
    validacao) - usado pelo envio diario automatico (tela /automatico, sempre 'ontem')."""
    apontamentos = odoo.buscar_apontamentos_validados_no_dia(data)
    return _montar_linhas_de_apontamentos(hana, odoo, apontamentos)


def montar_linhas_odoo_periodo(hana: HanaClient, odoo: OdooClient, data_inicio: str, data_fim: str) -> list[dict]:
    """Busca apontamentos aprovados no Odoo dentro de um periodo (inclusive) - usado pela
    importacao em massa (tela principal), como alternativa a subir um Excel gerado pelo n8n.
    Mostra tudo que ainda nao esta no SAP, inclusive o que esta bloqueado por erro/falta de
    dados - reaproveita o mesmo gerar_preview()/avaliar_linha() que ja classifica cada linha
    (pronto_para_envio, ja_existe_sap, erro_dados_ausentes, erro_projeto_invalido, etc)."""
    apontamentos = odoo.buscar_apontamentos_periodo(data_inicio, data_fim)
    return _montar_linhas_de_apontamentos(hana, odoo, apontamentos)


def gerar_preview_odoo(config: Config, data: str) -> list[dict]:
    """So leitura - mesmo preview que rodar_importacao_odoo calcularia (status por linha,
    sem enviar nada e sem gravar no Postgres). Usado pelo botao 'Ver preview' da tela
    /automatico, pra mostrar o que aconteceria antes de rodar de verdade."""
    odoo = OdooClient(config.odoo.url, config.odoo.db, config.odoo.username, config.odoo.api_key)
    hana_leitura = HanaClient(config.hana.host, config.hana.port, config.hana.user,
                               config.hana.password, config.hana.schema)
    try:
        linhas = montar_linhas_odoo(hana_leitura, odoo, data)
    finally:
        hana_leitura.close()

    ctx = montar_contexto_com_linhas(config, linhas, abrir_sap=False)
    try:
        return gerar_preview(ctx)
    finally:
        fechar_contexto(ctx)


def rodar_importacao_odoo(config: Config, hist: Historico, data: str, dry_run: bool, origem: str,
                           callback_progresso=None) -> int:
    """Espelha src/importer.py::rodar_importacao, mas monta as linhas direto do Odoo (dia
    exato 'data') em vez de ler um Excel. 'hist' ja vem aberto por quem chama (CLI/rota da
    API), que decide a conexao pra poder ler a flag de modo automatico antes de chamar isso."""
    odoo = OdooClient(config.odoo.url, config.odoo.db, config.odoo.username, config.odoo.api_key)
    hana_leitura = HanaClient(config.hana.host, config.hana.port, config.hana.user,
                               config.hana.password, config.hana.schema)
    try:
        linhas = montar_linhas_odoo(hana_leitura, odoo, data)
    finally:
        hana_leitura.close()

    execucao_id = hist.criar_execucao(config.sap.nome, f"odoo:{data}", dry_run, origem=origem)
    print(f"[execucao {execucao_id}] origem={origem} ambiente={config.sap.nome} "
          f"dry_run={dry_run} data_referencia={data}")

    ctx = montar_contexto_com_linhas(config, linhas, abrir_sap=not dry_run)
    print(f"[execucao {execucao_id}] {len(ctx.linhas)} linhas carregadas do Odoo")

    if dry_run:
        preview = gerar_preview(ctx)
        for row in preview:
            status = row["status"] if row["status"] != "pronto_para_envio" else "pendente_dry_run"
            hist.registrar_linha(execucao_id, row["linha_excel"], row, status, row.get("motivo"))
        hist.finalizar_execucao(execucao_id)
    else:
        def callback(pos, total, row, resultado):
            if pos % config.batch_size == 0 or pos == total:
                print(f"[execucao {execucao_id}] processadas {pos}/{total} linhas...")
            if callback_progresso:
                callback_progresso(pos, total, row, resultado)

        enviar_em_lotes(ctx, hist, execucao_id, ctx.linhas, config.batch_size,
                         config.batch_sleep_seconds, callback_progresso=callback)

    resumo = hist.resumo_execucao(execucao_id)
    print(f"[execucao {execucao_id}] concluida: {resumo}")
    fechar_contexto(ctx)
    return execucao_id
