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
