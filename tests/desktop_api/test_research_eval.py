"""Fixed synthetic research contract set; run with pytest -s to see denominators."""

import io
import json
import urllib.error
from pathlib import Path
from types import SimpleNamespace

from pypdf import PdfWriter
from reportlab.pdfgen import canvas

from jobfindsme.research import agent_sources
from jobfindsme.research.agent_store import _claim_basis

CASES = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "research_eval_cases.json").read_text()
)


def _pdf(text=None):
    output = io.BytesIO()
    if text is None:
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=300)
        writer.write(output)
    else:
        pdf = canvas.Canvas(output)
        pdf.drawString(30, 700, text)
        pdf.save()
    return output.getvalue()


def test_fixed_synthetic_research_denominators(monkeypatch):
    monkeypatch.setattr(
        agent_sources, "validate_public_http_url", lambda *_args, **_kwargs: None
    )
    observed = {}
    for case in CASES["retrieval"]:
        kind = case["kind"]
        if kind == "http_429":
            opener = SimpleNamespace(
                open=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    urllib.error.HTTPError(
                        "https://example.org/page", 429, "limited", {}, None
                    )
                )
            )
            content_type, body = "text/html", b""
        else:
            if kind.startswith("html"):
                content_type = "text/html"
                company = "示例公司" if kind == "html_relevant" else "其他公司"
                body = (
                    f"<html><title>{company}公告</title><article>{company}"
                    "在上海设立研发团队，并介绍产品、服务、历史与未来规划。"
                    "该材料还描述了团队成员职责、研发流程、办公地点和业务合作方式。"
                    "</article></html>"
                ).encode()
            else:
                content_type = "application/pdf"
                body = (
                    _pdf(
                        "ExampleCorp research team and busin"
                        "ess planning were disclosed in this"
                        " document."
                    )
                    if kind == "pdf_text_relevant"
                    else _pdf()
                )

            class Response:
                headers = SimpleNamespace(
                    get_content_type=lambda value=content_type: value,
                    get_content_charset=lambda: "utf-8",
                )

                def geturl(self):
                    return "https://example.org/page"

                def read(self, size, content=body):
                    return content[:size]

                def __enter__(self):
                    return self

                def __exit__(self, *_args):
                    pass

            opener = SimpleNamespace(open=lambda *_args, **_kwargs: Response())
        company = "ExampleCorp" if kind == "pdf_text_relevant" else "示例公司"
        row = agent_sources.read_original_page(
            "https://example.org/page", company, "web", opener=opener
        )
        observed[case["id"]] = row["status"]
        assert row["status"] == case["expected_status"], case["id"]
    positives = [
        case for case in CASES["retrieval"] if case["relevant_original_expected"]
    ]
    assert (
        sum(observed[case["id"]] == "read_original" for case in positives)
        == len(positives)
        == 2
    )
    decidable = [case for case in CASES["retrieval"] if case["entity_decidable"]]
    assert (
        sum(observed[case["id"]] == case["expected_status"] for case in decidable)
        == len(decidable)
        == 3
    )

    evidence = {
        "excerpt": "示例公司在上海设立研发团队，并介绍产品、服务、历史与未来规划。",
        "context": {"source_type": "public_web"},
    }
    citation_correct = 0
    for case in CASES["citations"]:
        claim = {
            "statement": case["statement"],
            "quote": case["quote"],
            "scope": case["scope"],
            "category": "business",
            "evidence_ids": ["ev_fixed"],
        }
        try:
            _claim_basis(claim, evidence, "示例公司")
            supported = True
        except ValueError:
            supported = False
        citation_correct += supported == case["expected_supported"]
    assert citation_correct == len(CASES["citations"]) == 3
    print(
        f"fixed synthetic retrieval {len(positives)}/{len(positives)}; "
        f"entity classification {len(decidable)}/{len(decidable)}; "
        f"citation decisions {citation_correct}/{len(CASES['citations'])}; "
        f"current job validity 0/{len(CASES['jobs'])} "
        "verified (unknown, not a success); model cost N/A"
    )
