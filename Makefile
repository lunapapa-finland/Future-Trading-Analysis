.PHONY: install run run-dev run-dev-data run-dev-performance scan \
        docker-up docker-down docker-logs docker-rebuild docker-ps \
        docker-job-trading docker-job-perf clean clean-data-artifacts help

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

## Run trading-data acquisition NOW (direct call) in dev
run-dev-data:
	$(PY) src/dashboard/utils/data_acquisition.py

## Process temp performance CSVs if any (idempotent) in dev
run-dev-performance:
	$(PY) src/dashboard/utils/performance_acquisition.py

## Full dry scan: syntax, security, tests (+optional frontend checks)
scan:
	@echo "==> Python compile check"
	PYTHONPATH=src $(PY) -m compileall -q src test jobs wsgi.py test_environment.py
	@echo "==> Security scan (bandit: src + jobs)"
	PYTHONPATH=src $(PY) -m bandit -q -r src jobs
	@echo "==> Backend tests"
	PYTHONPATH=src $(PY) -m pytest -q
	@echo "==> Frontend checks (optional)"
	@if command -v npm >/dev/null 2>&1; then \
		npm --prefix web run -s typecheck; \
		npm --prefix web run -s lint; \
	else \
		echo "npm not found; skipping frontend checks"; \
	fi

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
	find . -type f -name ".DS_Store" -delete
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache .coverage *.egg-info

## Remove stale macOS artifacts from runtime data folders
clean-data-artifacts:
	find data -type f -name ".DS_Store" -delete

## Show available commands
help:
	@echo "Targets:"
	@echo "  install             - pip install requirements + editable package"
	@echo "  run                 - run with gunicorn on $(HOST):$(PORT)"
	@echo "  run-dev             - run Dash dev server"
	@echo "  run-dev-data        - run data acquisition now without Docker locally"
	@echo "  run-dev-performance - process temp performance CSVs if present without Docker locally"
	@echo "  scan                - compile + bandit + pytest (+frontend checks if npm exists)"
	@echo "  docker-up           - docker compose up -d"
	@echo "  docker-down         - docker compose down"
	@echo "  docker-rebuild      - rebuild image(s) and restart"
	@echo "  docker-logs         - tail compose logs"
	@echo "  docker-ps           - list containers"
	@echo "  docker-job-trading  - run the trading job inside jobs container"
	@echo "  docker-job-perf     - run the performance job inside jobs container"
	@echo "  clean               - remove caches/build artifacts"
	@echo "  clean-data-artifacts - remove stale .DS_Store files under data/"
	
.DEFAULT_GOAL := help
