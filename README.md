# PlotSpec

PlotSpec is a proof-of-concept specification-driven dashboard runtime. It reads a JSON dashboard spec, queries data through DuckDB, renders Plotly visualizations, and serves an embeddable dashboard through FastAPI.

## Run locally

```bash
uv sync
uv run uvicorn plot_spec.api:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/embed/sales-overview`.

## Test

```bash
uv run pytest
```

## POC scope

The current implementation is intentionally narrow:

- one formal JSON dashboard spec structure
- CSV-backed DuckDB data source support
- line, bar, pie, and table components
- single-select and multi-select filters
- parent-child filter dependency relationships
- iframe-ready FastAPI embed endpoint
