# Paper-Wiki Agent Guide

## Project Scope

This repository is a personal research-paper knowledge base. The default development boundary for routine work is:

- Layer 0: read-only raw paper assets under `raw/{paper-slug}/`.
- Layer 1: generated per-paper artifacts under `artifacts/{paper-slug}/`.

Some Layer 2 graph and publishing utilities already exist. Maintain them only when the user explicitly asks for graph/publishing work. Do not implement new Layer 2 (`wiki/`) or Layer 3 (`retrieval/`, `api/`) phases unless the user explicitly asks for that phase.

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

Build deterministic Layer 1 assets without calling an LLM:

```bash
paper-wiki assets GraphWalker --overwrite
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
- The minimal paper assets contract is `manifest.json`, `assets/paper.md`, `assets/sections.json`, `assets/figures/manifest.json` plus image files, and `assets/references.json`.
- `paper-wiki assets <slug...> [--overwrite]` must stay deterministic and must not call an LLM.
- `ingest` should build or reuse assets before generating `summary.md`, `prior_works.json`, and `sci_pattern.json`.
- Layer 1 downstream code should consume `PaperAssetsBundle` through `AssetsReader`; do not reintroduce a legacy `ParsedPaper` adapter in the ingest main path.
- Validate JSON artifacts with Pydantic models before writing.
- `summary.md` must remain a content-only Markdown reading note; do not add YAML frontmatter or paper metadata there. It may include a deterministic trailing semantic appendix derived from `prior_works.json` and `sci_pattern.json`.
- Paper metadata and review state live in `artifacts/{paper-slug}/manifest.json` under `paper`, with `reviewed: false` until a human review happens.
- Do not let ingestion update `wiki/index.md`, graph files, concepts, embeddings, or any retrieval index in the Layer0/Layer1 phase.
- When adding tests, prefer deterministic parser and mock-LLM tests; real API smoke tests should be explicit and should not expose secrets.

## Documentation Maintenance

- Treat `README.md`, `docs/Paper-Wiki 需求文档.md`, `docs/Paper-Wiki 技术方案_v1.md`, and `docs/论文 Assets 需求与设计方案.md` as long-lived maintenance documents, not one-off design drafts.
- When implementing, removing, or materially changing behavior, update the requirements document so it clearly distinguishes implemented, unimplemented, and undecided requirements.
- When changing architecture, package structure, CLI behavior, data models, configuration, or workflow boundaries, update the technical design document in the same change.
- Keep documentation aligned with the current Layer 0/Layer 1 implementation boundary unless the user explicitly asks to start Layer 2 or Layer 3 work.
