import re
from collections import defaultdict


def normalizar_projeto(valor) -> str:
    """Mesma regra usada no fluxo n8n: mantem so o codigo numerico inicial do projeto."""
    if valor is None:
        return ""
    texto = str(valor).strip()
    m = re.match(r"^[\d.]+", texto)
    if not m:
        return texto
    return m.group(0).rstrip(".")


def _hhmm_para_horas(valor) -> float:
    """Campos de hora no HANA (StartTime/EndTime/Break/EffectTm) vem como inteiro HHMM, ex: 1730 = 17:30."""
    if valor is None:
        return 0.0
    valor = int(valor)
    horas, minutos = divmod(valor, 100)
    return horas + minutos / 60


class SapIndex:
    """Indice dos lancamentos ja existentes no SAP (lido direto do HANA), para checagem
    de idempotencia com tolerancia de horas antes de qualquer POST via Service Layer."""

    def __init__(self, linhas_hana: list[dict], tolerancia_horas: float):
        self.tolerancia_horas = tolerancia_horas
        self._por_chave = defaultdict(list)

        for linha in linhas_hana:
            data = linha["data"]
            data_str = data.date().isoformat() if hasattr(data, "date") else str(data)[:10]
            projeto = normalizar_projeto(linha.get("fi_project"))
            idsap = str(linha["idsap"]) if linha.get("idsap") is not None else None
            horas = _hhmm_para_horas(linha.get("effect_tm"))
            chave = (linha["user_id"], idsap, projeto, data_str)
            self._por_chave[chave].append(horas)

    def ja_existe(self, employee_id_sap: int, idsap: str, projeto: str, data: str, horas: float) -> bool:
        chave = (employee_id_sap, idsap, normalizar_projeto(projeto), data)
        candidatos = self._por_chave.get(chave, [])
        return any(abs(horas_existentes - horas) <= self.tolerancia_horas for horas_existentes in candidatos)
