"""Role and lifecycle templates for the project management app."""

from __future__ import annotations

import importlib
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class RoleTemplate(BaseModel):
    key: str
    label: str
    description: str
    role_class_path: str
    default_goals: List[str] = Field(default_factory=list)
    supported_stages: List[str] = Field(default_factory=list)


class DocumentTemplate(BaseModel):
    key: str
    title: str
    description: str
    assignee_role_keys: List[str] = Field(default_factory=list)
    outline: List[str] = Field(default_factory=list)
    required_inputs: List[str] = Field(default_factory=list)


class PeriodicDocumentTemplate(BaseModel):
    key: str
    title: str
    cadence: str
    description: str
    assignee_role_keys: List[str] = Field(default_factory=list)
    outline: List[str] = Field(default_factory=list)
    required_inputs: List[str] = Field(default_factory=list)


class LifecycleStageTemplate(BaseModel):
    key: str
    label: str
    order: int
    description: str
    recommended_role_keys: List[str] = Field(default_factory=list)
    documents: List[DocumentTemplate] = Field(default_factory=list)
    periodic_documents: List[PeriodicDocumentTemplate] = Field(default_factory=list)


class ProjectLifecycleTemplate(BaseModel):
    roles: Dict[str, RoleTemplate]
    stages: List[LifecycleStageTemplate]

    def get_stage(self, stage_key: str) -> Optional[LifecycleStageTemplate]:
        return next((stage for stage in self.stages if stage.key == stage_key), None)

    def get_role(self, role_key: str) -> Optional[RoleTemplate]:
        return self.roles.get(role_key)


ROLE_CLASS_PATHS: Dict[str, str] = {
    "team_leader": "metagpt.roles.di.team_leader.TeamLeader",
    "project_manager": "metagpt.roles.project_manager.ProjectManager",
    "product_manager": "metagpt.roles.product_manager.ProductManager",
    "architect": "metagpt.roles.architect.Architect",
    "development_manager": "metagpt.roles.engineer.Engineer",
    "engineer": "metagpt.roles.engineer.Engineer",
    "qa_manager": "metagpt.roles.qa_engineer.QaEngineer",
    "researcher": "metagpt.roles.researcher.Researcher",
    "customer_service": "metagpt.roles.customer_service.CustomerService",
    "sales": "metagpt.roles.sales.Sales",
}


def _default_roles() -> Dict[str, RoleTemplate]:
    return {
        "team_leader": RoleTemplate(
            key="team_leader",
            label="团队负责人",
            description="统筹项目目标、推进节奏与跨角色协作。",
            role_class_path=ROLE_CLASS_PATHS["team_leader"],
            default_goals=["项目统筹", "风险协调", "里程碑跟踪"],
            supported_stages=["initiation", "requirement", "design", "development", "testing", "deployment", "trial", "acceptance"],
        ),
        "project_manager": RoleTemplate(
            key="project_manager",
            label="项目经理",
            description="负责计划拆解、进度跟踪、文档流转与风险管理。",
            role_class_path=ROLE_CLASS_PATHS["project_manager"],
            default_goals=["任务拆解", "进度管理", "文档归档"],
            supported_stages=["initiation", "requirement", "design", "development", "testing", "deployment", "trial", "acceptance"],
        ),
        "product_manager": RoleTemplate(
            key="product_manager",
            label="产品经理",
            description="负责需求分析、范围定义、需求变更与验收支持。",
            role_class_path=ROLE_CLASS_PATHS["product_manager"],
            default_goals=["需求分析", "范围定义", "需求变更管理"],
            supported_stages=["initiation", "requirement", "acceptance"],
        ),
        "architect": RoleTemplate(
            key="architect",
            label="架构师",
            description="负责系统架构、接口设计、数据结构与技术方案。",
            role_class_path=ROLE_CLASS_PATHS["architect"],
            default_goals=["架构设计", "接口设计", "技术选型"],
            supported_stages=["design", "development"],
        ),
        "development_manager": RoleTemplate(
            key="development_manager",
            label="开发经理",
            description="负责开发计划、实现协调、代码质量与交付推进。",
            role_class_path=ROLE_CLASS_PATHS["development_manager"],
            default_goals=["开发推进", "代码质量", "实现协调"],
            supported_stages=["design", "development", "testing", "deployment", "trial"],
        ),
        "engineer": RoleTemplate(
            key="engineer",
            label="开发工程师",
            description="负责功能实现、代码编写、缺陷修复与实现说明。",
            role_class_path=ROLE_CLASS_PATHS["engineer"],
            default_goals=["功能实现", "缺陷修复", "代码总结"],
            supported_stages=["development", "testing", "deployment", "trial"],
        ),
        "qa_manager": RoleTemplate(
            key="qa_manager",
            label="测试经理",
            description="负责测试计划、测试执行、缺陷分析与验收支持。",
            role_class_path=ROLE_CLASS_PATHS["qa_manager"],
            default_goals=["测试规划", "测试执行", "缺陷管理"],
            supported_stages=["testing", "deployment", "trial", "acceptance"],
        ),
        "researcher": RoleTemplate(
            key="researcher",
            label="研究员",
            description="负责调研、资料汇总、竞品分析与外部信息研究。",
            role_class_path=ROLE_CLASS_PATHS["researcher"],
            default_goals=["资料研究", "竞品分析", "信息汇总"],
            supported_stages=["initiation", "requirement", "design"],
        ),
        "customer_service": RoleTemplate(
            key="customer_service",
            label="售后服务",
            description="负责试运行、问题响应、用户反馈与交付支持。",
            role_class_path=ROLE_CLASS_PATHS["customer_service"],
            default_goals=["问题响应", "用户支持", "交付保障"],
            supported_stages=["deployment", "trial", "acceptance"],
        ),
        "sales": RoleTemplate(
            key="sales",
            label="销售",
            description="负责商务沟通、客户反馈收集与交付对接。",
            role_class_path=ROLE_CLASS_PATHS["sales"],
            default_goals=["商务沟通", "客户反馈", "交付对接"],
            supported_stages=["initiation", "requirement", "acceptance"],
        ),
    }


def _default_stages() -> List[LifecycleStageTemplate]:
    return [
        LifecycleStageTemplate(
            key="initiation",
            label="立项阶段",
            order=1,
            description="明确目标、范围、资源边界和里程碑。",
            recommended_role_keys=["team_leader", "project_manager", "product_manager", "researcher"],
            documents=[
                DocumentTemplate(
                    key="project_charter",
                    title="项目立项书",
                    description="说明项目背景、目标、范围、约束和风险。",
                    assignee_role_keys=["project_manager", "team_leader"],
                    outline=["项目背景", "项目目标", "项目范围", "主要风险", "里程碑计划"],
                    required_inputs=["项目名称", "项目时长", "项目任务概述", "参与角色"],
                ),
                DocumentTemplate(
                    key="stakeholder_register",
                    title="干系人登记表",
                    description="记录项目相关干系人及职责边界。",
                    assignee_role_keys=["project_manager", "team_leader"],
                    outline=["干系人列表", "职责说明", "沟通机制"],
                    required_inputs=["组织结构", "角色清单"],
                ),
            ],
            periodic_documents=[
                PeriodicDocumentTemplate(
                    key="weekly_report",
                    title="周报",
                    cadence="weekly",
                    description="总结本周推进情况、问题和下周计划。",
                    assignee_role_keys=["project_manager", "team_leader"],
                    outline=["本周完成情况", "问题与风险", "下周计划", "需协调事项"],
                    required_inputs=["按天推进记录", "会议纪要", "风险清单"],
                )
            ],
        ),
        LifecycleStageTemplate(
            key="requirement",
            label="需求调研阶段",
            order=2,
            description="收集需求、梳理场景并形成需求基线。",
            recommended_role_keys=["product_manager", "project_manager", "researcher", "sales"],
            documents=[
                DocumentTemplate(
                    key="requirement_analysis",
                    title="需求分析",
                    description="梳理业务诉求、用户场景和范围边界。",
                    assignee_role_keys=["product_manager", "researcher"],
                    outline=["项目介绍", "需求背景", "用户场景", "业务规则", "优先级"],
                    required_inputs=["项目任务概述", "会议纪要", "需求访谈记录"],
                ),
                DocumentTemplate(
                    key="requirements_specification",
                    title="需求规格说明书",
                    description="形成可执行、可验收的需求清单。",
                    assignee_role_keys=["product_manager", "project_manager"],
                    outline=["功能需求", "非功能需求", "范围边界", "验收口径", "变更流程"],
                    required_inputs=["需求分析", "原始需求材料", "变更记录"],
                ),
                DocumentTemplate(
                    key="change_log",
                    title="需求变更记录",
                    description="记录需求增删改及审批结果。",
                    assignee_role_keys=["project_manager", "product_manager"],
                    outline=["变更内容", "变更原因", "影响评估", "审批结论"],
                    required_inputs=["需求变更单", "会议纪要"],
                ),
            ],
            periodic_documents=[
                PeriodicDocumentTemplate(
                    key="weekly_report",
                    title="周报",
                    cadence="weekly",
                    description="记录需求调研进展和待确认事项。",
                    assignee_role_keys=["project_manager", "product_manager"],
                    outline=["本周完成情况", "待确认需求", "风险与问题", "下周计划"],
                    required_inputs=["每日推进情况", "会议纪要", "需求变更"],
                )
            ],
        ),
        LifecycleStageTemplate(
            key="design",
            label="设计阶段",
            order=3,
            description="输出系统设计、接口设计和实施方案。",
            recommended_role_keys=["architect", "project_manager", "development_manager"],
            documents=[
                DocumentTemplate(
                    key="architecture_design",
                    title="系统架构设计",
                    description="定义模块、技术路线和关键链路。",
                    assignee_role_keys=["architect", "project_manager"],
                    outline=["系统架构", "模块划分", "技术选型", "关键流程", "风险说明"],
                    required_inputs=["需求规格说明书", "项目背景", "技术约束"],
                ),
                DocumentTemplate(
                    key="database_design",
                    title="数据库设计",
                    description="定义实体、字段、索引与关系约束。",
                    assignee_role_keys=["architect", "development_manager"],
                    outline=["ER 关系", "表结构", "字段说明", "索引设计", "约束规则"],
                    required_inputs=["业务实体", "数据流", "查询场景"],
                ),
                DocumentTemplate(
                    key="implementation_plan",
                    title="开发实施方案",
                    description="定义开发拆分、里程碑和协作方式。",
                    assignee_role_keys=["project_manager", "development_manager"],
                    outline=["开发计划", "任务拆分", "里程碑", "风险应对", "协作机制"],
                    required_inputs=["架构设计", "项目时长", "角色清单"],
                ),
            ],
            periodic_documents=[
                PeriodicDocumentTemplate(
                    key="monthly_report",
                    title="月报",
                    cadence="monthly",
                    description="总结设计阶段成果、风险和下月计划。",
                    assignee_role_keys=["project_manager", "architect"],
                    outline=["月度进展", "阶段成果", "风险问题", "下月计划"],
                    required_inputs=["设计文档", "会议纪要", "阶段里程碑"],
                )
            ],
        ),
        LifecycleStageTemplate(
            key="development",
            label="开发阶段",
            order=4,
            description="完成代码实现、代码评审和实现说明。",
            recommended_role_keys=["development_manager", "engineer", "project_manager", "qa_manager"],
            documents=[
                DocumentTemplate(
                    key="development_log",
                    title="开发记录",
                    description="记录功能实现进展、关键代码和说明。",
                    assignee_role_keys=["engineer", "development_manager"],
                    outline=["开发目标", "实现内容", "关键代码", "遗留问题", "后续任务"],
                    required_inputs=["设计文档", "代码仓库", "每日推进记录"],
                ),
                DocumentTemplate(
                    key="source_code_index",
                    title="重要源代码索引",
                    description="汇总关键代码文件、模块职责和变更说明。",
                    assignee_role_keys=["engineer", "development_manager"],
                    outline=["核心模块", "关键文件", "接口说明", "变更摘要"],
                    required_inputs=["源代码", "提交记录", "评审意见"],
                ),
            ],
            periodic_documents=[
                PeriodicDocumentTemplate(
                    key="weekly_report",
                    title="周报",
                    cadence="weekly",
                    description="记录开发进展、阻塞点和下周计划。",
                    assignee_role_keys=["development_manager", "project_manager"],
                    outline=["本周完成", "阻塞问题", "风险", "下周计划"],
                    required_inputs=["开发日志", "会议纪要", "代码提交记录"],
                )
            ],
        ),
        LifecycleStageTemplate(
            key="testing",
            label="测试阶段",
            order=5,
            description="完成测试计划、用例、缺陷管理和测试总结。",
            recommended_role_keys=["qa_manager", "engineer", "project_manager"],
            documents=[
                DocumentTemplate(
                    key="test_plan",
                    title="测试计划",
                    description="定义测试范围、策略、环境和排期。",
                    assignee_role_keys=["qa_manager"],
                    outline=["测试目标", "测试范围", "测试环境", "测试策略", "时间安排"],
                    required_inputs=["需求规格说明书", "系统设计", "开发进展"],
                ),
                DocumentTemplate(
                    key="test_cases",
                    title="测试用例",
                    description="覆盖功能、接口、性能和异常场景。",
                    assignee_role_keys=["qa_manager", "engineer"],
                    outline=["用例编号", "场景", "前置条件", "步骤", "预期结果"],
                    required_inputs=["需求分析", "接口说明", "风险清单"],
                ),
                DocumentTemplate(
                    key="test_report",
                    title="测试报告",
                    description="总结测试结果、缺陷分布和改进建议。",
                    assignee_role_keys=["qa_manager", "project_manager"],
                    outline=["测试概述", "测试结果", "缺陷统计", "遗留问题", "结论"],
                    required_inputs=["测试用例", "缺陷记录", "修复结果"],
                ),
            ],
            periodic_documents=[
                PeriodicDocumentTemplate(
                    key="weekly_report",
                    title="周报",
                    cadence="weekly",
                    description="记录测试进展、缺陷修复和风险。",
                    assignee_role_keys=["qa_manager", "project_manager"],
                    outline=["本周执行情况", "缺陷情况", "风险", "下周计划"],
                    required_inputs=["测试结果", "缺陷清单", "会议纪要"],
                )
            ],
        ),
        LifecycleStageTemplate(
            key="deployment",
            label="部署阶段",
            order=6,
            description="完成上线准备、部署说明和回滚预案。",
            recommended_role_keys=["development_manager", "qa_manager", "project_manager", "customer_service"],
            documents=[
                DocumentTemplate(
                    key="deployment_manual",
                    title="部署手册",
                    description="说明部署环境、步骤、回滚和故障处理。",
                    assignee_role_keys=["development_manager", "project_manager"],
                    outline=["部署环境", "部署步骤", "配置说明", "回滚方案", "常见问题"],
                    required_inputs=["系统设计", "测试结论", "发布范围"],
                ),
                DocumentTemplate(
                    key="release_notes",
                    title="发布说明",
                    description="说明版本特性、已修复问题和已知限制。",
                    assignee_role_keys=["project_manager", "qa_manager"],
                    outline=["版本概述", "功能变化", "修复内容", "已知问题", "注意事项"],
                    required_inputs=["变更列表", "测试报告", "版本号"],
                ),
            ],
        ),
        LifecycleStageTemplate(
            key="trial",
            label="试运行阶段",
            order=7,
            description="跟踪试运行反馈、问题处理和持续优化。",
            recommended_role_keys=["customer_service", "project_manager", "development_manager", "qa_manager"],
            documents=[
                DocumentTemplate(
                    key="trial_operation_report",
                    title="试运行报告",
                    description="总结试运行期间的使用反馈、问题和改进建议。",
                    assignee_role_keys=["customer_service", "project_manager"],
                    outline=["试运行概况", "用户反馈", "问题汇总", "改进建议", "下一步计划"],
                    required_inputs=["日报/周报", "用户反馈", "工单记录"],
                ),
                DocumentTemplate(
                    key="issue_log",
                    title="问题记录",
                    description="记录试运行阶段的问题、处理过程和关闭结果。",
                    assignee_role_keys=["customer_service", "qa_manager"],
                    outline=["问题现象", "影响范围", "处理过程", "关闭状态"],
                    required_inputs=["工单", "会议纪要", "修复记录"],
                ),
            ],
            periodic_documents=[
                PeriodicDocumentTemplate(
                    key="weekly_report",
                    title="周报",
                    cadence="weekly",
                    description="记录试运行阶段问题处理和交付状态。",
                    assignee_role_keys=["customer_service", "project_manager"],
                    outline=["本周运行状态", "问题处理", "风险", "下周计划"],
                    required_inputs=["工单", "运维记录", "会议纪要"],
                )
            ],
        ),
        LifecycleStageTemplate(
            key="acceptance",
            label="验收阶段",
            order=8,
            description="整理验收材料、确认交付结果并完成收尾。",
            recommended_role_keys=["project_manager", "team_leader", "product_manager", "customer_service"],
            documents=[
                DocumentTemplate(
                    key="acceptance_criteria",
                    title="验收标准",
                    description="定义验收检查点、通过条件和责任分工。",
                    assignee_role_keys=["project_manager", "product_manager"],
                    outline=["验收范围", "验收条件", "验收步骤", "责任人", "结果判定"],
                    required_inputs=["需求规格说明书", "测试报告", "上线结果"],
                ),
                DocumentTemplate(
                    key="acceptance_report",
                    title="验收报告",
                    description="总结交付物、验收结果、遗留问题和后续支持。",
                    assignee_role_keys=["project_manager", "team_leader"],
                    outline=["项目概述", "交付成果", "验收结论", "遗留问题", "经验总结"],
                    required_inputs=["试运行报告", "发布说明", "验收标准"],
                ),
            ],
            periodic_documents=[
                PeriodicDocumentTemplate(
                    key="monthly_report",
                    title="月报",
                    cadence="monthly",
                    description="总结验收收尾阶段的工作进展与项目结论。",
                    assignee_role_keys=["project_manager", "team_leader"],
                    outline=["月度总结", "里程碑达成", "问题与风险", "收尾计划"],
                    required_inputs=["验收材料", "会议纪要", "遗留问题"],
                )
            ],
        ),
    ]


DEFAULT_PROJECT_LIFECYCLE = ProjectLifecycleTemplate(roles=_default_roles(), stages=_default_stages())


def list_supported_roles() -> List[RoleTemplate]:
    return list(DEFAULT_PROJECT_LIFECYCLE.roles.values())


def list_supported_stages() -> List[LifecycleStageTemplate]:
    return DEFAULT_PROJECT_LIFECYCLE.stages


def get_recommended_roles_for_stage(stage_key: str) -> List[RoleTemplate]:
    stage = DEFAULT_PROJECT_LIFECYCLE.get_stage(stage_key)
    if not stage:
        return []
    return [DEFAULT_PROJECT_LIFECYCLE.roles[key] for key in stage.recommended_role_keys if key in DEFAULT_PROJECT_LIFECYCLE.roles]


def get_document_templates_for_stage(stage_key: str) -> List[DocumentTemplate]:
    stage = DEFAULT_PROJECT_LIFECYCLE.get_stage(stage_key)
    return stage.documents if stage else []


def get_periodic_document_templates_for_stage(stage_key: str) -> List[PeriodicDocumentTemplate]:
    stage = DEFAULT_PROJECT_LIFECYCLE.get_stage(stage_key)
    return stage.periodic_documents if stage else []


def resolve_role_class(role_key: str):
    """Resolve a role template key to the concrete MetaGPT role class."""

    template = DEFAULT_PROJECT_LIFECYCLE.get_role(role_key)
    if not template:
        raise KeyError(f"Unknown role key: {role_key}")

    module_name, class_name = template.role_class_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)
