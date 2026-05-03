.PHONY: test lint typecheck

test: lint typecheck
	pytest

lint:
	ruff check ctpool/ tests/
	ruff format --check ctpool/ tests/

typecheck:
	mypy ctpool/

fmt:
	ruff format ctpool/ tests/
	ruff check --fix ctpool/ tests/
