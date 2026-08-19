# ruff: noqa: E501 -- data literals are intentionally one job per line.
"""Build the deterministic golden matching dataset (synthetic regression set).

Labels are derived from construction, so this is a *regression* asset, not
field evidence: it proves the filter/rank pipeline does not drift, and it
keeps Recall@20 / False-Negative visible after every connector, normalizer,
ranker, or radar change.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path("evaluation/data/golden/golden_v1.json")

PLAN = {
    "target_role": "AI应用工程师",
    "locations": ["上海", "深圳"],
    "salary_min_k": 20,
    "recruitment_track": "social",
    "employment_type": "full_time",
    "exclusions": ["外包", "驻场"],
}


def match(
    job_id: str,
    title: str,
    company: str,
    city: str,
    salary: str,
    relevance: str,
    skills: str = "Python RAG Agent MCP",
    extra: str = "",
) -> dict:
    return {
        "id": job_id,
        "title": title,
        "company": company,
        "location": city,
        "description": (f"社招 全职 正式岗位 3-5年 {skills} {salary} {city} {extra}"),
        "url": f"https://example.com/golden/{job_id}",
        "label": {"should_match": True, "relevance": relevance, "reason": "构造匹配"},
    }


def reject(
    job_id: str, title: str, company: str, description: str, reason: str
) -> dict:
    return {
        "id": job_id,
        "title": title,
        "company": company,
        "location": "上海",
        "description": description,
        "url": f"https://example.com/golden/{job_id}",
        "label": {"should_match": False, "relevance": "low", "reason": reason},
    }


def build() -> dict:
    jobs = [
        match("m01", "AI应用工程师", "星河智联科技", "上海", "25-40K·14薪", "high"),
        match("m02", "AI应用工程师", "云帆智能科技", "深圳", "30-50K", "high"),
        match(
            "m03", "大模型应用开发工程师", "天工智能科技", "上海", "28-45K·15薪", "high"
        ),
        match("m04", "AI Agent工程师", "知行数据科技", "深圳", "25-45K", "high"),
        match(
            "m05", "AI应用工程师（Agent方向）", "深蓝智能科技", "上海", "30-55K", "high"
        ),
        match("m06", "AI应用开发工程师", "灵犀智能科技", "深圳", "22-40K·13薪", "high"),
        match("m07", "大模型应用工程师", "极目数字科技", "上海", "25-40K", "medium"),
        match("m08", "AI应用工程师", "华信数智科技", "深圳", "20-35K", "medium"),
        match("m09", "AI应用工程师", "蓝湖数据科技", "上海", "20-30K", "medium"),
        match(
            "m10",
            "大模型应用开发工程师",
            "青云智能科技",
            "深圳",
            "26-42K·14薪",
            "medium",
        ),
        match("m11", "AI应用工程师", "星图软件科技", "上海", "30-45K", "medium"),
        match("m12", "AI应用工程师", "微纳智能科技", "深圳", "25-35K", "medium"),
        match("m13", "AI应用工程师", "恒远信息技术", "上海", "20-40K", "low"),
        match("m14", "大模型应用工程师", "锐驰智能科技", "深圳", "22-38K", "low"),
        match("m15", "AI应用工程师", "万象互联科技", "上海", "21-36K", "low"),
        match(
            "m16", "AI Agent开发工程师", "北辰软件科技", "深圳", "24-44K·15薪", "low"
        ),
        match(
            "m17",
            "AI应用工程师",
            "辉宏科技公司",
            "上海",
            "35-60K",
            "high",
            skills="LangChain FastAPI",
        ),
        match(
            "m18",
            "大模型应用开发工程师",
            "恒创智能科技",
            "深圳",
            "30-50K·14薪",
            "high",
            skills="LLM RAG 向量检索",
        ),
        match(
            "m19",
            "AI应用工程师",
            "启明数据科技",
            "上海",
            "25-45K",
            "medium",
            skills="Dify 工作流",
        ),
        match(
            "m20",
            "AI应用工程师",
            "芯联智能科技",
            "深圳",
            "28-48K",
            "medium",
            skills="MCP 工具调用",
        ),
        match(
            "m21",
            "大模型应用工程师（智能体方向）",
            "智算未来科技",
            "上海",
            "30-50K",
            "high",
            skills="Agent 多智能体",
        ),
        match(
            "m22",
            "AI应用工程师",
            "数云智能科技",
            "深圳",
            "22-36K·13薪",
            "low",
            skills="API 集成",
        ),
        match(
            "m23",
            "AI应用工程师",
            "光点软件科技",
            "上海",
            "20-32K",
            "low",
            skills="Python Flask",
        ),
        match(
            "m24",
            "大模型应用开发工程师",
            "瀚海数据科技",
            "深圳",
            "23-40K",
            "medium",
            skills="RAG Agent",
        ),
        # ── Must be rejected ──────────────────────────────────────────
        reject(
            "x01",
            "AI产品经理",
            "某公司",
            "社招 全职 负责AI产品规划与需求分析",
            "角色不符",
        ),
        reject(
            "x02",
            "前端工程师",
            "某公司",
            "社招 全职 负责Web前端开发 React Vue",
            "角色不符",
        ),
        reject(
            "x03",
            "测试开发工程师",
            "某公司",
            "社招 全职 负责自动化测试平台开发",
            "角色不符",
        ),
        reject(
            "x04", "运维工程师", "某公司", "社招 全职 负责K8s运维与监控告警", "角色不符"
        ),
        reject(
            "x05",
            "数据仓库工程师",
            "某公司",
            "社招 全职 负责数仓建模与ETL开发",
            "角色不符",
        ),
        reject(
            "x06",
            "算法工程师（推荐系统）",
            "某公司",
            "社招 全职 Python 机器学习 推荐排序",
            "角色不符",
        ),
        reject(
            "x07",
            "AI应用工程师",
            "某公司",
            "社招 全职 Python RAG 25-40K 北京 岗位职责包括知识库问答",
            "城市不符",
        ),
        reject(
            "x08",
            "AI应用工程师",
            "某公司",
            "社招 全职 Python RAG 25-40K 杭州",
            "城市不符",
        ),
        reject(
            "x09",
            "AI应用工程师",
            "某公司",
            "社招 全职 Python RAG 15-18K 上海",
            "薪资过低",
        ),
        reject(
            "x10",
            "AI应用工程师",
            "某公司",
            "社招 全职 Python RAG 面议 上海",
            "薪资未公开",
        ),
        reject(
            "x11",
            "AI应用工程师",
            "某外包公司",
            "社招 全职 Python RAG 25-40K 上海 外包岗位",
            "外包",
        ),
        reject(
            "x12",
            "AI应用工程师",
            "某公司",
            "实习 全职 Python RAG 25-40K 上海 实习岗位",
            "实习",
        ),
        reject(
            "x13",
            "AI应用工程师",
            "某公司",
            "校招 应届 Python RAG 25-40K 上海 2027届",
            "校招",
        ),
        reject(
            "x14",
            "AI应用工程师",
            "某公司",
            "社招 全职 Python RAG 25-40K 广州",
            "城市不符",
        ),
        reject(
            "x15",
            "AI应用工程师",
            "某公司",
            "社招 全职 Python RAG 25-40K 上海 驻场开发",
            "驻场",
        ),
        reject(
            "x16",
            "AI应用工程师",
            "某公司",
            "社招 全职 Python RAG 25-40K 上海",
            "closed",
        ),
    ]
    # x16 must be closed: keep description, but mark closed via payload below.
    jobs[-1]["closed"] = True
    return {
        "dataset_version": "golden_v1",
        "dataset_type": "golden_synthetic_regression",
        "plan": PLAN,
        "provenance": {
            "evidence_kind": "synthetic",
            "collection_method": "generated_fixture",
            "human_annotated": False,
            "labeler": "script",
            "notes": "确定性构造的回归集，不可作为对外质量声明",
        },
        "jobs": jobs,
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(build(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT} ({len(build()['jobs'])} jobs)")


if __name__ == "__main__":
    main()
