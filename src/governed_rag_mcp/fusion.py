from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy


def reciprocal_rank_fusion(
    *,
    vector_rows: Iterable[dict[str, object]],
    fts_rows: Iterable[dict[str, object]],
    limit: int,
    k0: int = 60,
) -> list[dict[str, object]]:
    combined: dict[str, dict[str, object]] = {}

    def add_row(row: dict[str, object], branch: str, rank: int) -> None:
        chunk_id = str(row["id"])
        entry = combined.setdefault(
            chunk_id,
            {
                **{
                    key: deepcopy(value)
                    for key, value in row.items()
                    if key not in {"distance", "bm25"}
                },
                "scores": {
                    "rrf": 0.0,
                    "vector_rank": None,
                    "vector_distance": None,
                    "fts_rank": None,
                    "fts_bm25": None,
                },
            },
        )
        scores = entry["scores"]
        assert isinstance(scores, dict)
        scores["rrf"] = float(scores["rrf"]) + (1.0 / (k0 + rank))
        if branch == "vector":
            scores["vector_rank"] = rank
            scores["vector_distance"] = row.get("distance")
        else:
            scores["fts_rank"] = rank
            scores["fts_bm25"] = row.get("bm25")

    for rank, row in enumerate(vector_rows, start=1):
        add_row(row, "vector", rank)
    for rank, row in enumerate(fts_rows, start=1):
        add_row(row, "fts", rank)

    rows = list(combined.values())
    rows.sort(key=lambda item: (-float(item["scores"]["rrf"]), str(item["id"])))  # type: ignore[index]
    return rows[:limit]
