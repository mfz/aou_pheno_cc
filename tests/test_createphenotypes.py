import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from aou_pheno_cc.cli import createphenotypes


def _write_table(con: sqlite3.Connection, name: str, df: pd.DataFrame) -> None:
    df.to_sql(name, con, if_exists="replace", index=False)


def test_createphenotypes_simple(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "OMOP.db"
    con = sqlite3.connect(db_path)
    try:
        demographics = pd.DataFrame(
            {
                "person_id": [1, 2, 3, 4],
                "has_srwgs": [1, 1, 1, 0],
                "has_ehr_data": [1, 1, 1, 1],
                "dob": ["1980-01-01", "1970-01-01", "1980-01-01", "1985-01-01"],
                "age_at_consent": [30, 40, 30, 25],
                "sex_at_birth": ["Male", "Male", "Female", "Male"],
                "ancestry_pred": ["EUR", None, "AFR", "EUR"],
            }
        )
        _write_table(con, "demographics", demographics)

        condition_occurrence = pd.DataFrame(
            {
                "person_id": [1, 3],
                "condition_concept_id": [100, 100],
                "condition_start_date": ["2000-01-01", "2010-01-01"],
            }
        )
        _write_table(con, "condition_occurrence", condition_occurrence)

        procedure_occurrence = pd.DataFrame(
            {
                "person_id": [],
                "procedure_concept_id": [],
                "procedure_date": [],
            }
        )
        _write_table(con, "procedure_occurrence", procedure_occurrence)

        condition_descendants = pd.DataFrame(
            {
                "ancestor_concept_id": [999],
                "descendant_concept_id": [100],
                "descendant_name": ["dummy"],
            }
        )
        _write_table(con, "condition_descendants", condition_descendants)

        procedure_descendants = pd.DataFrame(
            {
                "ancestor_concept_id": [],
                "descendant_concept_id": [],
                "descendant_name": [],
            }
        )
        _write_table(con, "procedure_descendants", procedure_descendants)
    finally:
        con.commit()
        con.close()

    phenos = [
        {
            "phenotype_id": "ph1",
            "phenotype_name": "Test Pheno",
            "case.cond": [999],
            "case.proc": [],
            "case.excl.cond": [],
            "case.excl.proc": [],
            "case.min.age": 30,
            "case.max.age": 40,
            "ctrl.excl.cond": [],
            "ctrl.excl.proc": [],
            "universe.cond": [],
            "universe.proc": [],
            "universe.excl.cond": [],
            "universe.excl.proc": [],
        }
    ]
    jsonl_path = tmp_path / "phenos.jsonl"
    jsonl_path.write_text("\n".join(json.dumps(p) for p in phenos) + "\n")

    out_path = tmp_path / "out.tsv"
    monkeypatch.setattr(
        "sys.argv",
        [
            "createphenotypes",
            "--phenotypes",
            str(jsonl_path),
            "--sqlite",
            str(db_path),
            "--output",
            str(out_path),
        ],
    )
    assert createphenotypes.main() == 0

    df = pd.read_csv(out_path, sep="\t")
    assert set(df["person_id"]) == {1, 3}

    row1 = df[df["person_id"] == 1].iloc[0]
    row3 = df[df["person_id"] == 3].iloc[0]

    assert pd.isna(row1["ph1"])
    assert row3["ph1"] == 1
