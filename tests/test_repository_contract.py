from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_project_bootstrap_contract() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dev_dependencies = pyproject["dependency-groups"]["dev"]

    assert pyproject["project"]["name"] == "plotspec"
    assert "pytest>=9.1.1" in dev_dependencies
    assert (ROOT / "AGENTS.md").is_file()
    assert (ROOT / "documentation" / "project-proposition.md").is_file()
    assert (ROOT / "documentation" / "Development practices.md").is_file()
