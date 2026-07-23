import requests

from src.config import SapEnvConfig


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
        resp = self.session.post(
            f"{self.env.base_url}/Login",
            json={
                "CompanyDB": self.env.company_db,
                "UserName": self.env.username,
                "Password": self.env.password,
            },
            timeout=30,
        )
        resp.raise_for_status()

    def _request(self, method: str, path: str, retried: bool = False, **kwargs) -> requests.Response:
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
