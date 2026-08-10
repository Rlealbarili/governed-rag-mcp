from __future__ import annotations


class GovernedRagError(Exception):
    """Base error with a stable public code and a non-sensitive message."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self) -> dict[str, str]:
        return {"error": self.code, "message": self.message}


class IndexUnavailableError(GovernedRagError):
    def __init__(self) -> None:
        super().__init__("index_unavailable", "The governed knowledge index is unavailable.")


class EmbeddingError(GovernedRagError):
    def __init__(self, code: str = "embedding_unavailable") -> None:
        super().__init__(code, "The embedding provider is unavailable.")
