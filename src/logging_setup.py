import logging
import sys


def configurar_logging(postgres_dsn: str = "", nivel: int = logging.INFO) -> None:
    """Configura o logger raiz da aplicacao: sempre stdout (visibilidade no terminal/tarefa
    agendada), mais Postgres (tabela app_log) quando houver DSN - usado tanto pela app
    FastAPI quanto pelo script agendado, pra centralizar tudo no mesmo lugar consultavel.
    Idempotente: chamar mais de uma vez no mesmo processo nao duplica handler."""
    raiz = logging.getLogger()
    if raiz.handlers:
        return
    raiz.setLevel(nivel)

    formato = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler_stdout = logging.StreamHandler(sys.stdout)
    handler_stdout.setFormatter(formato)
    raiz.addHandler(handler_stdout)

    if postgres_dsn:
        from src.log_handler import PostgresLogHandler

        handler_pg = PostgresLogHandler(postgres_dsn)
        handler_pg.setLevel(logging.INFO)
        raiz.addHandler(handler_pg)
