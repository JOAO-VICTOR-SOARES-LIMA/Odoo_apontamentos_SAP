CREATE TABLE IF NOT EXISTS import_execucao (
    id               SERIAL PRIMARY KEY,
    iniciado_em      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finalizado_em    TIMESTAMPTZ,
    ambiente         TEXT NOT NULL,              -- test | prod
    arquivo_origem   TEXT NOT NULL,
    dry_run          BOOLEAN NOT NULL,
    total_linhas          INT NOT NULL DEFAULT 0,
    total_enviadas        INT NOT NULL DEFAULT 0,
    total_ja_existentes   INT NOT NULL DEFAULT 0,
    total_puladas         INT NOT NULL DEFAULT 0,
    total_erros           INT NOT NULL DEFAULT 0,
    status           TEXT NOT NULL DEFAULT 'em_andamento',  -- em_andamento | concluido | falhou
    -- origem: excel_manual (tela atual) | odoo_manual (botao "rodar agora") | odoo_automatico (2h)
    origem           TEXT NOT NULL DEFAULT 'excel_manual'
);

CREATE TABLE IF NOT EXISTS import_linha (
    id               SERIAL PRIMARY KEY,
    execucao_id      INT NOT NULL REFERENCES import_execucao(id),
    linha_excel      INT NOT NULL,
    colaborador      TEXT,
    data             DATE,
    projeto          TEXT,
    idsap            TEXT,
    tarefa           TEXT,
    descricao        TEXT,
    horas            NUMERIC(6,2),
    intervalo        TEXT,
    start_time       TEXT,
    end_time         TEXT,
    break_time       TEXT,
    employee_id_sap  INT,
    -- status: pendente_dry_run | enviado | ja_existe_sap | pulado_zero_horas |
    --         erro_horario_invalido | erro_dados_ausentes | erro_envio
    status           TEXT NOT NULL,
    motivo           TEXT,
    sap_response     JSONB,
    sap_request      JSONB,
    criado_em        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_import_linha_execucao ON import_linha(execucao_id);
CREATE INDEX IF NOT EXISTS idx_import_linha_status ON import_linha(status);
CREATE INDEX IF NOT EXISTS idx_import_linha_colab_data ON import_linha(colaborador, data);

-- Log de aplicacao (substitui os antigos logs em arquivo/print) - alimentado pelo
-- PostgresLogHandler (src/log_handler.py), configurado via src/logging_setup.py tanto
-- na app FastAPI quanto no script agendado (scripts/run_import_odoo_automatico.py).
CREATE TABLE IF NOT EXISTS app_log (
    id           BIGSERIAL PRIMARY KEY,
    criado_em    TIMESTAMPTZ NOT NULL DEFAULT now(),
    nivel        TEXT NOT NULL,   -- INFO | WARNING | ERROR | ...
    logger       TEXT NOT NULL,   -- nome do logger (modulo de origem)
    mensagem     TEXT NOT NULL,
    execucao_id  INT REFERENCES import_execucao(id),
    detalhes     TEXT             -- traceback, quando o registro vier de uma excecao
);

CREATE INDEX IF NOT EXISTS idx_app_log_criado_em ON app_log(criado_em);
CREATE INDEX IF NOT EXISTS idx_app_log_nivel ON app_log(nivel);
CREATE INDEX IF NOT EXISTS idx_app_log_execucao ON app_log(execucao_id);

-- Flag manual/automatico do envio diario Odoo -> SAP (linha unica, id sempre 1).
-- O agendamento em si e uma Tarefa Agendada do Windows que roda todo dia as 2h;
-- essa tabela so diz se o script deve realmente enviar (automatico) ou so logar e sair (manual).
CREATE TABLE IF NOT EXISTS automacao_config (
    id             SMALLINT PRIMARY KEY DEFAULT 1,
    modo           TEXT NOT NULL DEFAULT 'manual' CHECK (modo IN ('manual', 'automatico')),
    atualizado_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT automacao_config_singleton CHECK (id = 1)
);
INSERT INTO automacao_config (id, modo) VALUES (1, 'manual') ON CONFLICT (id) DO NOTHING;
