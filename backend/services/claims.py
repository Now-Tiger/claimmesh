#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Claim, Customer, Policy
from schemas.claim import (
    ClaimDetailResponse,
    ClaimSearchItem,
    ClaimSearchResponse,
    CustomerInfo,
    PolicyInfo,
)


async def get_claim_details_service(*, db: AsyncSession, claim_id: str) -> ClaimDetailResponse:
    """
    Fetch a claim along with its associated customer and policy.
    """

    res = await (
        db.execute(
            select(Claim, Policy, Customer)
            .join(Policy, Claim.policy_id == Policy.policy_id)
            .join(Customer, Policy.customer_id == Customer.customer_id)
            .where(Claim.claim_id == claim_id)
        ) 
    )

    row = res.one_or_none()

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Claim not found: {claim_id}")

    claim, policy, customer = row

    return ClaimDetailResponse(
        claim_id=claim.claim_id,
        loss_date=claim.loss_date,
        loss_amount=float(claim.loss_amount),
        cause=claim.cause,
        status=claim.status,
        rejection_reason=claim.rejection_reason,
        payout_amount=float(claim.payout_amount)
        if claim.payout_amount is not None
        else None,
        customer=CustomerInfo(
            customer_id=customer.customer_id,
            name=customer.name,
            age=customer.age,
            city=customer.city,
            state=customer.state,
            is_potential_fraud=customer.is_potential_fraud,
        ),
        policy=PolicyInfo(
            policy_id=policy.policy_id,
            policy_issue_date=policy.policy_issue_date,
            coverage_limit=float(policy.coverage_limit),
            deductible=float(policy.deductible),
            state=policy.state,
        ),
    )


async def search_claims_service(
    *,
    db: AsyncSession,
    city: Optional[str],
    state: Optional[str],
    cause: Optional[str],
    date_from: Optional[date],
    date_to: Optional[date],
    min_payout: Optional[float],
    max_payout: Optional[float],
    sort_by: str,
    sort_order: str,
    limit: int,
    offset: int,
) -> ClaimSearchResponse:
    """
    Search claims with filtering, sorting and pagination.
    """

    query = (
        select(Claim, Customer)
        .join(Policy, Claim.policy_id == Policy.policy_id)
        .join(Customer, Policy.customer_id == Customer.customer_id)
    )

    if city:
        query = query.where(Customer.city.ilike(city))

    if state:
        query = query.where(Customer.state == state.upper())

    if cause:
        query = query.where(Claim.cause.ilike(cause))

    if date_from:
        query = query.where(Claim.loss_date >= date_from)

    if date_to:
        query = query.where(Claim.loss_date <= date_to)

    if min_payout is not None:
        query = query.where(Claim.payout_amount >= min_payout)

    if max_payout is not None:
        query = query.where(Claim.payout_amount <= max_payout)

    sort_columns = {
        "loss_date": Claim.loss_date,
        "loss_amount": Claim.loss_amount,
        "payout_amount": Claim.payout_amount,
    }

    sort_column = sort_columns.get(sort_by, Claim.loss_date)

    query = query.order_by(sort_column.asc() if sort_order.lower() == "asc" else sort_column.desc())

    result = await db.execute(select(func.count()).select_from(query.subquery()))
    total  = result.scalar_one()

    res  = await db.execute(query.limit(limit).offset(offset))
    rows = res.all()

    items = [
        ClaimSearchItem(
            claim_id=claim.claim_id,
            policy_id=claim.policy_id,
            customer_id=customer.customer_id,
            city=customer.city,
            state=customer.state,
            cause=claim.cause,
            loss_date=claim.loss_date,
            loss_amount=float(claim.loss_amount),
            payout_amount=float(claim.payout_amount)
            if claim.payout_amount is not None
            else None,
            status=claim.status,
        )
        for claim, customer in rows
    ]

    return ClaimSearchResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=items,
    )
