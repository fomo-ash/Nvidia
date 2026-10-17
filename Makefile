.DEFAULT_GOAL := help
.PHONY: help setup dev up down logs migrate seed test lint clean reset-data
help:
	@echo "Targets: setup dev up down logs migrate seed test lint clean reset-data"
setup:
	@docker compose pull
dev:
	@docker compose up --build
up:
	@docker compose up --build -d
down:
	@docker compose down
logs:
	@docker compose logs -f --tail=200
migrate:
	@docker compose run --rm api alembic upgrade head
seed:
	@docker compose run --rm api python -m app.seed
test:
	@docker compose run --rm api pytest && docker compose run --rm web pnpm test --run
lint:
	@docker compose run --rm api ruff check . && docker compose run --rm web pnpm lint && docker compose run --rm web pnpm typecheck
clean:
	@docker compose down
	@echo "Stopped containers and networks. Persistent database volume was preserved."
reset-data:
	@docker compose down -v
	@echo "Removed Docker volumes, including local PostgreSQL data."
