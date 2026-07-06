#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# backend/db/models.py
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class Customer(Base):

    __tablename__ = "customers"
    __table_args__ = (CheckConstraint("age >= 0 AND age <= 130", name="ck_customers_age_range"),)

    customer_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name:  Mapped[str] = mapped_column(String(255), nullable=False)
    age:   Mapped[int] = mapped_column(SmallInteger, nullable=False)
    city:  Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    is_potential_fraud: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    policies: Mapped[list["Policy"]] = relationship(back_populates="customer")


class Policy(Base):
    __tablename__ = "policies"
    __table_args__ = (
        CheckConstraint("coverage_limit >= 0", name="ck_policies_coverage_limit_nonneg"),
        CheckConstraint("deductible >= 0", name="ck_policies_deductible_nonneg"),
        Index("idx_policies_customer_id", "customer_id"),
    )

    policy_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(20), ForeignKey("customers.customer_id"), nullable=False)
    policy_issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    coverage_limit: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    deductible: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    customer: Mapped["Customer"] = relationship(back_populates="policies")
    claims: Mapped[list["Claim"]] = relationship(back_populates="policy")


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = (
        CheckConstraint("loss_amount >= 0", name="ck_claims_loss_amount_nonneg"),
        CheckConstraint("payout_amount >= 0", name="ck_claims_payout_amount_nonneg"),
        Index("idx_claims_policy_id", "policy_id"),
        Index("idx_claims_loss_date", "loss_date"),
        Index("idx_claims_cause", "cause"),
    )

    claim_id:  Mapped[str] = mapped_column(String(20), primary_key=True)
    policy_id: Mapped[str] = mapped_column(String(20), ForeignKey("policies.policy_id"), nullable=False)
    loss_date: Mapped[date] = mapped_column(Date, nullable=False)
    loss_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    cause: Mapped[str] = mapped_column(String(100), nullable=False)
    payout_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="valid", server_default="valid")
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    policy: Mapped["Policy"] = relationship(back_populates="claims")


class UploadAudit(Base):
    __tablename__ = "upload_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset: Mapped[str] = mapped_column(String(20), nullable=False)
    total_records: Mapped[int] = mapped_column(Integer, nullable=False)
    inserted: Mapped[int] = mapped_column(Integer, nullable=False)
    rejected: Mapped[int] = mapped_column(Integer, nullable=False)
    errors:  Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    celery_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
