# Korektor — Slovak Proofreading Editor

A production-grade Slovak language proofreading and correction web application.

## Overview
Korektor is a web editor that provides Slovak grammar, spelling, casing and punctuation suggestions through a FastAPI REST service and a minimal single-page frontend. The project is containerized with Docker and served via Nginx with HTTPS.

## Achievements
- Production and Development environments running concurrently with HTTPS.
- Backend: FastAPI (Uvicorn) exposing /api/check returning JSON corrections.
- Frontend: Static single-page UI for editing and applying suggestions.
- Language tooling: LanguageTool integration plus additional model-based checks.
- Deployment automation: Shell scripts to deploy, reset dev from prod, and promote dev → prod.
- Operational stability: swap enabled; host-level cache recommended for large models to avoid repeated downloads.

## Architecture (short)
- Nginx reverse proxy
  - /api/* → backend
  - / → frontend static
- Docker Compose services
  - slovak-editor-backend (FastAPI)
  - slovak-editor-frontend (nginx)
  - languagetool (Java)
- Recommended host cache for models: /opt/huggingface_cache

## How to use
- Start dev: `cd /opt/korektor-dev && ./deploy-dev.sh`
- Reset dev from prod: `reset-dev` (alias)
- Deploy prod: `cd /opt/korektor && ./deploy-prod.sh`

## Locations
- Backend: /opt/korektor/backend
- Frontend: /opt/korektor/frontend
- Deployment scripts: /opt/korektor/ and /opt/korektor-dev/

## Status
Both Dev and Prod environments are operational. API and UI respond over HTTPS.
