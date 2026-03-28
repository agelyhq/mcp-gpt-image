.PHONY: install build lint test run

install:
	uv sync --all-extras

build:
	uv build

lint:
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

test:
	uv run pytest tests/ -v

run:
	uv run openai-imagegen-mcp
