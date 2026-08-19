.PHONY: install dev test lint format migration upgrade downgrade seed

install:
	python -m pip install -e ".[dev]"

dev:
	uvicorn silly_teamwork.main:app --reload

test:
	pytest

lint:
	ruff check .
	mypy src

format:
	ruff check --fix .
	ruff format .

migration:
	alembic revision --autogenerate -m "$(m)"

upgrade:
	alembic upgrade head

downgrade:
	alembic downgrade -1

seed:
	python -m silly_teamwork.cli.seed
