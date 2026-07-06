#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# backend/api/routers/reports.py
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from core.cache import cached
from schemas.report import StateReportItem, StateReportResponse

router = APIRouter(tags=["Reports"])

STATE_REPORT_SQL = text(
    """
    SELECT
        p.state AS state,
        COUNT(cl.claim_id) AS total_claims,
        COALESCE(AVG(cl.payout_amount), 0) AS average_payout,
        COALESCE(MAX(cl.payout_amount), 0) AS max_payout,
        COALESCE(SUM(cl.payout_amount), 0) AS total_payout
    FROM policies p
    JOIN claims cl ON cl.policy_id = p.policy_id AND cl.status = 'valid'
    GROUP BY p.state
    ORDER BY total_payout DESC
    """
)


@router.get(
    "/reports/state",
    response_model=StateReportResponse,
    summary="Get claims/payout aggregates broken down by policy state",
    response_description="Per-state totals: claim count, average/max/total payout",
)
@cached(ttl=60)
async def get_state_report(request: Request, db: AsyncSession = Depends(get_db)):
    """Aggregate **valid** claims by the state of the underlying policy: total claim count,
    average payout, maximum payout, and total payout.

    Implemented as a raw SQL query (per the raw-SQL requirement).
    """
    res  = await db.execute(STATE_REPORT_SQL)
    rows = res.all()

    items = [
        StateReportItem(
            state=row.state,
            total_claims=row.total_claims,
            average_payout=float(row.average_payout),
            max_payout=float(row.max_payout),
            total_payout=float(row.total_payout),
        )
        for row in rows
    ]

    return StateReportResponse(items=items)
