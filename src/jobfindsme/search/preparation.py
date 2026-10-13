"""Local job preparation and next actions. No external requests or submissions."""

from datetime import UTC, date, datetime
from uuid import uuid4

from jobfindsme.importing.repository import JobRepository
from jobfindsme.storage import Database

STAGES = {"considering", "applied", "interview", "offer", "closed"}


class JobPreparationService:
    def __init__(self, database: Database):
        self.database = database
        self.jobs = JobRepository(database)

    def get(self, workspace_id: str, job_id: str) -> dict:
        job = self.jobs.get(workspace_id=workspace_id, job_id=job_id)
        with self.database.connect() as db:
            row = db.execute(
                "SELECT * FROM job_preparations WHERE workspace_id=? AND job_id=?",
                (workspace_id, job_id),
            ).fetchone()
            applied = db.execute(
                "SELECT applied FROM job_tracking_flags "
                "WHERE workspace_id=? AND job_id=?",
                (workspace_id, job_id),
            ).fetchone()
        return {
            "job": job.model_dump(mode="json"),
            "preparation": dict(row)
            if row
            else {
                "workspace_id": workspace_id,
                "job_id": job_id,
                "stage": "applied" if applied and applied["applied"] else "considering",
                "next_action": "",
                "due_date": None,
                "note": "",
                "resume_version_id": None,
                "updated_at": None,
            },
        }

    def save(
        self,
        workspace_id: str,
        job_id: str,
        *,
        stage: str,
        next_action: str = "",
        due_date: str | None = None,
        note: str = "",
    ) -> dict:
        self.jobs.get(workspace_id=workspace_id, job_id=job_id)
        if stage not in STAGES:
            raise ValueError("invalid preparation stage")
        if len(next_action) > 200 or len(note) > 2000:
            raise ValueError("preparation text is too long")
        if due_date:
            date.fromisoformat(due_date)
        now = datetime.now(UTC).isoformat()
        with self.database.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO "
                "job_preparations(workspace_id,job_id,stage,next_action,"
                "due_date,note,updated_at) "
                "VALUES(?,?,?,?,?,?,?) ON CONFLICT(workspace_id,job_id) DO UPDATE SET "
                "stage=excluded.stage,next_action=excluded.next_action,d"
                "ue_date=excluded.due_date,"
                "note=excluded.note,updated_at=excluded.updated_at",
                (
                    workspace_id,
                    job_id,
                    stage,
                    next_action.strip(),
                    due_date or None,
                    note.strip(),
                    now,
                ),
            )
            if stage != "closed":
                applied = stage != "considering"
                db.execute(
                    "INSERT INTO "
                    "job_tracking_flags(workspace_id,job_id,saved,applied,updated_at) "
                    "VALUES(?,?,0,?,?) ON CONFLICT(workspace_id,job_id) DO UPDATE SET "
                    "applied=excluded.applied,updated_at=excluded.updated_at",
                    (workspace_id, job_id, int(applied), now),
                )
                db.execute(
                    "INSERT INTO "
                    "job_tracking_events(event_id,workspace_id,job_id,event_type,"
                    "enabled,created_at) "
                    "VALUES(?,?,?,'applied',?,?)",
                    (
                        f"tracking_{uuid4().hex}",
                        workspace_id,
                        job_id,
                        int(applied),
                        now,
                    ),
                )
        return self.get(workspace_id, job_id)

    def update_next_action(
        self,
        workspace_id: str,
        job_id: str,
        *,
        expected_updated_at: str | None,
        next_action: str,
        due_date: str | None = None,
    ) -> dict:
        """Arrange/complete a reminder without changing application or resume state."""
        job = self.jobs.get(workspace_id=workspace_id, job_id=job_id)
        if len(next_action) > 200:
            raise ValueError("next action is too long")
        if due_date:
            date.fromisoformat(due_date)
        with self.database.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM job_preparations WHERE workspace_id=? AND job_id=?",
                (workspace_id, job_id),
            ).fetchone()
            if (row["updated_at"] if row else None) != expected_updated_at:
                raise ValueError("待办已在其他操作中更新，请重新读取后再操作。")
            if not row:
                applied = db.execute(
                    "SELECT applied FROM job_tracking_flags "
                    "WHERE workspace_id=? AND job_id=?",
                    (workspace_id, job_id),
                ).fetchone()
                db.execute(
                    "INSERT INTO job_preparations"
                    "(workspace_id,job_id,stage,updated_at) "
                    "VALUES(?,?,?,?)",
                    (
                        workspace_id,
                        job_id,
                        "applied" if applied and applied["applied"] else "considering",
                        datetime.now(UTC).isoformat(),
                    ),
                )
            db.execute(
                "UPDATE job_preparations SET next_action=?,due_date=?,updated_at=? "
                "WHERE workspace_id=? AND job_id=?",
                (
                    next_action.strip(),
                    due_date if next_action.strip() else None,
                    datetime.now(UTC).isoformat(),
                    workspace_id,
                    job_id,
                ),
            )
            saved = db.execute(
                "SELECT * FROM job_preparations WHERE workspace_id=? AND job_id=?",
                (workspace_id, job_id),
            ).fetchone()
        return {"job": job.model_dump(mode="json"), "preparation": dict(saved)}

    def list_applications(
        self, workspace_id: str, job_id: str | None = None, *, deleted: bool = False
    ) -> list[dict]:
        with self.database.connect() as db:
            rows = db.execute(
                "SELECT * FROM application_records WHERE workspace_id=? "
                "AND (? IS NULL OR job_id=?) AND ((deleted_at IS NOT NULL)=?) "
                "ORDER BY created_at DESC, record_id",
                (workspace_id, job_id, job_id, int(deleted)),
            ).fetchall()
        return [dict(row) for row in rows]

    def set_application_deleted(
        self, workspace_id: str, job_id: str, record_id: str, deleted: bool
    ) -> dict:
        with self.database.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT 1 FROM application_records WHERE workspace_id=? "
                "AND job_id=? AND record_id=?",
                (workspace_id, job_id, record_id),
            ).fetchone()
            if not row:
                raise LookupError("application record not found")
            db.execute(
                "UPDATE application_records SET deleted_at=? WHERE workspace_id=? "
                "AND job_id=? AND record_id=?",
                (
                    datetime.now(UTC).isoformat() if deleted else None,
                    workspace_id,
                    job_id,
                    record_id,
                ),
            )
        return {"record_id": record_id, "deleted": deleted}

    def record_application(
        self,
        workspace_id: str,
        job_id: str,
        *,
        record_id: str,
        resume_version_id: str | None,
        message: str,
        status: str,
    ) -> dict:
        """Only a user-confirmed send changes tracking; opening a page never does."""
        self.jobs.get(workspace_id=workspace_id, job_id=job_id)
        if status not in {
            "prepared",
            "opened",
            "contacted",
            "resume_sent",
            "uncertain",
        }:
            raise ValueError("invalid application status")
        if not record_id or len(record_id) > 100 or len(message) > 3000:
            raise ValueError("invalid application record")
        if status == "resume_sent" and not resume_version_id:
            raise ValueError("请先选择实际使用的简历版本")
        now = datetime.now(UTC).isoformat()
        with self.database.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if (
                resume_version_id
                and not db.execute(
                    "SELECT 1 FROM resume_versions WHERE workspace_id=? AND "
                    "version_id=?",
                    (workspace_id, resume_version_id),
                ).fetchone()
            ):
                raise ValueError("resume version does not belong to workspace")
            old = db.execute(
                "SELECT * FROM application_records WHERE record_id=?", (record_id,)
            ).fetchone()
            if old and (old["workspace_id"] != workspace_id or old["job_id"] != job_id):
                raise ValueError("application record scope mismatch")
            if old and old["deleted_at"]:
                raise ValueError("记录已删除，请新建材料或先恢复记录")
            if old and old["status"] in {"contacted", "resume_sent", "uncertain"}:
                # Preserve confirmed materials; corrections create a new record.
                raise ValueError("已确认的记录不能覆盖，请新建记录")
            db.execute(
                "INSERT INTO application_records (record_id,workspace_id,job_id,"
                "resume_version_id,message,status,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?) "
                "ON CONFLICT(record_id) DO UPDATE SET "
                "resume_version_id=excluded.resume_version_id,"
                "message=excluded.message,status=excluded.status,u"
                "pdated_at=excluded.updated_at",
                (
                    record_id,
                    workspace_id,
                    job_id,
                    resume_version_id,
                    message.strip(),
                    status,
                    now,
                    now,
                ),
            )
            applied = db.execute(
                "SELECT applied FROM job_tracking_flags "
                "WHERE workspace_id=? AND job_id=?",
                (workspace_id, job_id),
            ).fetchone()
            db.execute(
                "INSERT INTO job_preparations(workspace_id,job_id,stage,updated_at) "
                "VALUES(?,?,?,?) ON CONFLICT(workspace_id,job_id) DO NOTHING",
                (
                    workspace_id,
                    job_id,
                    "applied" if applied and applied["applied"] else "considering",
                    now,
                ),
            )
            db.execute(
                "UPDATE job_preparations SET resume_version_id=?, updated_at=? "
                "WHERE workspace_id=? AND job_id=?",
                (resume_version_id, now, workspace_id, job_id),
            )
            if status == "resume_sent":
                db.execute(
                    "UPDATE job_preparations SET "
                    "stage='applied',updated_at=? WHERE workspace_id=? AND "
                    "job_id=? AND stage='considering'",
                    (now, workspace_id, job_id),
                )
                db.execute(
                    "INSERT INTO "
                    "job_tracking_flags(workspace_id,job_id,saved,applied,updated_at) "
                    "VALUES(?,?,0,1,?) ON CONFLICT(workspace_id,job_id) DO "
                    "UPDATE SET applied=1,updated_at=excluded.updated_at",
                    (workspace_id, job_id, now),
                )
                db.execute(
                    "INSERT INTO "
                    "job_tracking_events(event_id,workspace_id,job"
                    "_id,event_type,enabled,created_at) VALUES(?,?,?,'applied',1,?)",
                    (f"tracking_{uuid4().hex}", workspace_id, job_id, now),
                )
        return next(
            row
            for row in self.list_applications(workspace_id, job_id)
            if row["record_id"] == record_id
        )
