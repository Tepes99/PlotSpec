from __future__ import annotations

from pathlib import Path

from plot_spec.query_engine import DuckDBQueryEngine
from plot_spec.service import DashboardService
from plot_spec.specs import SpecStore


ROOT = Path(__file__).resolve().parents[1]


def test_region_filter_drives_child_options_and_component_results() -> None:
    service = DashboardService(SpecStore(ROOT / "projects"), DuckDBQueryEngine())

    payload = service.resolve_dashboard("sales-overview", {"region": "South"})
    filters = {item["id"]: item for item in payload["filters"]}

    assert filters["region"]["selected"] == ["South"]
    assert [option["value"] for option in filters["category"]["options"]] == [
        "Home",
        "Outdoor",
    ]

    table_component = next(
        item for item in payload["components"] if item["id"] == "sales_records_table"
    )
    assert table_component["render_mode"] == "table"
    assert {row[1] for row in table_component["rows"]} == {"South"}

    bar_component = next(
        item for item in payload["components"] if item["id"] == "category_revenue"
    )
    assert set(bar_component["figure"]["data"][0]["x"]) == {"Home", "Outdoor"}
