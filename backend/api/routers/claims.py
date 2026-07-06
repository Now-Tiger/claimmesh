#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# backend/api/router/claims.py
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from core.cache import cached
from schemas.claim import ClaimDetailResponse, ClaimSearchResponse
from schemas.response import ErrorResponse
from services.claims import get_claim_details_service, search_claims_service


router = APIRouter(tags=["Claims"])


@router.get(
    "/claims/{claim_id}",
    response_model=ClaimDetailResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get full details for a single claim",
    response_description="Claim, customer, and policy info plus the stored payout amount",
)
@cached(ttl=60)
async def get_claim_details(claim_id: str, request: Request, db: AsyncSession = Depends(get_db)) -> ClaimDetailResponse:
    """
    Fetch a claim along with its associated customer and policy.
    """
    return await get_claim_details_service(db=db, claim_id=claim_id)


@router.get(
    "/claims",
    response_model=ClaimSearchResponse,
    summary="Search and filter claims",
    response_description="Paginated list of claims matching the given filters",
)
@cached(ttl=60)
async def search_claims(
    request: Request,
    city: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    cause: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    min_payout: Optional[float] = Query(None),
    max_payout: Optional[float] = Query(None),
    sort_by: str = Query("loss_date"),
    sort_order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> ClaimSearchResponse:
    """
    Search claims with filtering, sorting and pagination.
    """
    return await search_claims_service(
        db=db,
        city=city,
        state=state,
        cause=cause,
        date_from=date_from,
        date_to=date_to,
        min_payout=min_payout,
        max_payout=max_payout,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )
