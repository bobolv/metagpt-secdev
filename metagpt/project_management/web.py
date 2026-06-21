"""Self-contained HTTP server for project management."""

from __future__ import annotations

import cgi
import json
import os
import re
from datetime import date, datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse
from uuid import UUID

from metagpt.project_management import (
    get_document_templates_for_stage,
    get_recommended_roles_for_stage,
    get_periodic_document_templates_for_stage,
    list_supported_roles,
    list_supported_stages,
)
from metagpt.project_management.schemas import (
    DocumentPlanRequest,
    PlannedDocumentResponse,
    ProjectBootstrapResponse,
    ProjectCreateRequest,
    ProjectGenerateRequest,
    ProjectAttachmentCreateRequest,
    ProjectPeriodicDocRequest,
    ProjectPeriodicDocumentResponse,
    ProjectRecordCreateRequest,
    ProjectRecordResponse,
    ProjectRecordUpdateRequest,
    GenerationContextResponse,
    ProjectResponse,
    ProjectStageDocRequest,
    ProjectStageDocumentResponse,
    ProjectUpdateRequest,
)
from metagpt.project_management.store import (
    ProjectAttachment,
    ProjectItem,
    ProjectPeriodicDocument,
    ProjectRecord,
    ProjectStageDocument,
    ProjectStore,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _project_cycle_days(start_date: date, end_date: date) -> int:
    return max((end_date - start_date).days + 1, 1)


def _format_duration(start_date: date, end_date: date) -> str:
    return f"{start_date.isoformat()} ~ {end_date.isoformat()}"


def _role_to_dict(role) -> dict[str, Any]:
    return role.model_dump()


def _stage_to_dict(stage) -> dict[str, Any]:
    return stage.model_dump()


def _record_to_dict(record: ProjectRecord) -> dict[str, Any]:
    return record.model_dump()


def _stage_doc_to_dict(doc: ProjectStageDocument) -> dict[str, Any]:
    return doc.model_dump()


def _periodic_doc_to_dict(doc: ProjectPeriodicDocument) -> dict[str, Any]:
    return doc.model_dump()


def _project_to_response(project: ProjectItem) -> ProjectResponse:
    payload = project.model_dump()
    payload["records"] = [_record_to_dict(record) for record in project.records]
    payload["stage_docs"] = [_stage_doc_to_dict(doc) for doc in project.stage_docs]
    payload["periodic_docs"] = [_periodic_doc_to_dict(doc) for doc in project.periodic_docs]
    return ProjectResponse.model_validate(payload)


def build_planned_documents(stage_key: str) -> list[PlannedDocumentResponse]:
    stage = next((item for item in list_supported_stages() if item.key == stage_key), None)
    if not stage:
        raise KeyError(stage_key)
    return [
        PlannedDocumentResponse(
            stage_key=stage.key,
            stage_label=stage.label,
            document_key=document.key,
            title=document.title,
            description=document.description,
            assignee_role_keys=document.assignee_role_keys,
            outline=document.outline,
            required_inputs=document.required_inputs,
        )
        for document in get_document_templates_for_stage(stage_key)
    ]


def _bootstrap_payload(store: ProjectStore) -> dict[str, Any]:
    return {
        "roles": [_role_to_dict(role) for role in list_supported_roles()],
        "stages": [_stage_to_dict(stage) for stage in list_supported_stages()],
        "projects": [_project_to_response(project).model_dump() for project in store.list_projects()],
    }


def _render_index_html() -> str:
    bootstrap_json = json.dumps(
        {
            "roles": [_role_to_dict(role) for role in list_supported_roles()],
            "stages": [_stage_to_dict(stage) for stage in list_supported_stages()],
        },
        ensure_ascii=False,
    )
    html = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MetaGPT 项目管理</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #edf2f7;
      --surface: #ffffff;
      --surface-2: #f8fafc;
      --border: #d8e0ea;
      --ink: #122033;
      --muted: #617286;
      --accent: #2d5bff;
      --accent-2: #0f9d58;
      --danger: #c2410c;
      --shadow: 0 10px 30px rgba(16, 24, 40, 0.07);
      --radius: 12px;
      --radius-sm: 10px;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: linear-gradient(180deg, #f6f8fc 0%, #edf2f7 100%);
      color: var(--ink);
    }
    button, input, textarea, select { font: inherit; }
    button { cursor: pointer; }
    .app {
      max-width: 1600px;
      margin: 0 auto;
      padding: 20px;
    }
    .hero {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 16px;
    }
    .hero h1 {
      margin: 0;
      font-size: 30px;
      line-height: 1.15;
      letter-spacing: 0;
    }
    .hero p {
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 15px;
    }
    .status {
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(45, 91, 255, 0.08);
      color: var(--accent);
      font-size: 13px;
      white-space: nowrap;
    }
    .layout {
      display: grid;
      grid-template-columns: 340px minmax(0, 1fr);
      gap: 16px;
      align-items: start;
    }
    .sidebar, .workspace {
      min-width: 0;
      display: grid;
      gap: 16px;
    }
    .panel {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 16px;
    }
    .panel h2 {
      margin: 0 0 12px;
      font-size: 18px;
      line-height: 1.2;
    }
    .panel h3 {
      margin: 0 0 8px;
      font-size: 14px;
      color: var(--muted);
      font-weight: 600;
    }
    .field { display: grid; gap: 6px; }
    .field label { color: var(--muted); font-size: 13px; }
    .field input, .field textarea, .field select {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      background: var(--surface);
      color: var(--ink);
      padding: 10px 12px;
      outline: none;
    }
    .field textarea { min-height: 110px; resize: vertical; }
    .field input:focus, .field textarea:focus, .field select:focus {
      border-color: rgba(45, 91, 255, 0.65);
      box-shadow: 0 0 0 3px rgba(45, 91, 255, 0.12);
    }
    .stack { display: grid; gap: 12px; }
    .two-up { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .three-up { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
    .actions { display: flex; gap: 10px; flex-wrap: wrap; }
    .actions button {
      border: 0;
      border-radius: 10px;
      padding: 10px 14px;
      color: #fff;
      background: var(--accent);
    }
    .actions button.secondary { background: #334155; }
    .actions button.success { background: var(--accent-2); }
    .actions button.danger { background: var(--danger); }
    .choice-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 8px;
    }
    .choice {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      padding: 10px 12px;
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      background: var(--surface-2);
      min-height: 48px;
      overflow: hidden;
    }
    .choice input { margin-top: 2px; flex: 0 0 auto; }
    .choice span { line-height: 1.3; word-break: break-word; }
    .project-list { display: grid; gap: 10px; }
    .project-row {
      width: 100%;
      text-align: left;
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      background: var(--surface);
      padding: 12px 14px;
      color: var(--ink);
      cursor: pointer;
      display: grid;
      gap: 6px;
    }
    .project-row.is-active {
      border-color: rgba(45, 91, 255, 0.5);
      box-shadow: 0 0 0 3px rgba(45, 91, 255, 0.08);
    }
    .project-row strong { font-size: 15px; }
    .project-meta, .muted { color: var(--muted); font-size: 13px; }
    .tag-row { display: flex; gap: 8px; flex-wrap: wrap; }
    .tag {
      display: inline-flex;
      align-items: center;
      padding: 3px 8px;
      border-radius: 999px;
      background: #e9efff;
      color: #1f45b8;
      font-size: 12px;
    }
    .summary-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }
    .summary {
      border: 1px solid var(--border);
      background: var(--surface-2);
      border-radius: var(--radius-sm);
      padding: 12px;
    }
    .summary .value { display: block; margin-top: 4px; font-size: 18px; font-weight: 700; }
    .tabs {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 12px;
    }
    .tab-btn {
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--ink);
      border-radius: 999px;
      padding: 8px 12px;
    }
    .tab-btn.is-active {
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
    }
    .detail-card {
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      background: var(--surface);
      padding: 14px;
    }
    .detail-head {
      display: flex;
      justify-content: space-between;
      align-items: start;
      gap: 12px;
      margin-bottom: 10px;
    }
    .detail-head h3 { margin: 0; font-size: 18px; color: var(--ink); }
    .list { display: grid; gap: 10px; }
    .list-item {
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      background: var(--surface);
      padding: 12px;
    }
    .list-item strong { font-size: 14px; }
    .list-item .desc {
      margin-top: 6px;
      color: var(--muted);
      font-size: 13px;
      white-space: pre-wrap;
    }
    .inline-actions { display: flex; gap: 8px; flex-wrap: wrap; }
    .inline-actions button {
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--ink);
      border-radius: 999px;
      padding: 6px 10px;
    }
    .inline-actions button.is-on {
      background: rgba(45, 91, 255, 0.08);
      border-color: rgba(45, 91, 255, 0.35);
      color: var(--accent);
    }
    .hidden { display: none; }
    .toast {
      position: fixed;
      right: 18px;
      bottom: 18px;
      padding: 10px 14px;
      border-radius: 10px;
      background: #122033;
      color: #fff;
      box-shadow: var(--shadow);
      opacity: 0;
      transform: translateY(8px);
      transition: all 0.18s ease;
      pointer-events: none;
      max-width: 360px;
      white-space: pre-wrap;
    }
    .toast.is-show {
      opacity: 1;
      transform: translateY(0);
    }
    @media (max-width: 1180px) {
      .layout { grid-template-columns: 1fr; }
      .summary-grid, .three-up { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 720px) {
      .app { padding: 14px; }
      .hero { flex-direction: column; align-items: start; }
      .two-up, .summary-grid, .three-up { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="app">
    <header class="hero">
      <div>
        <h1>MetaGPT 项目管理</h1>
        <p>创建项目、分配角色、维护生命周期阶段，并在同一页面里管理阶段文档、周期文档和推进记录。</p>
      </div>
      <div class="status" id="status">就绪</div>
    </header>

    <div class="layout">
      <aside class="sidebar">
        <section class="panel">
          <h2>新建项目</h2>
          <div class="stack">
            <div class="field">
              <label>项目名称</label>
              <input id="project-name" placeholder="例如：智慧电子档案平台" />
            </div>
            <div class="two-up">
              <div class="field">
                <label>项目时长</label>
                <input id="project-duration" placeholder="例如：6个月" />
              </div>
              <div class="field">
                <label>项目状态</label>
                <input value="创建后可编辑" disabled />
              </div>
            </div>
            <div class="field">
              <label>项目任务概述</label>
              <textarea id="project-summary" placeholder="项目介绍、需求任务、边界、目标、约束等"></textarea>
            </div>
            <div>
              <h3>选择团队角色</h3>
              <div id="create-role-list" class="choice-grid"></div>
            </div>
            <div class="actions">
              <button id="create-project-btn" type="button">创建项目</button>
              <button id="clear-create-btn" class="secondary" type="button">清空输入</button>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="detail-head">
            <div>
              <h2 style="margin:0">阶段模板预览</h2>
              <div class="muted">查看系统默认的阶段文档模板。</div>
            </div>
          </div>
          <div class="two-up">
            <div class="field">
              <label>选择阶段</label>
              <select id="template-stage"></select>
            </div>
            <div class="field" style="display:flex;align-items:end">
              <button id="load-template-btn" class="success" type="button">加载模板</button>
            </div>
          </div>
          <div id="template-list" class="list" style="margin-top:12px"></div>
        </section>
      </aside>

      <main class="workspace">
        <section class="panel">
          <div class="detail-head">
            <div>
              <h2 style="margin:0">项目列表</h2>
              <div class="muted">选择项目后，可在右侧直接编辑项目、阶段文档和定期文档。</div>
            </div>
            <div class="inline-actions">
              <button id="refresh-btn" type="button">刷新</button>
              <button id="clear-all-btn" type="button">清空全部</button>
            </div>
          </div>
          <div class="project-list" id="project-list"></div>
        </section>

        <section class="panel">
          <div class="detail-head">
            <div>
              <h2 style="margin:0">项目工作区</h2>
              <div class="muted">项目基础信息、阶段配置、文档清单和周期文档都在这里统一管理。</div>
            </div>
          </div>
          <div class="summary-grid" id="summary-grid"></div>
          <div class="tabs" style="margin-top:14px">
            <button class="tab-btn is-active" data-tab="overview" type="button">总览</button>
            <button class="tab-btn" data-tab="stage-docs" type="button">阶段文档</button>
            <button class="tab-btn" data-tab="periodic-docs" type="button">定期文档</button>
            <button class="tab-btn" data-tab="records" type="button">推进记录</button>
          </div>
          <div id="tab-overview" class="stack"></div>
          <div id="tab-stage-docs" class="stack hidden"></div>
          <div id="tab-periodic-docs" class="stack hidden"></div>
          <div id="tab-records" class="stack hidden"></div>
        </section>
      </main>
    </div>
  </div>

  <div id="toast" class="toast"></div>

  <script>
    const BOOTSTRAP = {BOOTSTRAP};
    const state = {
      projects: [],
      selectedProjectId: null,
      activeTab: 'overview',
      stageDocStage: '',
      selectedStageDocId: null,
      selectedPeriodicDocId: null,
      selectedRecordId: null,
    };

    const els = {
      status: document.getElementById('status'),
      toast: document.getElementById('toast'),
      projectList: document.getElementById('project-list'),
      summaryGrid: document.getElementById('summary-grid'),
      templateStage: document.getElementById('template-stage'),
      templateList: document.getElementById('template-list'),
      overview: document.getElementById('tab-overview'),
      stageDocs: document.getElementById('tab-stage-docs'),
      periodicDocs: document.getElementById('tab-periodic-docs'),
      records: document.getElementById('tab-records'),
      createRoleList: document.getElementById('create-role-list'),
    };

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    }

    function setMessage(text) {
      els.status.textContent = text;
      els.toast.textContent = text;
      els.toast.classList.add('is-show');
      clearTimeout(window.__toastTimer);
      window.__toastTimer = setTimeout(() => els.toast.classList.remove('is-show'), 2600);
    }

    function selectedValues(kind) {
      return Array.from(document.querySelectorAll(`input[type=checkbox][data-kind="${kind}"]:checked`)).map(el => el.value);
    }

    function buildCheckboxGrid(container, kind, items, selected = []) {
      container.innerHTML = items.map(item => `
        <label class="choice">
          <input type="checkbox" value="${escapeHtml(item.key)}" data-kind="${escapeHtml(kind)}" ${selected.includes(item.key) ? 'checked' : ''}/>
          <span>${escapeHtml(item.label)}</span>
        </label>
      `).join('');
    }

    function buildStageToggles(container, selected = []) {
      container.innerHTML = BOOTSTRAP.stages.map(stage => `
        <button type="button" class="${selected.includes(stage.key) ? 'is-on' : ''}" data-stage-toggle="${escapeHtml(stage.key)}">
          ${escapeHtml(stage.label)}
        </button>
      `).join('');
      container.querySelectorAll('[data-stage-toggle]').forEach(btn => {
        btn.addEventListener('click', () => btn.classList.toggle('is-on'));
      });
    }

    function currentProject() {
      return state.projects.find(project => project.id === state.selectedProjectId) || null;
    }

    function roleLabel(key) {
      const item = BOOTSTRAP.roles.find(role => role.key === key);
      return item ? item.label : key;
    }

    function stageLabel(key) {
      const item = BOOTSTRAP.stages.find(stage => stage.key === key);
      return item ? item.label : key;
    }

    function parseLines(text) {
      return String(text || '').split(/\\r?\\n/).map(item => item.trim()).filter(Boolean);
    }

    function joinLines(items) {
      return (items || []).join('\\n');
    }

    async function api(url, options = {}) {
      const rsp = await fetch(url, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
      });
      const contentType = rsp.headers.get('content-type') || '';
      const data = contentType.includes('application/json') ? await rsp.json() : await rsp.text();
      if (!rsp.ok) {
        const message = data && data.detail ? data.detail : '请求失败';
        throw new Error(message);
      }
      return data;
    }

    async function refreshProjects(keepSelection = true) {
      const data = await api('/api/projects');
      state.projects = data;
      if (!keepSelection || !state.projects.some(project => project.id === state.selectedProjectId)) {
        state.selectedProjectId = state.projects[0] ? state.projects[0].id : null;
      }
      renderAll();
    }

    function renderProjectList() {
      if (!state.projects.length) {
        els.projectList.innerHTML = '<div class="muted">暂无项目，请先在左侧创建一个。</div>';
        return;
      }
      els.projectList.innerHTML = state.projects.map(project => `
        <button type="button" class="project-row ${project.id === state.selectedProjectId ? 'is-active' : ''}" data-project-id="${escapeHtml(project.id)}">
          <strong>${escapeHtml(project.name)}</strong>
          <div class="project-meta">${escapeHtml(project.duration)} · ${project.records.length} 条记录</div>
          <div class="project-meta">${escapeHtml(project.output_dir)}</div>
        </button>
      `).join('');
      els.projectList.querySelectorAll('[data-project-id]').forEach(btn => {
        btn.addEventListener('click', () => {
          state.selectedProjectId = btn.dataset.projectId;
          state.selectedStageDocId = null;
          state.selectedPeriodicDocId = null;
          state.selectedRecordId = null;
          renderAll();
        });
      });
    }

    function renderSummary(project) {
      const items = project ? [
        { label: '角色', value: project.role_keys.length },
        { label: '阶段', value: project.stage_keys.length },
        { label: '阶段文档', value: project.stage_docs.length },
        { label: '定期文档', value: project.periodic_docs.length },
      ] : [
        { label: '角色', value: 0 },
        { label: '阶段', value: 0 },
        { label: '阶段文档', value: 0 },
        { label: '定期文档', value: 0 },
      ];
      els.summaryGrid.innerHTML = items.map(item => `
        <div class="summary">
          <div class="muted">${escapeHtml(item.label)}</div>
          <span class="value">${escapeHtml(item.value)}</span>
        </div>
      `).join('');
    }

    function renderTabsVisibility() {
      document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('is-active', btn.dataset.tab === state.activeTab);
      });
      els.overview.classList.toggle('hidden', state.activeTab !== 'overview');
      els.stageDocs.classList.toggle('hidden', state.activeTab !== 'stage-docs');
      els.periodicDocs.classList.toggle('hidden', state.activeTab !== 'periodic-docs');
      els.records.classList.toggle('hidden', state.activeTab !== 'records');
    }

    function renderOverview(project) {
      if (!project) {
        els.overview.innerHTML = `
          <div class="detail-card">
            <h3>请先选择一个项目</h3>
            <div class="muted">项目创建完成后，基础信息、阶段配置和文档管理都会显示在这里。</div>
          </div>
        `;
        return;
      }

      const stageCheckboxes = BOOTSTRAP.stages.map(stage => `
        <label class="choice" style="min-width: 160px">
          <input type="checkbox" value="${escapeHtml(stage.key)}" data-kind="project-stage" ${project.stage_keys.includes(stage.key) ? 'checked' : ''}/>
          <span>${escapeHtml(stage.label)}</span>
        </label>
      `).join('');
      const roleCheckboxes = BOOTSTRAP.roles.map(role => `
        <label class="choice" style="min-width: 160px">
          <input type="checkbox" value="${escapeHtml(role.key)}" data-kind="project-role" ${project.role_keys.includes(role.key) ? 'checked' : ''}/>
          <span>${escapeHtml(role.label)}</span>
        </label>
      `).join('');

      els.overview.innerHTML = `
        <div class="detail-card">
          <div class="detail-head">
            <div>
              <h3>项目基础信息</h3>
              <div class="muted">项目成果目录：${escapeHtml(project.output_dir)}</div>
            </div>
            <div class="inline-actions">
              <button type="button" id="save-project-btn">保存</button>
              <button type="button" id="delete-project-btn">删除项目</button>
            </div>
          </div>
          <div class="two-up">
            <div class="field">
              <label>项目名称</label>
              <input id="edit-project-name" value="${escapeHtml(project.name)}" />
            </div>
            <div class="field">
              <label>项目时长</label>
              <input id="edit-project-duration" value="${escapeHtml(project.duration)}" />
            </div>
          </div>
          <div class="field" style="margin-top:12px">
            <label>项目任务概述</label>
            <textarea id="edit-project-summary">${escapeHtml(project.summary)}</textarea>
          </div>
          <div style="margin-top:12px">
            <h3>角色</h3>
            <div class="choice-grid" id="edit-role-list">${roleCheckboxes}</div>
          </div>
          <div style="margin-top:12px">
            <h3>生命周期阶段</h3>
            <div class="choice-grid" id="edit-stage-list">${stageCheckboxes}</div>
          </div>
        </div>
      `;

      document.getElementById('save-project-btn').onclick = saveProject;
      document.getElementById('delete-project-btn').onclick = deleteProject;
    }

    function renderStageDocs(project) {
      if (!project) {
        els.stageDocs.innerHTML = '<div class="detail-card"><div class="muted">请先选择一个项目。</div></div>';
        return;
      }
      const activeStage = state.stageDocStage || project.stage_keys[0] || BOOTSTRAP.stages[0]?.key || '';
      state.stageDocStage = activeStage;
      const stageOptions = BOOTSTRAP.stages.map(stage => `
        <option value="${escapeHtml(stage.key)}" ${stage.key === activeStage ? 'selected' : ''}>${escapeHtml(stage.label)}</option>
      `).join('');
      const docs = project.stage_docs.filter(doc => !activeStage || doc.stage_key === activeStage);
      els.stageDocs.innerHTML = `
        <div class="detail-card">
          <div class="two-up">
            <div class="field">
              <label>阶段筛选</label>
              <select id="stage-doc-filter">${stageOptions}</select>
            </div>
            <div class="field" style="display:flex;align-items:end">
              <button type="button" class="success" id="new-stage-doc-btn">新增阶段文档</button>
            </div>
          </div>
        </div>
        <div class="two-up">
          <div class="detail-card">
            <h3>文档清单</h3>
            <div class="list" id="stage-doc-list" style="margin-top:10px">
              ${docs.length ? docs.map(doc => `
                <div class="list-item" data-stage-doc-id="${escapeHtml(doc.id)}">
                  <strong>${escapeHtml(doc.title)}</strong>
                  <div class="muted">${escapeHtml(stageLabel(doc.stage_key))} · ${escapeHtml(doc.document_key)}</div>
                  <div class="muted">负责人：${escapeHtml((doc.assignee_role_keys || []).map(roleLabel).join('、') || '未设置')}</div>
                  <div class="desc">${escapeHtml(doc.description)}</div>
                </div>
              `).join('') : '<div class="muted">当前阶段暂无文档。</div>'}
            </div>
          </div>
          <div class="detail-card">
            <h3>编辑阶段文档</h3>
            ${renderStageDocEditor(project)}
          </div>
        </div>
      `;
      document.getElementById('stage-doc-filter').onchange = event => {
        state.stageDocStage = event.target.value;
        state.selectedStageDocId = null;
        renderStageDocs(currentProject());
      };
      document.getElementById('new-stage-doc-btn').onclick = () => {
        state.selectedStageDocId = null;
        renderStageDocs(currentProject());
      };
      els.stageDocs.querySelectorAll('[data-stage-doc-id]').forEach(item => {
        item.addEventListener('click', () => {
          state.selectedStageDocId = item.dataset.stageDocId;
          renderStageDocs(currentProject());
        });
      });
    }

    function renderStageDocEditor(project) {
      const selected = project.stage_docs.find(doc => doc.id === state.selectedStageDocId) || null;
      const defaults = selected || {
        id: '',
        stage_key: state.stageDocStage || project.stage_keys[0] || BOOTSTRAP.stages[0]?.key || '',
        document_key: '',
        title: '',
        description: '',
        assignee_role_keys: [],
        outline: [],
        required_inputs: [],
        content: '',
      };
      const roleChecks = BOOTSTRAP.roles.map(role => `
        <label class="choice">
          <input type="checkbox" value="${escapeHtml(role.key)}" data-kind="stage-doc-role" ${defaults.assignee_role_keys.includes(role.key) ? 'checked' : ''}/>
          <span>${escapeHtml(role.label)}</span>
        </label>
      `).join('');
      const outline = joinLines(defaults.outline || []);
      const inputs = joinLines(defaults.required_inputs || []);
      return `
        <div class="stack">
          <input type="hidden" id="stage-doc-id" value="${escapeHtml(defaults.id || '')}" />
          <div class="two-up">
            <div class="field">
              <label>阶段</label>
              <select id="stage-doc-stage">${BOOTSTRAP.stages.map(stage => `<option value="${escapeHtml(stage.key)}" ${stage.key === defaults.stage_key ? 'selected' : ''}>${escapeHtml(stage.label)}</option>`).join('')}</select>
            </div>
            <div class="field">
              <label>文档标识</label>
              <input id="stage-doc-key" value="${escapeHtml(defaults.document_key)}" placeholder="例如：requirements_specification" />
            </div>
          </div>
          <div class="field">
            <label>标题</label>
            <input id="stage-doc-title" value="${escapeHtml(defaults.title)}" />
          </div>
          <div class="field">
            <label>说明</label>
            <textarea id="stage-doc-desc">${escapeHtml(defaults.description)}</textarea>
          </div>
          <div>
            <h3>完成人</h3>
            <div class="choice-grid" id="stage-doc-role-list">${roleChecks}</div>
          </div>
          <div class="two-up">
            <div class="field">
              <label>提纲目录</label>
              <textarea id="stage-doc-outline" placeholder="每行一个条目">${escapeHtml(outline)}</textarea>
            </div>
            <div class="field">
              <label>所需输入</label>
              <textarea id="stage-doc-inputs" placeholder="每行一个条目">${escapeHtml(inputs)}</textarea>
            </div>
          </div>
          <div class="field">
            <label>文档内容</label>
            <textarea id="stage-doc-content">${escapeHtml(defaults.content || '')}</textarea>
          </div>
          <div class="inline-actions">
            <button type="button" id="save-stage-doc-btn">保存</button>
            <button type="button" id="delete-stage-doc-btn">删除</button>
            <button type="button" id="reset-stage-doc-btn">重置</button>
          </div>
        </div>
      `;
    }

    function renderPeriodicDocs(project) {
      if (!project) {
        els.periodicDocs.innerHTML = '<div class="detail-card"><div class="muted">请先选择一个项目。</div></div>';
        return;
      }
      const selected = project.periodic_docs.find(doc => doc.id === state.selectedPeriodicDocId) || project.periodic_docs[0] || null;
      state.selectedPeriodicDocId = selected ? selected.id : null;
      els.periodicDocs.innerHTML = `
        <div class="detail-card">
          <div class="detail-head">
            <div>
              <h3>定期文档</h3>
              <div class="muted">这里包括项目基础信息、周报、月报等定期输出。</div>
            </div>
            <div class="inline-actions">
              <button type="button" id="new-periodic-doc-btn">新增定期文档</button>
            </div>
          </div>
        </div>
        <div class="two-up">
          <div class="detail-card">
            <h3>清单</h3>
            <div class="list" id="periodic-doc-list" style="margin-top:10px">
              ${project.periodic_docs.length ? project.periodic_docs.map(doc => `
                <div class="list-item" data-periodic-doc-id="${escapeHtml(doc.id)}">
                  <strong>${escapeHtml(doc.title)}</strong>
                  <div class="muted">${escapeHtml(doc.cadence)} · ${escapeHtml(doc.key)}</div>
                  <div class="muted">负责人：${escapeHtml((doc.assignee_role_keys || []).map(roleLabel).join('、') || '未设置')}</div>
                  <div class="desc">${escapeHtml(doc.description)}</div>
                </div>
              `).join('') : '<div class="muted">当前项目暂无定期文档。</div>'}
            </div>
          </div>
          <div class="detail-card">
            <h3>编辑定期文档</h3>
            ${renderPeriodicDocEditor(project, selected)}
          </div>
        </div>
      `;
      document.getElementById('new-periodic-doc-btn').onclick = () => {
        state.selectedPeriodicDocId = null;
        renderPeriodicDocs(currentProject());
      };
      els.periodicDocs.querySelectorAll('[data-periodic-doc-id]').forEach(item => {
        item.addEventListener('click', () => {
          state.selectedPeriodicDocId = item.dataset.periodicDocId;
          renderPeriodicDocs(currentProject());
        });
      });
    }

    function renderPeriodicDocEditor(project, selected) {
      const doc = selected || {
        id: '',
        key: '',
        title: '',
        cadence: 'weekly',
        description: '',
        assignee_role_keys: [],
        outline: [],
        required_inputs: [],
        content: '',
        period_label: '',
      };
      const roleChecks = BOOTSTRAP.roles.map(role => `
        <label class="choice">
          <input type="checkbox" value="${escapeHtml(role.key)}" data-kind="periodic-doc-role" ${doc.assignee_role_keys.includes(role.key) ? 'checked' : ''}/>
          <span>${escapeHtml(role.label)}</span>
        </label>
      `).join('');
      return `
        <div class="stack">
          <input type="hidden" id="periodic-doc-id" value="${escapeHtml(doc.id || '')}" />
          <div class="two-up">
            <div class="field">
              <label>标识</label>
              <input id="periodic-doc-key" value="${escapeHtml(doc.key)}" placeholder="例如：weekly_report" />
            </div>
            <div class="field">
              <label>周期</label>
              <select id="periodic-doc-cadence">
                <option value="project" ${doc.cadence === 'project' ? 'selected' : ''}>项目</option>
                <option value="weekly" ${doc.cadence === 'weekly' ? 'selected' : ''}>周报</option>
                <option value="monthly" ${doc.cadence === 'monthly' ? 'selected' : ''}>月报</option>
              </select>
            </div>
          </div>
          <div class="field">
            <label>标题</label>
            <input id="periodic-doc-title" value="${escapeHtml(doc.title)}" />
          </div>
          <div class="field">
            <label>说明</label>
            <textarea id="periodic-doc-desc">${escapeHtml(doc.description)}</textarea>
          </div>
          <div class="field">
            <label>期间标签</label>
            <input id="periodic-doc-label" value="${escapeHtml(doc.period_label || '')}" placeholder="例如：2026年6月第3周" />
          </div>
          <div>
            <h3>完成人</h3>
            <div class="choice-grid" id="periodic-doc-role-list">${roleChecks}</div>
          </div>
          <div class="two-up">
            <div class="field">
              <label>提纲目录</label>
              <textarea id="periodic-doc-outline">${escapeHtml(joinLines(doc.outline || []))}</textarea>
            </div>
            <div class="field">
              <label>所需输入</label>
              <textarea id="periodic-doc-inputs">${escapeHtml(joinLines(doc.required_inputs || []))}</textarea>
            </div>
          </div>
          <div class="field">
            <label>文档内容</label>
            <textarea id="periodic-doc-content">${escapeHtml(doc.content || '')}</textarea>
          </div>
          <div class="inline-actions">
            <button type="button" id="save-periodic-doc-btn">保存</button>
            <button type="button" id="delete-periodic-doc-btn">删除</button>
            <button type="button" id="reset-periodic-doc-btn">重置</button>
          </div>
        </div>
      `;
    }

    function renderRecords(project) {
      if (!project) {
        els.records.innerHTML = '<div class="detail-card"><div class="muted">请先选择一个项目。</div></div>';
        return;
      }
      const selected = project.records.find(record => record.id === state.selectedRecordId) || null;
      const record = selected || {
        id: '',
        stage_key: project.stage_keys[0] || BOOTSTRAP.stages[0]?.key || '',
        record_type: 'daily_progress',
        title: '',
        content: '',
        assignee_role_key: project.role_keys[0] || BOOTSTRAP.roles[0]?.key || '',
      };
      els.records.innerHTML = `
        <div class="two-up">
          <div class="detail-card">
            <div class="detail-head">
              <div>
                <h3>推进记录</h3>
                <div class="muted">按天、按周、会议纪要、里程碑和变更记录都可以在这里维护。</div>
              </div>
              <div class="inline-actions">
                <button type="button" id="new-record-btn">新增记录</button>
              </div>
            </div>
            <div class="list" id="record-list">
              ${project.records.length ? project.records.map(item => `
                <div class="list-item" data-record-id="${escapeHtml(item.id)}">
                  <strong>${escapeHtml(item.title)}</strong>
                  <div class="muted">${escapeHtml(stageLabel(item.stage_key))} · ${escapeHtml(item.record_type)} · ${escapeHtml(roleLabel(item.assignee_role_key || ''))}</div>
                  <div class="desc">${escapeHtml(item.content)}</div>
                </div>
              `).join('') : '<div class="muted">当前项目暂无推进记录。</div>'}
            </div>
          </div>
          <div class="detail-card">
            <h3>编辑记录</h3>
            ${renderRecordEditor(project, record)}
          </div>
        </div>
      `;
      document.getElementById('new-record-btn').onclick = () => {
        state.selectedRecordId = null;
        renderRecords(currentProject());
      };
      els.records.querySelectorAll('[data-record-id]').forEach(item => {
        item.addEventListener('click', () => {
          state.selectedRecordId = item.dataset.recordId;
          renderRecords(currentProject());
        });
      });
    }

    function renderRecordEditor(project, record) {
      return `
        <div class="stack">
          <input type="hidden" id="record-id" value="${escapeHtml(record.id || '')}" />
          <div class="two-up">
            <div class="field">
              <label>阶段</label>
              <select id="record-stage">${BOOTSTRAP.stages.map(stage => `<option value="${escapeHtml(stage.key)}" ${stage.key === record.stage_key ? 'selected' : ''}>${escapeHtml(stage.label)}</option>`).join('')}</select>
            </div>
            <div class="field">
              <label>记录类型</label>
              <select id="record-type">
                <option value="daily_progress" ${record.record_type === 'daily_progress' ? 'selected' : ''}>按天推进</option>
                <option value="meeting_note" ${record.record_type === 'meeting_note' ? 'selected' : ''}>会议纪要</option>
                <option value="milestone" ${record.record_type === 'milestone' ? 'selected' : ''}>重要里程碑</option>
                <option value="change_request" ${record.record_type === 'change_request' ? 'selected' : ''}>需求变更</option>
                <option value="source_code" ${record.record_type === 'source_code' ? 'selected' : ''}>重要源代码</option>
                <option value="summary" ${record.record_type === 'summary' ? 'selected' : ''}>阶段总结</option>
              </select>
            </div>
          </div>
          <div class="two-up">
            <div class="field">
              <label>标题</label>
              <input id="record-title" value="${escapeHtml(record.title)}" />
            </div>
            <div class="field">
              <label>完成人</label>
              <select id="record-role">${BOOTSTRAP.roles.map(role => `<option value="${escapeHtml(role.key)}" ${role.key === (record.assignee_role_key || '') ? 'selected' : ''}>${escapeHtml(role.label)}</option>`).join('')}</select>
            </div>
          </div>
          <div class="field">
            <label>内容</label>
            <textarea id="record-content">${escapeHtml(record.content)}</textarea>
          </div>
          <div class="inline-actions">
            <button type="button" id="save-record-btn">保存</button>
            <button type="button" id="delete-record-btn">删除</button>
            <button type="button" id="reset-record-btn">重置</button>
          </div>
        </div>
      `;
    }

    function renderTemplatePanel() {
      if (!BOOTSTRAP.stages.length) {
        els.templateList.innerHTML = '<div class="muted">暂无阶段模板。</div>';
        return;
      }
      if (!els.templateStage.value) {
        els.templateStage.value = BOOTSTRAP.stages[0].key;
      }
      renderTemplateList(els.templateStage.value).catch(err => setMessage(err.message));
    }

    async function renderTemplateList(stageKey) {
      const plans = await api(`/api/stages/${stageKey}/plan`);
      els.templateList.innerHTML = plans.length ? plans.map(plan => `
        <div class="list-item">
          <strong>${escapeHtml(plan.title)}</strong>
          <div class="muted">${escapeHtml(plan.stage_label)} · ${escapeHtml(plan.document_key)}</div>
          <div class="desc">${escapeHtml(plan.description)}</div>
          <div class="tag-row" style="margin-top:8px">
            ${plan.assignee_role_keys.map(key => `<span class="tag">${escapeHtml(roleLabel(key))}</span>`).join('')}
          </div>
          <div class="muted" style="margin-top:8px">提纲：${escapeHtml(plan.outline.join(' / '))}</div>
        </div>
      `).join('') : '<div class="muted">当前阶段暂无模板。</div>';
    }

    async function createProject() {
      const body = {
        name: document.getElementById('project-name').value.trim(),
        duration: document.getElementById('project-duration').value.trim(),
        summary: document.getElementById('project-summary').value.trim(),
        role_keys: selectedValues('create-role'),
      };
      const created = await api('/api/projects', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      clearCreateForm();
      setMessage(`项目已创建：${created.name}，成果目录已生成。`);
      state.selectedProjectId = created.id;
      await refreshProjects();
      state.activeTab = 'overview';
      renderAll();
    }

    function clearCreateForm() {
      document.getElementById('project-name').value = '';
      document.getElementById('project-duration').value = '';
      document.getElementById('project-summary').value = '';
      document.querySelectorAll('input[type=checkbox][data-kind="create-role"]').forEach(input => {
        input.checked = false;
      });
    }

    async function saveProject() {
      const project = currentProject();
      if (!project) return;
      const body = {
        name: document.getElementById('edit-project-name').value.trim(),
        duration: document.getElementById('edit-project-duration').value.trim(),
        summary: document.getElementById('edit-project-summary').value.trim(),
        role_keys: selectedValues('project-role'),
        stage_keys: selectedValues('project-stage'),
      };
      await api(`/api/projects/${project.id}`, {
        method: 'PUT',
        body: JSON.stringify(body),
      });
      setMessage('项目已保存。');
      await refreshProjects();
      state.activeTab = 'overview';
      renderAll();
    }

    async function deleteProject() {
      const project = currentProject();
      if (!project) return;
      if (!confirm(`确认删除项目“${project.name}”？`)) return;
      await api(`/api/projects/${project.id}`, { method: 'DELETE' });
      state.selectedProjectId = null;
      state.selectedStageDocId = null;
      state.selectedPeriodicDocId = null;
      state.selectedRecordId = null;
      setMessage('项目已删除。');
      await refreshProjects(false);
    }

    async function clearAllProjects() {
      if (!confirm('确认清空全部项目？此操作会删除数据库中的所有项目数据。')) return;
      await api('/api/projects', { method: 'DELETE' });
      state.selectedProjectId = null;
      state.selectedStageDocId = null;
      state.selectedPeriodicDocId = null;
      state.selectedRecordId = null;
      setMessage('全部项目信息已清空。');
      await refreshProjects(false);
    }

    async function saveStageDoc() {
      const project = currentProject();
      if (!project) return;
      const body = {
        id: document.getElementById('stage-doc-id').value || null,
        stage_key: document.getElementById('stage-doc-stage').value,
        document_key: document.getElementById('stage-doc-key').value.trim(),
        title: document.getElementById('stage-doc-title').value.trim(),
        description: document.getElementById('stage-doc-desc').value.trim(),
        assignee_role_keys: selectedValues('stage-doc-role'),
        outline: parseLines(document.getElementById('stage-doc-outline').value),
        required_inputs: parseLines(document.getElementById('stage-doc-inputs').value),
        content: document.getElementById('stage-doc-content').value,
      };
      const method = body.id ? 'PUT' : 'POST';
      const url = body.id ? `/api/projects/${project.id}/stage-docs/${body.id}` : `/api/projects/${project.id}/stage-docs`;
      await api(url, { method, body: JSON.stringify(body) });
      state.selectedStageDocId = null;
      setMessage('阶段文档已保存。');
      await refreshProjects();
      state.activeTab = 'stage-docs';
      renderAll();
    }

    async function deleteStageDoc() {
      const project = currentProject();
      if (!project) return;
      const id = document.getElementById('stage-doc-id').value;
      if (!id) return;
      if (!confirm('确认删除当前阶段文档？')) return;
      await api(`/api/projects/${project.id}/stage-docs/${id}`, { method: 'DELETE' });
      state.selectedStageDocId = null;
      setMessage('阶段文档已删除。');
      await refreshProjects();
      state.activeTab = 'stage-docs';
      renderAll();
    }

    async function savePeriodicDoc() {
      const project = currentProject();
      if (!project) return;
      const body = {
        id: document.getElementById('periodic-doc-id').value || null,
        key: document.getElementById('periodic-doc-key').value.trim(),
        title: document.getElementById('periodic-doc-title').value.trim(),
        cadence: document.getElementById('periodic-doc-cadence').value,
        description: document.getElementById('periodic-doc-desc').value.trim(),
        period_label: document.getElementById('periodic-doc-label').value.trim(),
        assignee_role_keys: selectedValues('periodic-doc-role'),
        outline: parseLines(document.getElementById('periodic-doc-outline').value),
        required_inputs: parseLines(document.getElementById('periodic-doc-inputs').value),
        content: document.getElementById('periodic-doc-content').value,
      };
      const method = body.id ? 'PUT' : 'POST';
      const url = body.id ? `/api/projects/${project.id}/periodic-docs/${body.id}` : `/api/projects/${project.id}/periodic-docs`;
      await api(url, { method, body: JSON.stringify(body) });
      state.selectedPeriodicDocId = null;
      setMessage('定期文档已保存。');
      await refreshProjects();
      state.activeTab = 'periodic-docs';
      renderAll();
    }

    async function deletePeriodicDoc() {
      const project = currentProject();
      if (!project) return;
      const id = document.getElementById('periodic-doc-id').value;
      if (!id) return;
      if (!confirm('确认删除当前定期文档？')) return;
      await api(`/api/projects/${project.id}/periodic-docs/${id}`, { method: 'DELETE' });
      state.selectedPeriodicDocId = null;
      setMessage('定期文档已删除。');
      await refreshProjects();
      state.activeTab = 'periodic-docs';
      renderAll();
    }

    async function saveRecord() {
      const project = currentProject();
      if (!project) return;
      const body = {
        id: document.getElementById('record-id').value || null,
        stage_key: document.getElementById('record-stage').value,
        record_type: document.getElementById('record-type').value,
        title: document.getElementById('record-title').value.trim(),
        content: document.getElementById('record-content').value.trim(),
        assignee_role_key: document.getElementById('record-role').value,
      };
      const method = body.id ? 'PUT' : 'POST';
      const url = body.id ? `/api/projects/${project.id}/records/${body.id}` : `/api/projects/${project.id}/records`;
      await api(url, { method, body: JSON.stringify(body) });
      state.selectedRecordId = null;
      setMessage('推进记录已保存。');
      await refreshProjects();
      state.activeTab = 'records';
      renderAll();
    }

    async function deleteRecord() {
      const project = currentProject();
      if (!project) return;
      const id = document.getElementById('record-id').value;
      if (!id) return;
      if (!confirm('确认删除当前记录？')) return;
      await api(`/api/projects/${project.id}/records/${id}`, { method: 'DELETE' });
      state.selectedRecordId = null;
      setMessage('推进记录已删除。');
      await refreshProjects();
      state.activeTab = 'records';
      renderAll();
    }

    function wireActiveTabButtons() {
      document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          state.activeTab = btn.dataset.tab;
          renderAll();
        });
      });
    }

    function wireCreateButtons() {
      document.getElementById('create-project-btn').onclick = () => createProject().catch(err => setMessage(err.message));
      document.getElementById('clear-create-btn').onclick = clearCreateForm;
      document.getElementById('refresh-btn').onclick = () => refreshProjects().catch(err => setMessage(err.message));
      document.getElementById('clear-all-btn').onclick = () => clearAllProjects().catch(err => setMessage(err.message));
      document.getElementById('load-template-btn').onclick = () => renderTemplateList(els.templateStage.value).catch(err => setMessage(err.message));
      els.templateStage.onchange = () => renderTemplateList(els.templateStage.value).catch(err => setMessage(err.message));
    }

    function wireDetailActions() {
      const saveProjectBtn = document.getElementById('save-project-btn');
      if (saveProjectBtn) saveProjectBtn.onclick = () => saveProject().catch(err => setMessage(err.message));
      const deleteProjectBtn = document.getElementById('delete-project-btn');
      if (deleteProjectBtn) deleteProjectBtn.onclick = () => deleteProject().catch(err => setMessage(err.message));

      const saveStageDocBtn = document.getElementById('save-stage-doc-btn');
      if (saveStageDocBtn) saveStageDocBtn.onclick = () => saveStageDoc().catch(err => setMessage(err.message));
      const deleteStageDocBtn = document.getElementById('delete-stage-doc-btn');
      if (deleteStageDocBtn) deleteStageDocBtn.onclick = () => deleteStageDoc().catch(err => setMessage(err.message));
      const resetStageDocBtn = document.getElementById('reset-stage-doc-btn');
      if (resetStageDocBtn) resetStageDocBtn.onclick = () => { state.selectedStageDocId = null; renderStageDocs(currentProject()); };

      const savePeriodicDocBtn = document.getElementById('save-periodic-doc-btn');
      if (savePeriodicDocBtn) savePeriodicDocBtn.onclick = () => savePeriodicDoc().catch(err => setMessage(err.message));
      const deletePeriodicDocBtn = document.getElementById('delete-periodic-doc-btn');
      if (deletePeriodicDocBtn) deletePeriodicDocBtn.onclick = () => deletePeriodicDoc().catch(err => setMessage(err.message));
      const resetPeriodicDocBtn = document.getElementById('reset-periodic-doc-btn');
      if (resetPeriodicDocBtn) resetPeriodicDocBtn.onclick = () => { state.selectedPeriodicDocId = null; renderPeriodicDocs(currentProject()); };

      const saveRecordBtn = document.getElementById('save-record-btn');
      if (saveRecordBtn) saveRecordBtn.onclick = () => saveRecord().catch(err => setMessage(err.message));
      const deleteRecordBtn = document.getElementById('delete-record-btn');
      if (deleteRecordBtn) deleteRecordBtn.onclick = () => deleteRecord().catch(err => setMessage(err.message));
      const resetRecordBtn = document.getElementById('reset-record-btn');
      if (resetRecordBtn) resetRecordBtn.onclick = () => { state.selectedRecordId = null; renderRecords(currentProject()); };
    }

    function renderAll() {
      renderTabsVisibility();
      const project = currentProject();
      renderSummary(project);
      renderProjectList();
      renderTemplatePanel();
      renderOverview(project);
      renderStageDocs(project);
      renderPeriodicDocs(project);
      renderRecords(project);
      wireDetailActions();
    }

    buildCheckboxGrid(els.createRoleList, 'create-role', BOOTSTRAP.roles);
    BOOTSTRAP.stages.forEach(stage => {
      const option = document.createElement('option');
      option.value = stage.key;
      option.textContent = stage.label;
      els.templateStage.appendChild(option);
    });
    if (BOOTSTRAP.stages[0]) {
      els.templateStage.value = BOOTSTRAP.stages[0].key;
    }
    wireCreateButtons();
    wireActiveTabButtons();
    refreshProjects().catch(err => setMessage(err.message));
  </script>
</body>
</html>
"""
    return html.replace("{BOOTSTRAP}", bootstrap_json)


def _send_json(handler: BaseHTTPRequestHandler, status: HTTPStatus, payload: Any) -> None:
    data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _read_json_body(handler: BaseHTTPRequestHandler) -> Any:
    length = int(handler.headers.get("Content-Length", "0"))
    if not length:
        return {}
    raw = handler.rfile.read(length).decode("utf-8")
    return json.loads(raw) if raw else {}


def _parse_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except Exception:
        return None


class ProjectManagementServer(ThreadingHTTPServer):
    def __init__(self, server_address, RequestHandlerClass, store: ProjectStore | None = None):
        self.store = store or ProjectStore()
        super().__init__(server_address, RequestHandlerClass)


class ProjectManagementHandler(BaseHTTPRequestHandler):
    server_version = "MetaGPTProjectManagement/1.0"

    @property
    def store(self) -> ProjectStore:
        return self.server.store  # type: ignore[attr-defined]

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/":
            self._html(_render_index_html())
            return
        if path == "/api/bootstrap":
            self._json(_bootstrap_payload(self.store))
            return
        if path == "/api/projects":
            self._json([_project_to_response(project).model_dump() for project in self.store.list_projects()])
            return
        if match := re.fullmatch(r"/api/projects/([^/]+)", path):
            self._get_project(match.group(1))
            return
        if match := re.fullmatch(r"/api/stages/([^/]+)/plan", path):
            self._get_stage_plan(match.group(1))
            return
        if match := re.fullmatch(r"/api/stages/([^/]+)/roles", path):
            self._get_stage_roles(match.group(1))
            return
        self._json({"detail": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/api/projects":
            self._create_project()
            return
        if match := re.fullmatch(r"/api/projects/([^/]+)/records", path):
            self._add_record(match.group(1))
            return
        if match := re.fullmatch(r"/api/projects/([^/]+)/stage-plan", path):
            self._project_stage_plan(match.group(1))
            return
        if match := re.fullmatch(r"/api/projects/([^/]+)/stage-docs", path):
            self._upsert_stage_doc(match.group(1))
            return
        if match := re.fullmatch(r"/api/projects/([^/]+)/periodic-docs", path):
            self._upsert_periodic_doc(match.group(1))
            return
        self._json({"detail": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_PUT(self):  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        if match := re.fullmatch(r"/api/projects/([^/]+)", path):
            self._update_project(match.group(1))
            return
        if match := re.fullmatch(r"/api/projects/([^/]+)/records/([^/]+)", path):
            self._update_record(match.group(1), match.group(2))
            return
        if match := re.fullmatch(r"/api/projects/([^/]+)/stage-docs/([^/]+)", path):
            self._update_stage_doc(match.group(1), match.group(2))
            return
        if match := re.fullmatch(r"/api/projects/([^/]+)/periodic-docs/([^/]+)", path):
            self._update_periodic_doc(match.group(1), match.group(2))
            return
        self._json({"detail": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_DELETE(self):  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/api/projects":
            self.store.clear_projects()
            self._json({"detail": "ok"})
            return
        if match := re.fullmatch(r"/api/projects/([^/]+)", path):
            self._delete_project(match.group(1))
            return
        if match := re.fullmatch(r"/api/projects/([^/]+)/records/([^/]+)", path):
            self._delete_record(match.group(1), match.group(2))
            return
        if match := re.fullmatch(r"/api/projects/([^/]+)/stage-docs/([^/]+)", path):
            self._delete_stage_doc(match.group(1), match.group(2))
            return
        if match := re.fullmatch(r"/api/projects/([^/]+)/periodic-docs/([^/]+)", path):
            self._delete_periodic_doc(match.group(1), match.group(2))
            return
        self._json({"detail": "Not found"}, HTTPStatus.NOT_FOUND)

    def log_message(self, fmt, *args):  # noqa: A003
        return

    def _html(self, content: str) -> None:
        data = content.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        _send_json(self, status, payload)

    def _get_project(self, project_id: str) -> None:
        uuid_value = _parse_uuid(project_id)
        if not uuid_value:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        project = self.store.get_project(uuid_value)
        if not project:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        self._json(_project_to_response(project).model_dump())

    def _create_project(self) -> None:
        try:
            payload = ProjectCreateRequest.model_validate(_read_json_body(self))
        except Exception as exc:
            self._json({"detail": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        project = ProjectItem(
            name=payload.name,
            duration=payload.duration,
            summary=payload.summary,
            role_keys=payload.role_keys,
            stage_keys=payload.stage_keys,
        )
        created = self.store.create_project(project)
        self._json(_project_to_response(created).model_dump(), HTTPStatus.CREATED)

    def _update_project(self, project_id: str) -> None:
        uuid_value = _parse_uuid(project_id)
        if not uuid_value:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            payload = ProjectUpdateRequest.model_validate(_read_json_body(self))
        except Exception as exc:
            self._json({"detail": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        project = self.store.get_project(uuid_value)
        if not project:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        changes = payload.model_dump(exclude_unset=True)
        if "name" in changes and changes["name"]:
            project.name = changes["name"]
        if "duration" in changes and changes["duration"] is not None:
            project.duration = changes["duration"]
        if "summary" in changes and changes["summary"] is not None:
            project.summary = changes["summary"]
        if "role_keys" in changes and changes["role_keys"] is not None:
            project.role_keys = changes["role_keys"]
        if "stage_keys" in changes and changes["stage_keys"] is not None:
            project.stage_keys = changes["stage_keys"]
        updated = self.store.save_project(project)
        self._json(_project_to_response(updated).model_dump())

    def _delete_project(self, project_id: str) -> None:
        uuid_value = _parse_uuid(project_id)
        if not uuid_value:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        if not self.store.delete_project(uuid_value):
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        self._json({"detail": "deleted"})

    def _add_record(self, project_id: str) -> None:
        uuid_value = _parse_uuid(project_id)
        if not uuid_value:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            payload = ProjectRecordCreateRequest.model_validate(_read_json_body(self))
        except Exception as exc:
            self._json({"detail": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        project = self.store.get_project(uuid_value)
        if not project:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        record = ProjectRecord(
            stage_key=payload.stage_key,
            record_type=payload.record_type,
            title=payload.title,
            content=payload.content,
            assignee_role_key=payload.assignee_role_key,
            occurred_at=payload.occurred_at or _utcnow(),
        )
        updated = self.store.add_record(uuid_value, record)
        self._json(_project_to_response(updated).model_dump(), HTTPStatus.CREATED)

    def _update_record(self, project_id: str, record_id: str) -> None:
        project_uuid = _parse_uuid(project_id)
        record_uuid = _parse_uuid(record_id)
        if not project_uuid or not record_uuid:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            payload = ProjectRecordUpdateRequest.model_validate(_read_json_body(self))
        except Exception as exc:
            self._json({"detail": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        project = self.store.get_project(project_uuid)
        if not project:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        record = ProjectRecord(
            id=record_uuid,
            stage_key=payload.stage_key,
            record_type=payload.record_type,
            title=payload.title,
            content=payload.content,
            assignee_role_key=payload.assignee_role_key,
            occurred_at=payload.occurred_at or _utcnow(),
            created_at=next((item.created_at for item in project.records if item.id == record_uuid), _utcnow()),
        )
        updated = self.store.update_record(project_uuid, record)
        if not updated:
            self._json({"detail": "Record not found"}, HTTPStatus.NOT_FOUND)
            return
        self._json(_project_to_response(updated).model_dump())

    def _delete_record(self, project_id: str, record_id: str) -> None:
        project_uuid = _parse_uuid(project_id)
        record_uuid = _parse_uuid(record_id)
        if not project_uuid or not record_uuid:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        updated = self.store.delete_record(project_uuid, record_uuid)
        if not updated:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        self._json(_project_to_response(updated).model_dump())

    def _save_stage_doc(self, project_uuid: UUID, payload: ProjectStageDocRequest, created: bool) -> None:
        if not project_uuid:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        project = self.store.get_project(project_uuid)
        if not project:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        doc = ProjectStageDocument(
            stage_key=payload.stage_key,
            document_key=payload.document_key,
            title=payload.title,
            description=payload.description,
            assignee_role_keys=payload.assignee_role_keys,
            outline=payload.outline,
            required_inputs=payload.required_inputs,
            content=payload.content,
        )
        if payload.id:
            doc.id = payload.id
            previous = next((item for item in project.stage_docs if item.id == payload.id), None)
            if previous:
                doc.created_at = previous.created_at
        updated = self.store.upsert_stage_doc(project_uuid, doc)
        if not updated:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        self._json(_project_to_response(updated).model_dump(), HTTPStatus.CREATED if created else HTTPStatus.OK)

    def _upsert_stage_doc(self, project_id: str) -> None:
        project_uuid = _parse_uuid(project_id)
        if not project_uuid:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            payload = ProjectStageDocRequest.model_validate(_read_json_body(self))
        except Exception as exc:
            self._json({"detail": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        self._save_stage_doc(project_uuid, payload, created=payload.id is None)

    def _update_stage_doc(self, project_id: str, doc_id: str) -> None:
        project_uuid = _parse_uuid(project_id)
        doc_uuid = _parse_uuid(doc_id)
        if not project_uuid or not doc_uuid:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            payload = ProjectStageDocRequest.model_validate(_read_json_body(self))
        except Exception as exc:
            self._json({"detail": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        payload.id = doc_uuid
        self._save_stage_doc(project_uuid, payload, created=False)

    def _delete_stage_doc(self, project_id: str, doc_id: str) -> None:
        project_uuid = _parse_uuid(project_id)
        doc_uuid = _parse_uuid(doc_id)
        if not project_uuid or not doc_uuid:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        updated = self.store.delete_stage_doc(project_uuid, doc_uuid)
        if not updated:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        self._json(_project_to_response(updated).model_dump())

    def _save_periodic_doc(self, project_uuid: UUID, payload: ProjectPeriodicDocRequest, created: bool) -> None:
        if not project_uuid:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        project = self.store.get_project(project_uuid)
        if not project:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        doc = ProjectPeriodicDocument(
            key=payload.key,
            title=payload.title,
            cadence=payload.cadence,
            description=payload.description,
            assignee_role_keys=payload.assignee_role_keys,
            outline=payload.outline,
            required_inputs=payload.required_inputs,
            content=payload.content,
            period_label=payload.period_label,
        )
        if payload.id:
            doc.id = payload.id
            previous = next((item for item in project.periodic_docs if item.id == payload.id), None)
            if previous:
                doc.created_at = previous.created_at
        updated = self.store.upsert_periodic_doc(project_uuid, doc)
        if not updated:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        self._json(_project_to_response(updated).model_dump(), HTTPStatus.CREATED if created else HTTPStatus.OK)

    def _upsert_periodic_doc(self, project_id: str) -> None:
        project_uuid = _parse_uuid(project_id)
        if not project_uuid:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            payload = ProjectPeriodicDocRequest.model_validate(_read_json_body(self))
        except Exception as exc:
            self._json({"detail": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        self._save_periodic_doc(project_uuid, payload, created=payload.id is None)

    def _update_periodic_doc(self, project_id: str, doc_id: str) -> None:
        project_uuid = _parse_uuid(project_id)
        doc_uuid = _parse_uuid(doc_id)
        if not project_uuid or not doc_uuid:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            payload = ProjectPeriodicDocRequest.model_validate(_read_json_body(self))
        except Exception as exc:
            self._json({"detail": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        payload.id = doc_uuid
        self._save_periodic_doc(project_uuid, payload, created=False)

    def _delete_periodic_doc(self, project_id: str, doc_id: str) -> None:
        project_uuid = _parse_uuid(project_id)
        doc_uuid = _parse_uuid(doc_id)
        if not project_uuid or not doc_uuid:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        updated = self.store.delete_periodic_doc(project_uuid, doc_uuid)
        if not updated:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        self._json(_project_to_response(updated).model_dump())

    def _project_stage_plan(self, project_id: str) -> None:
        uuid_value = _parse_uuid(project_id)
        if not uuid_value:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            payload = DocumentPlanRequest.model_validate(_read_json_body(self))
        except Exception as exc:
            self._json({"detail": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        project = self.store.get_project(uuid_value)
        if not project:
            self._json({"detail": "Project not found"}, HTTPStatus.NOT_FOUND)
            return
        if payload.stage_key not in project.stage_keys:
            self._json({"detail": "Stage is not enabled for this project"}, HTTPStatus.BAD_REQUEST)
            return
        try:
            self._json([plan.model_dump() for plan in build_planned_documents(payload.stage_key)])
        except KeyError:
            self._json({"detail": "Stage not found"}, HTTPStatus.NOT_FOUND)

    def _get_stage_plan(self, stage_key: str) -> None:
        try:
            self._json([plan.model_dump() for plan in build_planned_documents(stage_key)])
        except KeyError:
            self._json({"detail": "Stage not found"}, HTTPStatus.NOT_FOUND)

    def _get_stage_roles(self, stage_key: str) -> None:
        stage = next((item for item in list_supported_stages() if item.key == stage_key), None)
        if not stage:
            self._json({"detail": "Stage not found"}, HTTPStatus.NOT_FOUND)
            return
        self._json(
            {
                "stage_key": stage.key,
                "stage_label": stage.label,
                "recommended_roles": [
                    _role_to_dict(role) for role in get_recommended_roles_for_stage(stage_key)
                ],
            }
        )


def run_server(host: str = "127.0.0.1", port: int = 8008, store: ProjectStore | None = None) -> ProjectManagementServer:
    server = ProjectManagementServer((host, port), ProjectManagementHandler, store=store)
    print(f"MetaGPT project management server running at http://{host}:{port}")
    server.serve_forever()
    return server


if __name__ == "__main__":
    run_server()
