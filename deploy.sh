#!/bin/bash
set -e

cd /home/sywi/dagster-platform

echo "[1/4] Pulling latest code..."
git pull origin main

echo "[2/4] Generating configs..."
python3 generate_platform.py

echo "[3/4] Starting/updating containers..."
docker compose -f docker-compose.prod.yaml up --build -d --remove-orphans

echo "[4/4] Reloading webserver..."
docker compose -f docker-compose.prod.yaml restart dagster_webserver || true

echo "Deployment complete!"
