import logging
import traceback

import psycopg2


class PostgresLogHandler(logging.Handler):
    """Handler de logging que grava cada registro na tabela app_log do Postgres.

    Conexao dedicada (autocommit, separada da usada por Historico) reaberta sob demanda -
    falha ao gravar um log nunca deve derrubar a aplicacao, entao qualquer erro aqui cai no
    tratamento padrao do logging (self.handleError), que so avisa no stderr."""

    def __init__(self, dsn: str):
        super().__init__()
        self._dsn = dsn
        self._conn = None

    def _conectar(self):
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self._dsn)
            self._conn.autocommit = True
        return self._conn

    def emit(self, record: logging.LogRecord):
        try:
            detalhes = "".join(traceback.format_exception(*record.exc_info)) if record.exc_info else None
            execucao_id = getattr(record, "execucao_id", None)
            conn = self._conectar()
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO app_log (nivel, logger, mensagem, execucao_id, detalhes) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (record.levelname, record.name, record.getMessage(), execucao_id, detalhes),
                )
        except Exception:
            self.handleError(record)
