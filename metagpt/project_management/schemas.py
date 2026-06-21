"""Pydantic schemas for the project management web layer."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., description="Project name, supports Chinese.")
    start_date: date
    end_date: date
    duration: str = Field(..., description="Project duration label, generated from dates.")
    cycle_days: int = Field(..., ge=1)
    summary: str = Field(..., description="Project overview and requirements.")
    role_keys: List[str] = Field(default_factory=list)
    stage_keys: List[str] = Field(default_factory=list)


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    duration: Optional[str] = None
    cycle_days: Optional[int] = None
    summary: Optional[str] = None
    role_keys: Optional[List[str]] = None
    stage_keys: Optional[List[str]] = None


class ProjectRecordCreateRequest(BaseModel):
    stage_key: str
    record_type: str = Field(..., description="daily_progress, meeting_note, milestone, change_request, source_code, summary")
    title: str
    content: str
    assignee_role_key: Optional[str] = None
    occurred_at: Optional[datetime] = None


class ProjectRecordUpdateRequest(ProjectRecordCreateRequest):
    id: UUID


class ProjectStageDocRequest(BaseModel):
    id: Optional[UUID] = None
    stage_key: str
    document_key: str
    title: str
    description: str
    assignee_role_keys: List[str] = Field(default_factory=list)
    outline: List[str] = Field(default_factory=list)
    required_inputs: List[str] = Field(default_factory=list)
    content: str = ""


class ProjectAttachmentCreateRequest(BaseModel):
    stage_key: Optional[str] = None
    title: Optional[str] = None
    note: Optional[str] = None


class ProjectPeriodicDocRequest(BaseModel):
    id: Optional[UUID] = None
    key: str
    title: str
    cadence: str
    description: str
    assignee_role_keys: List[str] = Field(default_factory=list)
    outline: List[str] = Field(default_factory=list)
    required_inputs: List[str] = Field(default_factory=list)
    content: str = ""
    period_label: str = ""


class ProjectGenerateRequest(BaseModel):
    stage_key: str
    document_kind: str = Field(..., description="stage_doc or periodic_doc")
    document_id: UUID
    role_key: Optional[str] = None


class ProjectRecordResponse(BaseModel):
    id: UUID
    stage_key: str
    record_type: str
    title: str
    content: str
    assignee_role_key: Optional[str] = None
    occurred_at: datetime
    created_at: datetime


class ProjectStageDocumentResponse(BaseModel):
    id: UUID
    stage_key: str
    document_key: str
    title: str
    description: str
    assignee_role_keys: List[str]
    outline: List[str]
    required_inputs: List[str]
    content: str
    created_at: datetime
    updated_at: datetime


class ProjectPeriodicDocumentResponse(BaseModel):
    id: UUID
    key: str
    title: str
    cadence: str
    description: str
    assignee_role_keys: List[str]
    outline: List[str]
    required_inputs: List[str]
    content: str
    period_label: str
    created_at: datetime
    updated_at: datetime


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    start_date: date
    end_date: date
    duration: str
    cycle_days: int
    summary: str
    output_dir: str
    role_keys: List[str]
    stage_keys: List[str]
    created_at: datetime
    updated_at: datetime
    records: List[ProjectRecordResponse] = Field(default_factory=list)
    stage_docs: List[ProjectStageDocumentResponse] = Field(default_factory=list)
    periodic_docs: List[ProjectPeriodicDocumentResponse] = Field(default_factory=list)
    attachments: List[dict] = Field(default_factory=list)


class DocumentPlanRequest(BaseModel):
    stage_key: str


class PlannedDocumentResponse(BaseModel):
    stage_key: str
    stage_label: str
    document_key: str
    title: str
    description: str
    assignee_role_keys: List[str]
    outline: List[str]
    required_inputs: List[str]


class GenerationContextResponse(BaseModel):
    project_id: UUID
    project_name: str
    stage_key: str
    stage_label: str
    document_kind: str
    document_id: UUID
    role_key: Optional[str] = None
    role_label: Optional[str] = None
    prompt: str
    context: dict
    draft: str


class ProjectBootstrapResponse(BaseModel):
    roles: list
    stages: list
    projects: List[ProjectResponse]
