from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[a-zA-Z0-9+#.]+|[\u4e00-\u9fff]+")


def tokenize(text: str) -> tuple[str, ...]:
    tokens: list[str] = []
    for token in _TOKEN_RE.findall(text):
        normalized = token.casefold()
        tokens.append(normalized)
        if re.fullmatch(r"[\u4e00-\u9fff]+", normalized) and len(normalized) > 1:
            for size in (2, 3):
                tokens.extend(
                    normalized[index : index + size]
                    for index in range(len(normalized) - size + 1)
                )
    return tuple(tokens)
