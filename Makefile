.PHONY: install run run-dev data data-gated performance \
        docker-up docker-down docker-logs docker-rebuild docker-ps \
        docker-job-trading docker-job-perf clean help

# -------- Config --------
PY        ?= python
GUNI      ?= gunicorn
HOST      ?= 127.0.0.1
PORT      ?= 8050
WORKERS   ?= 2
TIMEOUT   ?= 120
ENV_FILE ?= src/dashboard/config/credentials.env

# -------- Local (no Docker) --------

## Install deps locally (editable package)
install:
	$(PY) -m pip install -r requirements.txt
	$(PY) -m pip install -e .

## Run with Gunicorn (production-style locally)
run:
	@set -a; . $(ENV_FILE); set +a; \
	 gunicorn -b 127.0.0.1:8050 --workers 2 --timeout 120 wsgi:server

## Run with Dash's dev server (debug/reload)
run-dev:
	$(PY) src/dashboard/app.py

## Run trading-data acquisition NOW (direct call)
data:
	$(PY) src/dashboard/utils/data_acquisition.py

## Run trading-data job with daily gate/stamp logic (respects HOURS_DELAY)
data-gated:
	$(PY) jobs/run_trading_if_ready.py

## Process temp performance CSVs if any (idempotent)
performance:
	$(PY) jobs/run_perf_if_files.py

# -------- Docker/Compose helpers --------

## Start containers (dash + jobs)
docker-up:
	docker compose up -d

## Stop/Remove containers
docker-down:
	docker compose down

## Rebuild image(s) and restart
docker-rebuild:
	docker compose build --no-cache
	docker compose up -d

## Tail all logs
docker-logs:
	docker compose logs -f

## Show container status
docker-ps:
	docker compose ps

## Trigger trading job inside the jobs container (once, immediately)
docker-job-trading:
	docker exec trading_jobs python /app/jobs/run_trading_if_ready.py

## Trigger performance job inside the jobs container (once, immediately)
docker-job-perf:
	docker exec trading_jobs python /app/jobs/run_perf_if_files.py

# -------- Housekeeping --------

## Remove Python caches & build artifacts
clean:
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache .coverage *.egg-info

## Show available commands
help:
	@echo "Targets:"
	@echo "  install             - pip install requirements + editable package"
	@echo "  run                 - run with gunicorn on $(HOST):$(PORT)"
	@echo "  run-dev             - run Dash dev server"
	@echo "  data                - run data acquisition now"
	@echo "  data-gated          - run trading job (respects HOURS_DELAY & stamp)"
	@echo "  performance         - process temp performance CSVs if present"
	@echo "  docker-up           - docker compose up -d"
	@echo "  docker-down         - docker compose down"
	@echo "  docker-rebuild      - rebuild image(s) and restart"
	@echo "  docker-logs         - tail compose logs"
	@echo "  docker-ps           - list containers"
	@echo "  docker-job-trading  - run the trading job inside jobs container"
	@echo "  docker-job-perf     - run the performance job inside jobs container"
	@echo "  clean               - remove caches/build artifacts"
	
.DEFAULT_GOAL := help
