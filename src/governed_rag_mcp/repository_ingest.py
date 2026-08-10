from __future__ import annotations

import ast
import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .embeddings import Embedder
from .indexer import build_index
from .models import DocumentInput, DocumentSource

MAX_PUBLIC_FILE_BYTES = 128 * 1024

_ALLOWED_PATTERNS = (
    "src/**/*.py",
    "docs/**/*.md",
    "README.md",
    "README.pt-BR.md",
    "SECURITY.md",
)

_NAMED_SECRET_PATTERNS = (
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(
        r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b"
    ),
    re.compile(r"/(?:home|mnt|opt)/[A-Za-z0-9_.-]+/"),
)


@dataclass(frozen=True)
class UnsafeRepositoryError(Exception):
    path: str
    reason: str

    def __str__(self) -> str:
        return f"repository_ingest_blocked:{self.reason}:{self.path}"


def _file_source(path: Path) -> DocumentSource:
    if path.suffix == ".py":
        return "code"
    if "adr" in path.parts:
        return "decisions"
    return "docs"


def _chunk_id(relative_path: str, symbol: str, text: str) -> str:
    payload = f"{relative_path}\0{symbol}\0{text}".encode()
    return hashlib.sha256(payload).hexdigest()


def _python_chunks(relative_path: str, text: str, project: str) -> list[DocumentInput]:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise UnsafeRepositoryError(relative_path, "python_parse_error") from exc
    lines = text.splitlines()
    chunks: list[DocumentInput] = []
    first_definition = min(
        (
            node.lineno
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ),
        default=len(lines) + 1,
    )
    preamble = "\n".join(lines[: max(0, first_definition - 1)]).strip()
    if preamble:
        chunks.append(
            DocumentInput(
                id=_chunk_id(relative_path, "module", preamble),
                path=relative_path,
                source="code",
                project=project,
                text=preamble,
                start_line=1,
                end_line=max(1, first_definition - 1),
            )
        )
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        start = min([node.lineno, *(item.lineno for item in node.decorator_list)])
        end = getattr(node, "end_lineno", node.lineno)
        chunk_text = "\n".join(lines[start - 1 : end]).strip()
        if not chunk_text:
            continue
        chunks.append(
            DocumentInput(
                id=_chunk_id(relative_path, node.name, chunk_text),
                path=relative_path,
                source="code",
                project=project,
                text=chunk_text,
                start_line=start,
                end_line=end,
            )
        )
    if not chunks and text.strip():
        chunks.append(
            DocumentInput(
                id=_chunk_id(relative_path, "module", text),
                path=relative_path,
                source="code",
                project=project,
                text=text.strip(),
                start_line=1,
                end_line=max(1, len(lines)),
            )
        )
    return chunks


def _markdown_chunks(
    relative_path: str, text: str, source: DocumentSource, project: str
) -> list[DocumentInput]:
    lines = text.splitlines()
    starts = [index for index, line in enumerate(lines) if line.startswith("#")]
    if not starts:
        starts = [0]
    chunks: list[DocumentInput] = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        chunk_text = "\n".join(lines[start:end]).strip()
        if not chunk_text:
            continue
        heading = lines[start].lstrip("# ") if start < len(lines) else "document"
        chunks.append(
            DocumentInput(
                id=_chunk_id(relative_path, heading, chunk_text),
                path=relative_path,
                source=source,
                project=project,
                text=chunk_text,
                start_line=start + 1,
                end_line=max(start + 1, end),
            )
        )
    return chunks


def _allowed_files(root: Path) -> Iterable[Path]:
    seen: set[Path] = set()
    for pattern in _ALLOWED_PATTERNS:
        for candidate in root.glob(pattern):
            if candidate in seen:
                continue
            seen.add(candidate)
            yield candidate


def collect_repository_documents(
    root: Path, *, project: str = "governed-rag-mcp"
) -> list[DocumentInput]:
    resolved_root = root.resolve()
    documents: list[DocumentInput] = []
    for candidate in sorted(_allowed_files(resolved_root)):
        relative_path = candidate.relative_to(resolved_root).as_posix()
        try:
            candidate.resolve(strict=True).relative_to(resolved_root)
        except (FileNotFoundError, ValueError) as exc:
            raise UnsafeRepositoryError(relative_path, "outside_repository") from exc
        if candidate.is_symlink() or not candidate.is_file():
            raise UnsafeRepositoryError(relative_path, "unsafe_file_type")
        if candidate.stat().st_size > MAX_PUBLIC_FILE_BYTES:
            raise UnsafeRepositoryError(relative_path, "file_too_large")
        raw = candidate.read_bytes()
        if b"\x00" in raw:
            raise UnsafeRepositoryError(relative_path, "binary_file")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise UnsafeRepositoryError(relative_path, "invalid_utf8") from exc
        if any(pattern.search(text) for pattern in _NAMED_SECRET_PATTERNS):
            raise UnsafeRepositoryError(relative_path, "named_secret")
        source = _file_source(candidate.relative_to(resolved_root))
        if candidate.suffix == ".py":
            documents.extend(_python_chunks(relative_path, text, project))
        else:
            documents.extend(_markdown_chunks(relative_path, text, source, project))
    if not documents:
        raise UnsafeRepositoryError(".", "empty_allowlist")
    return documents


def build_repository_index(
    root: Path,
    output_path: Path,
    embedder: Embedder,
) -> dict[str, object]:
    documents = collect_repository_documents(root)
    report = build_index(output_path, documents, embedder)
    report.update(
        {
            "files_indexed": len({document.path for document in documents}),
            "chunks_indexed": len(documents),
            "rejected_files": [],
            "fail_closed": True,
        }
    )
    return report
