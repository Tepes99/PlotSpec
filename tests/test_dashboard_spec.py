from __future__ import annotations

from pathlib import Path
import json

import pytest

from plot_spec.specs import SpecStore


ROOT = Path(__file__).resolve().parents[1]


def test_example_dashboard_spec_loads() -> None:
    definition = SpecStore(ROOT / "projects").get_dashboard("sales-overview")

    assert definition.spec.dashboard.title == "Sales Overview"
    assert [component.id for component in definition.spec.components] == [
        "monthly_revenue",
        "category_revenue",
        "sales_records_table",
    ]


def test_filter_relationship_cycles_are_rejected(tmp_path: Path) -> None:
    spec_path = ROOT / "projects" / "sales_overview" / "dashboard.json"
    raw_spec = json.loads(spec_path.read_text(encoding="utf-8"))
    raw_spec["relationships"].append(
        {
            "id": "category_to_region",
            "kind": "filter_dependency",
            "parent_filter": "category",
            "child_filter": "region",
        }
    )

    temp_project = tmp_path / "invalid_cycle"
    temp_project.mkdir(parents=True)
    (temp_project / "data").mkdir()
    (temp_project / "data" / "sales.csv").write_text(
        (ROOT / "projects" / "sales_overview" / "data" / "sales.csv").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    (temp_project / "dashboard.json").write_text(
        json.dumps(raw_spec, indent=2), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="acyclic"):
        SpecStore(tmp_path).get_dashboard("sales-overview")
