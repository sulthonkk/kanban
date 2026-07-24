#!/usr/bin/env bash
# Starts the Kanban backend services via Docker.
set -euo pipefail
docker compose up -d --build

for _ in $(seq 1 15); do
  if curl -fsS http://localhost:8000/api/ping >/dev/null 2>&1; then
    echo "Backend is up at http://localhost:8000"
    exit 0
  fi
  sleep 1
done
echo "Backend did not become healthy in time." >&2
exit 1