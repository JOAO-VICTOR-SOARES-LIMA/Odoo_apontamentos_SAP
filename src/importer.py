from src.config import Config
from src.core import enviar_em_lotes, fechar_contexto, gerar_preview, montar_contexto
from src.db import Historico


def rodar_importacao(config: Config, dry_run: bool) -> int:
    hist = Historico(config.postgres_dsn)
    execucao_id = hist.criar_execucao(config.sap.nome, config.excel_path, dry_run)
    print(f"[execucao {execucao_id}] ambiente={config.sap.nome} dry_run={dry_run} arquivo={config.excel_path}")

    ctx = montar_contexto(config, abrir_sap=not dry_run)
    print(f"[execucao {execucao_id}] {len(ctx.linhas)} linhas carregadas do Excel")

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

        enviar_em_lotes(ctx, hist, execucao_id, ctx.linhas, config.batch_size,
                         config.batch_sleep_seconds, callback_progresso=callback)

    resumo = hist.resumo_execucao(execucao_id)
    print(f"[execucao {execucao_id}] concluida: {resumo}")
    fechar_contexto(ctx)
    hist.close()
    return execucao_id
