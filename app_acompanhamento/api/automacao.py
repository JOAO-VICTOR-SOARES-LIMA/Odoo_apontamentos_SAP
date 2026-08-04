import datetime
import logging
import os

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from src.alertas import notificar_falha
from src.config import load_config
from src.db import Historico
from src.odoo_import import gerar_preview_odoo, rodar_importacao_odoo

from app_acompanhamento.state import state

router = APIRouter()
logger = logging.getLogger(__name__)


def _dsn_ou_erro() -> str:
    dsn = os.environ.get("POSTGRES_DSN")
    if not dsn:
        raise HTTPException(400, "POSTGRES_DSN nao configurado")
    return dsn


@router.get("/modo")
def obter_modo():
    hist = Historico(_dsn_ou_erro())
    try:
        return {"modo": hist.ler_modo_automacao()}
    finally:
        hist.close()


class ModoBody(BaseModel):
    modo: str  # "manual" | "automatico"


@router.post("/modo")
def definir_modo(body: ModoBody):
    hist = Historico(_dsn_ou_erro())
    try:
        hist.definir_modo_automacao(body.modo)
        return {"modo": body.modo}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        hist.close()


class PreviewBody(BaseModel):
    ambiente: str = "test"
    data: str | None = None  # YYYY-MM-DD, default: dia anterior
    confirmar_prod: bool = False


@router.post("/preview")
def preview(body: PreviewBody):
    """So leitura - mostra o status calculado de cada apontamento do Odoo pra 'data' (default:
    dia anterior) sem enviar nada e sem gravar no Postgres."""
    try:
        config = load_config(env=body.ambiente)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc

    data_referencia = body.data or (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

    try:
        preview_linhas = gerar_preview_odoo(config, data_referencia)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc

    contagem: dict[str, int] = {}
    for row in preview_linhas:
        contagem[row["status"]] = contagem.get(row["status"], 0) + 1

    return {
        "preview": preview_linhas,
        "contagem": contagem,
        "ambiente": config.sap.nome,
        "data_referencia": data_referencia,
    }


class RodarAgoraBody(BaseModel):
    ambiente: str = "test"
    data: str | None = None  # YYYY-MM-DD, default: dia anterior
    confirmar_prod: bool = False


def _run_automacao(config, data_referencia: str):
    # Historico(...) fica DENTRO do try de proposito: se a conexao com o Postgres falhar aqui,
    # precisa cair no except/finally igual a qualquer outra falha - senao a excecao escapa antes
    # do try, o finally nunca roda, e 'em_andamento' fica travado em True pra sempre (todo
    # proximo "Rodar agora" falharia com 409 ate reiniciar o container).
    hist = None
    try:
        hist = Historico(config.postgres_dsn)

        def callback(pos, total, row, resultado):
            with state.lock:
                state.automacao["pos"] = pos
                state.automacao["total"] = total
                linha_log = (f"[{pos}/{total}] linha {row['linha_excel']} {row['colaborador']} "
                             f"{row['data']} -> {resultado['status']}")
                state.automacao["logs"].append(linha_log)
                state.automacao["logs"] = state.automacao["logs"][-50:]

        execucao_id = rodar_importacao_odoo(
            config, hist, data_referencia, dry_run=False, origem="odoo_manual",
            callback_progresso=callback,
        )
        with state.lock:
            state.automacao["execucao_id"] = execucao_id
            state.automacao["resumo"] = hist.resumo_execucao(execucao_id)
    except Exception as exc:
        logger.exception("falha na execucao de 'rodar agora' (data_referencia=%s)", data_referencia)
        notificar_falha("ApontaSAP: falha no 'rodar agora'", f"data_referencia={data_referencia}: {exc}")
        with state.lock:
            state.automacao["erro"] = str(exc)
    finally:
        if hist is not None:
            hist.close()
        with state.lock:
            state.automacao["em_andamento"] = False


@router.post("/rodar-agora")
def rodar_agora(body: RodarAgoraBody, background_tasks: BackgroundTasks):
    if state.automacao["em_andamento"]:
        raise HTTPException(409, "Ja existe uma execucao automatica em andamento")

    try:
        config = load_config(env=body.ambiente)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc

    data_referencia = body.data or (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

    with state.lock:
        state.automacao.update(
            em_andamento=True, pos=0, total=0, logs=[], execucao_id=None, resumo=None, erro=None,
        )

    background_tasks.add_task(_run_automacao, config, data_referencia)
    return {"iniciado": True, "data_referencia": data_referencia, "ambiente": config.sap.nome}


@router.get("/progresso")
def progresso():
    with state.lock:
        return dict(state.automacao)
