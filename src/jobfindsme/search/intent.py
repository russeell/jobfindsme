"""Deterministic search intent. Resume evidence is never a desired role."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from jobfindsme.search.jobs import DesktopJobFilters

# Bounded vocabulary: unknown conditions require review, not silent widening.
CITIES = (
    "北京",
    "上海",
    "广州",
    "深圳",
    "杭州",
    "成都",
    "武汉",
    "南京",
    "苏州",
    "西安",
    "天津",
    "重庆",
    "长沙",
    "郑州",
    "厦门",
    "合肥",
    "东莞",
    "佛山",
    "珠海",
)
ROLE_ALIASES = {
    "agent": ("agent", "智能体"),
    "ai应用": ("ai应用", "人工智能应用", "大模型应用", "llm应用", "agent", "智能体"),
    "大模型": ("大模型", "llm", "语言模型"),
    "前端": ("前端", "frontend", "front-end"),
    "后端": ("后端", "backend", "back-end"),
    "数据分析": ("数据分析", "data analyst"),
    "python": ("python",),
    "java": ("java",),
}


@dataclass(frozen=True)
class SearchIntent:
    query: str
    target_roles: tuple[str, ...]
    filters: DesktopJobFilters
    resume_version: str | None
    source_scope: tuple[str, ...]
    unrecognized: tuple[str, ...] = ()

    def payload(self):
        return {
            **asdict(self),
            "remote_conditions": {
                "query": self.query,
                "city": next(iter(self.filters.cities), ""),
            },
            "local_conditions": asdict(self.filters),
        }


def parse_intent(
    text: str,
    *,
    filters: DesktopJobFilters | None = None,
    preferences: dict | None = None,
    resume_version: str | None = None,
    source_scope=(),
) -> SearchIntent:
    values = asdict(filters or DesktopJobFilters())
    prefs = preferences or {}
    text = " ".join(text.split()).strip()
    if len(text) > 500:
        raise ValueError("搜索要求过长，请缩短到岗位方向及筛选条件")
    # Empty input explicitly requests the confirmed desired role; never a skill.
    query = text or str(prefs.get("target_role") or "").strip()
    if not query:
        raise ValueError("请先确认目标岗位方向；简历技能不能代替求职意向")
    city_unlimited = bool(re.search(r"城市不限|不限城市|全国", query))
    salary_unlimited = "薪资不限" in query
    remaining = re.sub(r"城市不限|不限城市|全国|薪资不限", " ", query)
    if city_unlimited:
        values["cities"] = ()
    if salary_unlimited:
        values["salary_min_k"] = values["salary_max_k"] = None
    cities = tuple(city for city in CITIES if city in remaining)
    if cities:
        values["cities"] = cities
        for city in cities:
            remaining = remaining.replace(city, " ")
    salary = re.search(r"(\d{1,3})\s*[kK千]\s*(?:以上|起|\+)", remaining)
    if salary:
        values["salary_min_k"] = int(salary.group(1))
        values["salary_max_k"] = None
        values["salary_mode"] = "contained"
        remaining = remaining.replace(salary.group(0), " ")
    experience = re.search(r"(\d{1,2})\s*年(?:以内|以下)", remaining)
    if experience:
        values["experience_max_years"] = int(experience.group(1))
        remaining = remaining.replace(experience.group(0), " ")
    exclusions = list(values.get("exclusions", ()))
    for match in list(
        re.finditer(r"(?:不要|排除|不接受)\s*(外包|派遣|实习)", remaining)
    ):
        exclusions.append(match.group(1))
        remaining = remaining.replace(match.group(0), " ")
    values["exclusions"] = tuple(dict.fromkeys(exclusions))
    remaining = re.sub(
        r"^(?:帮我|请|我想|想|找|搜索|寻找|求职)+", "", remaining.strip()
    )
    remaining = re.sub(r"(?:的)?(?:岗位|职位|工作|岗)$", "", remaining.strip())
    remaining = re.sub(r"[，,；;、/]+", " ", remaining).strip()
    remaining = re.sub(r"(?:的)?(?:岗位|职位|工作|岗)$", "", remaining).strip()
    unsupported = re.search(
        r"(?:不要|排除|不接受|远程|双休|学历|以上|以下|以内|至少|最多|\d+\s*[-~至]\s*\d+\s*[kK千])",
        remaining,
    )
    leftovers = tuple(
        part
        for part in re.split(r"[，,；;]", text)
        if re.search(r"不要|排除|远程|双休|学历|以上|以下|以内|至少|最多", part)
        and (part.strip() in remaining or re.search(r"远程|双休|学历|至少|最多", part))
    )
    if not cities and not city_unlimited and not values.get("cities"):
        values["cities"] = tuple(prefs.get("cities") or ())
    if not salary and not salary_unlimited:
        for key in ("salary_min_k", "salary_max_k"):
            if values.get(key) is None and prefs.get(key) is not None:
                values[key] = prefs[key]
    if unsupported:
        leftovers = tuple(dict.fromkeys((*leftovers, remaining)))
    if not remaining:
        raise ValueError("请补充岗位方向，不能只输入筛选条件")
    effective = DesktopJobFilters(**values)
    effective.validate()
    return SearchIntent(
        remaining,
        (remaining,),
        effective,
        resume_version,
        tuple(source_scope),
        leftovers,
    )


def suggested_roles(content: dict) -> tuple[str, ...]:
    from jobfindsme.taxonomy import extract_skills

    corpus = " ".join(
        str(v)
        for section in ("skills", "projects", "experience")
        for v in content.get(section, ())
    ).casefold()
    skills = extract_skills(corpus)
    if {"Agent", "RAG", "LangChain", "LangGraph", "MCP"}.intersection(skills) or any(
        term in corpus for term in ("llm", "大模型", "智能体")
    ):
        return ("Agent工程师", "AI应用工程师", "大模型应用工程师")
    roles = []
    for word, role in (
        ("前端", "前端工程师"),
        ("react", "前端工程师"),
        ("java", "Java开发工程师"),
        ("python", "Python开发工程师"),
        ("数据分析", "数据分析师"),
    ):
        if word in corpus and role not in roles:
            roles.append(role)
    return tuple(roles[:3])


def query_relevance(job, query: str) -> dict:
    query = query.casefold().replace(" ", "")
    title = job.title.casefold().replace(" ", "")
    body = job.description.casefold().replace(" ", "")
    families = [
        aliases
        for key, aliases in ROLE_ALIASES.items()
        if key in query or any(alias in query for alias in aliases)
    ]
    terms = set(re.findall(r"[a-z][a-z0-9+#.-]*|[\u3400-\u9fff]+", query))
    terms = {re.sub(r"工程师|开发|岗位|职位", "", term) or term for term in terms}

    def contains(text, term):
        if term.isascii():
            return bool(re.search(r"(?<![a-z])" + re.escape(term) + r"(?![a-z])", text))
        return term in text

    hits = [any(contains(title, alias) for alias in family) for family in families]
    title_match = (
        contains(title, query)
        or bool(hits)
        and all(hits)
        or bool(terms)
        and all(contains(title, term) for term in terms)
    )
    body_match = (
        bool(terms)
        and any(contains(body, term) for term in terms)
        or any(contains(body, alias) for family in families for alias in family)
    )
    return {
        "score": 100 if title_match else 45 if body_match else 0,
        "basis": "title_or_role_alias"
        if title_match
        else "description"
        if body_match
        else "not_observed",
    }


def information_coverage(job) -> dict:
    fields = {
        "jd": bool(job.description and len(job.description) >= 100),
        "salary": job.salary_min_k is not None,
        "experience": job.experience_min_years is not None,
        "education": bool(re.search(r"本科|硕士|博士|大专|学历不限", job.description)),
        "location": bool(job.locations),
    }
    return {
        "ratio": sum(fields.values()) / len(fields),
        "known": [k for k, v in fields.items() if v],
        "unknown": [k for k, v in fields.items() if not v],
    }
