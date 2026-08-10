from __future__ import annotations

import threading
from collections import Counter


class MetricsRegistry:
    """Aggregate-only telemetry. Query text and chunk text never enter this object."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._request_count = 0
        self._latency_total_ms = 0.0
        self._by_profile: Counter[str] = Counter()
        self._by_source: Counter[str] = Counter()
        self._by_status: Counter[str] = Counter()
        self._by_winner: Counter[str] = Counter()

    def record(
        self,
        *,
        profile: str,
        requested_source: str,
        status: str,
        winning_source: str,
        latency_ms: float,
    ) -> None:
        with self._lock:
            self._request_count += 1
            self._latency_total_ms += max(0.0, latency_ms)
            self._by_profile[profile] += 1
            self._by_source[requested_source] += 1
            self._by_status[status] += 1
            self._by_winner[winning_source] += 1

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            average = self._latency_total_ms / self._request_count if self._request_count else 0.0
            return {
                "request_count": self._request_count,
                "average_latency_ms": round(average, 3),
                "by_profile": dict(sorted(self._by_profile.items())),
                "by_requested_source": dict(sorted(self._by_source.items())),
                "by_status": dict(sorted(self._by_status.items())),
                "by_winning_source": dict(sorted(self._by_winner.items())),
                "query_text_recorded": False,
                "chunk_text_recorded": False,
            }
