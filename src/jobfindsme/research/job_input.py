"""Explicit research input; never promotes pasted JD to verified source data."""

import re
from datetime import UTC, datetime
from hashlib import sha256
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from jobfindsme.connectors import RawJobRecord
from jobfindsme.contracts import SourceKind
from jobfindsme.importing.normalizer import normalize_job
from jobfindsme.importing.repository import JobRepository

ALLOWED_HOSTS = (
    "zhipin.com",
    "liepin.com",
    "zhaopin.com",
    "51job.com",
    "careers.tencent.com",
    "jobs.bytedance.com",
    "seed.bytedance.com",
    "talent.alibaba.com",
    "campus-talent.alibaba.com",
    "talent-holding.alibaba.com",
    "career.meituan.com",
    "talent.baidu.com",
    "zhaopin.jd.com",
    "hr.163.com",
    "campus.163.com",
    "campus.kuaishou.cn",
    "zhaopin.kuaishou.cn",
    "hr.xiaomi.com",
    "career.mi.com",
    "xiaomi.jobs.f.mioffice.cn",
    "talent.didiglobal.com",
    "careers.pddglobalhr.com",
    "talent.deepseek.com",
    "vrfi1sk8a0.jobs.feishu.cn",
    "www.zhipuai.cn",
    "careers.kimi.com",
    "careers.kimi.ai",
    "www.stepfun.com",
)


def validate_job_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or not (
            parsed.hostname == "tencent.wd1.myworkdayjobs.com"
            or (
                parsed.hostname == "app.mokahr.com"
                and any(
                    parsed.path == p or parsed.path.startswith(p + "/")
                    for p in (
                        "/social-recruitment/high-flyer/140576",
                        "/social-recruitment/zphz/148983",
                        "/campus-recruitment/zphz/148984",
                        "/apply/moonshot/148506",
                        "/social-recruitment/step/94904",
                        "/campus-recruitment/step/94905",
                    )
                )
            )
            or any(
                parsed.hostname == host or (parsed.hostname or "").endswith("." + host)
                for host in ALLOWED_HOSTS
            )
        )
    ):
        raise ValueError(
            "仅支持已接入招聘来源的 HTTPS 链接；不接受账号信息、内网或非标准端口。"
        )
    return value


def canonical_job_url(value: str) -> str:
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower()
    detail = re.search(r"/(job_detail|job|a|jobdetail)/", parsed.path, re.I)
    drop_all = detail and any(
        host.endswith(h) for h in ("zhipin.com", "liepin.com", "zhaopin.com")
    )
    query = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if not drop_all
        and not re.fullmatch(
            r"utm_.*|ka|lid|securityid|sessionid|pgref|ckid|from|"
            r"source|scene|timestamp|t|track_id",
            k,
            re.I,
        )
    ]
    netloc = host + (f":{parsed.port}" if parsed.port and parsed.port != 443 else "")
    return urlunsplit(
        (
            parsed.scheme.lower(),
            netloc,
            parsed.path or "/",
            urlencode(sorted(query)),
            parsed.fragment.split("?")[0]
            if host in {"app.mokahr.com", "campus.kuaishou.cn"}
            else "",
        )
    )


def prepare_job(
    repository: JobRepository,
    *,
    workspace_id: str,
    url: str,
    title: str,
    company: str,
    description: str,
) -> dict:
    validate_job_url(url)
    if not title.strip() or not company.strip() or len(description.strip()) < 30:
        raise ValueError("请确认岗位名称、公司，并提供至少 30 字的 JD 正文。")
    digest = sha256(canonical_job_url(url).encode()).hexdigest()
    job = normalize_job(
        RawJobRecord(
            source_kind=SourceKind.CAREER_SITE,
            source_name="用户确认 JD（未独立核验）",
            source_url=url,
            external_id="research-" + digest[:24],
            payload={
                "title": title.strip(),
                "company": company.strip(),
                "description": description.strip(),
                "apply_url": url,
            },
        ),
        fetched_at=datetime.now(UTC),
    )
    # Research drafts must not overwrite live jobs or their reports.
    job = job.model_copy(
        update={"job_id": "research_" + digest[:24], "fingerprint": digest}
    )
    repository.upsert(workspace_id, job)
    return job.model_dump(mode="json")


def enrich_boss_job(repository, *, workspace_id, job_id, **detail):
    old = repository.get(workspace_id=workspace_id, job_id=job_id)
    parsed = urlsplit(detail["url"])
    if (
        parsed.scheme != "https"
        or parsed.netloc != "www.zhipin.com"
        or not parsed.path.startswith("/job_detail/")
        or urlsplit(old.apply_url).path != parsed.path
        or urlsplit(old.apply_url).hostname != parsed.hostname
    ):
        raise ValueError("详情链接与当前岗位不一致。")
    job = normalize_job(
        RawJobRecord(
            source_kind=old.source.source_kind,
            source_name=old.source.source_name,
            source_url=detail["url"],
            external_id=old.external_id,
            payload={
                "title": detail["title"] or old.title,
                "company": detail["company"]
                or (old.company if old.company != "BOSS直聘" else ""),
                "location": detail.get("location") or list(old.locations),
                "salary": detail.get("salary") or "",
                **(
                    {"salary_min_k": old.salary_min_k, "salary_max_k": old.salary_max_k}
                    if not detail.get("salary")
                    else {}
                ),
                "description": detail["description"],
                "apply_url": old.apply_url,
                "detail_level": "detail_page",
                "description_is_plaintext": True,
                "description_source_url": detail["url"],
                "description_fetched_at": detail["fetched_at"],
            },
        ),
        fetched_at=datetime.now(UTC),
    )
    job = job.model_copy(update={"job_id": old.job_id, "fingerprint": old.fingerprint})
    repository.upsert(workspace_id, job)
    return repository.get(workspace_id=workspace_id, job_id=job_id).model_dump(
        mode="json"
    )


def enrich_source_job(repository, *, workspace_id, job_id, **detail):
    old = repository.get(workspace_id=workspace_id, job_id=job_id)
    validate_job_url(detail["url"])
    if canonical_job_url(detail["url"]) != canonical_job_url(old.apply_url):
        raise ValueError("详情链接与当前岗位不一致。")
    data = old.model_dump(mode="json")
    data.update(
        title=detail["title"] or old.title,
        company=detail["company"] or old.company,
        description=detail["description"],
    )
    data["source"].update(
        detail_level="detail_page",
        description_source_url=detail["url"],
        description_fetched_at=detail["fetched_at"],
    )
    data["source"]["fetched_at"] = datetime.now(UTC).isoformat()
    data["content_hash"] = sha256(
        (data["title"] + "\n" + data["company"] + "\n" + data["description"]).encode()
    ).hexdigest()
    job = type(old).model_validate(data)
    repository.upsert(workspace_id, job)
    return repository.get(workspace_id=workspace_id, job_id=job_id).model_dump(
        mode="json"
    )
