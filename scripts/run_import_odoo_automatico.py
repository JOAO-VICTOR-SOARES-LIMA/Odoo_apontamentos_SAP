import argparse
import datetime
import logging
import sys
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_PROJETO))

from src.alertas import notificar_falha
from src.config import load_config
from src.db import Historico
from src.logging_setup import configurar_logging
from src.odoo_import import rodar_importacao_odoo

logger = logging.getLogger("odoo_automatico")


def main():
    parser = argparse.ArgumentParser(
        description="Envio diario automatico Odoo -> SAP (apontamentos validados do dia anterior)"
    )
    parser.add_argument("--env", choices=["test", "prod"], required=True, help="Ambiente SAP de destino")
    parser.add_argument("--data", help="Data de referencia YYYY-MM-DD (default: ontem)")
    parser.add_argument("--forcar", action="store_true",
                         help="Ignora a flag 'modo' (manual/automatico) e roda mesmo assim - "
                              "usado pelo botao 'Rodar agora' da tela e para testes manuais")
    parser.add_argument("--send", action="store_true",
                         help="Sem essa flag o script roda em modo dry-run (nao escreve nada no SAP)")
    parser.add_argument("--confirm-prod", action="store_true",
                         help="Obrigatorio junto com --send quando --env=prod, para evitar envio acidental")
    args = parser.parse_args()

    dry_run = not args.send
    if args.env == "prod" and args.send and not args.confirm_prod:
        print("envio real para producao requer --send --confirm-prod explicitamente.", file=sys.stderr)
        sys.exit(1)

    data_referencia = args.data or (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

    config = load_config(env=args.env)
    configurar_logging(config.postgres_dsn)
    hist = Historico(config.postgres_dsn)
    try:
        modo = hist.ler_modo_automacao()
        if modo == "manual" and not args.forcar:
            logger.info("modo=manual, nada a fazer (tarefa agendada disparou mas a automacao esta desligada)")
            return

        origem = "odoo_manual" if args.forcar else "odoo_automatico"
        logger.info("iniciando: env=%s data_referencia=%s dry_run=%s origem=%s",
                    args.env, data_referencia, dry_run, origem)
        execucao_id = rodar_importacao_odoo(config, hist, data_referencia, dry_run, origem)
        logger.info("execucao %s concluida", execucao_id)
    except Exception as exc:
        logger.exception("falha na execucao do envio diario automatico")
        notificar_falha("ApontaSAP: falha no envio diario automatico",
                         f"env={args.env} data_referencia={data_referencia}: {exc}")
        sys.exit(1)
    finally:
        hist.close()


if __name__ == "__main__":
    main()
