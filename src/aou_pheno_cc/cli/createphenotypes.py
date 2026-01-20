#!/usr/bin/env python3
import argparse
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import pandas as pd


@dataclass
class PhenotypeDef:
    phenotype_id: str
    phenotype_name: str
    universe_cond: List[int]
    universe_proc: List[int]
    universe_excl_cond: List[int]
    universe_excl_proc: List[int]
    case_cond: List[int]
    case_proc: List[int]
    case_excl_cond: List[int]
    case_excl_proc: List[int]
    case_min_age: Optional[float]
    case_max_age: Optional[float]
    ctrl_excl_cond: List[int]
    ctrl_excl_proc: List[int]


def _read_jsonl(path: Path) -> List[PhenotypeDef]:
    phenos: List[PhenotypeDef] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            data = json.loads(line)
            phenos.append(
                PhenotypeDef(
                    phenotype_id=str(data["phenotype_id"]),
                    phenotype_name=str(data["phenotype_name"]),
                    universe_cond=data.get("universe.cond", []),
                    universe_proc=data.get("universe.proc", []),
                    universe_excl_cond=data.get("universe.excl.cond", []),
                    universe_excl_proc=data.get("universe.excl.proc", []),
                    case_cond=data.get("case.cond", []),
                    case_proc=data.get("case.proc", []),
                    case_excl_cond=data.get("case.excl.cond", []),
                    case_excl_proc=data.get("case.excl.proc", []),
                    case_min_age=data.get("case.min.age"),
                    case_max_age=data.get("case.max.age"),
                    ctrl_excl_cond=data.get("ctrl.excl.cond", []),
                    ctrl_excl_proc=data.get("ctrl.excl.proc", []),
                )
            )
    return phenos


def _fetchall_set(cur: sqlite3.Cursor) -> Set[int]:
    return {row[0] for row in cur.fetchall()}


def _descendants(cur: sqlite3.Cursor, table: str, concept_ids: Sequence[int]) -> List[int]:
    if not concept_ids:
        return []
    placeholders = ",".join(["?"] * len(concept_ids))
    sql = f"SELECT descendant_concept_id FROM {table} WHERE ancestor_concept_id IN ({placeholders})"
    cur.execute(sql, list(concept_ids))
    return [row[0] for row in cur.fetchall()]


def _occurrence(
    cur: sqlite3.Cursor,
    table: str,
    concept_ids: Sequence[int],
    date_col: str,
    descendant_table: str,
) -> pd.DataFrame:
    if not concept_ids:
        return pd.DataFrame(columns=["person_id", "min_date", "max_date", "min_age", "max_age", "n_dates"])

    keys = set(concept_ids)
    keys.update(_descendants(cur, descendant_table, concept_ids))
    if not keys:
        return pd.DataFrame(columns=["person_id", "min_date", "max_date", "min_age", "max_age", "n_dates"])

    placeholders = ",".join(["?"] * len(keys))
    sql = (
        f"SELECT person_id, {date_col} FROM {table} "
        f"WHERE {table.split('_')[0]}_concept_id IN ({placeholders})"
    )
    cur.execute(sql, list(keys))
    rows = cur.fetchall()
    if not rows:
        return pd.DataFrame(columns=["person_id", "min_date", "max_date", "min_age", "max_age", "n_dates"])

    df = pd.DataFrame(rows, columns=["person_id", "date"])
    df["date"] = pd.to_datetime(df["date"])

    demo = pd.read_sql_query("SELECT person_id, dob FROM demographics", cur.connection)
    demo["dob"] = pd.to_datetime(demo["dob"])

    grouped = (
        df.dropna()
        .groupby(["person_id", "date"], as_index=False)
        .size()
        .groupby("person_id")
        .agg(min_date=("date", "min"), max_date=("date", "max"), n_dates=("size", "count"))
        .reset_index()
    )
    merged = grouped.merge(demo, on="person_id", how="left")
    merged["min_age"] = (merged["min_date"] - merged["dob"]).dt.days / 365.25
    merged["max_age"] = (merged["max_date"] - merged["dob"]).dt.days / 365.25
    return merged[["person_id", "min_date", "max_date", "min_age", "max_age", "n_dates"]]


def _universe(cur: sqlite3.Cursor) -> Set[int]:
    sql = (
        "SELECT person_id FROM demographics "
        "WHERE sex_at_birth IN ('Male','Female') "
        "AND has_srwgs = 1 AND has_ehr_data = 1 "
        "AND ancestry_pred IS NOT NULL"
    )
    cur.execute(sql)
    return _fetchall_set(cur)


def _apply_universe_filters(
    cur: sqlite3.Cursor,
    universe: Set[int],
    cond: Sequence[int],
    proc: Sequence[int],
    excl_cond: Sequence[int],
    excl_proc: Sequence[int],
) -> Set[int]:
    if not (cond or proc or excl_cond or excl_proc):
        return universe

    if cond:
        co = _occurrence(cur, "condition_occurrence", cond, "condition_start_date", "condition_descendants")
        universe = universe.intersection(set(co["person_id"]))
    if proc:
        po = _occurrence(cur, "procedure_occurrence", proc, "procedure_date", "procedure_descendants")
        universe = universe.intersection(set(po["person_id"]))

    if excl_cond:
        co_ex = _occurrence(cur, "condition_occurrence", excl_cond, "condition_start_date", "condition_descendants")
        universe = universe.difference(set(co_ex["person_id"]))
    if excl_proc:
        po_ex = _occurrence(cur, "procedure_occurrence", excl_proc, "procedure_date", "procedure_descendants")
        universe = universe.difference(set(po_ex["person_id"]))

    return universe


def _get_case_control(
    cur: sqlite3.Cursor,
    universe: Set[int],
    pheno: PhenotypeDef,
) -> Tuple[Set[int], Set[int]]:
    co = _occurrence(cur, "condition_occurrence", pheno.case_cond, "condition_start_date", "condition_descendants")
    po = _occurrence(cur, "procedure_occurrence", pheno.case_proc, "procedure_date", "procedure_descendants")

    case_ids = set(co["person_id"]).union(set(po["person_id"]))
    cases_0 = universe.intersection(case_ids)
    controls_0 = universe.difference(cases_0)

    frames = [frame for frame in (co, po) if not frame.empty]
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not combined.empty:
        combined = (
            combined.groupby("person_id", as_index=False)
            .agg(age_at_first_diagnosis=("min_age", "min"))
        )
        min_age = pheno.case_min_age if pheno.case_min_age is not None else 0.0
        max_age = pheno.case_max_age if pheno.case_max_age is not None else float("inf")
        age_ok = combined[
            (combined["age_at_first_diagnosis"] >= min_age)
            & (combined["age_at_first_diagnosis"] <= max_age)
        ]
        cases_age = set(age_ok["person_id"])
    else:
        cases_age = set()

    cases = universe.intersection(cases_age)

    if pheno.case_excl_cond:
        co_ex = _occurrence(
            cur,
            "condition_occurrence",
            pheno.case_excl_cond,
            "condition_start_date",
            "condition_descendants",
        )
        cases = cases.difference(set(co_ex["person_id"]))
    if pheno.case_excl_proc:
        po_ex = _occurrence(
            cur,
            "procedure_occurrence",
            pheno.case_excl_proc,
            "procedure_date",
            "procedure_descendants",
        )
        cases = cases.difference(set(po_ex["person_id"]))

    controls = controls_0
    if pheno.ctrl_excl_cond:
        co_ex = _occurrence(
            cur,
            "condition_occurrence",
            pheno.ctrl_excl_cond,
            "condition_start_date",
            "condition_descendants",
        )
        controls = controls.difference(set(co_ex["person_id"]))
    if pheno.ctrl_excl_proc:
        po_ex = _occurrence(
            cur,
            "procedure_occurrence",
            pheno.ctrl_excl_proc,
            "procedure_date",
            "procedure_descendants",
        )
        controls = controls.difference(set(po_ex["person_id"]))

    return cases, controls


def _add_pheno_column(df: pd.DataFrame, cases: Set[int], controls: Set[int], label: str) -> pd.DataFrame:
    df[label] = pd.Series(pd.NA, index=df.index, dtype="Int64")
    df.loc[df["person_id"].isin(cases), label] = 1
    df.loc[df["person_id"].isin(controls), label] = 0
    return df


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create case/control phenotype matrix from JSONL and OMOP.db."
    )
    parser.add_argument("phenotypes", help="Phenotype definitions JSONL")
    parser.add_argument("--sqlite", required=True, help="Path to OMOP.db")
    parser.add_argument(
        "--output",
        default=None,
        help="Output TSV path (default: <phenotypes>.tsv)",
    )
    parser.add_argument(
        "--counts",
        default=None,
        help="Counts TSV path (default: <phenotypes>_counts.tsv)",
    )
    args = parser.parse_args()

    phenotypes_path = Path(args.phenotypes)
    phenos = _read_jsonl(phenotypes_path)
    if not phenos:
        raise SystemExit("No phenotypes found in JSONL")

    con = sqlite3.connect(args.sqlite)
    try:
        cur = con.cursor()
        base_universe = _universe(cur)

        df = pd.DataFrame({"person_id": sorted(base_universe)})
        demo = pd.read_sql_query(
            "SELECT person_id, ancestry_pred FROM demographics",
            con,
        )
        demo = demo[demo["person_id"].isin(base_universe)]
        demo["ancestry_pred"] = demo["ancestry_pred"].fillna("NA").astype(str)
        ancestry_df = df.merge(demo, on="person_id", how="left")
        ancestry_df["ancestry"] = ancestry_df["ancestry_pred"].fillna("NA")
        ancestry_df = ancestry_df[["person_id", "ancestry"]]
        counts_rows: List[Dict[str, object]] = []

        for pheno in phenos:
            universe = _apply_universe_filters(
                cur,
                base_universe,
                pheno.universe_cond,
                pheno.universe_proc,
                pheno.universe_excl_cond,
                pheno.universe_excl_proc,
            )
            cases, controls = _get_case_control(cur, universe, pheno)
            df = _add_pheno_column(df, cases, controls, pheno.phenotype_id)
            case_counts = ancestry_df[ancestry_df["person_id"].isin(cases)].groupby("ancestry").size()
            control_counts = ancestry_df[ancestry_df["person_id"].isin(controls)].groupby("ancestry").size()
            ancestries = sorted(set(case_counts.index).union(control_counts.index))
            for ancestry in ancestries:
                ncases = int(case_counts.get(ancestry, 0))
                ncontrols = int(control_counts.get(ancestry, 0))
                counts_rows.append(
                    {
                        "phenotype_id": pheno.phenotype_id,
                        "ancestry": ancestry,
                        "ncases": "<20" if ncases < 20 else ncases,
                        "ncontrols": "<20" if ncontrols < 20 else ncontrols,
                    }
                )
    finally:
        con.close()

    output_path = Path(args.output) if args.output else phenotypes_path.with_suffix(".tsv")
    df.to_csv(output_path, sep="\t", index=False, na_rep="NA")
    counts_path = (
        Path(args.counts)
        if args.counts
        else phenotypes_path.with_name(f"{phenotypes_path.stem}_counts.tsv")
    )
    counts_df = pd.DataFrame(counts_rows, columns=["phenotype_id", "ancestry", "ncases", "ncontrols"])
    counts_df.to_csv(counts_path, sep="\t", index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
