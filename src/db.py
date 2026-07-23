import json
import psycopg2
import psycopg2.extras


class Historico:
    def __init__(self, dsn: str):
        self.conn = psycopg2.connect(dsn)
        self.conn.autocommit = True

    def close(self):
        self.conn.close()

    def criar_execucao(self, ambiente: str, arquivo_origem: str, dry_run: bool,
                        origem: str = "excel_manual") -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO import_execucao (ambiente, arquivo_origem, dry_run, origem)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (ambiente, arquivo_origem, dry_run, origem),
            )
            return cur.fetchone()[0]

    def ler_modo_automacao(self) -> str:
        with self.conn.cursor() as cur:
            cur.execute("SELECT modo FROM automacao_config WHERE id = 1")
            row = cur.fetchone()
            return row[0] if row else "manual"

    def definir_modo_automacao(self, modo: str) -> None:
        if modo not in ("manual", "automatico"):
            raise ValueError(f"modo invalido: {modo!r} (use 'manual' ou 'automatico')")
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO automacao_config (id, modo, atualizado_em)
                VALUES (1, %s, now())
                ON CONFLICT (id) DO UPDATE SET modo = EXCLUDED.modo, atualizado_em = now()
                """,
                (modo,),
            )

    def registrar_linha(self, execucao_id: int, linha_excel: int, row: dict,
                         status: str, motivo: str | None = None, sap_response: dict | None = None,
                         sap_request: dict | None = None):
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO import_linha (
                    execucao_id, linha_excel, colaborador, data, projeto, idsap, tarefa,
                    descricao, horas, intervalo, start_time, end_time, break_time,
                    employee_id_sap, status, motivo, sap_response, sap_request
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    execucao_id, linha_excel, row.get("colaborador"), row.get("data"),
                    row.get("projeto"), row.get("idsap"), row.get("tarefa"),
                    row.get("descricao"), row.get("horas"), row.get("intervalo"),
                    row.get("start_time"), row.get("end_time"), row.get("break_time"),
                    row.get("employee_id_sap"), status, motivo,
                    json.dumps(sap_response) if sap_response is not None else None,
                    json.dumps(sap_request) if sap_request is not None else None,
                ),
            )

    def finalizar_execucao(self, execucao_id: int):
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE import_execucao SET
                    finalizado_em = now(),
                    status = 'concluido',
                    total_linhas = (SELECT count(*) FROM import_linha WHERE execucao_id = %(id)s),
                    total_enviadas = (SELECT count(*) FROM import_linha WHERE execucao_id = %(id)s AND status = 'enviado'),
                    total_ja_existentes = (SELECT count(*) FROM import_linha WHERE execucao_id = %(id)s AND status = 'ja_existe_sap'),
                    total_puladas = (SELECT count(*) FROM import_linha WHERE execucao_id = %(id)s AND status IN ('pulado_zero_horas', 'pendente_dry_run')),
                    total_erros = (SELECT count(*) FROM import_linha WHERE execucao_id = %(id)s AND status LIKE 'erro_%%')
                WHERE id = %(id)s
                """,
                {"id": execucao_id},
            )

    def resumo_execucao(self, execucao_id: int) -> dict:
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM import_execucao WHERE id = %s", (execucao_id,))
            return dict(cur.fetchone())
