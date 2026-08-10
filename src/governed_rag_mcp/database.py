from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .errors import IndexUnavailableError


def load_sqlite_vec(connection: sqlite3.Connection) -> None:
    import sqlite_vec  # type: ignore[import-untyped]

    connection.enable_load_extension(True)
    try:
        sqlite_vec.load(connection)
    finally:
        connection.enable_load_extension(False)


def create_schema(connection: sqlite3.Connection, dimensions: int) -> None:
    if not 8 <= dimensions <= 4096:
        raise ValueError("embedding dimensions must be between 8 and 4096")
    connection.executescript(
        """
        create table chunks (
          id text primary key,
          path text not null,
          source text not null,
          project text not null,
          start_line integer not null,
          end_line integer not null,
          text text not null
        );
        create virtual table chunks_fts using fts5(
          text,
          id unindexed,
          path unindexed,
          source unindexed,
          project unindexed,
          start_line unindexed,
          end_line unindexed,
          tokenize='unicode61 remove_diacritics 2'
        );
        create table metadata (key text primary key, value text not null);
        """
    )
    connection.execute(
        "create virtual table chunks_vec using vec0("
        f"id text primary key, embedding float[{dimensions}])"
    )


@contextmanager
def connect_readonly(path: Path, *, vector: bool = False) -> Iterator[sqlite3.Connection]:
    resolved = path.resolve()
    if not resolved.is_file() or not os.access(resolved, os.R_OK):
        raise IndexUnavailableError()
    connection = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True, timeout=3.0)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("pragma query_only=ON")
        connection.execute("pragma busy_timeout=3000")
        if vector:
            load_sqlite_vec(connection)
        yield connection
    finally:
        connection.close()


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
