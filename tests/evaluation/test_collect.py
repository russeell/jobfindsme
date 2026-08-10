import json

import pytest

from evaluation.datasets.collect import read_search_results


def test_read_full_job_match_output(tmp_path) -> None:
    path = tmp_path / "jobs.json"
    path.write_text(
        json.dumps(
            [
                {
                    "job": {
                        "job_id": "job-1",
                        "title": "AI应用工程师",
                        "company": "示例公司",
                        "locations": ["上海", "深圳"],
                        "apply_url": "https://example.com/jobs/1",
                        "source": {"source_name": "example-careers"},
                    },
                    "score": 0.9,
                }
            ],
            ensure_ascii=False,
        )
    )

    jobs = read_search_results(path)

    assert jobs == [
        {
            "job_id": "job-1",
            "source_name": "example-careers",
            "apply_url": "https://example.com/jobs/1",
            "title": "AI应用工程师",
            "company": "示例公司",
            "location": "上海 / 深圳",
        }
    ]


def test_read_compact_results_envelope(tmp_path) -> None:
    path = tmp_path / "jobs.json"
    path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "job": {
                            "job_id": "job-2",
                            "title": "Agent工程师",
                            "company": "示例公司",
                            "locations": ["杭州"],
                            "apply_url": "https://example.com/jobs/2",
                            "source_name": "example-careers",
                        }
                    }
                ]
            },
            ensure_ascii=False,
        )
    )

    assert read_search_results(path)[0]["source_name"] == "example-careers"


def test_read_search_results_rejects_unknown_shape(tmp_path) -> None:
    path = tmp_path / "jobs.json"
    path.write_text('{"message": "not results"}')

    with pytest.raises(ValueError, match="jobs/results"):
        read_search_results(path)
