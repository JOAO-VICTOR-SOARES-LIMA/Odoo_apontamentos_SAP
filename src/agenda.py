def _hhmm_int_para_horas(valor) -> float:
    if valor is None:
        return 0.0
    valor = int(valor)
    horas, minutos = divmod(valor, 100)
    return horas + minutos / 60


def horas_decimais_para_hhmm(horas_decimais: float) -> str:
    total_minutos = round(horas_decimais * 60)
    h, m = divmod(total_minutos, 60)
    return f"{h:02d}:{m:02d}"


def hhmm_para_horas_decimais(texto: str | None) -> float:
    if not texto:
        return 0.0
    h, m = str(texto).split(":")
    return int(h) + int(m) / 60


class AgendaHorarios:
    """Calcula StartTime/EndTime de um novo lancamento encadeando a partir do ultimo
    EndTime REAL ja registrado no SAP (lido do HANA) para o mesmo funcionario/dia,
    comecando as 08:00 se nao houver nenhum (regra de negocio confirmada).

    Importante: o encadeamento e por funcionario+dia, NAO por funcionario+dia+projeto.
    Uma pessoa nao pode ter dois lancamentos em horarios sobrepostos no mesmo dia mesmo que
    sejam em projetos diferentes - se a chave incluisse o projeto, cada projeto ganharia sua
    propria contagem a partir das 08:00 e o SAP rejeitaria por sobreposicao real de horario
    (erro nativo 'Cannot proceed; time periods overlap').

    Ao contrario do Excel do n8n (que congelava esses horarios no momento da exportacao),
    este calculo e feito na hora do envio e atualizado a cada linha enviada nesta mesma
    execucao, refletindo o estado real do SAP."""

    INICIO_PADRAO_HORAS = 8.0
    LIMITE_DIA_HORAS = 24.0

    def __init__(self, linhas_hana: list[dict]):
        self._ultimo_fim = {}
        for linha in linhas_hana:
            data = linha["data"]
            data_str = data.date().isoformat() if hasattr(data, "date") else str(data)[:10]
            fim = _hhmm_int_para_horas(linha.get("end_time"))
            chave = (linha["user_id"], data_str)
            atual = self._ultimo_fim.get(chave)
            if atual is None or fim > atual:
                self._ultimo_fim[chave] = fim

    def alocar(self, employee_id_sap: int, data: str, projeto: str, horas: float,
               intervalo_horas: float = 0.0) -> tuple[str, str, bool, float | None]:
        """Retorna (start_time, end_time, valido, horas_ja_lancadas). valido=False se ultrapassar
        24:00 no mesmo dia. horas_ja_lancadas e None se o lancamento comecaria as 08:00 (nao ha nada
        anterior nesse funcionario/dia, em nenhum projeto); caso contrario, e quantas horas ja estao
        ocupadas antes deste lancamento (util pra explicar o motivo do bloqueio). O parametro
        'projeto' e mantido na assinatura por compatibilidade mas nao participa mais da chave -
        ver docstring da classe.

        'intervalo_horas' (Break) entra na largura da janela StartTime->EndTime - o SAP calcula
        Effective Time = (EndTime - StartTime) - Break e rejeita (erro nativo 234008003) se isso
        for negativo, o que aconteceria se a janela so cobrisse as horas trabalhadas sem folga
        pro break."""
        chave = (employee_id_sap, data)
        ja_tinha_lancamento = chave in self._ultimo_fim
        inicio_horas = self._ultimo_fim.get(chave, self.INICIO_PADRAO_HORAS)
        fim_horas = inicio_horas + horas + intervalo_horas
        horas_ja_lancadas = (inicio_horas - self.INICIO_PADRAO_HORAS) if ja_tinha_lancamento else None

        if fim_horas >= self.LIMITE_DIA_HORAS:
            return horas_decimais_para_hhmm(inicio_horas), horas_decimais_para_hhmm(fim_horas), False, horas_ja_lancadas

        self._ultimo_fim[chave] = fim_horas
        return horas_decimais_para_hhmm(inicio_horas), horas_decimais_para_hhmm(fim_horas), True, horas_ja_lancadas

    def registrar_fixo(self, employee_id_sap: int, data: str, hora_fim_horas: float) -> None:
        """Registra um horario de fim REAL (nao calculado), vindo de um lancamento com horario
        proprio (ex: local='Campo', onde o colaborador preenche inicio/fim de verdade em vez de
        depender do encadeamento). Nao aloca nada - so atualiza o 'ultimo fim' desse
        funcionario/dia, pra que um proximo lancamento encadeado (nao-Campo) no mesmo dia comece
        depois desse horario real, em vez de sobrepor. Mesma regra 'mantem o maior' do __init__."""
        chave = (employee_id_sap, data)
        atual = self._ultimo_fim.get(chave)
        if atual is None or hora_fim_horas > atual:
            self._ultimo_fim[chave] = hora_fim_horas
