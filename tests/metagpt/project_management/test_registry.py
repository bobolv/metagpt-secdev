import types

import importlib

from metagpt.project_management import (
    DEFAULT_PROJECT_LIFECYCLE,
    get_document_templates_for_stage,
    get_recommended_roles_for_stage,
    list_supported_roles,
    list_supported_stages,
    resolve_role_class,
)


def test_supported_stages_cover_lifecycle():
    stages = [stage.key for stage in list_supported_stages()]
    assert stages == [
        "initiation",
        "requirement",
        "design",
        "development",
        "testing",
        "deployment",
        "trial",
        "acceptance",
    ]


def test_supported_roles_include_core_project_roles():
    role_keys = [role.key for role in list_supported_roles()]
    assert {"team_leader", "project_manager", "product_manager", "architect", "engineer", "qa_manager"}.issubset(
        set(role_keys)
    )


def test_stage_templates_are_populated():
    requirement_docs = get_document_templates_for_stage("requirement")
    assert {doc.key for doc in requirement_docs} >= {"requirement_analysis", "requirements_specification", "change_log"}

    design_roles = [role.key for role in get_recommended_roles_for_stage("design")]
    assert {"architect", "project_manager", "development_manager"}.issubset(set(design_roles))


def test_resolve_role_class(monkeypatch):
    fake_module = types.ModuleType("fake_project_manager_module")
    original_import_module = importlib.import_module

    class ProjectManager:
        pass

    fake_module.ProjectManager = ProjectManager
    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda name: fake_module if name == "metagpt.roles.project_manager" else original_import_module(name),
    )

    role_cls = resolve_role_class("project_manager")
    assert role_cls is ProjectManager


def test_default_template_is_consistent():
    assert DEFAULT_PROJECT_LIFECYCLE.get_stage("acceptance") is not None
