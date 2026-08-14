.PHONY: install build check lint format test run clean

install:
	uv sync --all-extras

build:
	uv build

# What CI runs, and what to run before pushing.
check: lint test

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests
	uv run mypy

format:
	uv run ruff format src tests
	uv run ruff check --fix src tests

test:
	uv run pytest

run:
	uv run mcp-gpt-image

clean:
	rm -rf dist .pytest_cache .ruff_cache .mypy_cache
	find src tests -name __pycache__ -type d -exec rm -rf {} +
