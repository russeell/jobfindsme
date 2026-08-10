from __future__ import annotations

import json
from pathlib import Path


def build_dataset() -> dict[str, object]:
    cases: list[dict[str, object]] = []
    for index in range(40):
        cases.append(
            {
                "case_id": f"match-{index:03}",
                "kind": "matching",
                "plan": {
                    "role": "AI应用工程师",
                    "location": "杭州",
                    "salary_min_k": 20,
                    "experience_max_years": 3,
                },
                "candidate": {
                    "title": ("AI应用工程师" if index % 2 == 0 else "大模型应用工程师"),
                    "location": "杭州" if index % 5 else "北京",
                    "description": (
                        "Python RAG Agent，1-3年，25-40K"
                        if index % 7
                        else "外包驻场，Python RAG，1-3年，25-40K"
                    ),
                },
                "expected_match": index % 5 != 0 and index % 7 != 0,
            }
        )
    for index in range(40):
        cases.append(
            {
                "case_id": f"fresh-{index:03}",
                "kind": "freshness",
                "age_days": index,
                "closed": index % 11 == 0,
                "expected": "closed" if index % 11 == 0 else "active",
            }
        )
    for index in range(40):
        cases.append(
            {
                "case_id": f"dedup-{index:03}",
                "kind": "deduplication",
                "same_company": index % 3 != 0,
                "same_title": index % 4 != 0,
                "same_url": index % 5 != 0,
                "expected_duplicate": (
                    index % 3 != 0 and index % 4 != 0 and index % 5 != 0
                ),
            }
        )
    return {
        "dataset_version": "0.1.0",
        "dataset_type": "synthetic_regression",
        "claims_policy": "Do not treat these scores as field performance.",
        "cases": cases,
    }


def write_dataset(path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(build_dataset(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    write_dataset("data/eval/v0.1.json")
