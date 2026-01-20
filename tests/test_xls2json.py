import json
from pathlib import Path

import pandas as pd
import pytest

from aou_pheno_cc.cli import xls2json


def test_xls2json_basic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = {
        "phenotype_id": ["ph1"],
        "phenotype_name": ["Phenotype 1"],
        "universe.cond": [""],
        "universe.proc": [None],
        "universe.excl.cond": [""],
        "universe.excl.proc": [""],
        "case.cond": ["100, 200"],
        "case.cond.icd": ["A01, B02"],
        "case.proc": [""],
        "case.excl.cond": [""],
        "case.excl.cond.icd": [""],
        "case.excl.proc": [""],
        "case.min.age": [30],
        "case.max.age": [40],
        "ctrl.excl.cond": [""],
        "ctrl.excl.cond.icd": [""],
        "ctrl.excl.proc": [""],
        "universe.cond.icd": [""],
        "universe.excl.cond.icd": [""],
    }
    df = pd.DataFrame(data)
    xlsx_path = tmp_path / "phenos.xlsx"
    df.to_excel(xlsx_path, index=False)

    out_path = tmp_path / "phenos.jsonl"
    monkeypatch.setattr(
        "sys.argv",
        ["xls2json", str(xlsx_path), "--output", str(out_path)],
    )
    assert xls2json.main() == 0

    lines = out_path.read_text().strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])

    assert record["phenotype_id"] == "ph1"
    assert record["phenotype_name"] == "Phenotype 1"
    assert record["case.cond"] == [100, 200]
    assert record["case.cond.icd"] == ["A01", "B02"]
    assert record["case.min.age"] == 30.0
    assert record["case.max.age"] == 40.0
    assert record["universe.cond"] == []
    assert record["universe.cond.icd"] == []
    assert record["case.proc"] == []
