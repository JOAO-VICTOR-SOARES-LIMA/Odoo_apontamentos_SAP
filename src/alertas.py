import logging
import os

import requests

logger = logging.getLogger(__name__)


def notificar_falha(titulo: str, detalhes: str) -> None:
    """Poste uma notificacao de falha num webhook generico (formato compativel com Slack/Teams
    incoming webhook: {"text": ...}) - so age se ALERTA_WEBHOOK_URL estiver configurado no
    .env; caso contrario so loga (a falha em si ja foi registrada no app_log por quem chamou).
    Nunca propaga excecao - uma falha ao notificar nao pode derrubar o fluxo principal."""
    webhook_url = os.environ.get("ALERTA_WEBHOOK_URL")
    if not webhook_url:
        return

    try:
        requests.post(webhook_url, json={"text": f"*{titulo}*\n{detalhes}"}, timeout=10)
    except Exception:
        logger.exception("falha ao enviar notificacao de alerta pro webhook")
