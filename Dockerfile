FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

COPY pyproject.toml README.md workspace.toml AGENTS.md /app/
COPY components /app/components
COPY projects /app/projects

RUN uv sync --no-dev

ENV PLOTSPEC_PROJECTS_ROOT=/app/projects

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "plot_spec.api:app", "--host", "0.0.0.0", "--port", "8000"]
