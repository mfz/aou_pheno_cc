# aou-pheno-cc

Tools to build All of Us case-control phenotypes in a reproducible way.

## Commands

- `aou-createphenodb`: query OMOP tables from BigQuery and build `OMOP.db` (SQLite).
- `aou-xls2json`: convert phenotype definition Excel to JSONL.
- `aou-createphenotypes`: generate case/control phenotype matrix.

## Install on RAP

Install `uv` package manager if not installed

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Clone the package and `cd` into repository

From a workspace terminal on the Researcher Workbench (RAP):

```bash
uv pip install .
```

For development (editable install with tests):

```bash
uv pip install -e '.[test]'
```

Ensure BigQuery access is configured via environment variables before running
`aou-createphenodb`:

- `GOOGLE_PROJECT`
- `WORKSPACE_CDR`
- `WORKSPACE_BUCKET` (for gsutil access, if needed)

## Notes

This repo follows the universe-first case/control flow described in
`AllOfUs_Phenotypes_CC.md`.
