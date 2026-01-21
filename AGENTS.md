# Repository Guidelines

## Project Structure & Module Organization
- `src/aou_pheno_cc/` contains the Python package.
- `src/aou_pheno_cc/cli/` holds CLI entry points (`createphenodb`, `xls2json`, `createphenotypes`).
- `tests/` contains pytest-based unit tests.
- `AllOfUs_Phenotypes_CC.md` documents the universe-first case/control flow used by the tools.

## Build, Test, and Development Commands
- `uv pip install .` installs the package.
- `uv pip install -e '.[test]'` installs in editable mode with test deps.
- `python -m pytest` runs the full test suite.
- `aou-createphenodb` builds the `OMOP.db` SQLite cache from BigQuery.
- `aou-xls2json` converts phenotype definition spreadsheets to JSONL.
- `aou-createphenotypes` generates the case/control phenotype matrix.

BigQuery access must be configured before `aou-createphenodb`:
`GOOGLE_PROJECT`, `WORKSPACE_CDR`, `WORKSPACE_BUCKET`.

## Coding Style & Naming Conventions
- Python 3.10+, 4-space indentation, type hints where helpful.
- Keep functions small and explicit; prefer clear variable names over abbreviations.
- Match existing patterns in `src/aou_pheno_cc/cli/` (dataclasses for structured inputs, helper functions prefixed with `_`).

## Testing Guidelines
- Tests use `pytest` and live under `tests/`.
- Name tests as `test_*.py` and functions `test_*`.
- Add coverage for new CLI behavior or parsing/validation logic.

## Commit & Pull Request Guidelines
- Commit messages are short, imperative summaries (e.g., “Add phenotype counts output”).
- Keep PRs focused; include a brief description and link relevant issues.
- For CLI changes, mention the command(s) affected and provide a sample invocation.

## Security & Configuration Tips
- Avoid hardcoding workspace or project IDs; rely on environment variables.
- Do not commit credentials, service account keys, or generated `OMOP.db` files.
