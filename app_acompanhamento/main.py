import os

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.gzip import GZipMiddleware

from src.logging_setup import configurar_logging

configurar_logging(os.environ.get("POSTGRES_DSN", ""))

from app_acompanhamento.api.automacao import router as automacao_router  # noqa: E402
from app_acompanhamento.api.historico import router as historico_router  # noqa: E402
from app_acompanhamento.auth import exigir_login  # noqa: E402

# dependencies=[Depends(exigir_login)] no nivel da app protege toda rota declarada via
# @app.get/include_router (HTTP Basic - ver app_acompanhamento/auth.py). Nao cobre o mount
# de /static (StaticFiles e um sub-app ASGI separado, fora do sistema de dependencies do
# FastAPI) - inofensivo, sao so CSS/JS estaticos, inuteis sem a pagina/API autenticada.
app = FastAPI(title="ApontaSAP", version="1.0.0", dependencies=[Depends(exigir_login)])

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.mount("/static", StaticFiles(directory="app_acompanhamento/static"), name="static")
templates = Jinja2Templates(directory="app_acompanhamento/templates")

app.include_router(historico_router, prefix="/api")
app.include_router(automacao_router, prefix="/api")


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
