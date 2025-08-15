FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 TZ=Europe/Helsinki
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential tzdata cron \
 && ln -fs /usr/share/zoneinfo/$TZ /etc/localtime && dpkg-reconfigure -f noninteractive tzdata \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

COPY . /app
# install package 
RUN pip install -e .
RUN mkdir -p /app/log /app/data

COPY docker/cron/trading /etc/cron.d/trading
RUN chmod 0644 /etc/cron.d/trading

EXPOSE 8050
ENV HOST=0.0.0.0 PORT=8050 WORKERS=2 TIMEOUT=120 LOG_DIR=/app/log
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8050/health').read()" || exit 1
CMD ["gunicorn","--bind","0.0.0.0:8050","--workers","2","--timeout","120","wsgi:server"]
