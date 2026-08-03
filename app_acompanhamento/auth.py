import os
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

_security = HTTPBasic()


def exigir_login(credenciais: HTTPBasicCredentials = Depends(_security)) -> str:
    """Dependency global (ver main.py) - protege toda a API/painel com usuario e senha
    unicos (APP_AUTH_USER/APP_AUTH_PASSWORD no .env). Comparacao em tempo constante
    (secrets.compare_digest) pra nao vazar a senha por timing attack."""
    usuario_esperado = os.environ.get("APP_AUTH_USER")
    senha_esperada = os.environ.get("APP_AUTH_PASSWORD")
    if not usuario_esperado or not senha_esperada:
        raise HTTPException(500, "APP_AUTH_USER/APP_AUTH_PASSWORD nao configurados no .env")

    usuario_ok = secrets.compare_digest(credenciais.username, usuario_esperado)
    senha_ok = secrets.compare_digest(credenciais.password, senha_esperada)
    if not (usuario_ok and senha_ok):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Usuario ou senha invalidos",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credenciais.username
