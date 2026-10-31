.PHONY: setup lint test up

setup:
	pip install -e .
	pip install pre-commit black ruff pytest
	pre-commit install

lint:
	ruff check .
	black --check .

test:
	pytest tests/

up:
	docker compose up -d