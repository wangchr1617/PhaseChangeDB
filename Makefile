.PHONY: install dev-api dev-web test lint build up down

install:
	uv sync
	corepack pnpm install --dir frontend

dev-api:
	uv run uvicorn app.main:app --reload

dev-web:
	corepack pnpm --dir frontend dev

test:
	uv run pytest

lint:
	uv run ruff check app tests
	corepack pnpm --dir frontend lint
	corepack pnpm --dir frontend typecheck

build:
	corepack pnpm --dir frontend build

up:
	docker compose up --build

down:
	docker compose down
