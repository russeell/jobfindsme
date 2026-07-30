#!/usr/bin/env python3
"""Build a synthetic Chinese fixture for evaluation regression tests.

Generates a 5-day, 50-job labeled dataset covering all five Chinese
recruitment platforms. Every job, URL, source outcome, and label is fabricated;
the output must never be used as M14 field evidence or a product-quality claim.

Usage:
  python scripts/build_chinese_synthetic_dataset.py \
    --output data/eval/synthetic/chinese_seed_v1.0.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobfindsme.evaluation.labeling import (
    DailyLabels,
    JobLabel,
    LabeledDataset,
    write_labeled_dataset,
)

# ── Fabricated Chinese job catalog (17 unique jobs across 5 platforms) ───────

_JOB_CATALOG: list[dict] = [
    # BOSS直聘 (indices 0-4)
    {
        "job_id": "boss-ai-app-001",
        "source_name": "BOSS直聘",
        "title": "AI应用工程师",
        "company": "字节跳动",
        "location": "上海·浦东新区",
        "apply_url": "https://www.zhipin.com/job_detail/ai-app-001.html",
    },
    {
        "job_id": "boss-llm-algo-002",
        "source_name": "BOSS直聘",
        "title": "大模型算法工程师",
        "company": "阿里巴巴",
        "location": "杭州·余杭区",
        "apply_url": "https://www.zhipin.com/job_detail/llm-algo-002.html",
    },
    {
        "job_id": "boss-agent-dev-003",
        "source_name": "BOSS直聘",
        "title": "AI Agent开发工程师",
        "company": "腾讯",
        "location": "深圳·南山区",
        "apply_url": "https://www.zhipin.com/job_detail/agent-dev-003.html",
    },
    {
        "job_id": "boss-ml-eng-004",
        "source_name": "BOSS直聘",
        "title": "机器学习工程师（大模型方向）",
        "company": "百度",
        "location": "北京·海淀区",
        "apply_url": "https://www.zhipin.com/job_detail/ml-eng-004.html",
    },
    {
        "job_id": "boss-ai-ops-005",
        "source_name": "BOSS直聘",
        "title": "AI运维开发工程师",
        "company": "蚂蚁集团",
        "location": "杭州·西湖区",
        "apply_url": "https://www.zhipin.com/job_detail/ai-ops-005.html",
    },
    # 猎聘 (indices 5-8)
    {
        "job_id": "liepin-llm-app-001",
        "source_name": "猎聘",
        "title": "LLM应用开发工程师",
        "company": "华为",
        "location": "深圳·龙岗区",
        "apply_url": "https://www.liepin.com/job/llm-app-001.shtml",
    },
    {
        "job_id": "liepin-ai-arch-002",
        "source_name": "猎聘",
        "title": "AI架构师（Agent方向）",
        "company": "小红书",
        "location": "上海·黄浦区",
        "apply_url": "https://www.liepin.com/job/ai-arch-002.shtml",
    },
    {
        "job_id": "liepin-rag-dev-003",
        "source_name": "猎聘",
        "title": "RAG应用开发工程师",
        "company": "美团",
        "location": "北京·朝阳区",
        "apply_url": "https://www.liepin.com/job/rag-dev-003.shtml",
    },
    {
        "job_id": "liepin-mcp-dev-004",
        "source_name": "猎聘",
        "title": "MCP协议开发工程师",
        "company": "蔚来",
        "location": "上海·嘉定区",
        "apply_url": "https://www.liepin.com/job/mcp-dev-004.shtml",
    },
    # 前程无忧 (indices 9-11)
    {
        "job_id": "51job-ai-py-001",
        "source_name": "前程无忧",
        "title": "Python AI开发工程师",
        "company": "网易",
        "location": "广州·天河区",
        "apply_url": "https://jobs.51job.com/guangzhou/ai-py-001.html",
    },
    {
        "job_id": "51job-dl-eng-002",
        "source_name": "前程无忧",
        "title": "深度学习工程师",
        "company": "拼多多",
        "location": "上海·长宁区",
        "apply_url": "https://jobs.51job.com/shanghai/dl-eng-002.html",
    },
    {
        "job_id": "51job-nlp-eng-003",
        "source_name": "前程无忧",
        "title": "NLP算法工程师",
        "company": "小米",
        "location": "北京·海淀区",
        "apply_url": "https://jobs.51job.com/beijing/nlp-eng-003.html",
    },
    # 智联招聘 (indices 12-13)
    {
        "job_id": "zhilian-ai-rd-001",
        "source_name": "智联招聘",
        "title": "AI研发工程师",
        "company": "商汤科技",
        "location": "北京·海淀区",
        "apply_url": "https://jobs.zhaopin.com/ai-rd-001.htm",
    },
    {
        "job_id": "zhilian-mlops-002",
        "source_name": "智联招聘",
        "title": "MLOps工程师",
        "company": "科大讯飞",
        "location": "合肥·高新区",
        "apply_url": "https://jobs.zhaopin.com/mlops-002.htm",
    },
    # 拉勾 (indices 14-16)
    {
        "job_id": "lagou-fullstack-ai-001",
        "source_name": "拉勾",
        "title": "AI全栈工程师",
        "company": "得物",
        "location": "上海·杨浦区",
        "apply_url": "https://www.lagou.com/jobs/ai-fullstack-001.html",
    },
    {
        "job_id": "lagou-agent-fe-002",
        "source_name": "拉勾",
        "title": "Agent前端开发工程师",
        "company": "B站",
        "location": "上海·杨浦区",
        "apply_url": "https://www.lagou.com/jobs/agent-fe-002.html",
    },
    {
        "job_id": "lagou-ai-pm-003",
        "source_name": "拉勾",
        "title": "AI产品经理（技术背景）",
        "company": "知乎",
        "location": "北京·海淀区",
        "apply_url": "https://www.lagou.com/jobs/ai-pm-003.html",
    },
]

ALL_SOURCES = ["BOSS直聘", "猎聘", "前程无忧", "智联招聘", "拉勾"]


def _make_label(
    rank: int,
    cat_idx: int,
    *,
    annotated: bool = True,
    relevance: int = 2,
    liveness: str = "active",
    valid_link: bool = True,
    duplicate_of: str | None = None,
    hard_filter_error: bool = False,
    hard_filter_reason: str = "",
    notes: str = "",
) -> JobLabel:
    job = _JOB_CATALOG[cat_idx]
    return JobLabel(
        rank=rank,
        job_id=job["job_id"],
        source_name=job["source_name"],
        apply_url=job["apply_url"],
        title=job["title"],
        company=job["company"],
        location=job["location"],
        annotated=annotated,
        relevance=relevance,
        liveness=liveness,
        valid_link=valid_link,
        duplicate_of=duplicate_of,
        hard_filter_error=hard_filter_error,
        hard_filter_reason=hard_filter_reason,
        notes=notes,
    )


def _make_day(
    day: int,
    date: str,
    plan_id: str,
    profile_hash: str,
    labels: list[JobLabel],
    source_attempts: list[str],
    source_successes: list[str],
    source_failures: list[str],
    duplicates_detected: int,
    total_discovered: int,
    total_after_filter: int,
    time_to_first: float | None = None,
    agent_host: str = "zcode",
) -> DailyLabels:
    return DailyLabels(
        day=day,
        date=date,
        plan_id=plan_id,
        profile_hash=profile_hash,
        total_discovered=total_discovered,
        total_after_filter=total_after_filter,
        duplicates_detected=duplicates_detected,
        source_attempts=tuple(source_attempts),
        source_successes=tuple(source_successes),
        source_failures=tuple(source_failures),
        labels=tuple(labels),
        time_to_first_results_seconds=time_to_first,
        agent_host=agent_host,
        notes="",
    )


def build_seed_dataset() -> LabeledDataset:
    plan_id = "plan-seed-001"
    profile_hash = "sha256:seed-v1-a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5"

    # ── Day 1 (2026-07-26): All sources succeed ─────────────────────────
    day1 = _make_day(
        day=1,
        date="2026-07-26",
        plan_id=plan_id,
        profile_hash=profile_hash,
        labels=[
            _make_label(1, 0, relevance=3, notes="完美匹配—AI应用工程师，技能完全覆盖"),
            _make_label(2, 1, relevance=3, notes="完美匹配—大模型算法，方向对口"),
            _make_label(3, 6, relevance=3, notes="完美匹配—RAG应用开发，核心技能"),
            _make_label(4, 5, relevance=3, notes="完美匹配—LLM应用开发华为"),
            _make_label(5, 2, relevance=2, notes="相关—Agent开发，要求3年经验"),
            _make_label(6, 14, relevance=2, notes="相关—AI全栈，技术栈宽泛"),
            _make_label(7, 9, relevance=2, notes="相关—Python AI开发广州"),
            _make_label(8, 12, relevance=2, notes="相关—AI研发商汤"),
            _make_label(9, 8, relevance=1, notes="弱相关—MCP协议开发，偏工程化"),
            _make_label(
                10,
                3,
                relevance=1,
                notes="弱相关—ML工程师偏传统ML",
            ),
        ],
        source_attempts=ALL_SOURCES,
        source_successes=ALL_SOURCES,
        source_failures=[],
        duplicates_detected=2,
        total_discovered=107,
        total_after_filter=42,
        time_to_first=8.5,
    )

    # ── Day 2 (2026-07-27): 拉勾 fails (anti-bot) ─────────────────────
    day2 = _make_day(
        day=2,
        date="2026-07-27",
        plan_id=plan_id,
        profile_hash=profile_hash,
        labels=[
            _make_label(1, 5, relevance=3, notes="LLM应用开发华为—新发布"),
            _make_label(2, 0, relevance=3, notes="AI应用工程师字节—持续招聘"),
            _make_label(
                3,
                1,
                relevance=2,
                notes="大模型算法阿里—重复出现",
                duplicate_of="boss-llm-algo-002",
            ),
            _make_label(4, 7, relevance=3, notes="AI架构师小红书—Agent方向"),
            _make_label(5, 12, relevance=2, notes="AI研发商汤"),
            _make_label(6, 10, relevance=2, notes="深度学习拼多多"),
            _make_label(
                7,
                15,
                relevance=1,
                notes="弱相关—Agent前端而非后端",
            ),
            _make_label(
                8,
                4,
                relevance=2,
                notes="AI运维蚂蚁—边缘相关",
            ),
            _make_label(
                9,
                3,
                relevance=1,
                notes="弱相关—ML工程师百度，apply_url加载失败（403）",
                valid_link=False,
            ),
            _make_label(
                10,
                6,
                relevance=2,
                notes="RAG开发美团",
                duplicate_of="liepin-rag-dev-003",
            ),
        ],
        source_attempts=ALL_SOURCES,
        source_successes=["BOSS直聘", "猎聘", "前程无忧", "智联招聘"],
        source_failures=["拉勾"],
        duplicates_detected=1,
        total_discovered=95,
        total_after_filter=38,
        time_to_first=14.2,
    )

    # ── Day 3 (2026-07-28): All succeed ─────────────────────────────────
    day3 = _make_day(
        day=3,
        date="2026-07-28",
        plan_id=plan_id,
        profile_hash=profile_hash,
        labels=[
            _make_label(1, 0, relevance=3, notes="AI应用工程师字节—第三次出现"),
            _make_label(2, 7, relevance=3, notes="AI架构师小红书"),
            _make_label(3, 5, relevance=3, notes="LLM应用开发华为"),
            _make_label(4, 2, relevance=2, notes="Agent开发腾讯"),
            _make_label(5, 14, relevance=2, notes="AI全栈得物"),
            _make_label(6, 11, relevance=2, notes="NLP算法小米"),
            _make_label(7, 9, relevance=2, notes="Python AI网易"),
            _make_label(
                8,
                13,
                relevance=1,
                notes="弱相关—MLOps地点非首选",
            ),
            _make_label(
                9,
                16,
                relevance=0,
                notes="不相关—AI产品经理，非技术岗",
            ),
            _make_label(
                10,
                15,
                relevance=1,
                notes="弱相关—Agent前端",
                hard_filter_error=True,
                hard_filter_reason="前端岗位，角色过滤应排除非AI后端岗位",
            ),
        ],
        source_attempts=ALL_SOURCES,
        source_successes=ALL_SOURCES,
        source_failures=[],
        duplicates_detected=2,
        total_discovered=112,
        total_after_filter=45,
        time_to_first=9.1,
    )

    # ── Day 4 (2026-07-29): 前程无忧 partial (timeout) ─────────────────
    day4 = _make_day(
        day=4,
        date="2026-07-29",
        plan_id=plan_id,
        profile_hash=profile_hash,
        labels=[
            _make_label(1, 1, relevance=3, notes="大模型算法阿里—新发布"),
            _make_label(2, 6, relevance=3, notes="RAG开发美团"),
            _make_label(3, 5, relevance=3, notes="LLM应用开发华为"),
            _make_label(4, 0, relevance=2, notes="AI应用工程师字节"),
            _make_label(
                5,
                2,
                relevance=2,
                notes="Agent开发腾讯",
                duplicate_of="boss-agent-dev-003",
            ),
            _make_label(6, 14, relevance=2, notes="AI全栈得物"),
            _make_label(
                7,
                7,
                relevance=2,
                notes="AI架构师小红书—降薪重发",
                liveness="stale",
            ),
            _make_label(8, 13, relevance=2, notes="MLOps科大讯飞—加薪"),
            _make_label(
                9,
                9,
                relevance=1,
                notes="弱相关—Python AI但薪资低于门槛",
                hard_filter_error=True,
                hard_filter_reason="薪资15K低于计划最低20K阈值",
            ),
            _make_label(
                10,
                3,
                relevance=1,
                notes="弱相关—ML工程师百度",
                liveness="closed",
                valid_link=False,
            ),
        ],
        source_attempts=ALL_SOURCES,
        source_successes=["BOSS直聘", "猎聘", "智联招聘", "拉勾"],
        source_failures=["前程无忧"],
        duplicates_detected=3,
        total_discovered=88,
        total_after_filter=35,
        time_to_first=22.0,
    )

    # ── Day 5 (2026-07-30): All succeed ─────────────────────────────────
    day5 = _make_day(
        day=5,
        date="2026-07-30",
        plan_id=plan_id,
        profile_hash=profile_hash,
        labels=[
            _make_label(1, 0, relevance=3, notes="AI应用工程师字节—持续热招"),
            _make_label(2, 5, relevance=3, notes="LLM应用开发华为"),
            _make_label(3, 7, relevance=3, notes="AI架构师小红书"),
            _make_label(4, 1, relevance=2, notes="大模型算法阿里"),
            _make_label(5, 6, relevance=2, notes="RAG开发美团"),
            _make_label(6, 14, relevance=2, notes="AI全栈得物"),
            _make_label(7, 12, relevance=2, notes="AI研发商汤"),
            _make_label(8, 8, relevance=2, notes="MCP协议开发蔚来"),
            _make_label(
                9,
                11,
                relevance=2,
                notes="NLP算法小米",
                duplicate_of="51job-nlp-eng-003",
            ),
            _make_label(
                10,
                4,
                relevance=1,
                notes="弱相关—AI运维蚂蚁，岗位已下架（404）",
                valid_link=False,
            ),
        ],
        source_attempts=ALL_SOURCES,
        source_successes=ALL_SOURCES,
        source_failures=[],
        duplicates_detected=4,
        total_discovered=118,
        total_after_filter=48,
        time_to_first=7.9,
    )

    return LabeledDataset(
        dataset_version="1.0.0",
        dataset_type="synthetic_chinese_regression",
        provenance={
            "evidence_kind": "synthetic",
            "collection_method": "generated_fixture",
            "human_annotated": False,
            "labeler": "jobfindsme-synthetic-builder",
            "date_range": "2026-07-26 to 2026-07-30",
            "platforms": ALL_SOURCES,
            "plan": {
                "target_roles": ["AI应用工程师", "大模型算法工程师", "AI Agent开发"],
                "locations": ["上海", "北京", "深圳", "杭州", "广州"],
                "salary_min_k": 20,
                "experience_max_years": 5,
            },
            "annotation_guide_version": "v0.2",
            "notes": (
                "Fabricated regression fixture. Jobs, URLs, source outcomes, "
                "and labels were generated by code. Never use for M14 evidence "
                "or public recommendation-quality claims."
            ),
        },
        days=(day1, day2, day3, day4, day5),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a synthetic Chinese evaluation fixture"
    )
    parser.add_argument(
        "--output",
        default="data/eval/synthetic/chinese_seed_v1.0.json",
        help="Output path for the assembled LabeledDataset JSON",
    )
    args = parser.parse_args()

    dataset = build_seed_dataset()
    output_path = Path(args.output)
    write_labeled_dataset(output_path, dataset)

    annotated = sum(1 for lb in dataset.all_labels if lb.annotated)
    unannotated = len(dataset.all_labels) - annotated
    duplicates = sum(1 for lb in dataset.all_labels if lb.duplicate_of is not None)
    hard_filter_errors = sum(1 for lb in dataset.all_labels if lb.hard_filter_error)
    invalid_links = sum(1 for lb in dataset.all_labels if not lb.valid_link)
    stale_or_closed = sum(
        1 for lb in dataset.all_labels if lb.liveness in ("stale", "closed")
    )

    print(f"Synthetic fixture written: {output_path}")
    print(f"   Days:            {len(dataset.days)}")
    print(f"   Total labels:    {len(dataset.all_labels)}")
    print(f"   Annotated:       {annotated}")
    print(f"   Unannotated:     {unannotated}")
    print(f"   Duplicates:      {duplicates}")
    print(f"   Hard-filter err: {hard_filter_errors}")
    print(f"   Invalid links:   {invalid_links}")
    print(f"   Stale/closed:    {stale_or_closed}")


if __name__ == "__main__":
    main()
