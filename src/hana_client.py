import re
from hdbcli import dbapi

from src.retry import com_retry

_SELECT_ONLY = re.compile(r"^\s*SELECT\b", re.IGNORECASE)

# Falha transitoria de rede/conexao com o HANA - seguro pra retry, ja que todo uso deste
# cliente e somente leitura (SELECT), nunca tem efeito colateral duplicavel.
_ERROS_TRANSITORIOS = (dbapi.Error,)


class HanaSomenteLeituraError(Exception):
    pass


class HanaClient:
    """Conexao direta ao HANA, usada exclusivamente para leitura/validacao
    (reconciliacao contra os lancamentos ja existentes no SAP).

    Toda escrita no SAP continua acontecendo via Service Layer (sap_client.py) -
    este cliente nunca deve executar INSERT/UPDATE/DELETE."""

    def __init__(self, host: str, port: int, user: str, password: str, schema: str,
                 ssl_validate_certificate: bool = False):
        self.schema = schema
        self.conn = com_retry(
            dbapi.connect, address=host, port=port, user=user, password=password,
            encrypt=True, sslValidateCertificate=ssl_validate_certificate,
            excecoes=_ERROS_TRANSITORIOS,
        )
        with self.conn.cursor() as cur:
            cur.execute(f'SET SCHEMA "{schema}"')

    def close(self):
        self.conn.close()

    def _select(self, sql: str, params: tuple = ()) -> list[dict]:
        if not _SELECT_ONLY.match(sql):
            raise HanaSomenteLeituraError("HanaClient so pode executar SELECT (uso exclusivo de leitura/validacao)")

        def _executar():
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                # aliases sem aspas voltam em maiusculo do HANA - normaliza pra minusculo
                colunas = [d[0].lower() for d in cur.description]
                return [dict(zip(colunas, row)) for row in cur.fetchall()]

        return com_retry(_executar, excecoes=_ERROS_TRANSITORIOS)

    def buscar_lancamentos_existentes(self, data_de: str) -> list[dict]:
        """Junta cabecalho (OTSH) e linhas (TSH1) do modulo de Project Management Timesheet.
        Campos de hora (StartTime/EndTime/Break/EffectTm) vem no formato inteiro HHMM (ex: 1730 = 17:30)."""
        sql = '''
            SELECT
                h."UserID"    AS user_id,
                l."Date"      AS data,
                l."ActType"   AS idsap,
                l."StartTime" AS start_time,
                l."EndTime"   AS end_time,
                l."Break"     AS break_min,
                l."EffectTm"  AS effect_tm,
                l."FiProject" AS fi_project
            FROM OTSH h
            JOIN TSH1 l ON h."AbsEntry" = l."AbsEntry"
            WHERE l."Date" >= ?
        '''
        return self._select(sql, (data_de,))

    def buscar_funcionarios_ativos(self) -> set[int]:
        rows = self._select('SELECT "empID" AS emp_id FROM OHEM WHERE "Active" = ?', ("Y",))
        return {r["emp_id"] for r in rows}

    def buscar_funcionarios_ativos_com_email(self) -> dict[str, int]:
        """Email (minusculo) -> empID, para cruzar com o 'login' dos usuarios do Odoo
        (usado no relatorio DE-PARA Odoo x SAP)."""
        rows = self._select('SELECT "empID" AS emp_id, "email" AS email FROM OHEM WHERE "Active" = ?', ("Y",))
        return {r["email"].strip().lower(): r["emp_id"] for r in rows if r.get("email")}

    def buscar_projetos_validos(self) -> set[str]:
        """Codigos de projeto (OPRJ.PrjCode) ativos no ambiente atual (test ou prod).
        Usado para bloquear ANTES do POST um projeto que o SAP vai rejeitar (erro OPRJ invalido)."""
        rows = self._select('SELECT "PrjCode" AS codigo FROM OPRJ WHERE "Active" = ?', ("Y",))
        return {r["codigo"] for r in rows}
