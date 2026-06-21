"""Project management templates and helpers."""

from .registry import (
    DEFAULT_PROJECT_LIFECYCLE,
    DocumentTemplate,
    LifecycleStageTemplate,
    PeriodicDocumentTemplate,
    RoleTemplate,
    get_document_templates_for_stage,
    get_periodic_document_templates_for_stage,
    get_recommended_roles_for_stage,
    list_supported_roles,
    list_supported_stages,
    resolve_role_class,
)

__all__ = [
    "DEFAULT_PROJECT_LIFECYCLE",
    "DocumentTemplate",
    "LifecycleStageTemplate",
    "PeriodicDocumentTemplate",
    "RoleTemplate",
    "get_document_templates_for_stage",
    "get_periodic_document_templates_for_stage",
    "get_recommended_roles_for_stage",
    "list_supported_roles",
    "list_supported_stages",
    "resolve_role_class",
]
