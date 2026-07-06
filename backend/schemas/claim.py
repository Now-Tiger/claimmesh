#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# backend/schemas/claim.py
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class CustomerInfo(BaseModel):
    customer_id: str
    name: str
    age: int
    city: str
    state: str
    is_potential_fraud: bool


class PolicyInfo(BaseModel):
    policy_id: str
    policy_issue_date: date
    coverage_limit: float
    deductible: float
    state: str


class ClaimDetailResponse(BaseModel):
    claim_id: str
    loss_date: date
    loss_amount: float
    cause: str
    status: str
    rejection_reason: Optional[str] = None
    payout_amount: Optional[float] = Field(None, description="Null when the claim was rejected")
    customer: CustomerInfo
    policy: PolicyInfo


class ClaimSearchItem(BaseModel):
    claim_id: str
    policy_id: str
    customer_id: str
    city: str
    state: str
    cause: str
    loss_date: date
    loss_amount: float
    payout_amount: Optional[float] = None
    status: str


class ClaimSearchResponse(BaseModel):
    total: int = Field(..., description="Total matching rows across all pages")
    limit: int
    offset: int
    items: list[ClaimSearchItem]
