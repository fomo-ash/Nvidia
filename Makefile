.DEFAULT_GOAL := help
.PHONY: help setup dev up down logs migrate seed test lint contracts clean reset-data
help:
	@echo "Targets: setup dev up down logs migrate seed test lint contracts clean reset-data"
setup:
	@docker compose pull
dev:
	@docker compose up --build
up:
	@docker compose up --build --wait --wait-timeout 180
down:
	@docker compose down
logs:
	@docker compose logs -f --tail=200
migrate:
	@docker compose run --rm api alembic upgrade head
seed:
	@docker compose run --rm api python -m app.seed
test:
	@docker compose -f compose.checks.yaml run --build --rm api-checks
	@docker compose -f compose.checks.yaml run --build --rm api-postgres-checks
	@docker compose -f compose.checks.yaml run --build --rm web-checks
lint:
	@docker compose -f compose.checks.yaml run --build --rm api-checks ruff check app tests scripts alembic
	@docker compose -f compose.checks.yaml run --build --rm api-checks ruff format --check app tests scripts alembic
	@docker compose -f compose.checks.yaml run --build --rm web-checks pnpm lint
	@docker compose -f compose.checks.yaml run --build --rm web-checks pnpm typecheck
contracts:
	@docker compose -f compose.checks.yaml run --build --rm api-checks python scripts/export_openapi.py --check
	@docker compose -f compose.checks.yaml run --build --rm web-checks pnpm contracts:check
clean:
	@docker compose down
	@echo "Stopped containers and networks. Persistent database volume was preserved."
reset-data:
	@docker compose down -v
	@echo "Removed Docker volumes, including local PostgreSQL data."
