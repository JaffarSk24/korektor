#!/bin/bash
set -e
cd /opt/korektor

echo "[PROD DEPLOY] Restarting prod containers..."
docker-compose down
docker-compose up -d --build

docker ps --format "table {{.Names}}\t{{.Ports}}\t{{.Status}}"