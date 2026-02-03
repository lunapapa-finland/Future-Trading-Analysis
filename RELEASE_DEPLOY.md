# Release and Deploy Guide

## 1) Push code/commits to GitHub
- Commands:
  - Stage & commit: `git add . && git commit -m "<message>"`
  - Push branch (e.g., master): `git push origin master`
- What CI does on push/PR to main/master:
  - Runs Python tests (`pytest -q`).
  - Builds the Next.js frontend (`npm ci && npm run build` in `web`).
  - Does **not** build/publish Docker images (kept for tag builds only).

## 2) Push a tag (release build)
- Commands:
  - Create tag: `git tag -a v1.0.1 -m "Release v1.0.1"`
  - Push tag: `git push origin v1.0.1`
- What CI does on tag push:
  - Runs tests and frontend build.
  - Builds and pushes multi-arch Docker images to GHCR:
    - `ghcr.io/<owner>/<repo>:v1.0.1`
    - `ghcr.io/<owner>/<repo>:latest`
    - `ghcr.io/<owner>/<repo>:<commit-sha>`

## 3) Deploy on Raspberry Pi (using GHCR image)
- Prereqs:
  - Access to GHCR image. If private, log in: `echo $GHCR_PAT | docker login ghcr.io -u <github-username> --password-stdin` (PAT needs `read:packages`).
  - Have `docker-compose.yml` and `docker-compose.rpi.yml` on the Pi, plus required env file (e.g., `src/dashboard/config/credentials.env` or equivalent path) and host data/log folders:
    - data/future, data/performance, data/temp_performance, data/portfolio, log
- Commands (from the compose directory on the Pi):
  - Pull images: `docker compose -f docker-compose.yml -f docker-compose.rpi.yml pull`
  - Start/upgrade: `docker compose -f docker-compose.yml -f docker-compose.rpi.yml up -d`
- Notes:
  - `docker-compose.rpi.yml` overrides the image to the prebuilt tag. Set it to a specific release (e.g., `v1.0.1`) for stability, or to `latest` to auto-track new builds.
  - No local build on the Pi; images are pulled from GHCR.
