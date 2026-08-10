FROM python:3.12-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    GOVERNED_RAG_CLIENT_PROFILE=restricted \
    GOVERNED_RAG_INDEX=/app/data/knowledge.sqlite \
    GOVERNED_RAG_EMBEDDING_PROVIDER=hash \
    GOVERNED_RAG_HASH_DIMENSIONS=64

WORKDIR /app

RUN groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid appuser --no-create-home --shell /usr/sbin/nologin appuser

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY docs ./docs
COPY README.pt-BR.md SECURITY.md ./
RUN python -m pip install --no-cache-dir --upgrade pip==26.2.1 \
    && python -m pip install --no-cache-dir . \
    && governed-rag-build --root /app --output /app/data/knowledge.sqlite --dimensions 64 \
    && chown -R appuser:appuser /app

USER 10001:10001

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "from pathlib import Path; from governed_rag_mcp.embeddings import HashingEmbedder; from governed_rag_mcp.service import SearchService; raise SystemExit(0 if SearchService(index_path=Path('/app/data/knowledge.sqlite'), embedder=HashingEmbedder()).status()['status'] == 'PASS' else 1)"

ENTRYPOINT ["governed-rag-mcp"]
