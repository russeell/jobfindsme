import json

from jobfindsme.connectors import ConnectorPolicy
from jobfindsme.connectors.company_careers import TencentCareersConnector
from jobfindsme.contracts import SourceKind


class Response:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, _limit):
        return self.payload


def test_tencent_public_careers_maps_structured_jd_and_pagination():
    calls = []

    def opener(request, **_kwargs):
        calls.append(request.full_url)
        return Response(
            {
                "Code": 200,
                "Data": {
                    "Count": 21,
                    "Posts": [
                        {
                            "PostId": "123",
                            "RecruitPostName": "AI 工程师",
                            "ComName": "腾讯云智研发子公司",
                            "LocationName": "上海",
                            "Responsibility": "负责 Python 平台开发",
                            "LastUpdateTime": "2026年09月17日",
                            "RequireWorkYearsName": "三年以上工作经验",
                        }
                    ],
                },
            }
        )

    connector = TencentCareersConnector(
        "Python",
        policy=ConnectorPolicy(public_access=True, robots_allowed=True),
        opener=opener,
        page_size=20,
    )
    records, next_page = connector.fetch_page(1)

    assert next_page == 2
    assert records[0].source_kind is SourceKind.ATS
    assert records[0].payload["description"] == "负责 Python 平台开发"
    assert records[0].payload["detail_level"] == "structured_source"
    assert (
        records[0]
        .payload["apply_url"]
        .startswith("https://careers.tencent.com/jobdesc.html")
    )
    assert "pageIndex=1" in calls[0]
