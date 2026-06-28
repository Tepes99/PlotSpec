# AGENTS.md

## Purpose

PlotSpec is a specification-driven dashboard runtime. The system should turn JSON dashboard definitions into embeddable Plotly dashboards with filters, data relationships, and DuckDB-backed query execution.

This repository should optimize for the highest functionality-to-flexibility ratio with the least code. Prefer narrow, composable primitives over broad frameworks or speculative abstraction.

## Source of Truth

- Product direction: `documentation/project-proposition.md`
- Development constraints: `documentation/Development practices.md`

If implementation details are unclear, follow those documents before inventing new patterns.

## Stack

- Language: Python
- Package manager: `uv`
- Repository structure: Polylith for Python monorepo
- API/server: FastAPI
- Visualization: Plotly
- Config format: JSON
- Data engine: DuckDB
- Frontend: vanilla HTML and CSS with minimal necessary JavaScript
- Deployment: Docker and Docker Compose

## Core Engineering Rule

Write the minimum code that preserves clarity, extension points, and correctness.

Prefer:

- explicit schemas over ad hoc dictionaries
- small service boundaries over shared implicit state
- a constrained feature set over partial support for many features
- simple embedding and delivery mechanisms over clever integration layers
- runtime behavior derived from config over one-off application code

Avoid:

- speculative abstractions
- custom frameworks inside the project
- frontend-heavy solutions when server-side composition is enough
- raw flexibility that weakens validation or makes behavior ambiguous

## Architectural Direction

Keep the system split into a few clear responsibilities:

1. Spec loading and validation
2. Internal domain models for dashboard definitions
3. DuckDB-backed query execution
4. Filter and relationship resolution
5. FastAPI delivery endpoints
6. Thin frontend rendering layer

Do not couple query logic, spec parsing, and rendering into the same module.

## Product Constraints

- The dashboard definition is a formal contract, not a loose config blob.
- The first versions should support a narrow set of chart types and filter types.
- Relationships between datasets or views should be explicit and validated.
- Embedding should start with the simplest reliable option, which is usually an iframe.
- Minimal JavaScript means minimal necessary JavaScript, not zero JavaScript.

## Polylith Guidance

- Keep reusable logic in `components`.
- Compose higher-level flows in `bases` and `projects`.
- Use `development` for local entry points and developer-facing assembly.
- Keep module boundaries simple and reflect the runtime architecture.

Do not spread cross-cutting helpers everywhere. Add a shared abstraction only when duplication is real and stable.

## Data and Config Guidance

- Prefer structured JSON sections such as `dashboard`, `data_sources`, `queries`, `filters`, `relationships`, `components`, `layout`, and `embed`.
- Treat spec validation as a first-class feature.
- Keep data source references logical in the spec. Do not duplicate connection details across components.
- Treat raw SQL as trusted-author functionality unless security constraints are expanded deliberately.

## API Guidance

Keep the API surface small and predictable. The default shape should be:

- dashboard metadata and structure endpoint
- dashboard data endpoint for initial render
- dashboard data update endpoint for filter state
- embed endpoint

Do not add endpoints for concepts that can stay internal.

## Frontend Guidance

- The frontend should render, collect filter state, request data, and update charts.
- Prefer server-prepared payloads over client-side transformation logic.
- Do not introduce a frontend framework unless the existing model has clearly failed.
- Keep CSS utilitarian and dashboard-focused.

## Testing

`pytest` is the project test runner and is included in the `dev` dependency group.

Testing rules:

- Add focused `pytest` coverage for shared behavior, parsing, validation, query generation, and filter/relationship logic.
- Keep tests close to the behavior they protect and prefer fast unit tests first.
- Add integration tests only where component boundaries or API behavior make unit tests insufficient.
- Do not add broad snapshot-style tests for unstable payloads unless the structure is the actual contract.

Run tests with:

```bash
uv run pytest
```

## Version Notes

Every new project version must add a version note file under `documentation/version_notes/`.

Rules:

- Create one file per released version, named with the exact version number, for example `0.1.0.md`.
- Write notes that are comprehensive but concise.
- Cover at least: summary, delivered scope, key behavior, API or interface changes, verification status, and known limitations.
- Keep the notes grounded in what actually shipped, not planned work.
- Update version notes as part of the same change set that introduces the new version.

## Dependency Rule

Every dependency must earn its place. Before adding one, ask:

1. Does the standard library already cover this?
2. Does an existing project dependency already cover this?
3. Does the new dependency remove meaningful complexity instead of hiding it?

If the answer is weak, do not add the dependency.
