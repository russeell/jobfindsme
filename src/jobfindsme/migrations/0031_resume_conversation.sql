ALTER TABLE resume_edit_sessions ADD COLUMN target_title TEXT NOT NULL DEFAULT '';
ALTER TABLE resume_edit_sessions ADD COLUMN target_url TEXT NOT NULL DEFAULT '';
ALTER TABLE resume_edit_sessions ADD COLUMN target_jd TEXT NOT NULL DEFAULT '';
ALTER TABLE resume_edit_sessions ADD COLUMN saved_version_id TEXT REFERENCES resume_versions(version_id);
