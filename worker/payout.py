#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# worker/payout.py
"""
Mirrored from backend/services/payout.py so the worker service has no dependency on the
backend package (independent deployability). Keep these two files in sync manually, or extract
to a shared library if this grows further.
"""
from __future__ import annotations


FLOOD_CAUSE = "flood"
CA_STATE = "ca"
MINOR_AGE_THRESHOLD = 18
MINOR_PAYOUT_MULTIPLIER = 0.5
FLOOD_CA_DEDUCTIBLE_MULTIPLIER = 1.10


def calculate_payout(
    loss_amount: float,
    cause: str,
    policy_state: str,
    deductible: float,
    coverage_limit: float,
    customer_age: int,
) -> float:
    is_flood_in_ca = (
        str(cause).strip().lower() == FLOOD_CAUSE
        and
        str(policy_state).strip().lower() == CA_STATE
    )

    effective_deductible = deductible * FLOOD_CA_DEDUCTIBLE_MULTIPLIER if is_flood_in_ca else deductible

    payout = max(0.0, float(loss_amount) - float(effective_deductible))
    payout = min(payout, float(coverage_limit))

    if int(customer_age) < MINOR_AGE_THRESHOLD:
        payout = payout * MINOR_PAYOUT_MULTIPLIER

    payout = max(0.0, payout)
    return round(payout, 2)
