import logging

from src.config import Config
from src.core import enviar_em_lotes, fechar_contexto, gerar_preview, montar_contexto
from src.db import Historico

logger = logging.getLogger(__name__)


def rodar_importacao(config: Config, dry_run: bool) -> int:
    hist = Historico(config.postgres_dsn)
    execucao_id = hist.criar_execucao(config.sap.nome, config.excel_path, dry_run)
    extra = {"execucao_id": execucao_id}
    logger.info("ambiente=%s dry_run=%s arquivo=%s", config.sap.nome, dry_run, config.excel_path, extra=extra)

    ctx = montar_contexto(config, abrir_sap=not dry_run)
    logger.info("%d linhas carregadas do Excel", len(ctx.linhas), extra=extra)

    if dry_run:
        preview = gerar_preview(ctx)
        for row in preview:
            status = row["status"] if row["status"] != "pronto_para_envio" else "pendente_dry_run"
            hist.registrar_linha(execucao_id, row["linha_excel"], row, status, row.get("motivo"))
        hist.finalizar_execucao(execucao_id)
    else:
        def callback(pos, total, row, resultado):
            if pos % config.batch_size == 0 or pos == total:
                logger.info("processadas %d/%d linhas...", pos, total, extra=extra)

        enviar_em_lotes(ctx, hist, execucao_id, ctx.linhas, config.batch_size,
                         config.batch_sleep_seconds, callback_progresso=callback)

    resumo = hist.resumo_execucao(execucao_id)
    logger.info("concluida: %s", resumo, extra=extra)
    fechar_contexto(ctx)
    hist.close()
    return execucao_id
