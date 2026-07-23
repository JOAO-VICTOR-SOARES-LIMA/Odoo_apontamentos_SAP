from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.gzip import GZipMiddleware

from app_acompanhamento.api.automacao import router as automacao_router
from app_acompanhamento.api.historico import router as historico_router

app = FastAPI(title="ApontaSAP", version="1.0.0")

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.mount("/static", StaticFiles(directory="app_acompanhamento/static"), name="static")
templates = Jinja2Templates(directory="app_acompanhamento/templates")

app.include_router(historico_router, prefix="/api")
app.include_router(automacao_router, prefix="/api")


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
