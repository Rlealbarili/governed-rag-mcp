from pathlib import Path


def test_ci_bootstraps_the_same_virtual_environment_used_by_makefile() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "run: make setup" in workflow
    assert "python -m pip install -e '.[dev]'" not in workflow
