from src.hana_client import HanaClient
from src.odoo_client import OdooClient
from src.reconciler import SapIndex, normalizar_projeto


def normalizar_apontamento_odoo(ap: dict, usuarios_odoo: dict, empid_por_email: dict) -> dict:
    """Extrai/normaliza um registro cru do Odoo (account.analytic.line) pro formato comum
    usado tanto pelo relatorio DE-PARA quanto pelo envio diario automatico (src/odoo_import.py).
    'usuarios_odoo' e {user_id: login}, 'empid_por_email' e {email-minusculo: empID}."""
    data = str(ap.get("date") or "")[:10]
    user_id, colaborador = (ap["user_id"] or [None, None])
    project_id, projeto_odoo = (ap["project_id"] or [None, None])
    task_id, tarefa = (ap["task_id"] or [None, None])
    idsap = ap.get("x_studio_id_sap_1") or None
    projeto_sap = ap.get("x_studio_related_field_74a_1jojldopb") or normalizar_projeto(projeto_odoo)
    horas = float(ap.get("unit_amount") or 0)
    descricao = ap.get("name") or None

    login = usuarios_odoo.get(user_id)
    employee_id_sap = empid_por_email.get(login.strip().lower()) if login else None

    return {
        "odoo_id": ap.get("id"),
        "data": data,
        "colaborador": colaborador,
        "odoo_user_id": user_id,
        "employee_id_sap": employee_id_sap,
        "projeto_odoo": projeto_odoo,
        "projeto_sap": projeto_sap,
        "idsap": idsap,
        "tarefa": tarefa,
        "descricao_apontamento": descricao,
        "horas_apontadas": horas,
        # Campos de horario real (so preenchidos quando local == "Campo" - ver src/odoo_import.py)
        "local": ap.get("x_studio_local") or None,
        "hora_inicio_campo": ap.get("x_studio_hora_inicio_1") or None,
        "hora_fim_campo": ap.get("x_studio_hora_fim_1") or None,
        "intervalo_horas": ap.get("x_studio_intervalo") or None,
    }


def gerar_de_para_odoo(hana: HanaClient, odoo: OdooClient, data_corte: str,
                        tolerancia_horas: float) -> list[dict]:
    """So leitura - compara apontamentos aprovados no Odoo (campo 'validated') com o que ja
    existe no SAP (via HANA), pra dar uma nocao real do backlog sem depender do fluxo n8n."""
    linhas_hana = hana.buscar_lancamentos_existentes(data_corte)
    indice_sap = SapIndex(linhas_hana, tolerancia_horas)
    empid_por_email = hana.buscar_funcionarios_ativos_com_email()

    usuarios_odoo = {u["id"]: u["login"] for u in odoo.buscar_usuarios()}
    apontamentos = odoo.buscar_apontamentos(data_corte)

    vistos = set()
    resultado = []
    for ap in apontamentos:
        linha = normalizar_apontamento_odoo(ap, usuarios_odoo, empid_por_email)

        assinatura = (linha["colaborador"], linha["data"], linha["projeto_sap"], linha["idsap"],
                      linha["tarefa"], linha["descricao_apontamento"], round(linha["horas_apontadas"], 2))
        if assinatura in vistos:
            continue
        vistos.add(assinatura)

        if not linha["employee_id_sap"] or not linha["idsap"]:
            status = "sem_dados_para_cruzar"
        elif indice_sap.ja_existe(linha["employee_id_sap"], linha["idsap"], linha["projeto_sap"],
                                   linha["data"], linha["horas_apontadas"]):
            status = "ja_no_sap"
        else:
            status = "falta_lancar_no_sap"

        resultado.append({"status": status, **linha})

    return resultado
