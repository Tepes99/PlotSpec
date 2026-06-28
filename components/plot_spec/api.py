from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from plotly.offline import get_plotlyjs

from plot_spec.query_engine import DuckDBQueryEngine
from plot_spec.service import DashboardService
from plot_spec.specs import SpecStore


class DashboardDataRequest(BaseModel):
    filters: dict[str, str | list[str] | None] = Field(default_factory=dict)


def create_app(projects_root: Path | None = None) -> FastAPI:
    resolved_projects_root = projects_root or _default_projects_root()
    service = DashboardService(
        spec_store=SpecStore(resolved_projects_root),
        query_engine=DuckDBQueryEngine(),
    )

    app = FastAPI(title="PlotSpec")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    def index() -> HTMLResponse:
        dashboard_links = "".join(
            (
                f"<li><a href='/embed/{escape(item['id'])}'>{escape(item['title'])}</a> "
                f"(<code>/dashboards/{escape(item['id'])}</code>)</li>"
            )
            for item in service.list_dashboards()
        )
        html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>PlotSpec</title>
    <style>
      body {{
        margin: 0;
        font-family: Inter, Arial, sans-serif;
        background: #f5f7fb;
        color: #18212f;
      }}
      main {{
        max-width: 960px;
        margin: 0 auto;
        padding: 40px 24px 64px;
      }}
      h1 {{
        margin-bottom: 12px;
      }}
      ul {{
        padding-left: 20px;
      }}
      code {{
        background: #e8edf5;
        padding: 2px 6px;
        border-radius: 4px;
      }}
    </style>
  </head>
  <body>
    <main>
      <h1>PlotSpec</h1>
      <p>Specification-driven dashboard proof of concept.</p>
      <ul>{dashboard_links}</ul>
    </main>
  </body>
</html>"""
        return HTMLResponse(html)

    @app.get("/assets/plotly.js")
    def plotly_asset() -> Response:
        return Response(get_plotlyjs(), media_type="application/javascript")

    @app.get("/dashboards/{dashboard_id}")
    def dashboard_definition(dashboard_id: str) -> dict[str, Any]:
        try:
            return service.describe_dashboard(dashboard_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/dashboards/{dashboard_id}/data")
    def dashboard_data(dashboard_id: str) -> dict[str, Any]:
        try:
            return service.resolve_dashboard(dashboard_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/dashboards/{dashboard_id}/data")
    def dashboard_data_filtered(
        dashboard_id: str, payload: DashboardDataRequest
    ) -> dict[str, Any]:
        try:
            return service.resolve_dashboard(dashboard_id, payload.filters)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/embed/{dashboard_id}")
    def embed_dashboard(dashboard_id: str) -> HTMLResponse:
        try:
            metadata = service.describe_dashboard(dashboard_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return HTMLResponse(_render_embed_page(metadata["dashboard"]["title"], dashboard_id))

    @app.exception_handler(FileNotFoundError)
    async def handle_missing_file(_, exc: FileNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    return app


def _default_projects_root() -> Path:
    configured_root = os.environ.get("PLOTSPEC_PROJECTS_ROOT")
    if configured_root:
        return Path(configured_root).resolve()
    return Path(__file__).resolve().parents[2] / "projects"


def _render_embed_page(title: str, dashboard_id: str) -> str:
    safe_title = escape(title)
    safe_id = escape(dashboard_id)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>{safe_title}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="/assets/plotly.js"></script>
    <style>
      :root {{
        color-scheme: light;
        font-family: Inter, Arial, sans-serif;
      }}
      * {{
        box-sizing: border-box;
      }}
      body {{
        margin: 0;
        background: #f3f6fb;
        color: #17212e;
      }}
      .shell {{
        max-width: 1280px;
        margin: 0 auto;
        padding: 20px;
      }}
      .header {{
        margin-bottom: 20px;
      }}
      .header h1 {{
        margin: 0 0 4px;
        font-size: 28px;
      }}
      .filters {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 220px));
        gap: 12px;
        margin-bottom: 20px;
      }}
      .filter {{
        display: flex;
        flex-direction: column;
        gap: 6px;
      }}
      .filter label {{
        font-size: 13px;
        font-weight: 600;
      }}
      .filter select {{
        min-height: 40px;
        padding: 8px 10px;
        border: 1px solid #c7d2e4;
        border-radius: 6px;
        background: #fff;
      }}
      .row {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 16px;
        margin-bottom: 16px;
      }}
      .card {{
        background: #fff;
        border: 1px solid #d7dfec;
        border-radius: 8px;
        padding: 16px;
        min-width: 0;
      }}
      .card.full {{
        grid-column: 1 / -1;
      }}
      .card h2 {{
        margin: 0 0 12px;
        font-size: 16px;
      }}
      .plot {{
        width: 100%;
        min-height: 360px;
      }}
      .table-wrap {{
        overflow-x: auto;
      }}
      table {{
        width: 100%;
        border-collapse: collapse;
      }}
      th, td {{
        padding: 8px 10px;
        border-bottom: 1px solid #e6ecf5;
        text-align: left;
        white-space: nowrap;
      }}
      .error {{
        display: none;
        margin-bottom: 16px;
        padding: 12px 14px;
        border: 1px solid #f0b8b8;
        border-radius: 6px;
        background: #fff2f2;
        color: #8f2020;
      }}
      @media (max-width: 900px) {{
        .row {{
          grid-template-columns: minmax(0, 1fr);
        }}
        .card.full {{
          grid-column: auto;
        }}
      }}
    </style>
  </head>
  <body>
    <div class="shell">
      <header class="header">
        <h1>{safe_title}</h1>
      </header>
      <div id="error" class="error"></div>
      <section id="filters" class="filters"></section>
      <section id="layout"></section>
    </div>
    <script>
      const dashboardId = {safe_id!r};
      const errorEl = document.getElementById("error");

      function showError(message) {{
        errorEl.textContent = message;
        errorEl.style.display = "block";
      }}

      function clearError() {{
        errorEl.textContent = "";
        errorEl.style.display = "none";
      }}

      function collectFilters() {{
        const payload = {{}};
        document.querySelectorAll("[data-filter-id]").forEach((element) => {{
          const filterId = element.dataset.filterId;
          if (element.multiple) {{
            payload[filterId] = Array.from(element.selectedOptions).map((option) => option.value);
          }} else if (element.value) {{
            payload[filterId] = element.value;
          }}
        }});
        return payload;
      }}

      function buildSelect(filterSpec) {{
        const wrapper = document.createElement("div");
        wrapper.className = "filter";

        const label = document.createElement("label");
        label.textContent = filterSpec.label;

        const select = document.createElement("select");
        select.dataset.filterId = filterSpec.id;
        select.multiple = filterSpec.kind === "multi_select";
        if (select.multiple) {{
          select.size = Math.max(3, Math.min(filterSpec.options.length, 6));
        }}

        if (!select.multiple) {{
          const placeholder = document.createElement("option");
          placeholder.value = "";
          placeholder.textContent = "All";
          select.appendChild(placeholder);
        }}

        const selected = new Set(filterSpec.selected);
        filterSpec.options.forEach((option) => {{
          const optionEl = document.createElement("option");
          optionEl.value = option.value;
          optionEl.textContent = option.label;
          optionEl.selected = selected.has(option.value);
          select.appendChild(optionEl);
        }});

        select.addEventListener("change", () => refreshDashboard());
        wrapper.append(label, select);
        return wrapper;
      }}

      function renderFilters(filters) {{
        const container = document.getElementById("filters");
        container.innerHTML = "";
        filters.forEach((filterSpec) => {{
          container.appendChild(buildSelect(filterSpec));
        }});
      }}

      function renderTable(component, container) {{
        const wrap = document.createElement("div");
        wrap.className = "table-wrap";

        const table = document.createElement("table");
        const thead = document.createElement("thead");
        const headerRow = document.createElement("tr");
        component.columns.forEach((column) => {{
          const th = document.createElement("th");
          th.textContent = column;
          headerRow.appendChild(th);
        }});
        thead.appendChild(headerRow);

        const tbody = document.createElement("tbody");
        component.rows.forEach((row) => {{
          const tr = document.createElement("tr");
          row.forEach((value) => {{
            const td = document.createElement("td");
            td.textContent = value ?? "";
            tr.appendChild(td);
          }});
          tbody.appendChild(tr);
        }});

        table.append(thead, tbody);
        wrap.appendChild(table);
        container.appendChild(wrap);
      }}

      function renderComponents(payload) {{
        const componentMap = new Map(payload.components.map((component) => [component.id, component]));
        const layout = document.getElementById("layout");
        layout.innerHTML = "";

        payload.layout.rows.forEach((rowSpec) => {{
          const row = document.createElement("div");
          row.className = "row";

          rowSpec.components.forEach((item) => {{
            const component = componentMap.get(item.component);
            const card = document.createElement("article");
            card.className = ("card" + (item.width === "full" ? " full" : "")).trim();

            const title = document.createElement("h2");
            title.textContent = component.title;
            card.appendChild(title);

            const body = document.createElement("div");
            if (component.render_mode === "plotly") {{
              body.className = "plot";
              card.appendChild(body);
              requestAnimationFrame(() => {{
                Plotly.react(body, component.figure.data, component.figure.layout, {{
                  responsive: true,
                  displayModeBar: false
                }});
              }});
            }} else {{
              renderTable(component, body);
              card.appendChild(body);
            }}

            row.appendChild(card);
          }});

          layout.appendChild(row);
        }});
      }}

      async function loadDashboard(filters = null) {{
        const url = `/dashboards/${{dashboardId}}/data`;
        const options = filters
          ? {{
              method: "POST",
              headers: {{ "Content-Type": "application/json" }},
              body: JSON.stringify({{ filters }})
            }}
          : {{}};

        const response = await fetch(url, options);
        const payload = await response.json();
        if (!response.ok) {{
          throw new Error(payload.detail || "Failed to load dashboard");
        }}
        return payload;
      }}

      async function refreshDashboard() {{
        try {{
          clearError();
          const payload = await loadDashboard(collectFilters());
          renderFilters(payload.filters);
          renderComponents(payload);
        }} catch (error) {{
          showError(error.message);
        }}
      }}

      async function initialize() {{
        try {{
          clearError();
          const payload = await loadDashboard();
          renderFilters(payload.filters);
          renderComponents(payload);
        }} catch (error) {{
          showError(error.message);
        }}
      }}

      initialize();
    </script>
  </body>
</html>"""


app = create_app()
