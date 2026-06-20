import sys
import os
sys.path.append(os.getcwd())
import asyncio

def load_context(project):
    path = f"/app/metagpt/projects/{project}/00_context.md"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


async def run_metagpt(stage, doc_name, project, context):
    # 根据文档类型选择对应的角色和生成要求
    role_prompt = ""
    requirements = ""
    
    if stage == "report":
        # 处理周报/月报生成
        from metagpt.roles.project_manager import ProjectManager
        role = ProjectManager()
        role_prompt = "你是资深项目经理，擅长编写项目周报和月报。"
        
        report_info = doc_name.split(":", 1)
        report_type, report_date = report_info
        
        if report_type == "weekly":
            requirements = f"生成{report_date}所在周的项目周报，内容包含：1. 本周工作完成情况；2. 下周工作计划；3. 当前存在的风险与问题；4. 需要协调的事项。结合项目背景，内容要真实具体，符合项目进度。"
        elif report_type == "monthly":
            requirements = f"生成{report_date}月份的项目月报，内容包含：1. 月度整体进度概述；2. 本月完成的主要工作和里程碑；3. 资源投入统计；4. 问题与风险总结；5. 下月工作计划。结合项目背景，内容要真实具体，符合项目2026年1月至12月的周期。"
    elif stage == "requirement":
        from metagpt.roles.product_manager import ProductManager
        role = ProductManager()
        role_prompt = "你是资深产品经理，擅长编写需求分析和需求规格说明文档。"
        requirements = f"输出完整的{doc_name}文档，包含所有必要章节，内容详细具体，符合电子文件系统与档案管理、BM系统适配项目的实际需求。"
    elif stage == "design":
        from metagpt.roles.architect import Architect
        role = Architect()
        role_prompt = "你是资深系统架构师，擅长编写技术设计相关文档。"
        if doc_name == "开发计划":
            requirements = "输出详细的项目开发计划，包含项目进度安排、人员分工、里程碑、风险评估等内容，项目周期为2026年1月至12月。"
        elif doc_name == "概要设计":
            requirements = "输出系统概要设计文档，包含系统架构、模块划分、接口设计、关键技术选型等内容。"
        elif doc_name == "详细设计":
            requirements = "输出系统详细设计文档，包含每个模块的实现逻辑、类图、时序图、算法设计等内容。"
        elif doc_name == "数据库结构设计":
            requirements = "输出数据库结构设计文档，包含ER图、表结构设计、字段说明、索引设计、关系约束等内容。"
        elif doc_name == "编码规范":
            requirements = "输出项目编码规范文档，包含命名规范、代码风格、注释要求、安全规范等内容。"
    elif stage == "implementation":
        from metagpt.roles.engineer import Engineer
        role = Engineer()
        role_prompt = "你是资深开发工程师，擅长编写实施和部署相关文档。"
        if doc_name == "部署手册":
            requirements = "输出系统部署手册，包含部署环境要求、部署步骤、配置说明、故障排查等内容。"
        elif doc_name == "系统配置":
            requirements = "输出系统配置文档，包含各个模块的配置项说明、配置方法、默认值等内容。"
        elif doc_name == "用户手册":
            requirements = "输出用户操作手册，包含系统功能介绍、操作步骤、常见问题等内容，适合普通用户使用。"
        elif doc_name == "系统维护手册":
            requirements = "输出系统维护手册，包含系统监控、日常维护、故障处理、版本升级等内容，适合运维人员使用。"
        elif doc_name == "试运行方案":
            requirements = "输出系统试运行方案，包含试运行目标、范围、时间安排、测试内容、问题处理流程等内容。"
    elif stage == "test":
        from metagpt.roles.tester import Tester
        role = Tester()
        role_prompt = "你是资深测试工程师，擅长编写测试相关文档。"
        if doc_name == "测试方案":
            requirements = "输出项目测试方案，包含测试目标、测试范围、测试环境、测试方法、测试用例设计策略等内容。"
        elif doc_name == "测试用例":
            requirements = "输出详细的测试用例，覆盖所有功能模块、接口、性能、安全等测试点，包含用例ID、测试场景、前置条件、测试步骤、预期结果等。"
        elif doc_name == "测试报告":
            requirements = "输出项目测试报告，包含测试概述、测试结果统计、问题分析、测试结论等内容。"
    elif stage == "acceptance":
        from metagpt.roles.project_manager import ProjectManager
        role = ProjectManager()
        role_prompt = "你是资深项目经理，擅长编写项目总结和验收相关文档。"
        requirements = "输出项目总结报告，包含项目概述、完成情况、成果展示、经验总结、后续建议等内容。"

    system_prompt = role_prompt
    user_prompt = f"""
        文档类型：{doc_name}
        项目阶段：{stage}

        项目背景：
        {context}

        要求：
        1. {requirements}
        2. 输出标准企业级文档，结构清晰，内容完整
        3. 必须符合软件工程生命周期和国家相关标准规范
        4. 可直接用于项目验收、开发和实施
        5. 输出 Markdown 格式，不要添加任何多余的解释内容
        """
    
    # 直接使用LLM API调用，更简单稳定
    from metagpt.llm import LLM
    llm = LLM()
    content = await llm.aask(user_prompt, system_msgs=[system_prompt])
    
    if not content or content.strip() in ['None', '']:
        raise ValueError(f"MetaGPT返回内容为空，请检查LLM调用是否正常。返回值: {content}")
    return content

async def main(stage, doc_name, project):
    context = load_context(project)

    output = await run_metagpt(stage, doc_name, project, context)

    # 生成正确的输出文件名
    from tools.lifecycle_orchestrator import STAGES, STAGE_ORDER
    from datetime import datetime
    
    if stage == "report":
        # 处理报告路径
        report_dir = f"./projects/{project}/reports"
        os.makedirs(report_dir, exist_ok=True)
        
        report_info = doc_name.split(":", 1)
        report_type, report_date = report_info
        
        if report_type == "weekly":
            date_obj = datetime.strptime(report_date, "%Y-%m-%d")
            week_num = date_obj.isocalendar()[1]
            file_path = f"{report_dir}/weekly_{date_obj.year}_{week_num}.md"
        else: # monthly
            file_path = f"{report_dir}/monthly_{report_date}.md"
    else:
        # 普通文档路径
        stage_idx = STAGE_ORDER.index(stage) + 1
        doc_idx = STAGES[stage].index(doc_name) + 1
        file_path = f"./projects/{project}/{stage_idx:02d}_{doc_idx:02d}_{doc_name}.md"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(str(output))   # ✔ 强制转 string
        
if __name__ == "__main__":
    stage = sys.argv[1]
    doc_name = sys.argv[2]
    project = sys.argv[3]

    asyncio.run(main(stage, doc_name, project))
