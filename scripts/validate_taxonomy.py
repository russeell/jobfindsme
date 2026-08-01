from __future__ import annotations

from jobfindsme.taxonomy import SKILL_ALIASES, SKILL_TAXONOMY_VERSION


def main() -> None:
    alias_count = sum(len(aliases) for aliases in SKILL_ALIASES.values())
    print(
        f"taxonomy={SKILL_TAXONOMY_VERSION} "
        f"skills={len(SKILL_ALIASES)} aliases={alias_count}"
    )


if __name__ == "__main__":
    main()
