ALTER TABLE research_reports ADD COLUMN directions_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE research_evidence ADD COLUMN context_json TEXT NOT NULL DEFAULT '{}';
CREATE TABLE research_corrections (
 correction_id TEXT PRIMARY KEY,
 evidence_id TEXT NOT NULL REFERENCES research_evidence(evidence_id) ON DELETE CASCADE,
 kind TEXT NOT NULL CHECK(kind IN ('wrong_entity','broken_link','wrong_team','other')),
 note TEXT NOT NULL,
 created_at TEXT NOT NULL
);
