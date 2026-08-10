import re
from pathlib import Path


def test_ci_bootstraps_the_same_virtual_environment_used_by_makefile() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "run: make setup" in workflow
    assert "python -m pip install -e '.[dev]'" not in workflow
    action_refs = re.findall(r"uses: [^@\s]+@([^\s]+)", workflow)
    assert action_refs
    assert all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in action_refs)


def test_dependabot_groups_safe_updates_and_defers_major_migrations() -> None:
    config = Path(".github/dependabot.yml").read_text(encoding="utf-8")

    assert "groups:" in config
    assert '"version-update:semver-major"' in config
