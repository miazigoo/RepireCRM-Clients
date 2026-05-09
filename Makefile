SHELL := /bin/bash
COMPOSE ?= docker compose
BACKEND_VENV := backend/.venv
FRONTEND_DIR := frontend

.PHONY: help install backend-install frontend-install build test lint pre-commit-run backend-tests frontend-tests frontend-dev up down restart logs migrate revision shell worker generate-secrets clean

help:
	@printf "Repair CRM Client commands:\n"
	@printf "  make install          Install local frontend/backend dependencies\n"
	@printf "  make build            Build frontend\n"
	@printf "  make lint             Black + flake8 + mypy (backend)\n"
	@printf "  make pre-commit-run   Run all pre-commit hooks on the repo\n"
	@printf "  make test             Run backend and frontend tests\n"
	@printf "  make frontend-dev     Start local Angular dev server\n"
	@printf "  make up               Start Postgres, backend, worker and nginx frontend\n"
	@printf "  make down             Stop containers\n"
	@printf "  make logs             Follow container logs\n"
	@printf "  make migrate          Run Alembic migrations in backend container\n"
	@printf "  make revision MSG=... Create Alembic revision locally\n"
	@printf "  make generate-secrets Print production secret values\n"

install: backend-install
	$(MAKE) frontend-install

frontend-install:
	cd $(FRONTEND_DIR) && npm ci

backend-install:
	python3 -m venv $(BACKEND_VENV)
	$(BACKEND_VENV)/bin/pip install -r backend/requirements.txt -r requirements-dev.txt

build:
	cd $(FRONTEND_DIR) && npm run build

lint:
	$(BACKEND_VENV)/bin/black --check backend
	$(BACKEND_VENV)/bin/flake8 backend/app backend/tests backend/alembic
	$(BACKEND_VENV)/bin/mypy --config-file pyproject.toml

pre-commit-run:
	$(BACKEND_VENV)/bin/pre-commit run --all-files

backend-tests:
	$(BACKEND_VENV)/bin/pytest backend/tests

frontend-tests:
	cd $(FRONTEND_DIR) && npm run test:ci

test: backend-tests frontend-tests

frontend-dev:
	cd $(FRONTEND_DIR) && npm run start:dev

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

restart: down up

logs:
	$(COMPOSE) logs -f

migrate:
	$(COMPOSE) exec backend alembic -c /app/backend/alembic.ini upgrade head

revision:
	$(BACKEND_VENV)/bin/alembic -c backend/alembic.ini revision --autogenerate -m "$${MSG:-manual migration}"

shell:
	$(COMPOSE) exec backend python

worker:
	$(BACKEND_VENV)/bin/python -m app.worker

generate-secrets:
	python3 scripts/generate_secrets.py

clean:
	$(COMPOSE) down -v
	rm -rf frontend/dist frontend/.angular .pytest_cache backend/.pytest_cache
