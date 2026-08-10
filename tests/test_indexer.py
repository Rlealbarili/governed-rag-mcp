from __future__ import annotations

import os
from pathlib import Path

import pytest

from governed_rag_mcp.embeddings import HashingEmbedder
from governed_rag_mcp.errors import EmbeddingError
from governed_rag_mcp.indexer import build_index
from governed_rag_mcp.models import DocumentInput


class FailingEmbedder:
    dimensions = 64
    model_name = "failure-fixture"

    def embed(self, text: str) -> list[float]:
        raise EmbeddingError("synthetic_failure")


def test_failed_build_removes_shadow_and_preserves_target(tmp_path: Path) -> None:
    target = tmp_path / "knowledge.sqlite"
    target.write_bytes(b"existing-index")
    document = DocumentInput(
        id="doc-1",
        path="docs/example.md",
        source="docs",
        project="example",
        text="Safe public documentation.",
    )

    with pytest.raises(EmbeddingError):
        build_index(target, [document], FailingEmbedder())

    assert target.read_bytes() == b"existing-index"
    assert list(tmp_path.glob(".*.tmp")) == []


def test_build_ignores_preplanted_predictable_temp_symlink(tmp_path: Path) -> None:
    target = tmp_path / "knowledge.sqlite"
    outside = tmp_path / "outside.sqlite"
    predictable = tmp_path / f".knowledge.sqlite.{os.getpid()}.tmp"
    predictable.symlink_to(outside)
    document = DocumentInput(
        id="doc-1",
        path="docs/example.md",
        source="docs",
        project="example",
        text="Reciprocal rank fusion documentation.",
    )

    build_index(target, [document], HashingEmbedder(dimensions=64))

    assert target.is_file()
    assert not target.is_symlink()
    assert not outside.exists()


def test_build_rejects_symlink_as_final_target(tmp_path: Path) -> None:
    victim = tmp_path / "victim.txt"
    victim.write_text("do-not-overwrite", encoding="utf-8")
    target = tmp_path / "knowledge.sqlite"
    target.symlink_to(victim)
    document = DocumentInput(
        id="doc-1",
        path="docs/example.md",
        source="docs",
        project="example",
        text="Safe documentation.",
    )

    with pytest.raises(ValueError, match="symlink"):
        build_index(target, [document], HashingEmbedder(dimensions=64))

    assert victim.read_text(encoding="utf-8") == "do-not-overwrite"
    assert target.is_symlink()
