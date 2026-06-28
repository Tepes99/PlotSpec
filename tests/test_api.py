from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from plot_spec.api import create_app


ROOT = Path(__file__).resolve().parents[1]
client = TestClient(create_app(ROOT / "projects"))


def test_dashboard_definition_endpoint() -> None:
    response = client.get("/dashboards/sales-overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dashboard"]["title"] == "Sales Overview"
    assert len(payload["components"]) == 3


def test_filtered_dashboard_data_endpoint() -> None:
    response = client.post(
        "/dashboards/sales-overview/data",
        json={"filters": {"region": "West", "category": ["Electronics"]}},
    )

    assert response.status_code == 200
    payload = response.json()
    filters = {item["id"]: item for item in payload["filters"]}
    assert filters["region"]["selected"] == ["West"]
    assert filters["category"]["selected"] == ["Electronics"]

    table_component = next(
        item for item in payload["components"] if item["id"] == "sales_records_table"
    )
    assert all(row[1] == "West" for row in table_component["rows"])
    assert all(row[2] == "Electronics" for row in table_component["rows"])


def test_embed_endpoint_serves_html() -> None:
    response = client.get("/embed/sales-overview")

    assert response.status_code == 200
    assert "Sales Overview" in response.text
    assert "/assets/plotly.js" in response.text
