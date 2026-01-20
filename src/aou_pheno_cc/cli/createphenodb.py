#!/usr/bin/env python3
import argparse
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Optional

import pandas as pd

try:
    from google.cloud import bigquery
except Exception as exc:  # pragma: no cover - import error shown at runtime
    bigquery = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


ANCESTRY_DEFAULT = (
    "gs://fc-aou-datasets-controlled/v8/wgs/short_read/snpindel/aux/ancestry/"
    "ancestry_preds.tsv"
)


def _require_bigquery() -> None:
    if bigquery is None:
        raise RuntimeError(
            "google-cloud-bigquery is required for createphenodb. "
            "Install it or run in an environment that has it."
        ) from _IMPORT_ERROR


def _resolve_dataset(project: str, dataset: str) -> str:
    return dataset if "." in dataset else f"{project}.{dataset}"


def _sql_queries(dataset_fq: str) -> Dict[str, str]:
    return {
        "condition_occurrence": f"""
SELECT
    co.person_id,
    co.condition_concept_id,
    co.condition_start_date
FROM `{dataset_fq}.condition_occurrence` co
JOIN `{dataset_fq}.concept` c
    ON co.condition_concept_id = c.concept_id
WHERE c.domain_id = 'Condition'
  AND c.standard_concept = 'S'
""".strip(),
        "procedure_occurrence": f"""
SELECT
    po.person_id,
    po.procedure_concept_id,
    po.procedure_date
FROM `{dataset_fq}.procedure_occurrence` po
JOIN `{dataset_fq}.concept` c
    ON po.procedure_concept_id = c.concept_id
WHERE c.domain_id = 'Procedure'
  AND c.standard_concept = 'S'
""".strip(),
        "condition_descendants": f"""
SELECT
    ca.ancestor_concept_id,
    ca.descendant_concept_id,
    d.concept_name AS descendant_name
FROM `{dataset_fq}.concept_ancestor` ca
JOIN `{dataset_fq}.concept` a
    ON ca.ancestor_concept_id = a.concept_id
JOIN `{dataset_fq}.concept` d
    ON ca.descendant_concept_id = d.concept_id
WHERE a.domain_id = 'Condition'
  AND a.standard_concept = 'S'
  AND d.standard_concept = 'S'
  AND d.domain_id = 'Condition'
""".strip(),
        "procedure_descendants": f"""
SELECT
    ca.ancestor_concept_id,
    ca.descendant_concept_id,
    d.concept_name AS descendant_name
FROM `{dataset_fq}.concept_ancestor` ca
JOIN `{dataset_fq}.concept` a
    ON ca.ancestor_concept_id = a.concept_id
JOIN `{dataset_fq}.concept` d
    ON ca.descendant_concept_id = d.concept_id
WHERE a.domain_id = 'Procedure'
  AND a.standard_concept = 'S'
  AND d.standard_concept = 'S'
  AND d.domain_id = 'Procedure'
""".strip(),
        "icd2omop": f"""
SELECT
    icd.concept_id AS icd_concept_id,
    icd.concept_code AS icd_code,
    icd.concept_name AS icd_name,
    icd.vocabulary_id AS icd_vocabulary,
    omop.concept_id AS omop_concept_id,
    omop.vocabulary_id AS source_vocabulary,
    omop.concept_code AS source_code,
    omop.concept_name AS source_name
FROM `{dataset_fq}.concept` icd
JOIN `{dataset_fq}.concept_relationship` cr
    ON icd.concept_id = cr.concept_id_1
   AND cr.relationship_id = 'Maps to'
JOIN `{dataset_fq}.concept` omop
    ON cr.concept_id_2 = omop.concept_id
WHERE icd.vocabulary_id IN ('ICD9CM', 'ICD10CM')
  AND omop.standard_concept = 'S'
  AND omop.domain_id = 'Condition'
""".strip(),
        "demographics": f"""
SELECT
    person_id,
    has_whole_genome_variant AS has_srwgs,
    has_ehr_data,
    dob,
    age_at_consent,
    sex_at_birth
FROM `{dataset_fq}.cb_search_person`
""".strip(),
    }


def _query_to_frames(client: "bigquery.Client", sql: str) -> Iterable[pd.DataFrame]:
    job = client.query(sql)
    result = job.result()
    try:
        return result.to_dataframe_iterable()
    except AttributeError:
        return [result.to_dataframe()]


def _write_frames_to_sqlite(
    con: sqlite3.Connection,
    name: str,
    frames: Iterable[pd.DataFrame],
    tsv_path: Optional[Path] = None,
) -> None:
    first = True
    for frame in frames:
        if frame.empty:
            continue
        frame.to_sql(name, con, if_exists="replace" if first else "append", index=False)
        if tsv_path is not None:
            frame.to_csv(
                tsv_path,
                sep="\t",
                index=False,
                mode="w" if first else "a",
                header=first,
            )
        first = False


def _download_ancestry(ancestry_src: str, out_path: Path, project: str) -> Path:
    if ancestry_src.startswith("gs://"):
        gsutil = shutil.which("gsutil")
        if not gsutil:
            raise RuntimeError(
                "gsutil not found; provide a local --ancestry-tsv path."
            )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [gsutil, "-u", project, "cp", ancestry_src, str(out_path)],
            check=True,
        )
        return out_path

    src_path = Path(ancestry_src)
    if not src_path.exists():
        raise FileNotFoundError(f"Ancestry TSV not found: {ancestry_src}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if src_path.resolve() != out_path.resolve():
        shutil.copy2(src_path, out_path)
    return out_path


def _create_indexes(con: sqlite3.Connection) -> None:
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_co_cci ON condition_occurrence(condition_concept_id)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_po_pci ON procedure_occurrence(procedure_concept_id)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_cd_aci ON condition_descendants(ancestor_concept_id)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_pd_aci ON procedure_descendants(ancestor_concept_id)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_i2o_icdcode_voc ON icd2omop(icd_code, icd_vocabulary)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_demographics_pi ON demographics(person_id)"
    )


def _write_metadata(
    con: sqlite3.Connection,
    project: str,
    dataset_fq: str,
    ancestry_src: str,
) -> None:
    rows = [
        ("created_at_utc", datetime.now(timezone.utc).isoformat()),
        ("google_project", project),
        ("workspace_cdr", dataset_fq),
        ("ancestry_source", ancestry_src),
    ]
    con.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT, value TEXT)")
    con.execute("DELETE FROM metadata")
    con.executemany("INSERT INTO metadata (key, value) VALUES (?, ?)", rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Query All of Us OMOP tables via BigQuery and build a SQLite OMOP.db."
    )
    parser.add_argument(
        "--project",
        default=os.getenv("GOOGLE_PROJECT"),
        help="GCP project for billing (default: $GOOGLE_PROJECT)",
    )
    parser.add_argument(
        "--dataset",
        default=os.getenv("WORKSPACE_CDR"),
        help="BigQuery dataset (default: $WORKSPACE_CDR)",
    )
    parser.add_argument(
        "--out-dir",
        default="OMOP",
        help="Output directory for TSVs and OMOP.db (default: OMOP)",
    )
    parser.add_argument(
        "--sqlite-path",
        default=None,
        help="Path to OMOP.db (default: <out-dir>/OMOP.db)",
    )
    parser.add_argument(
        "--ancestry-tsv",
        default=os.getenv("ANCESTRY_TSV", ANCESTRY_DEFAULT),
        help="Local path or gs:// URI to ancestry TSV",
    )
    parser.add_argument(
        "--no-tsv",
        action="store_true",
        help="Skip writing TSV cache files",
    )

    args = parser.parse_args()

    if not args.project:
        raise SystemExit("Missing --project or $GOOGLE_PROJECT")
    if not args.dataset:
        raise SystemExit("Missing --dataset or $WORKSPACE_CDR")

    _require_bigquery()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path = Path(args.sqlite_path) if args.sqlite_path else out_dir / "OMOP.db"

    dataset_fq = _resolve_dataset(args.project, args.dataset)
    queries = _sql_queries(dataset_fq)

    client = bigquery.Client(project=args.project)

    con = sqlite3.connect(sqlite_path)
    try:
        ancestry_path = _download_ancestry(
            args.ancestry_tsv, out_dir / "ancestry.tsv", args.project
        )
        print(f"[createphenodb] loading ancestry from {ancestry_path}")
        ancestry = pd.read_csv(ancestry_path, sep="\t")
        ancestry = ancestry.rename(columns={"research_id": "person_id"})
        ancestry = ancestry[["person_id", "ancestry_pred"]]

        for name, sql in queries.items():
            print(f"[createphenodb] querying {name}...")
            frames = _query_to_frames(client, sql)
            tsv_path = None if args.no_tsv else out_dir / f"{name}.tsv"

            if name == "demographics":
                print("[createphenodb] merging ancestry into demographics")
                def _merged_iter():
                    for frame in frames:
                        if frame.empty:
                            continue
                        yield frame.merge(ancestry, on="person_id", how="left")

                frames = _merged_iter()

            print(f"[createphenodb] writing {name} to sqlite")
            _write_frames_to_sqlite(con, name, frames, tsv_path)

        _create_indexes(con)
        print("[createphenodb] creating indexes")
        _write_metadata(con, args.project, dataset_fq, args.ancestry_tsv)
        print(f"[createphenodb] done; sqlite at {sqlite_path}")
    finally:
        con.commit()
        con.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
