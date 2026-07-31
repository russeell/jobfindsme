# jobfindsme MCP Server — Docker image
# Smithery-compatible container for Streamable HTTP deployment
#
# Build:  docker build -t jobfindsme .
# Run:    docker run -i --rm jobfindsme

FROM python:3.11-slim

WORKDIR /app

# Install uv for fast package resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install dependencies first (layer caching)
COPY pyproject.toml .
RUN uv pip install --system --no-cache pydantic>=2.10,<3 pypdf>=5,<7 certifi \
    requests websocket-client curl_cffi

# Install jobfindsme from local source
COPY src/ src/
COPY README.md .
RUN uv pip install --system --no-cache -e ".[browser]"

# MCP runs over stdio — no port exposed
CMD ["python", "-m", "jobfindsme", "mcp"]
