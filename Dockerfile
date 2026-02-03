FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 TZ=Europe/Helsinki
WORKDIR /app

# Runtime/public envs needed at build time (Next.js inlines NEXT_PUBLIC_* during build)
ENV HOST=0.0.0.0 PORT=8050 API_PORT=5000 WORKERS=2 TIMEOUT=120 LOG_DIR=/app/log \
    NEXT_PUBLIC_API_BASE_URL=/api \
    FRONTEND_ORIGIN=http://localhost:8050

# system deps + Node for Next.js build
RUN apt-get update && apt-get install -y --no-install-recommends curl build-essential tzdata cron ca-certificates gnupg \
 && ln -fs /usr/share/zoneinfo/$TZ /etc/localtime && dpkg-reconfigure -f noninteractive tzdata \
 && mkdir -p /etc/apt/keyrings \
 && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
 && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" > /etc/apt/sources.list.d/nodesource.list \
 && apt-get update && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

COPY . /app
# install package 
RUN pip install -e .
RUN mkdir -p /app/log /app/data

# build frontend
RUN cd /app/web && npm ci && npm run build

COPY docker/cron/trading /etc/cron.d/trading
RUN chmod 0644 /etc/cron.d/trading

EXPOSE 8050
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health').read()" || exit 1
CMD ["bash","-c","gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 wsgi:server & npm run start --prefix web -- --hostname 0.0.0.0 --port 8050"]
