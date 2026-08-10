from pathlib import Path

from governed_rag_mcp.publication_guard import audit_publication


def test_publication_guard_accepts_small_public_source(tmp_path: Path) -> None:
    safe = tmp_path / "src/app.py"
    safe.parent.mkdir()
    safe.write_text("def health(): return 'ok'\n", encoding="utf-8")

    report = audit_publication(tmp_path, [safe])

    assert report["status"] == "PASS"
    assert report["files_scanned"] == 1
    assert report["findings"] == []


def test_publication_guard_blocks_secret_without_echoing_it(tmp_path: Path) -> None:
    secret = "github_" + "pat_" + ("Z" * 24)
    unsafe = tmp_path / "src/settings.py"
    unsafe.parent.mkdir()
    unsafe.write_text(f'TOKEN = "{secret}"\n', encoding="utf-8")

    report = audit_publication(tmp_path, [unsafe])

    assert report["status"] == "BLOCKED"
    assert report["findings"] == [{"path": "src/settings.py", "reason": "named_secret"}]
    assert secret not in str(report)


def test_publication_guard_blocks_databases_and_absolute_private_paths(tmp_path: Path) -> None:
    database = tmp_path / "fixtures/memory.sqlite"
    database.parent.mkdir()
    database.write_bytes(b"SQLite format 3")
    path_leak = tmp_path / "docs/runbook.md"
    path_leak.parent.mkdir()
    path_leak.write_text("Read /" + "home/example/private.json\n", encoding="utf-8")

    report = audit_publication(tmp_path, [database, path_leak])

    assert report["status"] == "BLOCKED"
    assert {finding["reason"] for finding in report["findings"]} == {
        "forbidden_file_type",
        "private_absolute_path",
    }


def test_publication_audit_rejects_internal_symlink(tmp_path: Path) -> None:
    target = tmp_path / "safe.py"
    target.write_text("VALUE = 'public'\n", encoding="utf-8")
    alias = tmp_path / "alias.py"
    alias.symlink_to(target)

    report = audit_publication(tmp_path, [alias])

    assert report["status"] == "BLOCKED"
    assert report["findings"] == [{"path": "alias.py", "reason": "unsafe_file_type"}]
