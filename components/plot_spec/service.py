from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

import plotly.graph_objects as go

from plot_spec.models import ComponentSpec, DashboardSpec, FilterSpec
from plot_spec.query_engine import AppliedFilter, DuckDBQueryEngine, QueryResult
from plot_spec.specs import DashboardDefinition, SpecStore


class DashboardService:
    def __init__(self, spec_store: SpecStore, query_engine: DuckDBQueryEngine) -> None:
        self.spec_store = spec_store
        self.query_engine = query_engine

    def list_dashboards(self) -> list[dict[str, str]]:
        return self.spec_store.list_dashboards()

    def describe_dashboard(self, dashboard_id: str) -> dict[str, Any]:
        definition = self.spec_store.get_dashboard(dashboard_id)
        spec = definition.spec
        return {
            "dashboard": spec.dashboard.model_dump(),
            "filters": [
                {
                    "id": filter_spec.id,
                    "label": filter_spec.label,
                    "kind": filter_spec.kind,
                }
                for filter_spec in spec.filters
            ],
            "components": [
                {
                    "id": component.id,
                    "title": component.title,
                    "kind": component.kind,
                }
                for component in spec.components
            ],
            "layout": spec.layout.model_dump(),
            "embed": spec.embed.model_dump(),
        }

    def resolve_dashboard(
        self,
        dashboard_id: str,
        requested_filters: dict[str, str | list[str] | None] | None = None,
    ) -> dict[str, Any]:
        definition = self.spec_store.get_dashboard(dashboard_id)
        spec = definition.spec
        requested = requested_filters or {}
        normalized_filters = self._normalize_filters(spec, requested)
        filters_payload, active_filters = self._resolve_filters(definition, normalized_filters)

        return {
            "dashboard": spec.dashboard.model_dump(),
            "filters": filters_payload,
            "components": [
                self._resolve_component(definition, component, active_filters)
                for component in spec.components
            ],
            "layout": spec.layout.model_dump(),
            "embed": spec.embed.model_dump(),
        }

    def _normalize_filters(
        self, spec: DashboardSpec, requested_filters: dict[str, str | list[str] | None]
    ) -> dict[str, list[str]]:
        known_filters = {filter_spec.id for filter_spec in spec.filters}
        unknown_filters = sorted(set(requested_filters) - known_filters)
        if unknown_filters:
            raise ValueError(f"Unknown filters: {unknown_filters}")

        normalized: dict[str, list[str]] = {}
        for filter_spec in spec.filters:
            raw_value = requested_filters.get(filter_spec.id)
            if raw_value is None:
                normalized[filter_spec.id] = []
                continue
            if isinstance(raw_value, list):
                values = [str(value) for value in raw_value if value not in ("", None)]
            else:
                values = [str(raw_value)]
            if filter_spec.kind == "single_select" and len(values) > 1:
                raise ValueError(
                    f"Filter '{filter_spec.id}' only accepts a single selected value"
                )
            normalized[filter_spec.id] = values
        return normalized

    def _resolve_filters(
        self, definition: DashboardDefinition, normalized_filters: dict[str, list[str]]
    ) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
        spec = definition.spec
        filter_map = {filter_spec.id: filter_spec for filter_spec in spec.filters}
        parent_map = defaultdict(list)
        child_map = defaultdict(list)
        for relationship in spec.relationships:
            parent_map[relationship.child_filter].append(relationship.parent_filter)
            child_map[relationship.parent_filter].append(relationship.child_filter)

        active_filters = {filter_spec.id: list(normalized_filters.get(filter_spec.id, [])) for filter_spec in spec.filters}
        filters_payload: list[dict[str, Any]] = []

        for filter_id in _topological_filter_order(spec):
            filter_spec = filter_map[filter_id]
            parent_filters = [
                AppliedFilter(field=filter_map[parent_id].field, values=tuple(active_filters[parent_id]))
                for parent_id in parent_map[filter_id]
                if active_filters[parent_id]
            ]
            result = self.query_engine.run_query(
                definition, filter_spec.query, parent_filters
            )
            options = _build_options(result.rows, filter_spec.field, filter_spec.label_field)
            option_values = {option["value"] for option in options}

            selected_values = [
                value for value in active_filters[filter_id] if value in option_values
            ]
            if not selected_values:
                selected_values = [
                    value for value in filter_spec.default if value in option_values
                ]
            if filter_spec.kind == "single_select":
                selected_values = selected_values[:1]
            active_filters[filter_id] = selected_values

            filters_payload.append(
                {
                    "id": filter_spec.id,
                    "label": filter_spec.label,
                    "kind": filter_spec.kind,
                    "selected": selected_values,
                    "options": options,
                    "depends_on": parent_map[filter_id],
                    "children": child_map[filter_id],
                }
            )

        return filters_payload, active_filters

    def _resolve_component(
        self,
        definition: DashboardDefinition,
        component: ComponentSpec,
        active_filters: dict[str, list[str]],
    ) -> dict[str, Any]:
        applied_filters = self._filters_for_query(definition.spec, component.query, active_filters)
        result = self.query_engine.run_query(definition, component.query, applied_filters)

        if component.kind == "table":
            columns = component.columns or result.columns
            return {
                "id": component.id,
                "title": component.title,
                "kind": component.kind,
                "render_mode": "table",
                "columns": columns,
                "rows": [
                    [row.get(column) for column in columns]
                    for row in result.rows
                ],
            }

        figure = self._build_figure(component, result)
        return {
            "id": component.id,
            "title": component.title,
            "kind": component.kind,
            "render_mode": "plotly",
            "figure": figure.to_plotly_json(),
        }

    def _filters_for_query(
        self,
        spec: DashboardSpec,
        query_id: str,
        active_filters: dict[str, list[str]],
    ) -> list[AppliedFilter]:
        applied_filters: list[AppliedFilter] = []
        for filter_spec in spec.filters:
            if query_id not in filter_spec.target_queries:
                continue
            selected_values = active_filters[filter_spec.id]
            if not selected_values:
                continue
            applied_filters.append(
                AppliedFilter(field=filter_spec.field, values=tuple(selected_values))
            )
        return applied_filters

    def _build_figure(self, component: ComponentSpec, result: QueryResult) -> go.Figure:
        figure = go.Figure()

        if component.kind == "line":
            figure.add_trace(
                go.Scatter(
                    x=[row.get(component.x) for row in result.rows],
                    y=[row.get(component.y) for row in result.rows],
                    mode="lines+markers",
                    name=component.title,
                )
            )
        elif component.kind == "bar":
            figure.add_trace(
                go.Bar(
                    x=[row.get(component.x) for row in result.rows],
                    y=[row.get(component.y) for row in result.rows],
                    name=component.title,
                )
            )
        elif component.kind == "pie":
            figure.add_trace(
                go.Pie(
                    labels=[row.get(component.labels) for row in result.rows],
                    values=[row.get(component.values) for row in result.rows],
                    hole=0.35,
                )
            )
        else:
            raise ValueError(f"Unsupported component kind '{component.kind}'")

        figure.update_layout(
            template="none",
            title=component.title,
            margin={"l": 32, "r": 16, "t": 48, "b": 32},
            height=360,
            paper_bgcolor="#ffffff",
            plot_bgcolor="#ffffff",
            font={"color": "#17212e"},
        )
        figure.update_xaxes(showgrid=True, gridcolor="#e7edf7")
        figure.update_yaxes(showgrid=True, gridcolor="#e7edf7")
        return figure


def _build_options(
    rows: list[dict[str, Any]], field: str, label_field: str | None
) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    seen: set[str] = set()
    effective_label_field = label_field or field

    for row in rows:
        value = row.get(field)
        if value is None:
            continue
        string_value = str(value)
        if string_value in seen:
            continue
        seen.add(string_value)
        options.append(
            {
                "label": str(row.get(effective_label_field, value)),
                "value": string_value,
            }
        )

    options.sort(key=lambda option: option["label"])
    return options


def _topological_filter_order(spec: DashboardSpec) -> list[str]:
    graph: dict[str, list[str]] = defaultdict(list)
    in_degree = {filter_spec.id: 0 for filter_spec in spec.filters}

    for relationship in spec.relationships:
        graph[relationship.parent_filter].append(relationship.child_filter)
        in_degree[relationship.child_filter] += 1

    queue = deque(filter_id for filter_id, degree in in_degree.items() if degree == 0)
    ordered_filters: list[str] = []

    while queue:
        filter_id = queue.popleft()
        ordered_filters.append(filter_id)
        for child_filter in graph[filter_id]:
            in_degree[child_filter] -= 1
            if in_degree[child_filter] == 0:
                queue.append(child_filter)

    return ordered_filters
