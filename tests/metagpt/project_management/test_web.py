from metagpt.project_management.store import ProjectItem, ProjectRecord, ProjectStore
from metagpt.project_management.web import build_planned_documents


def test_build_planned_documents_for_requirement():
    plans = build_planned_documents("requirement")
    assert [plan.document_key for plan in plans] == [
        "requirement_analysis",
        "requirements_specification",
        "change_log",
    ]


def test_store_round_trip(tmp_path):
    store = ProjectStore(root=tmp_path)
    project = ProjectItem(
        name="中文项目",
        duration="6个月",
        summary="测试项目",
        role_keys=["project_manager"],
        stage_keys=["requirement"],
    )
    store.create_project(project)

    record = ProjectRecord(
        stage_key="requirement",
        record_type="meeting_note",
        title="第一次会议",
        content="讨论需求边界",
        assignee_role_key="project_manager",
    )
    updated = store.add_record(project.id, record)

    assert updated is not None
    assert updated.name == "中文项目"
    assert updated.records[0].title == "第一次会议"
    assert store.get_project(project.id) is not None
