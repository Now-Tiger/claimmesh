#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# backend/services/payout.py
"""
Payout Calculation Engine — canonical formula (ClaimMesh roadmap Section 5, rules 4-6-7-9-10).

Applied in this exact order once a claim has passed the reject checks (rules 1-3, 5, 10):

    1. effective_deductible = deductible * 1.10   if cause == 'Flood' and policy.state == 'CA'
                             = deductible          otherwise                          (Rule 7)
    2. payout = max(0, loss_amount - effective_deductible)                            (pre-cap)
    3. payout = min(payout, coverage_limit)                                           (Rule 4)
    4. payout = payout * 0.5                       if customer.age < 18               (Rule 6)
    5. payout = max(0, payout)                                                        (Rule 5, floor)

This module is intentionally framework-free (no FastAPI/Celery/SQLAlchemy imports) so it can be
imported unchanged from both the `backend` service and the `worker` service.
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
    """
    Compute the final payout for a single claim. Returns a value rounded to 2 decimal places,
    guaranteed to be >= 0 and <= coverage_limit.
    """
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
