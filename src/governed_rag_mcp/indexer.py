from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import time
from collections.abc import Iterable
from pathlib import Path

from .database import create_schema, fsync_directory, load_sqlite_vec
from .embeddings import Embedder
from .models import DocumentInput


def build_index(
    path: Path, documents: Iterable[DocumentInput], embedder: Embedder
) -> dict[str, object]:
    """Build a complete shadow index and atomically replace the target."""

    target = Path(os.path.abspath(path))
    if target.is_symlink():
        raise ValueError("index target must not be a symlink")
    documents_list = list(documents)
    if len({document.id for document in documents_list}) != len(documents_list):
        raise ValueError("document ids must be unique")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    os.close(descriptor)
    temp = Path(temp_name)

    try:
        connection = sqlite3.connect(temp)
        try:
            load_sqlite_vec(connection)
            create_schema(connection, embedder.dimensions)
            for document in documents_list:
                embedding = embedder.embed(document.text)
                connection.execute(
                    """insert into chunks
                       (id, path, source, project, start_line, end_line, text)
                       values (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        document.id,
                        document.path,
                        document.source,
                        document.project,
                        document.start_line,
                        document.end_line,
                        document.text,
                    ),
                )
                connection.execute(
                    """insert into chunks_fts
                       (text, id, path, source, project, start_line, end_line)
                       values (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        document.text,
                        document.id,
                        document.path,
                        document.source,
                        document.project,
                        document.start_line,
                        document.end_line,
                    ),
                )
                connection.execute(
                    "insert into chunks_vec (id, embedding) values (?, ?)",
                    (document.id, json.dumps(embedding, separators=(",", ":"))),
                )
            metadata = {
                "schema_version": "1",
                "embedding_model": embedder.model_name,
                "embedding_dimensions": str(embedder.dimensions),
                "built_at": str(int(time.time())),
            }
            connection.executemany(
                "insert into metadata (key, value) values (?, ?)", metadata.items()
            )
            connection.commit()
            if connection.execute("pragma integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("index integrity check failed")
        finally:
            connection.close()

        with temp.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temp, target)
        fsync_directory(target.parent)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise
    return {
        "path": str(target),
        "documents": len(documents_list),
        "dimensions": embedder.dimensions,
    }
