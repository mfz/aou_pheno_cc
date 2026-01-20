# All of Us Case-Control Phenotype Principles

- Universe-first: restrict to subjects with srWGS, EHR, and ancestry data; all case/control logic is within this universe.
- Phenotypes: defined by inclusion/exclusion lists of OMOP concept IDs (conditions/procedures).
- Mapping: ICD9/10 can map to OMOP condition concepts; procedure IDs must be specified across all standard vocabularies (no cross-mapping).
- Flow: cases = universe ∩ (case.cond OR case.proc) → age filter → case exclusions; controls = remaining universe → control exclusions.
- Template: one row per phenotype with comma-separated concept IDs; empty cells mean no constraint; concept lists use OR semantics.
- Data access: OMOP in BigQuery on RAP; local indexed SQLite used for faster queries with demographics, concept mapping, descendants, and occurrence tables.
