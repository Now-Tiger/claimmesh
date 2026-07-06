#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# backend/schemas/customer.py
from __future__ import annotations

from pydantic import BaseModel


class TopCustomerItem(BaseModel):
    customer_id: str
    name: str
    city: str
    state: str
    is_potential_fraud: bool
    total_payout: float
    claim_count: int


class TopCustomersResponse(BaseModel):
    items: list[TopCustomerItem]
