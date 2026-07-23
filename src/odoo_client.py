import xmlrpc.client

_CAMPOS_APONTAMENTOS = [
    "date", "user_id", "project_id", "name", "task_id", "unit_amount",
    "x_studio_id_sap_1", "x_studio_related_field_74a_1jojldopb",
    "x_studio_local", "x_studio_hora_inicio_1", "x_studio_hora_fim_1", "x_studio_intervalo",
]


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
            self._uid = self._common.authenticate(self.db, self.username, self.api_key, {})
            if not self._uid:
                raise ValueError("Falha ao autenticar no Odoo - verifique db/usuario/api_key")
        return self._uid

    def search_read(self, model: str, domain: list, fields: list[str], limit: int = 10000) -> list[dict]:
        uid = self._autenticar()
        return self._object.execute_kw(
            self.db, uid, self.api_key, model, "search_read",
            [domain], {"fields": fields, "limit": limit},
        )

    def buscar_apontamentos(self, data_de: str) -> list[dict]:
        """Apontamentos aprovados (campo 'validated') a partir de 'data_de' - mesmo criterio
        que o fluxo n8n ja usa hoje para decidir o que e candidato a envio pro SAP. Ignora
        apontamentos com horas <= 0 (negativos ou zerados nunca vao pro SAP)."""
        domain = [["date", ">=", data_de], ["validated", "=", True], ["unit_amount", ">", 0]]
        return self.search_read("account.analytic.line", domain, _CAMPOS_APONTAMENTOS)

    def buscar_apontamentos_do_dia(self, data: str) -> list[dict]:
        """Apontamentos aprovados de um dia exato (usado pelo envio diario automatico -
        so o dia anterior, sem acumular backlog de dias perdidos). Ignora apontamentos com
        horas <= 0 (negativos ou zerados nunca vao pro SAP)."""
        domain = [["date", "=", data], ["validated", "=", True], ["unit_amount", ">", 0]]
        return self.search_read("account.analytic.line", domain, _CAMPOS_APONTAMENTOS)

    def buscar_apontamentos_periodo(self, data_inicio: str, data_fim: str) -> list[dict]:
        """Apontamentos aprovados dentro de um periodo (inclusive nas duas pontas) - usado pela
        importacao em massa direto do Odoo (fonte alternativa ao Excel), pra deixar o usuario
        escolher o intervalo em vez de um dia exato. Ignora apontamentos com horas <= 0
        (negativos ou zerados nunca vao pro SAP)."""
        domain = [["date", ">=", data_inicio], ["date", "<=", data_fim],
                  ["validated", "=", True], ["unit_amount", ">", 0]]
        return self.search_read("account.analytic.line", domain, _CAMPOS_APONTAMENTOS)

    def buscar_usuarios(self) -> list[dict]:
        return self.search_read("res.users", [], ["login", "id", "name"])
