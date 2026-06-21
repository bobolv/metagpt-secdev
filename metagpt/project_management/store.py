"""SQLite-backed persistence for project management data."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from metagpt.const import DEFAULT_WORKSPACE_ROOT
from metagpt.project_management.registry import (
    get_document_templates_for_stage,
    get_periodic_document_templates_for_stage,
    list_supported_roles,
    list_supported_stages,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_component(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\\\|?*]+', "_", value).strip().strip(".")
    return cleaned or "project"


def _ensure_list(value):
    return value if isinstance(value, list) else []


class ProjectRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    stage_key: str
    record_type: str
    title: str
    content: str
    assignee_role_key: Optional[str] = None
    occurred_at: datetime = Field(default_factory=_now)
    created_at: datetime = Field(default_factory=_now)


class ProjectStageDocument(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    stage_key: str
    document_key: str
    title: str
    description: str
    assignee_role_keys: List[str] = Field(default_factory=list)
    outline: List[str] = Field(default_factory=list)
    required_inputs: List[str] = Field(default_factory=list)
    content: str = ""
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class ProjectPeriodicDocument(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    key: str
    title: str
    cadence: str
    description: str
    assignee_role_keys: List[str] = Field(default_factory=list)
    outline: List[str] = Field(default_factory=list)
    required_inputs: List[str] = Field(default_factory=list)
    content: str = ""
    period_label: str = ""
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class ProjectAttachment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    stage_key: Optional[str] = None
    title: str
    note: str = ""
    original_name: str
    stored_name: str
    file_path: str
    content_type: str = ""
    size: int = 0
    created_at: datetime = Field(default_factory=_now)


class ProjectItem(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    start_date: date
    end_date: date
    duration: str
    cycle_days: int
    summary: str
    output_dir: str = ""
    role_keys: List[str] = Field(default_factory=list)
    stage_keys: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    stage_docs: List[ProjectStageDocument] = Field(default_factory=list)
    periodic_docs: List[ProjectPeriodicDocument] = Field(default_factory=list)
    records: List[ProjectRecord] = Field(default_factory=list)
    attachments: List[ProjectAttachment] = Field(default_factory=list)


def _make_stage_docs() -> List[ProjectStageDocument]:
    docs: List[ProjectStageDocument] = []
    for stage in list_supported_stages():
        for template in get_document_templates_for_stage(stage.key):
            docs.append(
                ProjectStageDocument(
                    stage_key=stage.key,
                    document_key=template.key,
                    title=template.title,
                    description=template.description,
                    assignee_role_keys=template.assignee_role_keys,
                    outline=template.outline,
                    required_inputs=template.required_inputs,
                )
            )
    return docs


def _make_periodic_docs(project_name: str, summary: str) -> List[ProjectPeriodicDocument]:
    docs = [
        ProjectPeriodicDocument(
            key="project_profile",
            title="项目基础信息",
            cadence="project",
            description="记录项目名称、时长、目标和当前概况。",
            assignee_role_keys=["project_manager", "team_leader"],
            outline=["项目名称", "项目时长", "项目目标", "当前进展", "风险与依赖"],
            required_inputs=["项目名称", "项目时长", "项目任务概述"],
            content=f"项目名称：{project_name}\n项目概述：{summary}",
            period_label="基础信息",
        )
    ]
    for stage_key in ("initiation", "design"):
        for template in get_periodic_document_templates_for_stage(stage_key):
            docs.append(
                ProjectPeriodicDocument(
                    key=template.key,
                    title=template.title,
                    cadence=template.cadence,
                    description=template.description,
                    assignee_role_keys=template.assignee_role_keys,
                    outline=template.outline,
                    required_inputs=template.required_inputs,
                )
            )
    return docs


class ProjectStore:
    def __init__(self, root: Optional[Path] = None):
        self.root = root or (DEFAULT_WORKSPACE_ROOT / "project_management")
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "projects.db"
        self.legacy_json_path = self.root / "projects.json"
        self.output_root = self.root / "projects"
        self.output_root.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._migrate_legacy_json()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _table_columns(self, conn: sqlite3.Connection) -> set[str]:
        rows = conn.execute("PRAGMA table_info(projects)").fetchall()
        return {row[1] for row in rows}

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    start_date TEXT NOT NULL DEFAULT '',
                    end_date TEXT NOT NULL DEFAULT '',
                    duration TEXT NOT NULL,
                    cycle_days INTEGER NOT NULL DEFAULT 1,
                    summary TEXT NOT NULL,
                    output_dir TEXT NOT NULL,
                    role_keys_json TEXT NOT NULL,
                    stage_keys_json TEXT NOT NULL,
                    stage_docs_json TEXT NOT NULL,
                    periodic_docs_json TEXT NOT NULL,
                    records_json TEXT NOT NULL,
                    attachments_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            columns = self._table_columns(conn)
            for column, ddl in (
                ("start_date", "TEXT NOT NULL DEFAULT ''"),
                ("end_date", "TEXT NOT NULL DEFAULT ''"),
                ("cycle_days", "INTEGER NOT NULL DEFAULT 1"),
                ("attachments_json", "TEXT NOT NULL DEFAULT '[]'"),
            ):
                if column not in columns:
                    conn.execute(f"ALTER TABLE projects ADD COLUMN {column} {ddl}")

    def _migrate_legacy_json(self) -> None:
        if not self.legacy_json_path.exists():
            return
        if self.list_projects():
            return
        try:
            payload = json.loads(self.legacy_json_path.read_text(encoding="utf-8"))
        except Exception:
            return
        for item in payload:
            try:
                project = ProjectItem.model_validate(item)
            except Exception:
                continue
            if not project.output_dir:
                project.output_dir = self.build_output_dir(project.name, project.id)
            if not project.stage_docs:
                project.stage_docs = _make_stage_docs()
            if not project.periodic_docs:
                project.periodic_docs = _make_periodic_docs(project.name, project.summary)
            self._upsert_project(project)

    def build_output_dir(self, project_name: str, project_id: UUID | None = None) -> str:
        safe_name = _safe_component(project_name)
        candidate = self.output_root / safe_name
        if candidate.exists() and project_id:
            candidate = self.output_root / f"{safe_name}_{str(project_id)[:8]}"
        candidate.mkdir(parents=True, exist_ok=True)
        (candidate / "attachments").mkdir(parents=True, exist_ok=True)
        return str(candidate)

    def list_projects(self) -> List[ProjectItem]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY datetime(created_at) DESC").fetchall()
        return [self._row_to_project(row) for row in rows if row]

    def get_project(self, project_id: UUID) -> Optional[ProjectItem]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (str(project_id),)).fetchone()
        return self._row_to_project(row) if row else None

    def create_project(self, item: ProjectItem) -> ProjectItem:
        if not item.stage_keys:
            item.stage_keys = [stage.key for stage in list_supported_stages()]
        if not item.role_keys:
            item.role_keys = [role.key for role in list_supported_roles()]
        if not item.stage_docs:
            item.stage_docs = _make_stage_docs()
        if not item.periodic_docs:
            item.periodic_docs = _make_periodic_docs(item.name, item.summary)
        item.output_dir = item.output_dir or self.build_output_dir(item.name, item.id)
        item.created_at = _now()
        item.updated_at = item.created_at
        self._upsert_project(item)
        return item

    def save_project(self, project: ProjectItem) -> ProjectItem:
        project.updated_at = _now()
        if not project.output_dir:
            project.output_dir = self.build_output_dir(project.name, project.id)
        self._upsert_project(project)
        return project

    def update_project(self, project_id: UUID, **changes) -> Optional[ProjectItem]:
        project = self.get_project(project_id)
        if not project:
            return None
        for key, value in changes.items():
            if hasattr(project, key):
                setattr(project, key, value)
        if "name" in changes and not changes.get("output_dir"):
            project.output_dir = self.build_output_dir(project.name, project.id)
        return self.save_project(project)

    def delete_project(self, project_id: UUID) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM projects WHERE id = ?", (str(project_id),))
            return cursor.rowcount > 0

    def clear_projects(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM projects")

    def add_record(self, project_id: UUID, record: ProjectRecord) -> Optional[ProjectItem]:
        project = self.get_project(project_id)
        if not project:
            return None
        project.records.append(record)
        project.updated_at = _now()
        self.save_project(project)
        return project

    def update_record(self, project_id: UUID, record: ProjectRecord) -> Optional[ProjectItem]:
        project = self.get_project(project_id)
        if not project:
            return None
        for idx, current in enumerate(project.records):
            if current.id == record.id:
                project.records[idx] = record
                project.updated_at = _now()
                self.save_project(project)
                return project
        return None

    def delete_record(self, project_id: UUID, record_id: UUID) -> Optional[ProjectItem]:
        project = self.get_project(project_id)
        if not project:
            return None
        project.records = [record for record in project.records if record.id != record_id]
        project.updated_at = _now()
        self.save_project(project)
        return project

    def upsert_stage_doc(self, project_id: UUID, doc: ProjectStageDocument) -> Optional[ProjectItem]:
        project = self.get_project(project_id)
        if not project:
            return None
        doc.updated_at = _now()
        if any(item.id == doc.id for item in project.stage_docs):
            project.stage_docs = [doc if item.id == doc.id else item for item in project.stage_docs]
        else:
            project.stage_docs.append(doc)
        project.updated_at = _now()
        self.save_project(project)
        return project

    def delete_stage_doc(self, project_id: UUID, doc_id: UUID) -> Optional[ProjectItem]:
        project = self.get_project(project_id)
        if not project:
            return None
        project.stage_docs = [item for item in project.stage_docs if item.id != doc_id]
        project.updated_at = _now()
        self.save_project(project)
        return project

    def upsert_periodic_doc(self, project_id: UUID, doc: ProjectPeriodicDocument) -> Optional[ProjectItem]:
        project = self.get_project(project_id)
        if not project:
            return None
        doc.updated_at = _now()
        if any(item.id == doc.id for item in project.periodic_docs):
            project.periodic_docs = [doc if item.id == doc.id else item for item in project.periodic_docs]
        else:
            project.periodic_docs.append(doc)
        project.updated_at = _now()
        self.save_project(project)
        return project

    def delete_periodic_doc(self, project_id: UUID, doc_id: UUID) -> Optional[ProjectItem]:
        project = self.get_project(project_id)
        if not project:
            return None
        project.periodic_docs = [item for item in project.periodic_docs if item.id != doc_id]
        project.updated_at = _now()
        self.save_project(project)
        return project

    def add_attachment(self, project_id: UUID, attachment: ProjectAttachment) -> Optional[ProjectItem]:
        project = self.get_project(project_id)
        if not project:
            return None
        project.attachments.append(attachment)
        project.updated_at = _now()
        self.save_project(project)
        return project

    def delete_attachment(self, project_id: UUID, attachment_id: UUID) -> Optional[ProjectItem]:
        project = self.get_project(project_id)
        if not project:
            return None
        project.attachments = [item for item in project.attachments if item.id != attachment_id]
        project.updated_at = _now()
        self.save_project(project)
        return project

    def _row_to_project(self, row: sqlite3.Row) -> ProjectItem:
        start_date = row["start_date"] or date.today().isoformat()
        end_date = row["end_date"] or start_date
        return ProjectItem(
            id=UUID(row["id"]),
            name=row["name"],
            start_date=date.fromisoformat(start_date),
            end_date=date.fromisoformat(end_date),
            duration=row["duration"],
            cycle_days=int(row["cycle_days"] or 1),
            summary=row["summary"],
            output_dir=row["output_dir"],
            role_keys=_ensure_list(json.loads(row["role_keys_json"])),
            stage_keys=_ensure_list(json.loads(row["stage_keys_json"])),
            stage_docs=[ProjectStageDocument.model_validate(item) for item in json.loads(row["stage_docs_json"] or "[]")],
            periodic_docs=[ProjectPeriodicDocument.model_validate(item) for item in json.loads(row["periodic_docs_json"] or "[]")],
            records=[ProjectRecord.model_validate(item) for item in json.loads(row["records_json"] or "[]")],
            attachments=[ProjectAttachment.model_validate(item) for item in json.loads(row["attachments_json"] or "[]")],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _upsert_project(self, project: ProjectItem) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO projects (
                    id, name, start_date, end_date, duration, cycle_days, summary, output_dir,
                    role_keys_json, stage_keys_json, stage_docs_json, periodic_docs_json,
                    records_json, attachments_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    start_date = excluded.start_date,
                    end_date = excluded.end_date,
                    duration = excluded.duration,
                    cycle_days = excluded.cycle_days,
                    summary = excluded.summary,
                    output_dir = excluded.output_dir,
                    role_keys_json = excluded.role_keys_json,
                    stage_keys_json = excluded.stage_keys_json,
                    stage_docs_json = excluded.stage_docs_json,
                    periodic_docs_json = excluded.periodic_docs_json,
                    records_json = excluded.records_json,
                    attachments_json = excluded.attachments_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    str(project.id),
                    project.name,
                    project.start_date.isoformat(),
                    project.end_date.isoformat(),
                    project.duration,
                    project.cycle_days,
                    project.summary,
                    project.output_dir,
                    json.dumps(project.role_keys, ensure_ascii=False),
                    json.dumps(project.stage_keys, ensure_ascii=False),
                    json.dumps([json.loads(item.model_dump_json()) for item in project.stage_docs], ensure_ascii=False),
                    json.dumps([json.loads(item.model_dump_json()) for item in project.periodic_docs], ensure_ascii=False),
                    json.dumps([json.loads(item.model_dump_json()) for item in project.records], ensure_ascii=False),
                    json.dumps([json.loads(item.model_dump_json()) for item in project.attachments], ensure_ascii=False),
                    project.created_at.isoformat(),
                    project.updated_at.isoformat(),
                ),
            )
