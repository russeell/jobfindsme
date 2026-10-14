"""Small, validated document model. Plain facts remain the matching/AI contract.

No HTML, URLs, images or executable attributes are persisted or rendered.
Formatting belongs to immutable resume versions, never to imported source files.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from difflib import SequenceMatcher
from html import escape

SECTIONS = ("basic_information", "education", "experience", "projects", "skills")
MARKS = {"bold", "italic", "underline", "strike", "textStyle"}
TEMPLATES = {"classic", "professional", "campus", "compact"}


def document_template(document: dict | None) -> str | None:
    attrs = (document or {}).get("attrs") or {}
    value = attrs.get("template") if isinstance(attrs, dict) else None
    return value if isinstance(value, str) and value in TEMPLATES else None


def text_style(attrs: dict) -> dict:
    """Only portable typography, never arbitrary CSS or font/file references."""
    result = {}
    if attrs.get("color") is not None:
        color = attrs["color"]
        if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise ValueError("invalid resume text color")
        result["color"] = color.lower()
    if attrs.get("fontSize") is not None:
        size = attrs["fontSize"]
        if type(size) not in (int, float) or not 6 <= size <= 72:
            raise ValueError("invalid resume font size")
        result["fontSize"] = round(size, 2)
    return result


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
    """Keep unchanged blocks; revised paragraphs inherit their existing typography."""
    old = {
        s["attrs"]["section"]: s["content"] for s in (previous or {}).get("content", [])
    }
    sections = []
    for key in SECTIONS:
        candidates = list(old.get(key, []))
        blocks = []
        values = content.get(key, ())
        for index, value in enumerate(values):
            match = next(
                (i for i, b in enumerate(candidates) if block_text(b).strip() == value),
                None,
            )
            if match is not None:
                blocks.append(deepcopy(candidates.pop(match)))
            elif (
                len(values) == len(old.get(key, []))
                and old[key][index]["type"] == "paragraph"
            ):
                blocks.append(restyle_paragraph(value, old[key][index]))
            else:
                blocks.append(paragraph(value))
        sections.append(
            {
                "type": "resumeSection",
                "attrs": deepcopy(
                    next(
                        (
                            s["attrs"]
                            for s in (previous or {}).get("content", [])
                            if s["attrs"]["section"] == key
                        ),
                        {"section": key},
                    )
                ),
                "content": blocks or [paragraph("")],
            }
        )
    return {
        "type": "doc",
        **(
            {"attrs": {"template": template}}
            if (template := document_template(previous))
            else {}
        ),
        "content": sections,
    }


def restyle_paragraph(value: str, previous: dict) -> dict:
    old_text, formats = [], []
    for child in previous.get("content", []):
        text = "\n" if child["type"] == "hardBreak" else child["text"]
        old_text.extend(text)
        formats.extend([child.get("marks", [])] * len(text))
    applied = [[] for _ in value]
    for tag, a, b, c, d in SequenceMatcher(
        None, "".join(old_text), value, autojunk=False
    ).get_opcodes():
        if tag == "equal":
            applied[c:d] = formats[a:b]
        elif tag in {"replace", "insert"} and formats:
            applied[c:d] = [formats[min(a, len(formats) - 1)]] * (d - c)
    nodes = []
    for char, marks in zip(value, applied, strict=True):
        if char == "\n":
            nodes.append({"type": "hardBreak"})
        elif (
            nodes
            and nodes[-1]["type"] == "text"
            and nodes[-1].get("marks", []) == marks
        ):
            nodes[-1]["text"] += char
        else:
            nodes.append(
                {
                    "type": "text",
                    "text": char,
                    **({"marks": deepcopy(marks)} if marks else {}),
                }
            )
    return {
        "type": "paragraph",
        **({"attrs": deepcopy(previous["attrs"])} if previous.get("attrs") else {}),
        "content": nodes,
    }


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
        if kind == "doc":
            template = node.get("attrs", {}).get("template")
            if template is not None:
                if not isinstance(template, str) or template not in TEMPLATES:
                    raise ValueError("invalid resume template")
                result["attrs"] = {"template": template}
        elif kind == "text":
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
                cleaned = {}
                for mark in marks:
                    mark_kind = mark["type"]
                    clean = {"type": mark_kind}
                    if mark_kind == "textStyle":
                        attrs = text_style(mark.get("attrs") or {})
                        if not attrs:
                            continue
                        clean["attrs"] = attrs
                    cleaned[mark_kind] = clean
                result["marks"] = [cleaned[k] for k in sorted(cleaned)]
        elif kind == "resumeSection":
            section = node.get("attrs", {}).get("section")
            if section not in SECTIONS:
                raise ValueError("invalid resume section")
            result["attrs"] = {"section": section}
            attrs = node.get("attrs", {})
            style = text_style(
                {
                    "color": attrs.get("headingColor"),
                    "fontSize": attrs.get("headingSize"),
                }
            )
            if "color" in style:
                result["attrs"]["headingColor"] = style["color"]
            if "fontSize" in style:
                result["attrs"]["headingSize"] = style["fontSize"]
            if attrs.get("headingHidden") is True:
                result["attrs"]["headingHidden"] = True
        elif kind == "paragraph":
            align = node.get("attrs", {}).get("textAlign")
            if align is not None:
                if align not in {"left", "center", "right", "justify"}:
                    raise ValueError("invalid resume alignment")
                result["attrs"] = {"textAlign": align}
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
        if mark["type"] == "textStyle":
            attrs = text_style(mark.get("attrs") or {})
            attributes = " ".join(
                f'{key}="{attrs[field]}"'
                for field, key in (("color", "color"), ("fontSize", "size"))
                if field in attrs
            )
            text = f"<font {attributes}>{text}</font>"
            continue
        tag = tags[mark["type"]]
        text = f"<{tag}>{text}</{tag}>"
    return text
