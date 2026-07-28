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

SECTIONS = {
    "项目经历": FactType.PROJECT,
    "projects": FactType.PROJECT,
    "工作经历": FactType.EXPERIENCE,
    "工作经验": FactType.EXPERIENCE,
    "experience": FactType.EXPERIENCE,
    "教育经历": FactType.EDUCATION,
    "education": FactType.EDUCATION,
}


@dataclass(frozen=True)
class ParsedFact:
    fact_type: FactType
    value: str
    evidence_snippet: str
    evidence_start: int
    evidence_end: int


class DeterministicResumeParser:
    version = "deterministic-resume-v2"

    def __init__(self) -> None:
        aliases = sorted(SKILLS, key=len, reverse=True)
        self.skill_pattern = re.compile(
            r"(?<![\w-])(" + "|".join(re.escape(item) for item in aliases) + r")"
            r"(?![\w-])",
            flags=re.IGNORECASE,
        )

    def parse(self, text: str) -> list[ParsedFact]:
        facts = self._skills(text)
        facts.extend(self._sections(text))
        return _deduplicate(facts)

    def _skills(self, text: str) -> list[ParsedFact]:
        return [
            ParsedFact(
                fact_type=FactType.SKILL,
                value=SKILLS[match.group(0).lower()],
                evidence_snippet=match.group(0),
                evidence_start=match.start(),
                evidence_end=match.end(),
            )
            for match in self.skill_pattern.finditer(text)
        ]

    def _sections(self, text: str) -> list[ParsedFact]:
        facts = []
        current_type = None
        offset = 0
        for raw_line in text.splitlines(keepends=True):
            line = raw_line.rstrip("\r\n")
            stripped = line.strip()
            heading = stripped.lstrip("#").strip().rstrip(":：").strip()
            section_type = SECTIONS.get(heading.lower())
            if section_type is not None:
                current_type = section_type
                offset += len(raw_line)
                continue

            value = re.sub(r"^(?:[-*+]|\d+[.)])\s*", "", stripped).strip()
            if current_type is not None and value:
                start = offset + line.find(value)
                facts.append(
                    ParsedFact(
                        fact_type=current_type,
                        value=value,
                        evidence_snippet=text[start : start + len(value)],
                        evidence_start=start,
                        evidence_end=start + len(value),
                    )
                )
            offset += len(raw_line)
        return facts


def _deduplicate(facts: list[ParsedFact]) -> list[ParsedFact]:
    seen = set()
    result = []
    for fact in facts:
        key = (fact.fact_type, fact.value.casefold())
        if key not in seen:
            seen.add(key)
            result.append(fact)
    return result
