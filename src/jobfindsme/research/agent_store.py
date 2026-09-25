"""Workspace-scoped conversation and execution state for the existing research service."""

from __future__ import annotations

import json
import hashlib
import re
from urllib.parse import urlsplit
from uuid import uuid4
from datetime import UTC, datetime, timedelta

from jobfindsme.storage import Database
from .agent_sources import SITES
from .service import _host_matches


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _fresh(item: dict, *, at: datetime) -> bool:
    context = item.get("context") or {}
    source_type = context.get("source_type")
    topic = context.get("research_topic")
    days = 1 if topic == "job" else 365 if source_type == "official_disclosure" else 180
    try:
        retrieved = datetime.fromisoformat(item["retrieved_at"].replace("Z", "+00:00"))
        return at - retrieved <= timedelta(days=days)
    except (KeyError, TypeError, ValueError):
        return False


_CATEGORIES = {"business", "listing", "positive", "negative", "workload", "benefits", "role", "development"}
_REGIONS = ("上海", "北京", "深圳", "广州", "杭州", "成都", "全国", "全球", "海外", "中国", "美国", "欧洲", "华东", "华南", "华北")


def _normalized(value: str) -> str:
    return "".join(char for char in value.casefold() if char.isalnum())


def _negative(value: str) -> bool:
    return bool(re.search(r"尚未|未曾|未|没有|无|不|否认", value))


def _listing_status(value: str) -> str:
    if re.search(r"(?:已|完成|成功)上市", value):
        return "listed"
    if re.search(r"(?:拟|计划|筹备|申请)上市", value):
        return "planned"
    if re.search(r"(?:未|尚未)上市", value):
        return "not_listed"
    return ""


def _claim_basis(claim: dict, evidence: dict, company: str) -> dict:
    quote = str(claim.get("quote") or "").strip()
    statement = str(claim.get("statement") or quote).strip()
    body = str(evidence.get("excerpt") or "")
    if not (8 <= len(quote) <= 360 and 8 <= len(statement) <= 180):
        raise ValueError("invalid claim length")
    if quote not in body or company not in quote or company not in statement:
        raise ValueError("claim entity or quote is unsupported")
    if claim.get("category") not in _CATEGORIES:
        raise ValueError("invalid claim category")
    if _negative(statement) != _negative(quote) or re.search(r"目前|现在|当前|至今|如今|仍然|仍在|现已", statement):
        raise ValueError("claim polarity or current-time scope is unsupported")
    if _listing_status(statement) and _listing_status(statement) != _listing_status(quote):
        raise ValueError("claim listing status is unsupported")
    numbers = re.findall(r"\d+(?:\.\d+)?%?|[一二三四五六七八九十百千万]+(?:年|月|日|人|倍|%)", statement)
    if any(number not in quote for number in numbers) or any(region in statement and region not in quote for region in _REGIONS):
        raise ValueError("claim number or region is unsupported")
    direct = _normalized(statement) in _normalized(quote)
    if not direct:
        a, b = _normalized(statement), _normalized(quote)
        grams = {a[i:i + 2] for i in range(len(a) - 1)}
        if not grams or sum(part in b for part in grams) / len(grams) < 0.85:
            raise ValueError("claim wording is insufficiently supported")
    scope = str(claim.get("scope") or "团队、地区或法律主体未核实")
    if scope != "团队、地区或法律主体未核实" and scope not in quote:
        raise ValueError("claim scope is not present in cited original")
    source_type = (evidence.get("context") or {}).get("source_type")
    return {"statement": statement, "quote": quote, "evidence_ids": claim["evidence_ids"],
            "category": claim["category"], "scope": scope,
            "source_type": "official_disclosure" if source_type == "official_disclosure" else "personal_account",
            "support_level": "direct" if direct else "qualified"}


class ResearchAgentStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    def _workspace(self, connection, workspace_id: str) -> None:
        if not connection.execute(
            "SELECT 1 FROM workspaces WHERE workspace_id=?", (workspace_id,)
        ).fetchone():
            raise LookupError("workspace not found")

    def save_conversation(self, workspace_id: str, item: dict) -> dict:
        conversation_id = str(item["id"])
        turns = item.get("turns") or []
        if not conversation_id or len(conversation_id) > 100 or len(turns) > 40:
            raise ValueError("invalid conversation")
        if any(
            not isinstance(turn, dict)
            or turn.get("role") not in {"user", "assistant"}
            or not isinstance(turn.get("text"), str)
            or len(turn["text"]) > 8000
            for turn in turns
        ):
            raise ValueError("invalid conversation turn")
        context = {
            "company": str(item.get("subject_company") or "")[:300],
            "title": str(item.get("subject_title") or "")[:300],
            "failure": str(item.get("failure") or "")[:500],
        }
        reports = [str(value) for value in (item.get("report_ids") or [])[:30]]
        now = _now()
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._workspace(connection, workspace_id)
            existing = connection.execute(
                "SELECT workspace_id FROM research_conversations WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()
            if existing and existing["workspace_id"] != workspace_id:
                raise PermissionError("conversation belongs to another workspace")
            connection.execute(
                """INSERT INTO research_conversations
                   (conversation_id,workspace_id,subject_key,context_json,turns_json,
                    report_ids_json,draft,pending_json,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(conversation_id) DO UPDATE SET
                    subject_key=excluded.subject_key, context_json=excluded.context_json,
                    turns_json=excluded.turns_json, report_ids_json=excluded.report_ids_json,
                    draft=excluded.draft,pending_json=excluded.pending_json,
                    updated_at=excluded.updated_at""",
                (
                    conversation_id,
                    workspace_id,
                    str(item.get("subject_key") or "")[:300],
                    json.dumps(context, ensure_ascii=False),
                    json.dumps(turns, ensure_ascii=False),
                    json.dumps(reports),
                    str(item["draft"])[:700] if item.get("draft") else None,
                    json.dumps(item["pending"], ensure_ascii=False)
                    if item.get("pending")
                    else None,
                    now,
                ),
            )
        return {**item, "updated_at": now}

    def list_conversations(self, workspace_id: str) -> list[dict]:
        with self.database.connect() as connection:
            self._workspace(connection, workspace_id)
            rows = connection.execute(
                """SELECT * FROM research_conversations WHERE workspace_id=?
                   AND hidden_at IS NULL ORDER BY updated_at DESC LIMIT 50""",
                (workspace_id,),
            ).fetchall()
        return [
            {
                "id": row["conversation_id"],
                "subject_key": row["subject_key"],
                "subject_company": json.loads(row["context_json"]).get("company"),
                "subject_title": json.loads(row["context_json"]).get("title"),
                "failure": json.loads(row["context_json"]).get("failure"),
                "turns": json.loads(row["turns_json"]),
                "report_ids": json.loads(row["report_ids_json"]),
                "draft": row["draft"],
                "pending": json.loads(row["pending_json"])
                if row["pending_json"]
                else None,
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def save_execution(self, workspace_id: str, item: dict) -> dict:
        execution_id = str(item["id"])
        status = item.get("status")
        if not execution_id or len(execution_id) > 100 or status not in {
            "running", "complete", "failed", "cancelled"
        }:
            raise ValueError("invalid research execution")
        actions = item.get("actions") or []
        evidence = item.get("evidence") or []
        failures = item.get("failures") or []
        if len(actions) > 60 or len(evidence) > 24 or len(failures) > 30:
            raise ValueError("research execution exceeds storage bounds")
        now = _now()
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._workspace(connection, workspace_id)
            existing = connection.execute(
                "SELECT workspace_id,started_at FROM research_executions WHERE execution_id=?",
                (execution_id,),
            ).fetchone()
            if existing and existing["workspace_id"] != workspace_id:
                raise PermissionError("execution belongs to another workspace")
            report_id = item.get("report_id")
            if report_id and not connection.execute(
                "SELECT 1 FROM research_reports WHERE report_id=? AND workspace_id=?",
                (report_id, workspace_id),
            ).fetchone():
                raise ValueError("report belongs to another workspace")
            connection.execute(
                """INSERT INTO research_executions
                   (execution_id,workspace_id,conversation_id,subject_key,status,
                    budgets_json,actions_json,evidence_json,failures_json,report_id,
                    started_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(execution_id) DO UPDATE SET
                    status=excluded.status,budgets_json=excluded.budgets_json,
                    actions_json=excluded.actions_json,evidence_json=excluded.evidence_json,
                    failures_json=excluded.failures_json,report_id=excluded.report_id,
                    updated_at=excluded.updated_at""",
                (
                    execution_id,
                    workspace_id,
                    item.get("conversation_id"),
                    str(item.get("subject_key") or "")[:300],
                    status,
                    json.dumps(item.get("budgets") or {}),
                    json.dumps(actions, ensure_ascii=False),
                    json.dumps(evidence, ensure_ascii=False),
                    json.dumps(failures, ensure_ascii=False),
                    report_id,
                    existing["started_at"] if existing else now,
                    now,
                ),
            )
        return {**item, "updated_at": now}

    def find_evidence(self, workspace_id: str, company: str, *, limit: int = 12) -> list[dict]:
        key = "".join(company.casefold().split())
        if not key:
            return []
        with self.database.connect() as connection:
            self._workspace(connection, workspace_id)
            reports = connection.execute(
                """SELECT report_id,job_context_json FROM research_reports
                   WHERE workspace_id=? ORDER BY created_at DESC LIMIT 40""",
                (workspace_id,),
            ).fetchall()
            executions = connection.execute(
                """SELECT evidence_json,subject_key FROM research_executions
                   WHERE workspace_id=? ORDER BY updated_at DESC LIMIT 20""",
                (workspace_id,),
            ).fetchall()
            evidence: list[dict] = []
            for report in reports:
                context = json.loads(report["job_context_json"])
                if "".join(str(context.get("company") or "").casefold().split()) != key:
                    continue
                rows = connection.execute(
                    "SELECT * FROM research_evidence WHERE report_id=?",
                    (report["report_id"],),
                ).fetchall()
                evidence.extend(
                    {**dict(row), "context": json.loads(row["context_json"]), "report_id": report["report_id"]}
                    for row in rows
                )
        for execution in executions:
            if execution["subject_key"].split("|")[0] != key:
                continue
            evidence.extend(json.loads(execution["evidence_json"]))
        now = datetime.now(UTC)
        seen: set[str] = set()
        result = []
        for item in evidence:
            if item.get("verification_status") != "independently_retrieved" or not _fresh(item, at=now):
                continue
            dedupe = f"{item.get('url','').split('#')[0]}|{str(item.get('excerpt') or '')[:100]}"
            if dedupe in seen:
                continue
            seen.add(dedupe)
            result.append(item)
            if len(result) >= limit:
                break
        return result

    def save_report(self, workspace_id: str, item: dict) -> str | None:
        """Commit a checked Agent result only when it adds original evidence."""
        company = str(item.get("company") or "").strip()
        evidence = item.get("evidence") or []
        claims = item.get("claims") or []
        if not company or len(company) > 100 or not isinstance(evidence, list) or len(evidence) > 24:
            raise ValueError("invalid Agent report")
        if not isinstance(claims, list) or len(claims) > 30:
            raise ValueError("invalid claims")
        verified = [row for row in evidence if isinstance(row, dict)
                    and row.get("verification_status") == "independently_retrieved"
                    and row.get("status") in (None, "read_original")
                    and row.get("url", "").startswith("https://")]
        if not verified:
            return None
        for row in verified:
            parsed = urlsplit(row["url"])
            if not any(_host_matches(parsed.hostname, domain) for domain, _, _ in SITES.values()):
                raise ValueError("evidence URL is outside permitted research sources")
        ids = {str(row.get("evidence_id")) for row in verified}
        if len(ids) != len(verified):
            raise ValueError("duplicate evidence ids")
        by_id = {row["evidence_id"]: row for row in verified}
        checked_claims = []
        for claim in claims:
            if not isinstance(claim, dict) or len(claim.get("evidence_ids") or []) != 1 or not set(claim.get("evidence_ids") or []).issubset(ids):
                raise ValueError("claim references unknown evidence")
            checked_claims.append(_claim_basis(claim, by_id[claim["evidence_ids"][0]], company))
        if not checked_claims:
            return None
        evidence_fingerprint = hashlib.sha256(json.dumps(sorted(
            (row["url"], row.get("excerpt", "")) for row in verified
        ), ensure_ascii=False).encode()).hexdigest()
        claim_fingerprint = hashlib.sha256(json.dumps(sorted(
            (_normalized(claim["statement"]), claim["category"], by_id[claim["evidence_ids"][0]]["url"])
            for claim in checked_claims
        ), ensure_ascii=False).encode()).hexdigest()
        now = _now()
        report_id = f"research_{uuid4().hex}"
        job_id = item.get("job_id")
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._workspace(connection, workspace_id)
            job_row = connection.execute(
                "SELECT payload_json FROM jobs WHERE workspace_id=? AND job_id=?", (workspace_id, job_id)
            ).fetchone() if job_id else None
            if job_id and not job_row:
                raise ValueError("job belongs to another workspace")
            job_snapshot = json.loads(job_row["payload_json"]) if job_row else None
            previous = connection.execute(
                "SELECT job_id,job_context_json FROM research_reports WHERE workspace_id=? ORDER BY created_at DESC LIMIT 50",
                (workspace_id,),
            ).fetchall()
            same = [json.loads(row["job_context_json"]) for row in previous
                    if row["job_id"] == job_id and json.loads(row["job_context_json"]).get("company", "").casefold() == company.casefold()]
            existing_material = set()
            for row in connection.execute(
                "SELECT e.url,e.excerpt FROM research_evidence e JOIN research_reports r ON e.report_id=r.report_id WHERE r.workspace_id=? AND json_extract(r.job_context_json,'$.company')=?",
                (workspace_id, company),
            ):
                existing_material.add((row["url"], row["excerpt"]))
            has_new_evidence = any((row["url"], row.get("excerpt", "")) not in existing_material for row in verified)
            if not has_new_evidence and same and same[0].get("agent_claim_fingerprint") == claim_fingerprint:
                return None
            context = {"scope": "job" if job_id else "company", "company": company,
                       "title": str(item.get("title") or (job_snapshot or {}).get("title") or "")[:300],
                       "description": (job_snapshot or {}).get("description") or "",
                       "url": (job_snapshot or {}).get("apply_url") or "",
                       "job_snapshot": job_snapshot,
                       "interest_question": str(item.get("question") or "")[:700],
                       "agent_summary": str(item.get("summary") or "")[:2000],
                       "agent_claims": [{**claim, "evidence_ids": [f"{report_id}_{value}" for value in claim["evidence_ids"]]} for claim in checked_claims],
                       "agent_fingerprint": evidence_fingerprint,
                       "agent_claim_fingerprint": claim_fingerprint,
                       "version_number": len(same) + 1,
                       "outcome": "partial"}
            limitations = item.get("limitations") or []
            if not isinstance(limitations, list):
                raise ValueError("invalid limitations")
            connection.execute(
                """INSERT INTO research_reports
                   (report_id,workspace_id,job_id,resume_version_id,status,jd_facts_json,
                    resume_observations_json,project_rewrites_json,interview_topics_json,
                    model_connection_id,model_status,limitations_json,created_at,directions_json,job_context_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (report_id, workspace_id, job_id, None, "limited", "[]", "[]", "[]", "[]",
                 None, "complete", json.dumps([str(x)[:500] for x in limitations[:20]], ensure_ascii=False),
                 now, "[]", json.dumps(context, ensure_ascii=False)),
            )
            for row in verified:
                connection.execute(
                    """INSERT INTO research_evidence
                       (evidence_id,report_id,url,platform,published_at,retrieved_at,company,team,
                        excerpt,evidence_kind,verification_status,relevance,limitations,context_json)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (f"{report_id}_{row['evidence_id']}", report_id, row["url"], row.get("platform") or "公开网页",
                     row.get("published_at"), row.get("retrieved_at") or now, company, row.get("team"),
                     str(row.get("excerpt") or "")[:1500], "public_source", "independently_retrieved",
                     row.get("relevance") if row.get("relevance") in {"company", "team", "role"} else "company",
                     str(row.get("limitations") or "")[:800], json.dumps(row.get("context") or {}, ensure_ascii=False)),
                )
        return report_id
