.PHONY: up down migrate revision test test-unit test-integration test-e2e lint seed demo

up:
	docker compose up -d

down:
	docker compose down

migrate:
	alembic upgrade head

revision:
	alembic revision --autogenerate -m "$(MSG)"

test:
	pytest tests/ -v

test-unit:
	pytest tests/unit/ -v $(ARGS)

test-integration:
	pytest tests/integration/ -v $(ARGS)

test-e2e:
	pytest tests/e2e/ -v $(ARGS)

lint:
	ruff check app/ tests/ scripts/ && ruff format --check app/ tests/ scripts/

seed:
	python -m scripts.seed

demo:
	python -m scripts.demo
