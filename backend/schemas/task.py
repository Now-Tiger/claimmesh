# backend/schemas/task.py
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class UploadAcceptedResponse(BaseModel):
    """Returned by POST /upload when sync=false (default)."""

    task_id: str = Field(..., description="Celery task id for the enqueued upload batch")
    status_url: str = Field(..., description="Polling URL to check task status")


class DatasetSummary(BaseModel):
    total_records: int = Field(..., description="Rows found in this dataset's CSV")
    inserted: int = Field(..., description="Rows written to the database for this dataset")
    rejected: int = Field(..., description="Rows that could not be written at all for this dataset")


class UploadResult(BaseModel):
    """
    Returned by POST /upload when sync=true, and nested inside TaskStatusResponse.result once a task finishes.
    """

    total_records: int = Field(..., description="Total rows across all three files")
    inserted: int = Field(..., description="Rows successfully written to the database (includes soft-rejected-status claims)")
    rejected: int = Field(..., description="Rows that could not be written to the database at all")
    errors: list[str] = Field(default_factory=list, description="Human-readable reasons for hard-rejected rows")
    datasets: dict[str, DatasetSummary] = Field(default_factory=dict, description="Per-dataset breakdown: customers, policies, claims")


class TaskStatusResponse(BaseModel):

    task_id: str
    state: str = Field(..., description="PENDING | STARTED | SUCCESS | FAILURE")
    result: Optional[UploadResult] = Field(None, description="Populated once state == SUCCESS")
    error: Optional[str] = Field(None, description="Populated once state == FAILURE")
