"""Durable reservations and material snapshots for explicit BOSS applications.

This service never visits a website. Only the dedicated desktop executor supplies
receipts; navigation or a successful click is not a delivery receipt.
"""

import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit
from uuid import uuid4

from jobfindsme.search.preparation import JobPreparationService
from jobfindsme.storage import Database


def boss_job_id(value: str) -> str:
    url = urlsplit(value)
    match = re.fullmatch(r"/job_detail/([\w-]+)\.html", url.path)
    if (
        url.scheme != "https"
        or url.hostname != "www.zhipin.com"
        or url.username
        or url.password
        or url.port not in (None, 443)
        or not match
    ):
        raise ValueError("仅支持 BOSS 准确岗位详情链接")
    return match[1]


class ApplicationAttemptService:
    def __init__(self, database: Database):
        self.database = database

    def list(self, workspace_id: str, job_id: str) -> list[dict]:
        with self.database.connect() as db:
            rows = db.execute(
                "SELECT a.*,r.resume_version_id,r.message FROM application_attempts a "
                "JOIN application_records r USING(record_id) "
                "WHERE a.workspace_id=? AND a.job_id=? ORDER BY a.created_at DESC",
                (workspace_id, job_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def begin(
        self,
        *,
        workspace_id: str,
        job_id: str,
        record_id: str,
        expected_updated_at: str,
        target_url: str,
        title: str,
        company: str,
        file_name: str | None,
        file_sha256: str | None,
    ) -> dict:
        job = JobPreparationService(self.database).jobs.get(
            workspace_id=workspace_id, job_id=job_id
        )
        platform_id = boss_job_id(target_url)
        if (
            job.source.source_name != "BOSS直聘"
            or boss_job_id(job.apply_url) != platform_id
        ):
            raise ValueError("岗位来源或链接已变化，请重新核对")
        if not title.strip() or not company.strip():
            raise ValueError("未能核对岗位和公司")
        now = datetime.now(UTC)
        attempt_id, snapshot_id = f"apply_{uuid4().hex}", f"materials_{uuid4().hex}"
        with self.database.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            source = db.execute(
                "SELECT session_status FROM desktop_source_capabilities "
                "WHERE source_id='boss'"
            ).fetchone()
            if source and source["session_status"] == "blocked":
                raise ValueError("BOSS 已暂停，请在原页处理验证后重新检查")
            previous = db.execute(
                "SELECT 1 FROM application_attempts WHERE platform_job_id=? "
                "AND (state IN ('running','completed','uncertain') OR write_started=1)",
                (platform_id,),
            ).fetchone()
            if previous:
                raise ValueError("该岗位已有执行记录，请先核对结果，不能重复发送")
            if db.execute(
                "SELECT 1 FROM application_records r JOIN jobs j "
                "ON j.workspace_id=r.workspace_id AND j.job_id=r.job_id "
                "WHERE j.source_name='BOSS直聘' AND (j.external_id=? OR "
                "json_extract(j.payload_json,'$.apply_url') LIKE ?) "
                "AND r.status IN ('contacted','resume_sent','uncertain')",
                (platform_id, f"https://www.zhipin.com/job_detail/{platform_id}.html%"),
            ).fetchone():
                raise ValueError("该岗位已有沟通记录，请核对原页，不能重复发送")
            if db.execute(
                "SELECT 1 FROM application_attempts WHERE state='running'"
            ).fetchone():
                raise ValueError("已有 BOSS 投递正在执行，请等待完成")
            recent = db.execute(
                "SELECT 1 FROM application_attempts WHERE created_at>?",
                ((now - timedelta(seconds=60)).isoformat(),),
            ).fetchone()
            if recent:
                raise ValueError("请间隔至少一分钟再执行下一次投递")
            if db.execute(
                "SELECT 1 FROM job_tracking_flags WHERE workspace_id=? AND job_id=? "
                "AND applied=1",
                (workspace_id, job_id),
            ).fetchone():
                raise ValueError("该岗位已标记投递，请查看投递记录")
            row = db.execute(
                "SELECT * FROM application_records WHERE record_id=? "
                "AND workspace_id=? "
                "AND job_id=? AND deleted_at IS NULL",
                (record_id, workspace_id, job_id),
            ).fetchone()
            if (
                not row
                or row["updated_at"] != expected_updated_at
                or row["status"] not in {"prepared", "opened"}
                or not row["message"].strip()
            ):
                raise ValueError("投递材料已变化，请保存后重新核对")
            if row["resume_version_id"]:
                if not file_name or not re.fullmatch(
                    r"[a-f0-9]{64}", file_sha256 or ""
                ):
                    raise ValueError("没有核对实际发送的简历文件")
            elif file_name or file_sha256:
                raise ValueError("本次材料明确不附简历")
            db.execute(
                "INSERT INTO application_records(record_id,workspace_id,job_id,"
                "resume_version_id,message,status,created_at,updated_at) "
                "VALUES(?,?,?,?,?,'prepared',?,?)",
                (
                    snapshot_id,
                    workspace_id,
                    job_id,
                    row["resume_version_id"],
                    row["message"],
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            db.execute(
                "INSERT INTO application_attempts(attempt_id,record_id,workspace_id,"
                "job_id,platform_job_id,target_url,title,company,file_name,file_sha256,"
                "state,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,'running',?,?)",
                (
                    attempt_id,
                    snapshot_id,
                    workspace_id,
                    job_id,
                    platform_id,
                    target_url,
                    title[:300],
                    company[:300],
                    file_name,
                    file_sha256,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
        return self.list(workspace_id, job_id)[0]

    def update(
        self,
        attempt_id: str,
        *,
        state: str = "running",
        phase: str,
        write_started: bool = False,
        message_confirmed: bool = False,
        resume_confirmed: bool = False,
        detail: str = "",
    ) -> dict:
        if state not in {
            "running",
            "completed",
            "blocked",
            "failed",
            "cancelled",
            "uncertain",
        }:
            raise ValueError("invalid execution state")
        now = datetime.now(UTC).isoformat()
        with self.database.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute(
                "SELECT a.*,r.resume_version_id FROM application_attempts a "
                "JOIN application_records r USING(record_id) WHERE attempt_id=?",
                (attempt_id,),
            ).fetchone()
            if not old:
                raise LookupError("attempt not found")
            if old["state"] != "running":
                raise ValueError("执行已经结束，不能覆盖结果")
            sent = bool(message_confirmed or old["message_confirmed"])
            attached = bool(resume_confirmed or old["resume_confirmed"])
            started = bool(write_started or old["write_started"])
            if (sent or attached) and not started:
                raise ValueError("没有执行发送，不能记录送达")
            if attached and (not old["resume_version_id"] or not sent):
                raise ValueError("没有确认对应招呼语与简历")
            if state == "completed" and (
                not sent or old["resume_version_id"] and not attached
            ):
                raise ValueError("缺少完整发送回执")
            if state != "running" and started and state != "completed":
                state = "uncertain"
            db.execute(
                "UPDATE application_attempts SET state=?,phase=?,write_started=?,"
                "message_confirmed=?,resume_confirmed=?,detail=?,updated_at=? "
                "WHERE attempt_id=?",
                (
                    state,
                    phase[:80],
                    started,
                    sent,
                    attached,
                    detail[:500],
                    now,
                    attempt_id,
                ),
            )
            status = (
                "resume_sent"
                if attached
                else "contacted"
                if sent
                else "uncertain"
                if started
                else "prepared"
            )
            db.execute(
                "UPDATE application_records SET status=?,updated_at=? "
                "WHERE record_id=?",
                (status, now, old["record_id"]),
            )
            if attached and not old["resume_confirmed"]:
                already_applied = db.execute(
                    "SELECT applied FROM job_tracking_flags "
                    "WHERE workspace_id=? AND job_id=?",
                    (old["workspace_id"], old["job_id"]),
                ).fetchone()
                db.execute(
                    "INSERT INTO job_tracking_flags(workspace_id,job_id,"
                    "saved,applied,updated_at) "
                    "VALUES(?,?,0,1,?) ON CONFLICT(workspace_id,job_id) "
                    "DO UPDATE SET applied=1,updated_at=excluded.updated_at",
                    (old["workspace_id"], old["job_id"], now),
                )
                db.execute(
                    "UPDATE job_preparations SET stage='applied',updated_at=? "
                    "WHERE workspace_id=? AND job_id=? AND stage='considering'",
                    (now, old["workspace_id"], old["job_id"]),
                )
                if not already_applied or not already_applied["applied"]:
                    db.execute(
                        "INSERT INTO job_tracking_events(event_id,workspace_id,job_id,"
                        "event_type,enabled,created_at) VALUES(?,?,?,'applied',1,?)",
                        (
                            f"tracking_{uuid4().hex}",
                            old["workspace_id"],
                            old["job_id"],
                            now,
                        ),
                    )
        return next(
            row
            for row in self.list(old["workspace_id"], old["job_id"])
            if row["attempt_id"] == attempt_id
        )

    def recover(self) -> None:
        """At process startup, never resume or retry an interrupted side effect."""
        with self.database.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "UPDATE application_records SET status='uncertain' WHERE record_id IN "
                "(SELECT record_id FROM application_attempts "
                "WHERE state='running' AND write_started=1) "
                "AND status NOT IN ('contacted','resume_sent')"
            )
            db.execute(
                "UPDATE application_attempts SET state=CASE WHEN write_started=1 "
                "THEN 'uncertain' ELSE 'cancelled' END,"
                "detail='应用在执行中退出，请核对原页；不会自动重发',"
                "updated_at=? WHERE state='running'",
                (datetime.now(UTC).isoformat(),),
            )
