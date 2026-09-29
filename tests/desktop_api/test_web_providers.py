import json
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from jobfindsme.research import agent_sources, web_providers


class Response:
    def __init__(self, body, url="https://docs.example.org/api"):
        self.body = body.encode()
        self.url = url
        self.headers = SimpleNamespace(
            get_content_type=lambda: "text/html", get_content_charset=lambda: "utf-8"
        )

    def read(self, size):
        return self.body[:size]

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass


def test_unconfigured_adapters_do_not_make_requests(monkeypatch):
    monkeypatch.delenv("JOBFINDSME_EXA_API_KEY", raising=False)
    monkeypatch.delenv("JOBFINDSME_JINA_READER", raising=False)

    def unexpected(*args, **kwargs):
        raise AssertionError("unconfigured provider used")

    opener = SimpleNamespace(open=unexpected)
    assert web_providers.exa_search("API", opener=opener, timeout=1) is None
    assert (
        web_providers.jina_read("https://example.org/", opener=opener, timeout=1)
        is None
    )
    assert web_providers.provider_status()["exa"] == {
        "configured": False,
        "status": "not_probed",
    }


@pytest.mark.parametrize("query", ["比较检索与生成框架", "retrieval API comparison"])
def test_exa_candidates_are_not_evidence_and_keep_query(monkeypatch, query):
    monkeypatch.setenv("JOBFINDSME_EXA_API_KEY", "fixture-only-not-a-real-key")
    monkeypatch.setattr(
        web_providers, "validate_public_http_url", lambda *a, **kw: None
    )
    requests = []

    def open_request(request, **kwargs):
        requests.append(request)
        return Response(
            json.dumps(
                {
                    "results": [
                        {"title": "Docs", "url": "https://docs.example.org/api"},
                        None,
                    ]
                }
            )
        )

    rows = web_providers.exa_search(
        query, opener=SimpleNamespace(open=open_request), timeout=1
    )
    assert len(rows) == 1
    assert rows[0]["status"] == "search_hint_only"
    assert "excerpt" not in rows[0] and "evidence_id" not in rows[0]
    assert json.loads(requests[0].data)["query"] == query
    assert requests[0].full_url == "https://api.exa.ai/search"


@pytest.mark.parametrize(
    "code,status", [(429, "rate_limited"), (403, "restricted"), (503, "read_failed")]
)
def test_reader_distinguishes_failure_statuses_without_retry(monkeypatch, code, status):
    monkeypatch.setenv("JOBFINDSME_JINA_READER", "1")
    monkeypatch.setattr(
        web_providers, "validate_public_http_url", lambda *a, **kw: None
    )
    calls = []

    def fail(request, **kwargs):
        calls.append(request)
        raise HTTPError(request.full_url, code, "fixture", None, None)

    row = web_providers.jina_read(
        "https://docs.example.org/api", opener=SimpleNamespace(open=fail), timeout=1
    )
    assert row["status"] == status
    assert len(calls) == 1


def test_reader_requires_exact_origin_and_keeps_provenance(monkeypatch):
    monkeypatch.setenv("JOBFINDSME_JINA_READER", "1")
    monkeypatch.setattr(
        web_providers, "validate_public_http_url", lambda *a, **kw: None
    )
    url = "https://docs.example.org/api"
    text = (
        "The API separates retrieval from generation "
        "and describes the public interface."
    )

    def read(origin):
        return web_providers.jina_read(
            url,
            opener=SimpleNamespace(
                open=lambda *a, **kw: Response(
                    f"URL Source: {origin}\n\nMarkdown Content:\n{text}"
                )
            ),
            timeout=1,
        )

    row = read(url)
    assert row["status"] == "read_original"
    assert row["url"] == url and row["retrieved_at"]
    assert row["context"]["retrieval_method"] == "jina_reader"
    assert read(url + "-unrelated")["status"] == "read_failed"


def test_generic_english_document_does_not_require_chinese_subject(monkeypatch):
    monkeypatch.setattr(
        agent_sources, "validate_public_http_url", lambda *a, **kw: None
    )
    html = (
        "<html><title>Retrieval API</title><article>"
        + "The framework separates retrieval from generation. " * 12
        + "</article></html>"
    )
    row = agent_sources.read_original_page(
        "https://docs.example.org/api",
        "",
        "web",
        question="retrieval API",
        opener=SimpleNamespace(open=lambda *a, **kw: Response(html)),
    )
    assert row["status"] == "read_original"
    assert row["context"]["company_match"] == "not_requested"
    assert row["context"]["retrieval_method"] == "http"


def test_reader_rejects_private_url_before_request(monkeypatch):
    monkeypatch.setenv("JOBFINDSME_JINA_READER", "1")

    def unexpected(*args, **kwargs):
        raise AssertionError("unsafe URL requested")

    with pytest.raises(ValueError, match="private"):
        web_providers.jina_read(
            "https://127.0.0.1/", opener=SimpleNamespace(open=unexpected), timeout=1
        )
