from __future__ import annotations

import json
import re
from importlib.resources import files
from typing import Any


def validate_skill_taxonomy(payload: Any) -> dict[str, tuple[str, ...]]:
    """Validate a community-editable taxonomy before matching uses it."""
    if not isinstance(payload, dict) or not isinstance(payload.get("version"), str):
        raise ValueError("skill taxonomy requires a string version")
    skills = payload.get("skills")
    if not isinstance(skills, dict) or not skills:
        raise ValueError("skill taxonomy requires a non-empty skills mapping")
    normalized: dict[str, tuple[str, ...]] = {}
    seen_terms: dict[str, str] = {}
    for canonical, aliases in skills.items():
        if not isinstance(canonical, str) or not canonical.strip():
            raise ValueError("canonical skill names must be non-empty strings")
        if not isinstance(aliases, list) or not aliases:
            raise ValueError(f"{canonical} requires at least one alias")
        cleaned = tuple(
            dict.fromkeys(alias.strip() for alias in aliases if alias.strip())
        )
        if len(cleaned) != len(aliases):
            raise ValueError(f"{canonical} aliases must be unique non-empty strings")
        for term in (canonical, *cleaned):
            key = term.casefold()
            owner = seen_terms.get(key)
            if owner and owner != canonical:
                raise ValueError(
                    f"taxonomy term {term!r} belongs to both {owner} and {canonical}"
                )
            seen_terms[key] = canonical
        normalized[canonical] = cleaned
    return normalized


def load_skill_taxonomy() -> tuple[str, dict[str, tuple[str, ...]]]:
    resource = files("jobfindsme.resources.taxonomy").joinpath("skills.json")
    payload = json.loads(resource.read_text(encoding="utf-8"))
    return payload["version"], validate_skill_taxonomy(payload)


SKILL_TAXONOMY_VERSION, SKILL_ALIASES = load_skill_taxonomy()

ROLE_ALIASES: dict[str, tuple[str, ...]] = {
    "AI应用工程师": (
        "ai应用工程师",
        "大模型应用工程师",
        "llm应用工程师",
        "生成式ai工程师",
        "agent工程师",
        "rag工程师",
        "智能体工程师",
        "ai engineer",
        "llm engineer",
        "generative ai engineer",
    ),
    "算法工程师": ("算法工程师", "机器学习工程师", "深度学习工程师"),
    "后端工程师": ("后端工程师", "服务端工程师", "backend engineer"),
}

TECHNICAL_ROLE_MARKERS = (
    "工程师",
    "开发",
    "研发",
    "架构师",
    "算法",
    "技术专家",
    "engineer",
    "developer",
    "architect",
    "scientist",
)

AI_ROLE_SIGNALS = (
    "ai",
    "人工智能",
    "大模型",
    "llm",
    "rag",
    "agent",
    "智能体",
    "生成式",
    "aigc",
    "机器学习",
    "深度学习",
    "nlp",
)

NON_ENGINEERING_ROLE_MARKERS = (
    "产品经理",
    "产品运营",
    "product manager",
    "product owner",
)

LOCATION_ALIASES: dict[str, tuple[str, ...]] = {
    "中国": ("china", "cn -"),
    "北京": ("beijing", "北京市"),
    "上海": ("shanghai", "上海市"),
    "深圳": ("shenzhen", "深圳市"),
    "杭州": ("hangzhou", "杭州市"),
    "广州": ("guangzhou", "广州市"),
    "成都": ("chengdu", "成都市"),
    "重庆": ("chongqing", "重庆市"),
    "武汉": ("wuhan", "武汉市"),
    "西安": ("xi'an", "xian", "西安市"),
    "南京": ("nanjing", "南京市"),
    "苏州": ("suzhou", "苏州市"),
}


def extract_skills(text: str) -> dict[str, str]:
    """Return canonical skill -> exact evidence snippet."""
    normalized = text.casefold()
    found: dict[str, str] = {}
    for canonical, aliases in SKILL_ALIASES.items():
        candidates = (canonical, *aliases)
        for alias in sorted(candidates, key=len, reverse=True):
            match = re.search(
                rf"(?<![a-z0-9+#]){re.escape(alias.casefold())}(?![a-z0-9+#])",
                normalized,
            )
            if match:
                found[canonical] = text[match.start() : match.end()]
                break
    return found


def extract_required_skills(text: str) -> dict[str, str]:
    markers = ("任职要求", "职位要求", "必备条件", "必须", "requirements")
    normalized = text.casefold()
    offsets = [normalized.find(marker.casefold()) for marker in markers]
    offsets = [offset for offset in offsets if offset >= 0]
    required_text = text[min(offsets) :] if offsets else ""
    return extract_skills(required_text)


def expand_role_terms(roles: tuple[str, ...]) -> tuple[str, ...]:
    expanded: list[str] = []
    for role in roles:
        normalized = role.casefold()
        expanded.append(role)
        for canonical, aliases in ROLE_ALIASES.items():
            family = (canonical, *aliases)
            if any(
                item.casefold() in normalized or normalized in item.casefold()
                for item in family
            ):
                expanded.extend(family)
    return tuple(dict.fromkeys(expanded))


def expand_location_terms(locations: tuple[str, ...]) -> tuple[str, ...]:
    expanded: list[str] = []
    for location in locations:
        normalized = location.casefold()
        expanded.append(location)
        for canonical, aliases in LOCATION_ALIASES.items():
            family = (canonical, *aliases)
            if any(
                item.casefold() in normalized or normalized in item.casefold()
                for item in family
            ):
                expanded.extend(family)
    return tuple(dict.fromkeys(expanded))


def is_target_role_candidate(
    title: str,
    description: str,
    roles: tuple[str, ...],
) -> bool:
    """Reject location-only matches before ranking.

    A candidate either names the requested role family in its title, or has a
    technical title plus an explicit AI marker in the title ("AI全栈工程师",
    "AI应用研发工程师"), or has a technical title plus multiple AI signals
    across its title and description.
    """

    normalized_title = title.casefold()
    normalized_roles = tuple(role.casefold() for role in roles)
    non_engineering_markers = tuple(
        marker for marker in NON_ENGINEERING_ROLE_MARKERS if marker in normalized_title
    )
    if non_engineering_markers:
        return any(
            marker in role
            for marker in non_engineering_markers
            for role in normalized_roles
        )
    role_terms = expand_role_terms(roles)
    if any(term.casefold() in normalized_title for term in role_terms):
        return True
    if not any(marker in normalized_title for marker in TECHNICAL_ROLE_MARKERS):
        return False
    if "ai" in normalized_title or "人工智能" in normalized_title:
        return True
    searchable = f"{title} {description}".casefold()
    signals = {signal for signal in AI_ROLE_SIGNALS if signal in searchable}
    return len(signals) >= 2
