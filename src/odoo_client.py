import xmlrpc.client

from src.retry import com_retry

# Falha de rede (nao erro de negocio - xmlrpc.client.Fault fica de fora de proposito) - seguro
# pra retry, ja que OdooClient e somente leitura em toda a aplicacao.
_ERROS_TRANSITORIOS = (ConnectionError, TimeoutError, OSError)

_CAMPOS_APONTAMENTOS = [
    "date", "user_id", "project_id", "name", "task_id", "unit_amount",
    "x_studio_related_field_74a_1jojldopb",
    "x_studio_local", "x_studio_hora_inicio_1", "x_studio_hora_fim_1", "x_studio_intervalo",
]

# Apontamentos com essa tarefa sao time off (folga/ferias/ausencia) - nunca vao pro SAP,
# entao ficam de fora ja na consulta ao Odoo (domain "task_id.name not in [...]").
_TAREFAS_TIME_OFF = ["Time Off"]
_FILTRO_SEM_TIME_OFF = ["task_id.name", "not in", _TAREFAS_TIME_OFF]


class OdooClient:
    """Cliente XML-RPC minimo pro Odoo, usado exclusivamente para leitura (relatorio
    "DE-PARA Odoo x SAP") - nunca escreve nada no Odoo."""

    def __init__(self, url: str, db: str, username: str, api_key: str):
        self.db = db
        self.username = username
        self.api_key = api_key
        self._common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        self._object = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
        self._uid = None

    def _autenticar(self) -> int:
        if self._uid is None:
            self._uid = com_retry(self._common.authenticate, self.db, self.username, self.api_key, {},
                                   excecoes=_ERROS_TRANSITORIOS)
            if not self._uid:
                raise ValueError("Falha ao autenticar no Odoo - verifique db/usuario/api_key")
        return self._uid

    def search_read(self, model: str, domain: list, fields: list[str], limit: int = 10000) -> list[dict]:
        uid = self._autenticar()
        return com_retry(
            self._object.execute_kw, self.db, uid, self.api_key, model, "search_read",
            [domain], {"fields": fields, "limit": limit},
            excecoes=_ERROS_TRANSITORIOS,
        )

    def buscar_apontamentos(self, data_de: str) -> list[dict]:
        """Apontamentos aprovados (campo 'validated') a partir de 'data_de' - mesmo criterio
        que o fluxo n8n ja usa hoje para decidir o que e candidato a envio pro SAP. Ignora
        apontamentos com horas <= 0 (negativos ou zerados nunca vao pro SAP) e os de time off."""
        domain = [["date", ">=", data_de], ["validated", "=", True], ["unit_amount", ">", 0],
                  _FILTRO_SEM_TIME_OFF]
        return self.search_read("account.analytic.line", domain, _CAMPOS_APONTAMENTOS)

    def buscar_apontamentos_validados_no_dia(self, data: str) -> list[dict]:
        """Apontamentos que foram VALIDADOS num dia exato (usado pelo envio diario automatico -
        so o dia anterior, sem acumular backlog de dias perdidos). Nao ha campo dedicado de
        'data de validacao' no Odoo, entao usa 'write_date' (ultima modificacao do registro)
        como aproximacao - assume que validar e a ultima acao feita no apontamento. O dia
        efetivamente TRABALHADO (campo 'date') pode ser diferente e vem em cada linha normalmente.
        Ignora apontamentos com horas <= 0 (negativos ou zerados nunca vao pro SAP) e os de time off."""
        domain = [
            ["write_date", ">=", f"{data} 00:00:00"],
            ["write_date", "<=", f"{data} 23:59:59"],
            ["validated", "=", True],
            ["unit_amount", ">", 0],
            _FILTRO_SEM_TIME_OFF,
        ]
        return self.search_read("account.analytic.line", domain, _CAMPOS_APONTAMENTOS)

    def buscar_apontamentos_periodo(self, data_inicio: str, data_fim: str) -> list[dict]:
        """Apontamentos aprovados dentro de um periodo (inclusive nas duas pontas) - usado pela
        importacao em massa direto do Odoo (fonte alternativa ao Excel), pra deixar o usuario
        escolher o intervalo em vez de um dia exato. Ignora apontamentos com horas <= 0
        (negativos ou zerados nunca vao pro SAP) e os de time off."""
        domain = [["date", ">=", data_inicio], ["date", "<=", data_fim],
                  ["validated", "=", True], ["unit_amount", ">", 0], _FILTRO_SEM_TIME_OFF]
        return self.search_read("account.analytic.line", domain, _CAMPOS_APONTAMENTOS)

    def buscar_usuarios(self) -> list[dict]:
        return self.search_read("res.users", [], ["login", "id", "name"])

    def buscar_id_sap_tarefas(self, task_ids: list[int]) -> dict[int, str | None]:
        """Pra cada task_id, le o x_studio_id_sap preenchido na propria tarefa (modulo de
        Projetos do Odoo) - o ActivityType enviado ao SAP e sempre o da tarefa vinculada ao
        apontamento, sem subir pra tarefa pai/raiz.

        Depende da credencial do Odoo (ODOO_USERNAME/ODOO_API_KEY) ter acesso de leitura ao
        project.task pra qualquer tarefa (a conta de integracao foi adicionada como seguidora
        de todas as tarefas via automacao no Odoo, pra contornar a regra de registro que
        restringe project.task por visibilidade de projeto/seguidor)."""
        task_ids = {t for t in task_ids if t}
        if not task_ids:
            return {}

        rows = self.search_read("project.task", [["id", "in", list(task_ids)]],
                                 ["x_studio_id_sap"], limit=len(task_ids))
        return {r["id"]: r.get("x_studio_id_sap") or None for r in rows}
