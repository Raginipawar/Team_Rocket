# ─────────────────────────────────────────────────────────────────────────────
# GoldenHour — Project Makefile (Team_Rocket root)
# Assumes: docker compose uses infra/docker-compose.yml as the compose file.
# Run all targets from the repo root.
# ─────────────────────────────────────────────────────────────────────────────

COMPOSE       := docker compose -f infra/docker-compose.yml
CORE_SVC      := core
WORKER_SVC    := worker
ML_SVC        := ml
ALEMBIC       := $(COMPOSE) exec $(CORE_SVC) alembic
PYTEST_CORE   := $(COMPOSE) exec $(CORE_SVC) pytest
PYTEST_ML     := $(COMPOSE) exec $(ML_SVC)  pytest

.PHONY: up down restart logs \
        migrate seed reset \
        test test-concurrency test-scenarios test-invariants test-unit test-ml \
        lint format \
        osrm-pull model-pull \
        hooks

# ── Docker lifecycle ──────────────────────────────────────────────────────────

## up: Start all services in detached mode and wait for health checks.
up:
	$(COMPOSE) up -d --build
	@echo "Waiting for core to be healthy..."
	@$(COMPOSE) exec $(CORE_SVC) python -c "import asyncio; asyncio.run(__import__('asyncio').sleep(2))" 2>/dev/null || true

## down: Stop and remove containers (keeps volumes).
down:
	$(COMPOSE) down

## down-v: Stop containers AND remove volumes (full reset of DB/Redis data).
down-v:
	$(COMPOSE) down -v

## restart: Rebuild and restart all services.
restart: down up

## logs: Tail all service logs (Ctrl-C to stop).
logs:
	$(COMPOSE) logs -f

## logs-core: Tail core + worker logs only.
logs-core:
	$(COMPOSE) logs -f $(CORE_SVC) $(WORKER_SVC)

## logs-ml: Tail ml service logs.
logs-ml:
	$(COMPOSE) logs -f $(ML_SVC)

## ps: Show running containers and their health.
ps:
	$(COMPOSE) ps

# ── Database ──────────────────────────────────────────────────────────────────

## migrate: Apply all pending Alembic migrations.
migrate:
	$(ALEMBIC) upgrade head

## migrate-down: Roll back the last Alembic migration.
migrate-down:
	$(ALEMBIC) downgrade -1

## migrate-history: Show Alembic migration history.
migrate-history:
	$(ALEMBIC) history --verbose

## seed: Populate the database with Pune demo-area fixtures
##       (8 hospitals, 15 ambulances, rooms, resources, staff, landmarks, users).
seed:
	$(COMPOSE) exec $(CORE_SVC) python -m data.seed.seed

## reset: Wipe sim state (ambulances → offline, emergencies → closed,
##        reservations released) and re-seed. Uses the ops reset endpoint
##        so the same domain functions run as in production.
reset:
	$(COMPOSE) exec $(CORE_SVC) python -m app.sim.ops_reset

# ── Testing ───────────────────────────────────────────────────────────────────

## test: Run ALL tests (unit + concurrency + scenario + invariants + ML).
test:
	$(PYTEST_CORE) services/core/tests services/ml/training/mci \
	    -v --tb=short -p no:warnings
	$(PYTEST_ML)   services/ml/tests \
	    -v --tb=short -p no:warnings

## test-unit: Fast unit tests only (FSMs, scoring utilities, parsers).
test-unit:
	$(PYTEST_CORE) services/core/tests/unit \
	    -v --tb=short -p no:warnings

## test-concurrency: T1–T3, T8, T9 via asyncio.gather + testcontainers Postgres.
##   Verifies double-booking prevention, simultaneous accepts, idempotency.
test-concurrency:
	$(PYTEST_CORE) services/core/tests/concurrency \
	    -v --tb=long --timeout=60

## test-scenarios: Every §14 row scenario test in headless sim mode.
test-scenarios:
	$(PYTEST_CORE) services/core/tests/scenarios \
	    -v --tb=long --timeout=120

## test-invariants: Five DB invariants (§14 invariant checker).
test-invariants:
	$(PYTEST_CORE) services/core/tests/invariants.py \
	    -v --tb=short

## test-ml: ML model unit tests and MCI solver tests.
test-ml:
	$(PYTEST_ML) services/ml/training/mci \
	    -v --tb=short

## test-contracts: Schemathesis contract tests against core + ml OpenAPI specs.
test-contracts:
	$(COMPOSE) exec $(CORE_SVC) \
	    schemathesis run packages/contracts/openapi.core.yaml \
	        --base-url=http://localhost:8000 --checks all --max-examples 25
	$(COMPOSE) exec $(ML_SVC) \
	    schemathesis run packages/contracts/openapi.ml.yaml \
	        --base-url=http://localhost:8001 --checks all --max-examples 25

# ── Code quality ──────────────────────────────────────────────────────────────

## lint: Run ruff + mypy on all Python services.
lint:
	$(COMPOSE) exec $(CORE_SVC) ruff check services/ && \
	$(COMPOSE) exec $(CORE_SVC) mypy services/ --ignore-missing-imports

## lint-fix: Auto-fix lint issues where possible.
lint-fix:
	$(COMPOSE) exec $(CORE_SVC) ruff check services/ --fix

## format: Auto-format with ruff formatter.
format:
	$(COMPOSE) exec $(CORE_SVC) ruff format services/

# ── OSRM data preparation ─────────────────────────────────────────────────────

## osrm-pull: Download and prepare the Pune OSM/OSRM graph (run once).
##   Requires: osmosis, docker. Expects the output in infra/osrm/.
osrm-pull:
	bash infra/osrm/prepare_pune.sh

# ── LLM model pulling ─────────────────────────────────────────────────────────

## model-pull: Pull the Qwen2.5-7B-Instruct model into the Ollama container.
##   Run after 'make up' (Ollama must be healthy).
model-pull:
	$(COMPOSE) exec ollama ollama pull qwen2.5:7b-instruct

# ── git hooks ─────────────────────────────────────────────────────────────────

## hooks: Install pre-commit hooks (runs lint before every commit).
hooks:
	pre-commit install

# ── Help ─────────────────────────────────────────────────────────────────────

help:
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## //' | column -t -s ':'

.DEFAULT_GOAL := help
