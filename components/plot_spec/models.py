from __future__ import annotations

from collections import Counter, defaultdict, deque
from typing import Literal
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
FIELD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def validate_identifier(value: str) -> str:
    if not IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"Invalid identifier: {value}")
    return value


def validate_field_name(value: str) -> str:
    if not FIELD_RE.fullmatch(value):
        raise ValueError(f"Invalid field name: {value}")
    return value


class DashboardMeta(StrictModel):
    id: str
    title: str
    description: str | None = None

    _validate_id = field_validator("id")(validate_identifier)


class DataSourceSpec(StrictModel):
    id: str
    kind: Literal["csv"]
    path: str

    _validate_id = field_validator("id")(validate_identifier)


class QuerySpec(StrictModel):
    id: str
    sql: str

    _validate_id = field_validator("id")(validate_identifier)

    @field_validator("sql")
    @classmethod
    def validate_sql(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Query SQL cannot be empty")
        return value


class FilterSpec(StrictModel):
    id: str
    label: str
    kind: Literal["single_select", "multi_select"]
    field: str
    query: str
    target_queries: list[str] = Field(default_factory=list)
    label_field: str | None = None
    default: list[str] = Field(default_factory=list)

    _validate_id = field_validator("id")(validate_identifier)
    _validate_field = field_validator("field")(validate_field_name)
    _validate_query = field_validator("query")(validate_identifier)
    _validate_target_queries = field_validator("target_queries")(lambda value: [validate_identifier(item) for item in value])

    @field_validator("label_field")
    @classmethod
    def validate_label_field(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_field_name(value)

    @model_validator(mode="after")
    def validate_defaults(self) -> "FilterSpec":
        if self.kind == "single_select" and len(self.default) > 1:
            raise ValueError("single_select filters may only define one default value")
        return self


class RelationshipSpec(StrictModel):
    id: str
    kind: Literal["filter_dependency"]
    parent_filter: str
    child_filter: str

    _validate_id = field_validator("id")(validate_identifier)
    _validate_parent = field_validator("parent_filter")(validate_identifier)
    _validate_child = field_validator("child_filter")(validate_identifier)


class ComponentSpec(StrictModel):
    id: str
    title: str
    kind: Literal["bar", "line", "pie", "table"]
    query: str
    x: str | None = None
    y: str | None = None
    labels: str | None = None
    values: str | None = None
    columns: list[str] = Field(default_factory=list)

    _validate_id = field_validator("id")(validate_identifier)
    _validate_query = field_validator("query")(validate_identifier)

    @field_validator("x", "y", "labels", "values")
    @classmethod
    def validate_optional_field_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_field_name(value)

    @field_validator("columns")
    @classmethod
    def validate_columns(cls, value: list[str]) -> list[str]:
        return [validate_field_name(item) for item in value]

    @model_validator(mode="after")
    def validate_component_fields(self) -> "ComponentSpec":
        if self.kind in {"bar", "line"} and (self.x is None or self.y is None):
            raise ValueError(f"{self.kind} components require x and y fields")
        if self.kind == "pie" and (self.labels is None or self.values is None):
            raise ValueError("pie components require labels and values fields")
        return self


class LayoutItemSpec(StrictModel):
    component: str
    width: Literal["full", "half"] = "full"

    _validate_component = field_validator("component")(validate_identifier)


class LayoutRowSpec(StrictModel):
    components: list[LayoutItemSpec]

    @field_validator("components")
    @classmethod
    def validate_components(cls, value: list[LayoutItemSpec]) -> list[LayoutItemSpec]:
        if not value:
            raise ValueError("layout rows must contain at least one component")
        return value


class LayoutSpec(StrictModel):
    rows: list[LayoutRowSpec]

    @field_validator("rows")
    @classmethod
    def validate_rows(cls, value: list[LayoutRowSpec]) -> list[LayoutRowSpec]:
        if not value:
            raise ValueError("layout must define at least one row")
        return value


class EmbedSpec(StrictModel):
    height: int = 760


class DashboardSpec(StrictModel):
    dashboard: DashboardMeta
    data_sources: list[DataSourceSpec]
    queries: list[QuerySpec]
    filters: list[FilterSpec]
    relationships: list[RelationshipSpec]
    components: list[ComponentSpec]
    layout: LayoutSpec
    embed: EmbedSpec = Field(default_factory=EmbedSpec)

    @model_validator(mode="after")
    def validate_references(self) -> "DashboardSpec":
        data_source_ids = _unique_ids(self.data_sources, "data_sources")
        query_ids = _unique_ids(self.queries, "queries")
        filter_ids = _unique_ids(self.filters, "filters")
        component_ids = _unique_ids(self.components, "components")

        for query in self.queries:
            for source_id in data_source_ids:
                if source_id in query.sql:
                    break
            else:
                raise ValueError(
                    f"Query '{query.id}' must reference at least one declared data source"
                )

        for filter_spec in self.filters:
            if filter_spec.query not in query_ids:
                raise ValueError(
                    f"Filter '{filter_spec.id}' references unknown query '{filter_spec.query}'"
                )
            missing_targets = set(filter_spec.target_queries) - query_ids
            if missing_targets:
                raise ValueError(
                    f"Filter '{filter_spec.id}' references unknown target queries: {sorted(missing_targets)}"
                )

        for relationship in self.relationships:
            if relationship.parent_filter not in filter_ids:
                raise ValueError(
                    f"Relationship '{relationship.id}' references unknown parent filter '{relationship.parent_filter}'"
                )
            if relationship.child_filter not in filter_ids:
                raise ValueError(
                    f"Relationship '{relationship.id}' references unknown child filter '{relationship.child_filter}'"
                )
            if relationship.parent_filter == relationship.child_filter:
                raise ValueError(
                    f"Relationship '{relationship.id}' cannot reference the same filter twice"
                )

        _assert_acyclic_relationships(self.relationships)

        for component in self.components:
            if component.query not in query_ids:
                raise ValueError(
                    f"Component '{component.id}' references unknown query '{component.query}'"
                )

        layout_components = []
        for row in self.layout.rows:
            layout_components.extend(item.component for item in row.components)

        duplicate_layout = [
            component_id
            for component_id, count in Counter(layout_components).items()
            if count > 1
        ]
        if duplicate_layout:
            raise ValueError(
                f"Layout references duplicate components: {sorted(duplicate_layout)}"
            )

        missing_from_layout = component_ids - set(layout_components)
        if missing_from_layout:
            raise ValueError(
                f"Layout is missing components: {sorted(missing_from_layout)}"
            )

        unknown_in_layout = set(layout_components) - component_ids
        if unknown_in_layout:
            raise ValueError(
                f"Layout references unknown components: {sorted(unknown_in_layout)}"
            )

        return self


def _unique_ids(items: list[StrictModel], label: str) -> set[str]:
    ids = [item.id for item in items]
    duplicates = [item_id for item_id, count in Counter(ids).items() if count > 1]
    if duplicates:
        raise ValueError(f"Duplicate ids in {label}: {sorted(duplicates)}")
    return set(ids)


def _assert_acyclic_relationships(relationships: list[RelationshipSpec]) -> None:
    graph: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = defaultdict(int)

    for relationship in relationships:
        graph[relationship.parent_filter].append(relationship.child_filter)
        in_degree[relationship.child_filter] += 1
        in_degree.setdefault(relationship.parent_filter, 0)

    queue = deque(node for node, degree in in_degree.items() if degree == 0)
    visited = 0

    while queue:
        node = queue.popleft()
        visited += 1
        for child in graph[node]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    if visited != len(in_degree):
        raise ValueError("Filter dependency relationships must be acyclic")
