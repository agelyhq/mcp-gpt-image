FROM python:3.11-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ src/
COPY fastmcp_server.py .

ENV OPENAI_IMAGEGEN_OUTPUT_DIR=/data/generated-images
EXPOSE 8000

CMD ["uv", "run", "openai-imagegen-mcp", "--transport", "streamable-http"]
