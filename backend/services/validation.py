#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# backend/services/validation.py
"""
Pandas cleaning + business-rule validation pipeline (ClaimMesh roadmap Phase 4).

Each `clean_*` function takes a raw pandas DataFrame straight from `pd.read_csv` and returns
`(clean_df, errors)`:

- `clean_df` contains only rows that are safe to insert into the database (i.e. rows that would
  not violate a NOT NULL / CHECK / FOREIGN KEY / PRIMARY KEY constraint). For claims specifically,
  "safe to insert" includes rows that fail *soft* business rules (future loss date, loss date
  before policy issue date) — those are still inserted, but flagged with
  `status='rejected'` + `rejection_reason` so they remain queryable/auditable, per the claims
  table design in roadmap Section 4.

- `errors` is a flat list of human-readable strings describing every row that was dropped
  entirely (hard exclusions: unparseable data, duplicates, negative loss amount, missing
  customer/policy references).

Framework-free by design (no FastAPI/Celery/SQLAlchemy imports) so it can be reused unchanged
from both the `backend` service (sync pre-checks) and the `worker` service (actual processing).
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from services.payout import calculate_payout


def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Strip/lowercase/underscore-ify column names to tolerate messy source headers.
    """
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def _is_blank(value) -> bool:
    return value is None or str(value).strip() == "" or str(value).strip().lower() == "nan"


def clean_customers(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Clean & validate the customers dataset. 
    No soft-rejection concept here — a row is either
    insertable or it isn't.
    """
    errors: list[str] = []
    df = _standardize_columns(df)
    df = df.drop_duplicates()

    required_cols = {"customer_id", "name", "age", "city", "state"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"customer.csv is missing required columns: {sorted(missing)}")

    df = df.copy()
    for col in ("customer_id", "name", "city", "state"):
        df[col] = df[col].astype(str).str.strip()

    df["state"] = df["state"].str.upper()
    df["age_parsed"] = pd.to_numeric(df["age"], errors="coerce")

    keep_rows: list[dict] = []
    seen_ids: set[str] = set()

    for _, row in df.iterrows():
        cid, name, city, state = row["customer_id"], row["name"], row["city"], row["state"]
        age = row["age_parsed"]

        if _is_blank(cid):
            _ = errors.append("Missing Customer ID")
            continue

        if cid in seen_ids:
            _ = errors.append(f"Duplicate Customer ID: {cid}")
            continue

        if _is_blank(name):
            _ = errors.append(f"Missing name for customer {cid}")
            continue

        if pd.isna(age):
            _ = errors.append(f"Invalid age for customer {cid}")
            continue

        age = int(age)
        if age < 0 or age > 130:
            _ = errors.append(f"Age out of valid range for customer {cid}")
            continue

        if _is_blank(state) or len(state) != 2:
            _ = errors.append(f"Invalid state code for customer {cid}")
            continue

        if _is_blank(city):
            _ = errors.append(f"Missing city for customer {cid}")
            continue

        _ = seen_ids.add(cid)
        _ = keep_rows.append({"customer_id": cid, "name": name, "age": age, "city": city, "state": state})

    clean_df = pd.DataFrame(keep_rows, columns=["customer_id", "name", "age", "city", "state"])
    return clean_df, errors


def clean_policies(df: pd.DataFrame, known_customer_ids: set[str]) -> tuple[pd.DataFrame, list[str]]:
    """Clean & validate the policies dataset. Rule 10: reject policies referencing non-existing
    customers (checked against `known_customer_ids`, which should reflect the full customers
    table, not just this batch)."""
    errors: list[str] = []
    df = _standardize_columns(df)
    df = df.drop_duplicates()

    required_cols = {"policy_id", "customer_id", "policy_issue_date", "coverage_limit", "deductible", "state"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"policy.csv is missing required columns: {sorted(missing)}")

    df = df.copy()
    for col in ("policy_id", "customer_id", "state"):
        df[col] = df[col].astype(str).str.strip()
    df["state"] = df["state"].str.upper()
    df["policy_issue_date_parsed"] = pd.to_datetime(
        df["policy_issue_date"].astype(str).str.strip(), errors="coerce"
    ).dt.date
    df["coverage_limit_parsed"] = pd.to_numeric(df["coverage_limit"], errors="coerce")
    df["deductible_parsed"] = pd.to_numeric(df["deductible"], errors="coerce")

    keep_rows: list[dict] = []
    seen_ids: set[str] = set()

    for _, row in df.iterrows():
        pid, cid, state = row["policy_id"], row["customer_id"], row["state"]
        issue_date = row["policy_issue_date_parsed"]
        coverage_limit = row["coverage_limit_parsed"]
        deductible = row["deductible_parsed"]

        if _is_blank(pid):
            _ = errors.append("Missing Policy ID")
            continue

        if pid in seen_ids:
            _ = errors.append(f"Duplicate Policy ID: {pid}")
            continue

        if _is_blank(cid) or cid not in known_customer_ids:
            _ = errors.append(f"Customer not found: {cid} (policy {pid})")
            continue

        if pd.isna(issue_date):
            _ = errors.append(f"Invalid date for policy {pid}")
            continue

        if pd.isna(coverage_limit) or coverage_limit < 0:
            _ = errors.append(f"Invalid coverage limit for policy {pid}")
            continue

        if pd.isna(deductible) or deductible < 0:
            _ = errors.append(f"Invalid deductible for policy {pid}")
            continue

        if _is_blank(state) or len(state) != 2:
            _ = errors.append(f"Invalid state code for policy {pid}")
            continue

        _ = seen_ids.add(pid)
        _ = keep_rows.append(
            {
                "policy_id": pid,
                "customer_id": cid,
                "policy_issue_date": issue_date,
                "coverage_limit": float(coverage_limit),
                "deductible": float(deductible),
                "state": state,
            }
        )

    clean_df = pd.DataFrame(
        keep_rows,
        columns=[
            "policy_id",
            "customer_id",
            "policy_issue_date",
            "coverage_limit",
            "deductible",
            "state"
        ],
    )

    return clean_df, errors


def clean_claims(df: pd.DataFrame, known_policy_map: dict[str, dict]) -> tuple[pd.DataFrame, list[str]]:
    """
    Clean & validate the claims dataset and compute payouts for rows that pass all checks.

    `known_policy_map`: policy_id -> {coverage_limit, deductible, state, policy_issue_date, customer_age}

    Hard exclusions (row dropped entirely, would violate a DB constraint):
        - unparseable/missing claim_id, loss_date, or loss_amount
        - duplicate claim_id (keep first)
        - loss_amount < 0                                  (Rule 1 — CHECK constraint)
        - policy_id not found                               (Rule 10 analog — FK constraint)

    Soft rejections (row IS inserted, with status='rejected' + rejection_reason, payout_amount=None):
        - loss_date in the future                           (Rule 2)
        - loss_date earlier than the policy's issue date     (Rule 3)
    """
    errors: list[str] = []
    df = _standardize_columns(df)
    df = df.drop_duplicates()

    required_cols = {"claim_id", "policy_id", "loss_date", "loss_amount", "cause"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"claims.csv is missing required columns: {sorted(missing)}")

    df = df.copy()
    for col in ("claim_id", "policy_id", "cause"):
        df[col] = df[col].astype(str).str.strip()

    df["loss_date_parsed"] = pd.to_datetime(df["loss_date"].astype(str).str.strip(), errors="coerce").dt.date
    df["loss_amount_parsed"] = pd.to_numeric(df["loss_amount"], errors="coerce")

    keep_rows: list[dict] = []
    seen_claim_ids: set[str] = set()
    today = date.today()

    for _, row in df.iterrows():
        claim_id, policy_id, cause = row["claim_id"], row["policy_id"], row["cause"]
        loss_date = row["loss_date_parsed"]
        loss_amount = row["loss_amount_parsed"]

        if _is_blank(claim_id):
            _ = errors.append("Missing Claim ID")
            continue

        if claim_id in seen_claim_ids:
            _ = errors.append(f"Duplicate Claim ID: {claim_id}")
            continue

        if pd.isna(loss_date):
            _ = errors.append(f"Invalid date for claim {claim_id}")
            continue
        if pd.isna(loss_amount):
            _ = errors.append(f"Invalid loss amount for claim {claim_id}")
            continue
        if loss_amount < 0:
            _ = errors.append(f"Loss amount cannot be negative: {claim_id}")
            continue
        if policy_id not in known_policy_map:
            _ = errors.append(f"Policy not found: {policy_id}")
            continue

        _ = seen_claim_ids.add(claim_id)
        policy_info = known_policy_map[policy_id]

        status = "valid"
        rejection_reason = None
        payout_amount = None

        if loss_date > today:
            status = "rejected"
            rejection_reason = "Loss date cannot be in the future"

        elif loss_date < policy_info["policy_issue_date"]:
            status = "rejected"
            rejection_reason = "Claim date earlier than policy issue date"

        else:
            payout_amount = calculate_payout(
                loss_amount=float(loss_amount),
                cause=cause,
                policy_state=policy_info["state"],
                deductible=float(policy_info["deductible"]),
                coverage_limit=float(policy_info["coverage_limit"]),
                customer_age=int(policy_info["customer_age"]),
            )

        _ = keep_rows.append(
            {
                "claim_id": claim_id,
                "policy_id": policy_id,
                "loss_date": loss_date,
                "loss_amount": float(loss_amount),
                "cause": cause,
                "payout_amount": payout_amount,
                "status": status,
                "rejection_reason": rejection_reason,
            }
        )

    clean_df = pd.DataFrame(
        keep_rows,
        columns=[
            "claim_id",
            "policy_id",
            "loss_date",
            "loss_amount",
            "cause",
            "payout_amount",
            "status",
            "rejection_reason",
        ],
    )

    return clean_df, errors
