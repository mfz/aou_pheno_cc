# Simplified Case–Control Phenotype Specification

## 1. Scope and Purpose

This specification defines a **restricted, case–control phenotype framework** for use with OMOP Common Data Model data in the All of Us Research Program. The framework is optimized for GWAS and large-scale analyses, prioritizing clarity, auditability, and ease of adoption over full clinical expressiveness.

The specification intentionally supports a limited subset of cohort logic and is **not intended to replace ATLAS/CIRCE cohort definitions**.

---

## 2. Data Requirements (Universe)

A subject is eligible for analysis (i.e., part of the **universe**) if all of the following are available:

* Short-read whole genome sequencing (srWGS) data
* Electronic health record (EHR) data mapped to OMOP CDM
* Ancestry assignment suitable for GWAS

Only subjects in the universe are considered for case or control classification.

Optional universe-level clinical constraints may be applied using inclusion and exclusion lists (see Section 4).

---

## 3. Vocabulary and Coding Conventions

### 3.1 Conditions

* Conditions are specified as OMOP concept ids.
* Alternatively, condition codes may be specified using ICD9/10 codes in the optional `.cond.icd` columns; these are mapped to OMOP condition concepts at runtime.


### 3.2 Procedures

* OMOP does not provide complete cross-vocabulary mappings for procedures.
* Procedures **must therefore be specified explicitly in all relevant OMOP vocabularies (as OMOP concept ids)** (e.g., CPT4, HCPCS, ICD9Proc, ICD10PCS, SNOMED).
* No automatic mapping across procedure vocabularies is assumed.

All procedure definitions consist of flat lists of OMOP procedure concept IDs, potentially spanning multiple vocabularies.

---

## 4. Phenotype Components

Each phenotype is defined using the following components. All concept lists are interpreted as **logical OR** (i.e., at least one occurrence satisfies the criterion).

### 4.1 Universe-Level Constraints (Optional)

* `universe.cond`: conditions required for universe inclusion
* `universe.proc`: procedures required for universe inclusion
* `universe.excl.cond`: conditions excluding subjects from the universe
* `universe.excl.proc`: procedures excluding subjects from the universe
* `universe.min.age`, `universe.max.age`: age constraints applied at first qualifying event

### 4.2 Case Definition

* `case.cond`: condition concepts defining case status
* `case.proc`: procedure concepts defining case status
* `case.excl.cond`: conditions excluding subjects from cases
* `case.excl.proc`: procedures excluding subjects from cases
* `case.min.age`: minimum age at first qualifying diagnosis or procedure
* `case.max.age`: maximum age at first qualifying diagnosis or procedure

A subject is classified as a **case** if they have at least one occurrence of any concept in `case.cond` **or** `case.proc`, satisfy the age constraints, and do not meet any case exclusion criteria.

### 4.3 Control Definition

* `ctrl.excl.cond`: conditions excluding subjects from controls
* `ctrl.excl.proc`: procedures excluding subjects from controls

Controls are defined in two steps. First, the **control candidate set** is constructed as the universe minus subjects who meet `case.cond` or `case.proc` (prior to any case age or case exclusion filtering). Second, control exclusion criteria (`ctrl.excl.cond`, `ctrl.excl.proc`) are applied to this candidate set.

---

## 5. Execution Flow

Phenotype assignment proceeds in the following order:

1. Construct the universe of eligible subjects.
2. Identify candidate cases based on `case.cond` and `case.proc`.
3. Construct the control candidate set as the universe minus subjects meeting `case.cond` or `case.proc`.
4. Apply case age constraints using age at first qualifying diagnosis or procedure.
5. Exclude cases meeting `case.excl.cond` or `case.excl.proc`.
6. Exclude controls meeting `ctrl.excl.cond` or `ctrl.excl.proc`.

---

## 6. Explicit Limitations (Out of Scope)

The following are intentionally not supported:

* Temporal sequencing of events
* Minimum or maximum occurrence counts
* Time windows relative to index events
* Washout periods
* Recurrent-event logic
* Nested Boolean logic beyond OR-based inclusion/exclusion

---

## 7. Intended Use

This framework is intended for:

* GWAS and case–control analyses
* High-throughput phenotype generation
* Transparent review by non-informatician stakeholders

It is not intended for detailed clinical cohort construction or regulatory-grade phenotyping.

---

# Reference Excel Template

Each row defines one phenotype. Concept ID columns contain comma-separated OMOP concept IDs.

| Column Name        | Description                             |
| ------------------ | --------------------------------------- |
| phenotype_id       | Unique phenotype identifier             |
| phenotype_name     | Human-readable phenotype name           |
| universe.cond      | Inclusion condition concept IDs         |
| universe.cond.icd  | Inclusion condition ICD9/10 codes       |
| universe.proc      | Inclusion procedure concept IDs         |
| universe.excl.cond | Exclusion condition concept IDs         |
| universe.excl.cond.icd | Exclusion condition ICD9/10 codes   |
| universe.excl.proc | Exclusion procedure concept IDs         |
| universe.min.age   | Minimum age for universe eligibility    |
| universe.max.age   | Maximum age for universe eligibility    |
| case.cond          | Case-defining condition concept IDs     |
| case.cond.icd      | Case-defining ICD9/10 codes             |
| case.proc          | Case-defining procedure concept IDs     |
| case.excl.cond     | Case exclusion condition concept IDs    |
| case.excl.cond.icd | Case exclusion ICD9/10 codes            |
| case.excl.proc     | Case exclusion procedure concept IDs    |
| case.min.age       | Minimum age at first case event         |
| case.max.age       | Maximum age at first case event         |
| ctrl.excl.cond     | Control exclusion condition concept IDs |
| ctrl.excl.cond.icd | Control exclusion ICD9/10 codes         |
| ctrl.excl.proc     | Control exclusion procedure concept IDs |

### Notes

* Empty cells indicate no constraint.
* All concept lists are evaluated using OR semantics.
* ICD code lists are comma-separated ICD9/10 codes and are only supported for condition columns.
* Procedure concept lists may include multiple vocabularies.
