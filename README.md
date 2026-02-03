# Future Trading Dashboard

An interactive futures dashboard with a Flask API backend and a Next.js frontend. Data and logs stay on disk so containers can be restarted without loss. CI builds multi-arch Docker images (amd64/arm64) and publishes to GHCR on tags.

---

## What it does

- **Market data (daily):** Fetches and appends daily futures data (holiday-aware) from yfinance.
- **Performance data (on demand):** Drop CSVs into `data/temp_performance/`; they’re auto-processed into the performance pool every few minutes.
- **Dashboard:** Candles, stats, and behavioral insights for MES, MNQ, M2K, M6E, M6B, MBT, MET (extendable via config).
- **Login & health:** Basic login; `/health` endpoint.
- **Logging:** App logs in `log/app.log`; cron logs for background jobs.
- **CI/CD:** Tests and frontend build run on push/PR; Docker images build and push to GHCR on tag events.

---

## TODO

- Backtesting module (Backtrader) integration
- More modular abstractions
- Expose persistent configuration
- UI refinements

---


---

## Folders you’ll use

```
data/
  future/           # market CSVs per symbol
  performance/      # combined performance + daily performance files
  temp_performance/ # drop your raw performance CSVs here
log/                # app.log and job logs
```

*(These are mounted both locally and on the Server so files persist.)*

---

## Credentials (one file for local & Docker)

Create **`src/dashboard/config/credentials.env`** (don’t commit it):

```env
DASH_USER=yourusername
DASH_PASS=yourstrongpassword
# Generate once and paste (any long random string is fine):
# python -c "import secrets; print(secrets.token_urlsafe(32))"
SECRET_KEY=PASTE_GENERATED_SECRET_HERE
```

---

## Run locally (venv or conda)

```bash
python -m venv .venv  # or conda activate finance_env
. .venv/bin/activate

pip install -r requirements.txt
pip install -e .

mkdir -p data/{future,performance,temp_performance} log

# load creds into the shell for this session
set -a; . src/dashboard/config/credentials.env; set +a

gunicorn -b 127.0.0.1:5000 --workers 2 --timeout 120 wsgi:server
# open: http://127.0.0.1:8050 (Next.js) | API: http://127.0.0.1:5000 | health: http://127.0.0.1:5000/health
```

**Handy make targets (optional):**

```
make run          # gunicorn locally
make performance  # process temp_performance now
make data         # fetch market data now
```

---

## Run with Docker (local or server)

1) **Prepare folders** (local path or server path):

```bash
mkdir -p data/{future,performance,temp_performance,portfolio} log
# or use /srv/trading-dashboard/... on a server and chown accordingly
```

2) **Get the code & credentials:**

```bash
git clone <your repo> Future-Trading-Analysis
cd Future-Trading-Analysis
# copy src/dashboard/config/credentials.env into this path
```

3) **(Optional) copy existing CSVs:**

```bash
# rsync -avz data/performance/ <host>:/path/to/data/performance/
# rsync -avz data/future/      <host>:/path/to/data/future/
```

4) **Start (build locally):**

```bash
docker compose build
docker compose up -d
curl -s http://127.0.0.1:8050/health   # -> ok
```

5) **Deploy using prebuilt image on RPI/arm64 (no build on device):**

```bash
docker compose -f docker-compose.yml -f docker-compose.rpi.yml pull
docker compose -f docker-compose.yml -f docker-compose.rpi.yml up -d
```

> Set the image tag in docker-compose.rpi.yml (e.g., `v1.0.1` for stability or `latest` to track new builds). If the GHCR image is private, login first: `echo $GHCR_PAT | docker login ghcr.io -u <user> --password-stdin`.

> If you use a subdomain, point your reverse proxy to `http://127.0.0.1:8050/`. For HTTPS, you can add proxy-level basic auth if desired.

---

## Background jobs (automatic)

* **Market data:** runs once per day after a small delay (configured in compose).
* **Performance data:** checks every few minutes; if it finds CSVs in `data/temp_performance/`, it processes them and removes the originals.

You can still trigger them manually:

```bash
# inside Docker
docker exec trading_jobs python /app/jobs/run_trading_if_ready.py
docker exec trading_jobs python /app/jobs/run_perf_if_files.py
```

---

## Images (examples)

![Sample Candlestick Chart](img/sample1.png)
![Performance Metrics Dashboard](img/sample2.png)
![Trade Behavior Insights](img/sample3.png)
![Rolling Win Rate Visualization](img/sample4.png)


## License

This project is distributed under the [MIT License](LICENSE). See the LICENSE file for full terms.

