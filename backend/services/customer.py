#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# backend/services/customer.py
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.customer import TopCustomerItem, TopCustomersResponse


TOP_CUSTOMERS_SQL = text(
    """
    SELECT
        c.customer_id,
        c.name,
        c.city,
        c.state,
        c.is_potential_fraud,
        COALESCE(SUM(cl.payout_amount), 0) AS total_payout,
        COUNT(cl.claim_id) AS claim_count
    FROM customers c
    JOIN policies p
        ON p.customer_id = c.customer_id
    JOIN claims cl
        ON cl.policy_id = p.policy_id
       AND cl.status = 'valid'
    GROUP BY
        c.customer_id,
        c.name,
        c.city,
        c.state,
        c.is_potential_fraud
    ORDER BY total_payout DESC
    LIMIT :n
    """
)


async def get_top_customers_service(*, db: AsyncSession, n: int) -> TopCustomersResponse:
    """
    Return the customers ranked by the highest cumulative payout
    across all valid claims.
    """

    res  = await db.execute(TOP_CUSTOMERS_SQL, {"n": n})
    rows = res.all()

    items = [
        TopCustomerItem(
            customer_id=row.customer_id,
            name=row.name,
            city=row.city,
            state=row.state,
            is_potential_fraud=row.is_potential_fraud,
            total_payout=float(row.total_payout),
            claim_count=row.claim_count,
        )
        for row in rows
    ]

    return TopCustomersResponse(items=items)
