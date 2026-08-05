FROM python:3.13-slim

ENV TZ=America/Sao_Paulo

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends cron tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY docker/crontab /etc/cron.d/apontasap
RUN chmod 0644 /etc/cron.d/apontasap

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8010

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "run_acompanhamento.py"]
