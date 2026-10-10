"""Small, validated document model. Plain facts remain the matching/AI contract.

No HTML, URLs, images or executable attributes are persisted or rendered.
Formatting belongs to immutable resume versions, never to imported source files.
"""

from __future__ import annotations

import json
from copy import deepcopy
from html import escape

SECTIONS = ("basic_information", "education", "experience", "projects", "skills")
MARKS = {"bold", "italic", "underline", "strike"}


def paragraph(text: str) -> dict:
    nodes = []
    for index, line in enumerate(text.split("\n")):
        if index:
            nodes.append({"type": "hardBreak"})
        if line:
            nodes.append({"type": "text", "text": line})
    return {"type": "paragraph", "content": nodes}


def block_text(node: dict) -> str:
    kind = node["type"]
    if kind == "text":
        return node["text"]
    if kind == "hardBreak":
        return "\n"
    children = node.get("content", [])
    if kind in {"bulletList", "orderedList"}:
        return "\n".join(
            (
                "• "
                if kind == "bulletList"
                else f"{node.get('attrs', {}).get('start', 1) + i}. "
            )
            + block_text(child)
            for i, child in enumerate(children)
        )
    return ("\n" if kind == "listItem" else "").join(block_text(c) for c in children)


def document_content(document: dict) -> dict[str, tuple[str, ...]]:
    return {
        section["attrs"]["section"]: tuple(
            text for block in section["content"] if (text := block_text(block).strip())
        )
        for section in document["content"]
    }


def reconcile_document(content: dict, previous: dict | None = None) -> dict:
    """Keep formatting on unchanged entries; changed AI facts become plain text."""
    old = {
        s["attrs"]["section"]: s["content"] for s in (previous or {}).get("content", [])
    }
    sections = []
    for key in SECTIONS:
        candidates = list(old.get(key, []))
        blocks = []
        for value in content.get(key, ()):
            match = next(
                (i for i, b in enumerate(candidates) if block_text(b).strip() == value),
                None,
            )
            blocks.append(
                deepcopy(candidates.pop(match))
                if match is not None
                else paragraph(value)
            )
        sections.append(
            {
                "type": "resumeSection",
                "attrs": {"section": key},
                "content": blocks or [paragraph("")],
            }
        )
    return {"type": "doc", "content": sections}


def validate_document(value: dict) -> dict:
    if (
        not isinstance(value, dict)
        or len(json.dumps(value, ensure_ascii=False)) > 500_000
    ):
        raise ValueError("invalid resume document size")
    count = 0

    def visit(node, parent, depth=0):
        nonlocal count
        count += 1
        if count > 12000 or depth > 8 or not isinstance(node, dict):
            raise ValueError("invalid resume document structure")
        kind = node.get("type")
        allowed = {
            None: {"doc"},
            "doc": {"resumeSection"},
            "resumeSection": {"paragraph", "bulletList", "orderedList"},
            "paragraph": {"text", "hardBreak"},
            "bulletList": {"listItem"},
            "orderedList": {"listItem"},
            "listItem": {"paragraph", "bulletList", "orderedList"},
        }
        if kind not in allowed.get(parent, set()):
            raise ValueError("unsupported resume document node")
        result = {"type": kind}
        if kind == "text":
            text = node.get("text")
            if not isinstance(text, str) or not text or len(text) > 100_000:
                raise ValueError("invalid resume text")
            result["text"] = text
            marks = node.get("marks", [])
            if not isinstance(marks, list) or any(
                not isinstance(m, dict) or m.get("type") not in MARKS for m in marks
            ):
                raise ValueError("unsupported resume text format")
            if marks:
                result["marks"] = [
                    {"type": m} for m in sorted({m["type"] for m in marks})
                ]
        elif kind == "resumeSection":
            section = node.get("attrs", {}).get("section")
            if section not in SECTIONS:
                raise ValueError("invalid resume section")
            result["attrs"] = {"section": section}
        elif kind == "orderedList":
            start = node.get("attrs", {}).get("start", 1)
            if type(start) is not int or not 1 <= start <= 999:
                raise ValueError("invalid resume list start")
            result["attrs"] = {"start": start}
        if kind not in {"text", "hardBreak"}:
            children = node.get("content", [])
            if not isinstance(children, list) or (not children and kind != "paragraph"):
                raise ValueError("invalid resume document children")
            result["content"] = [visit(c, kind, depth + 1) for c in children]
        return result

    result = visit(value, None)
    keys = [s["attrs"]["section"] for s in result["content"]]
    if len(keys) != len(SECTIONS) or set(keys) != set(SECTIONS):
        raise ValueError("resume document must retain all sections")
    return result


def paragraphs(block: dict):
    """Flatten list paragraphs for both Word and PDF, preserving inline marks."""
    if block["type"] == "paragraph":
        yield "", block
    else:
        for i, item in enumerate(block["content"]):
            prefix = (
                "• "
                if block["type"] == "bulletList"
                else f"{block.get('attrs', {}).get('start', 1) + i}. "
            )
            for j, p in enumerate(item["content"]):
                if p["type"] == "paragraph":
                    yield prefix if j == 0 else "  ", p
                else:
                    for nested_prefix, nested in paragraphs(p):
                        yield "  " + nested_prefix, nested


def pdf_markup(node: dict) -> str:
    if node["type"] == "hardBreak":
        return "<br/>"
    text = escape(node.get("text", ""))
    tags = {"bold": "b", "italic": "i", "underline": "u", "strike": "strike"}
    for mark in node.get("marks", []):
        tag = tags[mark["type"]]
        text = f"<{tag}>{text}</{tag}>"
    return text
