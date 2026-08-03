import logging
import time

logger = logging.getLogger(__name__)


def com_retry(func, *args, tentativas: int = 3, espera_inicial: float = 1.0,
              excecoes: tuple = (Exception,), **kwargs):
    """Chama func(*args, **kwargs) com retry e backoff exponencial (espera_inicial,
    espera_inicial*2, espera_inicial*4, ...), tentando de novo somente para 'excecoes'
    informadas - erros de negocio/validacao devem ser deixados de fora e propagar direto
    na primeira tentativa. Usado so pra falha transitoria de rede (timeout, conexao
    recusada/perdida), nunca pra erro de resposta HTTP (SapError etc), onde retry poderia
    duplicar um envio que na verdade ja foi recebido pelo servidor."""
    espera = espera_inicial
    for tentativa in range(1, tentativas + 1):
        try:
            return func(*args, **kwargs)
        except excecoes as exc:
            if tentativa == tentativas:
                raise
            logger.warning("tentativa %d/%d falhou (%s: %s) - nova tentativa em %.1fs",
                            tentativa, tentativas, type(exc).__name__, exc, espera)
            time.sleep(espera)
            espera *= 2
