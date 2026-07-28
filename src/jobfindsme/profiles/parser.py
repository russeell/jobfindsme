from __future__ import annotations

import re
from dataclasses import dataclass

from jobfindsme.profiles.models import FactType
from jobfindsme.taxonomy import SKILL_ALIASES

SKILLS = {
    alias.casefold(): canonical
    for canonical, aliases in SKILL_ALIASES.items()
    for alias in (canonical, *aliases)
}

SECTION_PATTERNS: tuple[tuple[re.Pattern[str], FactType | None], ...] = (
    (
        re.compile(
            r"^(?:项目经历|项目经验|个人项目|独立项目|项目实践|projects?)$",
            re.I,
        ),
        FactType.PROJECT,
    ),
    (
        re.compile(
            r"^(?:工作经历|工作经验|实习经历|职业经历|独立实践与工作经历|experience)$",
            re.I,
        ),
        FactType.EXPERIENCE,
    ),
    (
        re.compile(r"^(?:教育经历|教育背景|学历信息|education)$", re.I),
        FactType.EDUCATION,
    ),
    (
        re.compile(
            r"^(?:专业技能|技能清单|技术栈|个人信息|基本信息|求职意向|"
            r"个人优势|自我评价|证书|获奖经历|skills?)$",
            re.I,
        ),
        None,
    ),
)

DATE_RANGE = re.compile(
    r"(?:19|20)\d{2}[./年-]\d{1,2}?"
    r".{0,8}(?:(?:19|20)\d{2}[./年-]\d{1,2}?|至今|现在|present)",
    re.I,
)


@dataclass(frozen=True)
class ParsedFact:
    fact_type: FactType
    value: str
    evidence_snippet: str
    evidence_start: int
    evidence_end: int


@dataclass(frozen=True)
class _Line:
    text: str
    start: int
    end: int


class DeterministicResumeParser:
    """Extract reviewable facts without treating every PDF line as a project."""

    version = "deterministic-resume-v3"

    def __init__(self) -> None:
        aliases = sorted(SKILLS, key=len, reverse=True)
        self.skill_pattern = re.compile(
            r"(?<![\w-])(" + "|".join(re.escape(item) for item in aliases) + r")"
            r"(?![\w-])",
            flags=re.IGNORECASE,
        )

    def parse(self, text: str) -> list[ParsedFact]:
        facts = self._skills(text)
        facts.extend(self._section_blocks(text))
        return _deduplicate(facts)

    def _skills(self, text: str) -> list[ParsedFact]:
        return [
            ParsedFact(
                fact_type=FactType.SKILL,
                value=SKILLS[match.group(0).casefold()],
                evidence_snippet=match.group(0),
                evidence_start=match.start(),
                evidence_end=match.end(),
            )
            for match in self.skill_pattern.finditer(text)
        ]

    def _section_blocks(self, text: str) -> list[ParsedFact]:
        lines = _lines(text)
        facts: list[ParsedFact] = []
        current_type: FactType | None = None
        current: list[_Line] = []

        def flush() -> None:
            if current_type is None or not current:
                current.clear()
                return
            for block in _split_entries(current):
                value = _normalize_block(block)
                if len(value) < 8:
                    continue
                start, end = block[0].start, block[-1].end
                facts.append(
                    ParsedFact(
                        fact_type=current_type,
                        value=value,
                        evidence_snippet=text[start:end],
                        evidence_start=start,
                        evidence_end=end,
                    )
                )
            current.clear()

        for line in lines:
            heading = _section_heading(line.text)
            if heading is not _NOT_A_HEADING:
                flush()
                current_type = heading
                continue
            if current_type is not None and line.text.strip():
                current.append(line)
        flush()
        return facts


_NOT_A_HEADING = object()


def _section_heading(value: str) -> FactType | None | object:
    normalized = value.strip().lstrip("#").strip().rstrip(":：").strip()
    for pattern, fact_type in SECTION_PATTERNS:
        if pattern.fullmatch(normalized):
            return fact_type
    return _NOT_A_HEADING


def _lines(text: str) -> list[_Line]:
    result = []
    offset = 0
    for raw in text.splitlines(keepends=True):
        line = raw.rstrip("\r\n")
        stripped = line.strip()
        if stripped:
            left = len(line) - len(line.lstrip())
            result.append(_Line(stripped, offset + left, offset + len(line.rstrip())))
        offset += len(raw)
    return result


def _split_entries(lines: list[_Line]) -> list[list[_Line]]:
    """Split on date-bearing headers; keep wrapped responsibility lines together."""

    entries: list[list[_Line]] = []
    current: list[_Line] = []
    for line in lines:
        starts_entry = bool(DATE_RANGE.search(line.text))
        if starts_entry and current:
            entries.append(current)
            current = []
        current.append(line)
    if current:
        entries.append(current)
    return entries


def _normalize_block(lines: list[_Line]) -> str:
    parts = [
        re.sub(r"^(?:[-*•·+]|\d+[.)、])\s*", "", line.text).strip() for line in lines
    ]
    return " ".join(part for part in parts if part)


def _deduplicate(facts: list[ParsedFact]) -> list[ParsedFact]:
    seen = set()
    result = []
    for fact in facts:
        key = (fact.fact_type, fact.value.casefold())
        if key not in seen:
            seen.add(key)
            result.append(fact)
    return result
