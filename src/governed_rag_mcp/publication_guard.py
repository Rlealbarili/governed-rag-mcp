from __future__ import annotations

import os
import re
from collections.abc import Iterable
from pathlib import Path

MAX_PUBLIC_FILE_BYTES = 512 * 1024
FORBIDDEN_SUFFIXES = frozenset(
    {".sqlite", ".sqlite3", ".db", ".bak", ".log", ".key", ".pem", ".p12", ".pfx"}
)
IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "data",
        "dist",
    }
)
IGNORED_FILES = frozenset({".coverage", "coverage.xml"})

# Fragmented literals keep the guard from matching its own source while preserving the rule.
_SECRET_PATTERNS = (
    re.compile("sk" + r"-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile("github" + r"_pat_[A-Za-z0-9_]{16,}"),
    re.compile("AK" + r"IA[0-9A-Z]{16}"),
    re.compile("-----BEGIN " + r"[A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?:https?|ssh)://[^\s/@:]+:[^\s/@]+@"),
)
_PRIVATE_PATH = re.compile("/" + r"(?:home|mnt|opt)/")
_PRIVATE_IP = re.compile(
    r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\."
    r"(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b"
)


def _finding(path: str, reason: str) -> dict[str, str]:
    return {"path": path, "reason": reason}


def repository_files(root: Path) -> list[Path]:
    resolved_root = root.resolve()
    files: list[Path] = []
    for candidate in resolved_root.rglob("*"):
        relative = candidate.relative_to(resolved_root)
        if candidate.name in IGNORED_FILES:
            continue
        if any(
            part in IGNORED_DIRECTORIES or part.endswith(".egg-info") for part in relative.parts
        ):
            continue
        if candidate.is_file() or candidate.is_symlink():
            files.append(candidate)
    return sorted(files)


def audit_publication(root: Path, files: Iterable[Path]) -> dict[str, object]:
    resolved_root = root.resolve()
    findings: list[dict[str, str]] = []
    scanned = 0
    candidates = {Path(os.path.abspath(path)) for path in files}
    for candidate in sorted(candidates):
        try:
            relative = candidate.relative_to(resolved_root).as_posix()
        except ValueError:
            findings.append(_finding(candidate.name, "outside_repository"))
            continue
        scanned += 1
        if candidate.is_symlink() or not candidate.is_file():
            findings.append(_finding(relative, "unsafe_file_type"))
            continue
        try:
            candidate.resolve(strict=True).relative_to(resolved_root)
        except (FileNotFoundError, ValueError):
            findings.append(_finding(relative, "outside_repository"))
            continue
        if candidate.suffix.lower() in FORBIDDEN_SUFFIXES or candidate.name == ".env":
            findings.append(_finding(relative, "forbidden_file_type"))
            continue
        if candidate.stat().st_size > MAX_PUBLIC_FILE_BYTES:
            findings.append(_finding(relative, "file_too_large"))
            continue
        raw = candidate.read_bytes()
        if b"\x00" in raw:
            findings.append(_finding(relative, "binary_file"))
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            findings.append(_finding(relative, "invalid_utf8"))
            continue
        if any(pattern.search(text) for pattern in _SECRET_PATTERNS):
            findings.append(_finding(relative, "named_secret"))
        elif _PRIVATE_PATH.search(text):
            findings.append(_finding(relative, "private_absolute_path"))
        elif _PRIVATE_IP.search(text):
            findings.append(_finding(relative, "private_network_address"))
    findings.sort(key=lambda item: (item["path"], item["reason"]))
    return {
        "status": "PASS" if not findings else "BLOCKED",
        "files_scanned": scanned,
        "findings": findings,
        "secret_values_recorded": False,
    }
