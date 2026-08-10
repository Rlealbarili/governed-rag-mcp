from __future__ import annotations

import json
from pathlib import Path

from governed_rag_mcp.cli import (
    _atomic_write_json,
    _embedder,
    build_main,
    evaluate_main,
    publication_audit_main,
)
from governed_rag_mcp.embeddings import OllamaEmbedder


def _write_repository(root: Path) -> None:
    package = root / "src/example"
    package.mkdir(parents=True)
    (package / "fusion.py").write_text(
        "def reciprocal_rank_fusion():\n"
        '    """Merge vector and FTS rankings with reciprocal rank fusion."""\n'
        "    return 'rrf'\n",
        encoding="utf-8",
    )


def test_build_cli_indexes_repository_source(tmp_path: Path, capsys: object) -> None:
    _write_repository(tmp_path)
    index = tmp_path / "data/knowledge.sqlite"

    exit_code = build_main(["--root", str(tmp_path), "--output", str(index), "--dimensions", "64"])

    assert exit_code == 0
    assert index.is_file()
    report = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert report["files_indexed"] == 1
    assert report["fail_closed"] is True


def test_evaluate_cli_enforces_metrics_for_self_index(tmp_path: Path, capsys: object) -> None:
    _write_repository(tmp_path)
    index = tmp_path / "data/knowledge.sqlite"
    build_main(["--root", str(tmp_path), "--output", str(index), "--dimensions", "64"])
    capsys.readouterr()  # type: ignore[attr-defined]
    suite = tmp_path / "evaluation.json"
    suite.write_text(
        json.dumps(
            {
                "name": "self-index-smoke",
                "k": 3,
                "queries": [
                    {
                        "query": "reciprocal rank fusion vector FTS rankings",
                        "expected_paths": ["src/example/fusion.py"],
                        "source": "code",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "artifacts/evaluation.json"

    exit_code = evaluate_main(
        [
            "--index",
            str(index),
            "--suite",
            str(suite),
            "--output",
            str(output),
            "--dimensions",
            "64",
            "--min-hit-rate",
            "1.0",
            "--min-mrr",
            "1.0",
        ]
    )

    assert exit_code == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["gate"] == "PASS"
    assert report["metrics"] == {
        "query_count": 1,
        "k": 3,
        "hit_rate_at_k": 1.0,
        "mrr": 1.0,
    }
    assert json.loads(capsys.readouterr().out)["gate"] == "PASS"  # type: ignore[attr-defined]


def test_evaluate_cli_returns_failure_when_gate_is_missed(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    index = tmp_path / "knowledge.sqlite"
    build_main(["--root", str(tmp_path), "--output", str(index), "--dimensions", "64"])
    suite = tmp_path / "evaluation.json"
    suite.write_text(
        json.dumps(
            {
                "name": "negative-gate",
                "k": 3,
                "queries": [
                    {
                        "query": "unrelated quantum chemistry",
                        "expected_paths": ["src/example/missing.py"],
                        "source": "code",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert (
        evaluate_main(
            [
                "--index",
                str(index),
                "--suite",
                str(suite),
                "--output",
                str(tmp_path / "report.json"),
                "--dimensions",
                "64",
                "--min-hit-rate",
                "1.0",
            ]
        )
        == 1
    )


def test_cli_ollama_provider_uses_environment_contract(monkeypatch: object) -> None:
    monkeypatch.setenv("OLLAMA_EMBEDDINGS_URL", "http://127.0.0.1:11434/api/embeddings")  # type: ignore[attr-defined]
    monkeypatch.setenv("OLLAMA_EMBEDDING_MODEL", "example-embed")  # type: ignore[attr-defined]

    embedder = _embedder("ollama", 384)

    assert isinstance(embedder, OllamaEmbedder)
    assert embedder.url == "http://127.0.0.1:11434/api/embeddings"
    assert embedder.model_name == "example-embed"
    assert embedder.dimensions == 384


def test_publication_audit_cli_blocks_without_echoing_secret(
    tmp_path: Path, capsys: object
) -> None:
    synthetic = "github" + "_pat_" + ("Z" * 24)
    (tmp_path / "README.md").write_text("# Safe project\n", encoding="utf-8")
    (tmp_path / "leak.txt").write_text(synthetic, encoding="utf-8")

    exit_code = publication_audit_main(["--root", str(tmp_path)])

    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert exit_code == 1
    assert json.loads(output)["status"] == "BLOCKED"
    assert synthetic not in output


def test_atomic_json_write_ignores_preplanted_temp_symlink(tmp_path: Path) -> None:
    output = tmp_path / "evaluation.json"
    victim = tmp_path / "victim.txt"
    victim.write_text("do-not-overwrite", encoding="utf-8")
    (tmp_path / ".evaluation.json.tmp").symlink_to(victim)

    _atomic_write_json(output, {"gate": "PASS"})

    assert victim.read_text(encoding="utf-8") == "do-not-overwrite"
    assert output.is_file()
    assert not output.is_symlink()
