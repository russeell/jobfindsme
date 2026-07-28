from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[a-zA-Z0-9+#.]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> tuple[str, ...]:
    return tuple(token.casefold() for token in _TOKEN_RE.findall(text))
