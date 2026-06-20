import os
import argparse
from datetime import datetime, timedelta

STAGES = {
    "requirement": ["需求分析", "需求规格说明"],
    "design": ["开发计划", "概要设计", "详细设计", "数据库结构设计", "编码规范"],
    "implementation": ["部署手册", "系统配置", "用户手册", "系统维护手册", "试运行方案"],
    "test": ["测试方案", "测试用例", "测试报告"],
    "acceptance": ["项目总结报告"]
}

# 阶段顺序
STAGE_ORDER = ["requirement", "design", "implementation", "test", "acceptance"]

# 报告类型
REPORT_TYPES = ["weekly", "monthly"]

def get_next_task(project_path):
    """获取下一个需要生成的文档任务"""
    for stage_idx, stage_name in enumerate(STAGE_ORDER):
        docs = STAGES[stage_name]
        for doc_idx, doc_name in enumerate(docs):
            file = f"{project_path}/{stage_idx+1:02d}_{doc_idx+1}_{doc_name}.md"
            if not os.path.exists(file):
                return stage_name, doc_name, file
    return None, None, None


def run_metagpt(stage, doc_name, project):
    os.system(
        f'python tools/lifecycle_agent.py {stage} "{doc_name}" {project}'
    )


def run_report(report_type, report_date, project):
    os.system(
        f'python tools/lifecycle_agent.py report "{report_type}:{report_date}" {project}'
    )


def get_tasks_by_stages(project_path, selected_stages):
    """根据指定阶段获取需要生成的文档任务"""
    tasks = []
    for stage_idx, stage_name in enumerate(STAGE_ORDER):
        if stage_name not in selected_stages:
            continue
        docs = STAGES[stage_name]
        for doc_idx, doc_name in enumerate(docs):
            file = f"{project_path}/{stage_idx+1:02d}_{doc_idx+1}_{doc_name}.md"
            if not os.path.exists(file):
                tasks.append((stage_name, doc_name, file))
    return tasks


def auto_run(project, selected_stages=None):
    project_path = f"./projects/{project}"
    
    if selected_stages:
        # 生成指定阶段的文档
        tasks = get_tasks_by_stages(project_path, selected_stages)
        if not tasks:
            print(f"✅ All documents in selected stages {selected_stages} are already generated")
            return
        
        for stage, doc_name, output_file in tasks:
            print(f"🚀 Generating document: {doc_name} (Stage: {stage})")
            run_metagpt(stage, doc_name, project)
            
            if os.path.exists(output_file):
                print(f"✅ Document saved: {output_file}")
            else:
                print(f"❌ Failed to generate document: {doc_name}")
                return
    else:
        # 生成所有阶段文档
        while True:
            stage, doc_name, output_file = get_next_task(project_path)
            
            if not stage:
                print("✅ All project documents generated successfully")
                return
            
            print(f"🚀 Generating document: {doc_name} (Stage: {stage})")
            run_metagpt(stage, doc_name, project)
            
            if os.path.exists(output_file):
                print(f"✅ Document saved: {output_file}")
            else:
                print(f"❌ Failed to generate document: {doc_name}")
                return


def list_stages():
    """列出所有支持的阶段和文档"""
    print("Supported stages and documents:")
    print("-" * 50)
    for i, stage in enumerate(STAGE_ORDER):
        print(f"{i+1}. {stage}:")
        for j, doc in enumerate(STAGES[stage]):
            print(f"  {i+1}.{j+1} {doc}")
    print("\nReport types: weekly (周报), monthly (月报)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MetaGPT Project Document Generator")
    parser.add_argument("project", help="Project name (directory under projects/)")
    parser.add_argument("--stage", "-s", help="Generate documents for specific stages, comma separated (e.g. requirement,design)")
    parser.add_argument("--report", "-r", help="Generate report, format: type:date (e.g. weekly:2026-01-01, monthly:2026-06)")
    parser.add_argument("--list", "-l", action="store_true", help="List all supported stages and documents")
    
    args = parser.parse_args()
    
    if args.list:
        list_stages()
    elif args.report:
        report_info = args.report.split(":", 1)
        if len(report_info) != 2:
            print("❌ Invalid report format, use: type:date (e.g. weekly:2026-01-01)")
            exit(1)
        report_type, report_date = report_info
        if report_type not in REPORT_TYPES:
            print(f"❌ Unsupported report type: {report_type}, supported types: {REPORT_TYPES}")
            exit(1)
        
        print(f"🚀 Generating {report_type} report for {report_date}")
        run_report(report_type, report_date, args.project)
        
        # 检查报告是否生成成功
        report_dir = f"./projects/{args.project}/reports"
        if report_type == "weekly":
            date_obj = datetime.strptime(report_date, "%Y-%m-%d")
            week_num = date_obj.isocalendar()[1]
            report_file = f"{report_dir}/weekly_{date_obj.year}_{week_num}.md"
        else: # monthly
            report_file = f"{report_dir}/monthly_{report_date}.md"
        
        if os.path.exists(report_file):
            print(f"✅ Report saved: {report_file}")
        else:
            print(f"❌ Failed to generate report")
    else:
        selected_stages = None
        if args.stage:
            selected_stages = [s.strip() for s in args.stage.split(",")]
            # 验证阶段是否有效
            for s in selected_stages:
                if s not in STAGE_ORDER:
                    print(f"❌ Unsupported stage: {s}, supported stages: {STAGE_ORDER}")
                    exit(1)
            print(f"📋 Selected stages: {selected_stages}")
        
        auto_run(args.project, selected_stages)
