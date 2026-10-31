.PHONY: setup lint test up

setup:
	python -m pip install --upgrade pip
	python -m pip install -e .
	python -m pip install -r requirements.txt
	python -m pip install pre-commit black ruff pytest
	pre-commit install

lint:
	ruff check .
	black --check .

test:
	pytest tests/

up:
	docker compose up -d