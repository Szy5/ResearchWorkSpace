# Paper-Wiki Agent Guide

## Project Scope

This repository is a personal research-paper knowledge base. The current implemented scope is limited to:

- Layer 0: read-only raw paper assets under `raw/{paper-slug}/`.
- Layer 1: generated per-paper artifacts under `artifacts/{paper-slug}/`.

Do not implement Layer 2 (`wiki/`) or Layer 3 (`retrieval/`, `api/`) unless the user explicitly asks for that phase.

## Environment And Dependencies

- Use conda for package management.
- Recommended environment name: `paper-wiki`.
- Python version: 3.11 or newer.
- Keep `requirements.txt` in sync with runtime and test dependencies.
- Load model configuration from `.env`; never print or commit API keys.
- Supported `.env` keys include `API_KEY`, `BASE_URL`, and `MODEL_NAME` plus OpenAI-style aliases.

Example setup:

```bash
conda create -n paper-wiki python=3.11 -y
conda activate paper-wiki
pip install -r requirements.txt
pip install -e .
```

## Commands

Parse Layer 0 LaTeX without calling an LLM:

```bash
paper-wiki parse GraphWalker
```

Generate Layer 1 artifacts:

```bash
paper-wiki ingest GraphWalker --overwrite
```

Run tests:

```bash
pytest
```

## Coding Rules

- Keep Layer 0 raw files read-only.
- Write generated files only under `artifacts/{paper-slug}/`.
- Validate JSON artifacts with Pydantic models before writing.
- `summary.md` must include YAML frontmatter and `reviewed: false` until a human review happens.
- Do not let ingestion update `wiki/index.md`, graph files, concepts, embeddings, or any retrieval index in the Layer0/Layer1 phase.
- When adding tests, prefer deterministic parser and mock-LLM tests; real API smoke tests should be explicit and should not expose secrets.
