from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .embeddings import HashingEmbedder, OllamaEmbedder
from .evaluation import EvaluationQuery, evaluate_service
from .models import ClientProfile, NRCReason, Status
from .publication_guard import audit_publication, repository_files
from .repository_ingest import build_repository_index
from .service import SearchService


class EvaluationCaseSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    query: str = Field(min_length=1, max_length=500)
    expected_paths: list[str] = Field(default_factory=list)
    source: Literal["all", "code", "docs", "decisions", "config", "memory"] = "all"
    project: str | None = None
    profile: ClientProfile | None = None
    expected_status: Status = Status.PASS
    expected_reason: NRCReason | None = None
    expected_skipped_sources: list[str] = Field(default_factory=list)


class EvaluationSuiteSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(min_length=1, max_length=100)
    k: int = Field(default=5, ge=1, le=20)
    queries: list[EvaluationCaseSpec] = Field(min_length=1)


def _embedder(provider: str, dimensions: int) -> HashingEmbedder | OllamaEmbedder:
    if provider == "hash":
        return HashingEmbedder(dimensions=dimensions)
    return OllamaEmbedder(
        dimensions=dimensions,
        url=os.environ.get("OLLAMA_EMBEDDINGS_URL", "http://127.0.0.1:11434/api/embeddings"),
        model_name=os.environ.get("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
    )


def _atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def build_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a fail-closed index from this repository.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("data/knowledge.sqlite"))
    parser.add_argument("--provider", choices=("hash", "ollama"), default="hash")
    parser.add_argument("--dimensions", type=int, default=64)
    args = parser.parse_args(argv)
    report = build_repository_index(
        args.root,
        args.output,
        _embedder(args.provider, args.dimensions),
    )
    print(json.dumps(report, sort_keys=True, ensure_ascii=True))
    return 0


def evaluate_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure HitRate@K and MRR against a golden suite."
    )
    parser.add_argument("--index", type=Path, default=Path("data/knowledge.sqlite"))
    parser.add_argument("--suite", type=Path, default=Path("examples/evaluation.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/evaluation.json"))
    parser.add_argument("--provider", choices=("hash", "ollama"), default="hash")
    parser.add_argument("--dimensions", type=int, default=64)
    parser.add_argument("--min-hit-rate", type=float, default=0.8)
    parser.add_argument("--min-mrr", type=float, default=0.6)
    args = parser.parse_args(argv)

    suite = EvaluationSuiteSpec.model_validate_json(args.suite.read_text(encoding="utf-8"))
    cases = [
        EvaluationQuery(
            query=case.query,
            expected_paths=frozenset(case.expected_paths),
            source=case.source,
            project=case.project,
            profile=case.profile,
            expected_status=case.expected_status,
            expected_reason=case.expected_reason,
            expected_skipped_sources=frozenset(case.expected_skipped_sources),
        )
        for case in suite.queries
    ]
    report = evaluate_service(
        SearchService(index_path=args.index, embedder=_embedder(args.provider, args.dimensions)),
        cases,
        k=suite.k,
        profile=ClientProfile.AUDITOR,
    )
    metrics = report["metrics"]
    if not isinstance(metrics, dict):
        raise RuntimeError("evaluation metrics contract violated")
    passed = (
        float(metrics["hit_rate_at_k"]) >= args.min_hit_rate
        and float(metrics["mrr"]) >= args.min_mrr
        and not report["contract_failures"]
    )
    report.update(
        {
            "suite": suite.name,
            "gate": "PASS" if passed else "FAIL",
            "thresholds": {
                "min_hit_rate_at_k": args.min_hit_rate,
                "min_mrr": args.min_mrr,
            },
        }
    )
    _atomic_write_json(args.output, report)
    print(json.dumps(report, sort_keys=True, ensure_ascii=True))
    return 0 if passed else 1


def publication_audit_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail closed before publishing repository files.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    report = audit_publication(args.root, repository_files(args.root))
    print(json.dumps(report, sort_keys=True, ensure_ascii=True))
    return 0 if report["status"] == "PASS" else 1
