#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# backend/api/router/customers
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from core.cache import cached
from schemas.customer import TopCustomersResponse
from services.customer import get_top_customers_service

router = APIRouter(tags=["Customers"])


@router.get(
    "/customers/top",
    response_model=TopCustomersResponse,
    summary="Get customers with the highest total payouts",
    response_description="Customers ranked by total payout, descending",
)
@cached(ttl=60)
async def get_top_customers(
    request: Request,
    n: int = Query(
        10,
        ge=1,
        le=1000,
        description="Number of top customers to return",
    ),
    db: AsyncSession = Depends(get_db),
):
    return await get_top_customers_service(db=db, n=n,)
