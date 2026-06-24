# Paper-Wiki Layer0/Layer1 E2E Report

Date: 2026-06-24

## Scope

Implemented only Layer 0 and Layer 1:

- Layer 0: LaTeX source discovery, recursive `\input` / `\include` inlining, abstract and target-section extraction.
- Layer 1: generation of `summary.md`, `prior_works.json`, and `sci_pattern.json` under `artifacts/{slug}/`.

Out of scope and not implemented:

- Layer 2 wiki graph/index/concepts/log updates.
- Layer 3 retrieval, embeddings, vector store, FastAPI routes.

## Environment

- Conda environment: `paper-wiki`
- Python: 3.11.15
- Conda channel note: `defaults` returned HTTP 403, so the environment was created with `conda-forge`.
- pip install note: the default pip mirror did not return required packages, so dependencies were installed from `https://pypi.org/simple`.
- Model configuration was loaded from `.env` using `API_KEY`, `BASE_URL`, and `MODEL_NAME`. Secret values were not printed.

## Implemented Files

- `src/paper_wiki/core/enums.py`
- `src/paper_wiki/core/models.py`
- `src/paper_wiki/core/config.py`
- `src/paper_wiki/ingestion/latex_parser.py`
- `src/paper_wiki/ingestion/llm_client.py`
- `src/paper_wiki/ingestion/generators/summary_generator.py`
- `src/paper_wiki/ingestion/generators/prior_works_generator.py`
- `src/paper_wiki/ingestion/generators/pattern_generator.py`
- `src/paper_wiki/ingestion/pipeline.py`
- `src/paper_wiki/cli/main.py`
- `tests/unit/test_latex_parser.py`
- `tests/unit/test_models.py`
- `tests/integration/test_pipeline.py`
- `pyproject.toml`
- `requirements.txt`
- `AGENTS.md`

## Commands Run

```bash
conda create -n paper-wiki -c conda-forge --override-channels python=3.11 -y
conda run -n paper-wiki python -m pip install -i https://pypi.org/simple -r requirements.txt
conda run -n paper-wiki python -m pip install -i https://pypi.org/simple --no-build-isolation -e .
conda run -n paper-wiki pytest
conda run -n paper-wiki paper-wiki parse GraphWalker
conda run -n paper-wiki paper-wiki ingest GraphWalker --overwrite
```

## Test Results

```text
4 passed in 0.55s
```

Layer 0 parse smoke test for `GraphWalker`:

- Entry file: `colm2026_conference.tex`
- Inlined source files: 16 `.tex` files
- Matched sections:
  - `introduction`: true
  - `related_work`: true
  - `method`: true
  - `experiments`: true

Layer 1 schema validation:

```text
schema validation ok
```

## Generated Artifacts

Generated under `artifacts/GraphWalker/`:

- `summary.md` - 2,839 bytes
- `prior_works.json` - 3,659 bytes
- `sci_pattern.json` - 741 bytes

The final `summary.md` has local authoritative YAML frontmatter with `reviewed: false`.

The final `sci_pattern.json` classified GraphWalker as:

- Primary pattern: `P01` / `Gap-Driven Reframing`
- Secondary pattern: `P03` / `Representation Shift & Primitive Recasting`
- Confidence: `high`

## Layer Boundary Check

No files were written under `wiki/` during ingestion. This preserves the requested Layer0/Layer1-only boundary.

## Review Notes

`prior_works.json` is schema-valid but should be manually reviewed before any future Layer2 graph ingestion. The current requirement document explicitly treats LLM-generated prior-work extraction as hallucination-prone and requires human review before graph/RAG inclusion.
