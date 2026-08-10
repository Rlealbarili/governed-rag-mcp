PYTHON ?= python3
VENV := .venv
BIN := $(VENV)/bin

.PHONY: setup build-index evaluate demo test lint typecheck audit ci clean

setup:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install --upgrade pip==26.1.2
	$(BIN)/python -m pip install -e '.[dev]'

build-index:
	$(BIN)/governed-rag-build --root . --output data/knowledge.sqlite --dimensions 64

evaluate: build-index
	$(BIN)/governed-rag-eval --index data/knowledge.sqlite --suite examples/evaluation.json --output artifacts/evaluation.json --dimensions 64 --min-hit-rate 0.8 --min-mrr 0.6

demo: evaluate
	@printf 'Self-indexed RAG gate: PASS\n'

test:
	$(BIN)/python -m pytest --cov=governed_rag_mcp --cov-report=term-missing --cov-report=xml

lint:
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

typecheck:
	$(BIN)/mypy src

audit:
	$(BIN)/python -m pip check
	$(BIN)/pip-audit
	$(BIN)/governed-rag-audit --root .

ci: lint typecheck test demo audit

clean:
	rm -rf .coverage coverage.xml artifacts/*.json data build dist
