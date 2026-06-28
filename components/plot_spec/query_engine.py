from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re

import duckdb

from plot_spec.models import QuerySpec
from plot_spec.specs import DashboardDefinition, FILTER_TOKEN


FIELD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class AppliedFilter:
    field: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[dict[str, Any]]


class DuckDBQueryEngine:
    def run_query(
        self,
        definition: DashboardDefinition,
        query_id: str,
        applied_filters: list[AppliedFilter],
    ) -> QueryResult:
        query = _get_query(definition, query_id)
        sql, params = _render_sql(query, applied_filters)

        with duckdb.connect() as connection:
            self._register_sources(connection, definition)
            cursor = connection.execute(sql, params)
            columns = [column[0] for column in cursor.description]
            rows = [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]

        return QueryResult(columns=columns, rows=rows)

    def _register_sources(self, connection: duckdb.DuckDBPyConnection, definition: DashboardDefinition) -> None:
        for data_source in definition.spec.data_sources:
            source_path = definition.resolve_path(data_source.path)
            escaped_path = str(source_path).replace("'", "''")
            connection.execute(
                f'CREATE VIEW "{data_source.id}" AS SELECT * FROM read_csv_auto(\'{escaped_path}\')'
            )


def _get_query(definition: DashboardDefinition, query_id: str) -> QuerySpec:
    for query in definition.spec.queries:
        if query.id == query_id:
            return query
    raise KeyError(f"Unknown query '{query_id}'")


def _render_sql(query: QuerySpec, applied_filters: list[AppliedFilter]) -> tuple[str, list[str]]:
    where_clauses: list[str] = []
    params: list[str] = []

    for applied_filter in applied_filters:
        if not FIELD_RE.fullmatch(applied_filter.field):
            raise ValueError(f"Invalid filter field '{applied_filter.field}'")
        if not applied_filter.values:
            continue
        placeholders = ", ".join("?" for _ in applied_filter.values)
        where_clauses.append(f'"{applied_filter.field}" IN ({placeholders})')
        params.extend(applied_filter.values)

    where_clause = ""
    if where_clauses:
        where_clause = "WHERE " + " AND ".join(where_clauses)

    if FILTER_TOKEN in query.sql:
        return query.sql.replace(FILTER_TOKEN, where_clause), params

    wrapped_sql = f"SELECT * FROM ({query.sql}) AS base"
    if where_clause:
        wrapped_sql = f"{wrapped_sql} {where_clause}"
    return wrapped_sql, params
