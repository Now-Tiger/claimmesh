#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# backend/api/routers/upload.py
from __future__ import annotations

import base64
import io

import pandas as pd
from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile, status
from loguru import logger

from schemas.response import ErrorResponse
from schemas.task import TaskStatusResponse, UploadAcceptedResponse, UploadResult
from services import taskservice

router = APIRouter(tags=["Upload"])

REQUIRED_COLUMNS = {
    "customers": {"customer_id", "name", "age", "city", "state"},
    "policies":  {"policy_id", "customer_id", "policy_issue_date", "coverage_limit", "deductible", "state"},
    "claims":    {"claim_id", "policy_id", "loss_date", "loss_amount", "cause"},
}


def _check_required_columns(raw_bytes: bytes, dataset: str) -> None:
    """Fail fast with a 422 if a file is missing required columns, before enqueueing any work."""
    try:
        header_df = pd.read_csv(io.BytesIO(raw_bytes), nrows=0)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not parse {dataset} file as CSV: {exc}",
        ) from exc

    normalized_cols = {str(c).strip().lower().replace(" ", "_") for c in header_df.columns}
    missing = REQUIRED_COLUMNS[dataset] - normalized_cols
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{dataset} file is missing required columns: {sorted(missing)}",
        )


@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        200: {"model": UploadResult, "description": "Returned instead when sync=true"},
        202: {"model": UploadAcceptedResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    summary="Upload customers, policies, and claims CSVs for ingestion",
    response_description="Task id to poll (default) or the final ingestion summary (sync=true)",
)
async def upload_csvs(
    response: Response,
    customers: UploadFile = File(..., description="customer.csv"),
    policies: UploadFile = File(..., description="policy.csv"),
    claims: UploadFile = File(..., description="claims.csv"),
    sync: bool = Query(
        False,
        description="If true, block until processing finishes and return the final counts inline instead of a task id to poll.",
    ),
):
    """
    Ingest the three source CSVs (customers, policies, claims) into the database.

    - **customers/policies/claims**: multipart CSV file uploads.
    - **sync**: when `true`, the request blocks until the worker finishes and returns
      `{total_records, inserted, rejected, errors}` directly (`200`). Default is `false`,
      which returns a `task_id` immediately (`202 Accepted`) pollable via
      `GET /upload/{task_id}/status`.

    Processing order is always customers -> policies -> claims, since policies depend on
    customers and claims depend on policies for referential validation.
    """
    customers_bytes = await customers.read()
    policies_bytes = await policies.read()
    claims_bytes = await claims.read()

    _ = _check_required_columns(customers_bytes, "customers")
    _ = _check_required_columns(policies_bytes, "policies")
    _ = _check_required_columns(claims_bytes, "claims")

    customers_b64 = base64.b64encode(customers_bytes).decode("ascii")
    policies_b64 = base64.b64encode(policies_bytes).decode("ascii")
    claims_b64 = base64.b64encode(claims_bytes).decode("ascii")

    try:
        if sync:
            result = taskservice.get_upload_result_sync(customers_b64, policies_b64, claims_b64)
            response.status_code = status.HTTP_200_OK
            return result

        task_id = taskservice.enqueue_upload(customers_b64, policies_b64, claims_b64)
    except HTTPException:
        raise
    except Exception as exc:
        _ = logger.error(f"Failed to process/enqueue upload batch: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not reach the background processing service. Please try again shortly.",
        ) from exc

    return UploadAcceptedResponse(task_id=task_id, status_url=f"/upload/{task_id}/status")


@router.get(
    "/upload/{task_id}/status",
    response_model=TaskStatusResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Poll the status of a previously submitted upload task",
    response_description="Current task state and, if finished, the ingestion summary",
)
async def get_upload_status(task_id: str):
    """
    Poll a background upload task by id.

    - **state** will be one of `PENDING`, `STARTED`, `SUCCESS`, or `FAILURE`.
    - When `state` is `SUCCESS`, `result` contains the same shape as the synchronous
      `POST /upload?sync=true` response.
    """
    return taskservice.get_task_status(task_id)
