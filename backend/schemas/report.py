#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# backend/schemas/report.py
from __future__ import annotations

from pydantic import BaseModel


class StateReportItem(BaseModel):
    state: str
    total_claims: int
    average_payout: float
    max_payout: float
    total_payout: float


class StateReportResponse(BaseModel):
    items: list[StateReportItem]
