"""Portable text for resume copies; source bytes and stored versions stay intact."""

import re
from copy import deepcopy


def normalize_resume_text(text: str) -> str:
    # WPS KingsoftSign / Symbol encodes its bullet as a private-use character.
    # Only repair a line-leading marker; other private glyphs and inline text
    # have no reliable font-independent meaning and must not be guessed away.
    return re.sub(r"(?m)^([ \t]*)\uf0b7", r"\1•", text)


def normalize_resume_document(document: dict | None) -> dict | None:
    if document is None:
        return None
    result = deepcopy(document)

    def visit(node):
        if node.get("type") == "paragraph":
            prefix = ""
            for child in node.get("content", []):
                if child.get("type") == "hardBreak":
                    prefix = ""
                elif child.get("type") == "text":
                    text = child["text"]
                    child["text"] = normalize_resume_text(prefix + text)[len(prefix) :]
                    prefix = (prefix + text).rsplit("\n", 1)[-1]
        else:
            for child in node.get("content", []):
                visit(child)

    visit(result)
    return result
