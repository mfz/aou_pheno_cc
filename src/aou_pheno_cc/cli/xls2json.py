#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


REQUIRED_COLUMNS = [
    "phenotype_id",
    "phenotype_name",
]

OPTIONAL_COLUMNS = [
    "universe.cond",
    "universe.cond.icd",
    "universe.proc",
    "universe.excl.cond",
    "universe.excl.cond.icd",
    "universe.excl.proc",
    "case.cond",
    "case.cond.icd",
    "case.proc",
    "case.excl.cond",
    "case.excl.cond.icd",
    "case.excl.proc",
    "case.min.age",
    "case.max.age",
    "ctrl.excl.cond",
    "ctrl.excl.cond.icd",
    "ctrl.excl.proc",
]

ALLOWED_COLUMNS = set(REQUIRED_COLUMNS) | set(OPTIONAL_COLUMNS)

CONCEPT_LIST_COLUMNS = {
    "universe.cond",
    "universe.proc",
    "universe.excl.cond",
    "universe.excl.proc",
    "case.cond",
    "case.proc",
    "case.excl.cond",
    "case.excl.proc",
    "ctrl.excl.cond",
    "ctrl.excl.proc",
}

ICD_LIST_COLUMNS = {
    "universe.cond.icd",
    "universe.excl.cond.icd",
    "case.cond.icd",
    "case.excl.cond.icd",
    "ctrl.excl.cond.icd",
}

AGE_COLUMNS = {"case.min.age", "case.max.age"}


def _normalize_cell(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    text = str(value).strip()
    return text if text else None


def _parse_concept_list(value: Any) -> List[int]:
    text = _normalize_cell(value)
    if text is None:
        return []
    parts = [p.strip() for p in text.split(",") if p.strip()]
    ids: List[int] = []
    for part in parts:
        if not part.isdigit():
            raise ValueError(
                f"Invalid concept id '{part}'. Only numeric OMOP concept IDs are supported."
            )
        ids.append(int(part))
    return ids


def _parse_icd_list(value: Any) -> List[str]:
    text = _normalize_cell(value)
    if text is None:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def _parse_age(value: Any) -> Optional[float]:
    text = _normalize_cell(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"Invalid age value '{text}'") from exc


def _row_to_record(row: pd.Series) -> Dict[str, Any]:
    record: Dict[str, Any] = {}
    for col in REQUIRED_COLUMNS + OPTIONAL_COLUMNS:
        if col in CONCEPT_LIST_COLUMNS:
            record[col] = _parse_concept_list(row.get(col))
        elif col in ICD_LIST_COLUMNS:
            record[col] = _parse_icd_list(row.get(col))
        elif col in AGE_COLUMNS:
            record[col] = _parse_age(row.get(col))
        else:
            record[col] = _normalize_cell(row.get(col))
    if not record["phenotype_id"]:
        raise ValueError("Missing phenotype_id")
    if not record["phenotype_name"]:
        raise ValueError(f"Missing phenotype_name for {record['phenotype_id']}")
    if not (record["case.cond"] or record["case.cond.icd"]):
        raise ValueError(
            f"Missing case.cond or case.cond.icd for {record['phenotype_id']}"
        )
    return record


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert phenotype definition Excel file to JSONL."
    )
    parser.add_argument("input", help="Path to .xlsx file")
    parser.add_argument(
        "-s",
        "--sheet",
        default=0,
        help="Sheet name or index (default: 0)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output .jsonl path (default: input filename with .jsonl)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input not found: {input_path}")

    sheet = args.sheet
    if isinstance(sheet, str) and sheet.isdigit():
        sheet = int(sheet)

    df = pd.read_excel(input_path, sheet_name=sheet, engine="openpyxl")

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    extra = [col for col in df.columns if col not in ALLOWED_COLUMNS]
    if extra:
        raise ValueError(f"Unknown columns: {', '.join(extra)}")

    output_path = Path(args.output) if args.output else input_path.with_suffix(".jsonl")

    with output_path.open("w", encoding="utf-8") as handle:
        for _, row in df.iterrows():
            if pd.isna(row.get("phenotype_id")) and pd.isna(row.get("phenotype_name")):
                continue
            record = _row_to_record(row)
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
