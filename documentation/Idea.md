I want to abstract plotly figures as json configurations that can be then used to render the figures as a dasboard. It should have support for filters, data relationships and be able to be served as a single embeddable element in a web page.

## Tech stack

1. Main language for project: Python
2. Plotly for the interactive plots
3. Configs in JSON format (Can be just a file for now)
4. Server: FastAPI
5. Front end: Vanilla HTML + CSS (Minimal/No JavaScript)
6. Data source DB: DuckDB (Not just tables inside the DuckDB, but anything that it can query)
7. Deployment: Docker container and compose files