from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

from plot_spec.models import DashboardSpec


SPEC_FILENAME = "dashboard.json"
FILTER_TOKEN = "__filters__"


@dataclass(frozen=True)
class DashboardDefinition:
    spec: DashboardSpec
    root_path: Path

    def resolve_path(self, relative_path: str) -> Path:
        return (self.root_path / relative_path).resolve()


class SpecStore:
    def __init__(self, projects_root: Path) -> None:
        self.projects_root = projects_root.resolve()

    def list_dashboards(self) -> list[dict[str, str]]:
        dashboards: list[dict[str, str]] = []
        for spec_path in sorted(self.projects_root.glob(f"*/{SPEC_FILENAME}")):
            definition = self._load_definition(spec_path)
            dashboards.append(
                {
                    "id": definition.spec.dashboard.id,
                    "title": definition.spec.dashboard.title,
                }
            )
        return dashboards

    def get_dashboard(self, dashboard_id: str) -> DashboardDefinition:
        for spec_path in self.projects_root.glob(f"*/{SPEC_FILENAME}"):
            definition = self._load_definition(spec_path)
            if definition.spec.dashboard.id == dashboard_id:
                return definition
        raise FileNotFoundError(f"Unknown dashboard '{dashboard_id}'")

    def _load_definition(self, spec_path: Path) -> DashboardDefinition:
        raw_spec = json.loads(spec_path.read_text(encoding="utf-8"))
        spec = DashboardSpec.model_validate(raw_spec)
        definition = DashboardDefinition(spec=spec, root_path=spec_path.parent.resolve())

        for data_source in spec.data_sources:
            resolved_path = definition.resolve_path(data_source.path)
            if not resolved_path.is_file():
                raise FileNotFoundError(
                    f"Missing data source file '{resolved_path}' for dashboard '{spec.dashboard.id}'"
                )

        return definition
