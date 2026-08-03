import requests

from src.config import SapEnvConfig
from src.retry import com_retry

# So retry em falha de rede antes de qualquer resposta chegar (timeout/conexao recusada) -
# nunca em HTTPError ou resposta de negocio, onde o servidor pode ja ter recebido/processado
# o POST e um retry duplicaria o envio do apontamento.
_ERROS_TRANSITORIOS = (requests.exceptions.ConnectionError, requests.exceptions.Timeout)


class SapError(Exception):
    def __init__(self, message: str, response_body=None):
        super().__init__(message)
        self.response_body = response_body


class SapClient:
    """Cliente minimo para o SAP B1 Service Layer, com relogin automatico em sessao expirada."""

    def __init__(self, env: SapEnvConfig):
        self.env = env
        self.session = requests.Session()
        self.session.verify = True
        self._login()

    def _login(self):
        resp = com_retry(
            self.session.post, f"{self.env.base_url}/Login",
            json={
                "CompanyDB": self.env.company_db,
                "UserName": self.env.username,
                "Password": self.env.password,
            },
            timeout=30,
            excecoes=_ERROS_TRANSITORIOS,
        )
        resp.raise_for_status()

    def _request(self, method: str, path: str, retried: bool = False, **kwargs) -> requests.Response:
        # Sem retry aqui de proposito: isso cobre o POST do timesheet, e um timeout pode
        # acontecer DEPOIS do SAP ja ter recebido/criado o lancamento (so a resposta que se
        # perdeu) - reenviar as cegas arriscaria duplicar horas lancadas. Falha de rede aqui
        # vira 'erro_envio' (ver core.py::enviar_linha) pra revisao manual, nao retry automatico.
        resp = self.session.request(method, f"{self.env.base_url}{path}", timeout=60, **kwargs)
        if resp.status_code == 401 and not retried:
            self._login()
            return self._request(method, path, retried=True, **kwargs)
        return resp

    def post_timesheet(self, payload: dict) -> dict:
        resp = self._request("POST", "/ProjectManagementTimeSheet", json=payload)
        if not resp.ok:
            raise SapError(f"Falha ao enviar apontamento: HTTP {resp.status_code}", self._safe_json(resp))
        return self._safe_json(resp)

    @staticmethod
    def _safe_json(resp: requests.Response):
        try:
            return resp.json()
        except ValueError:
            return {"raw": resp.text}
