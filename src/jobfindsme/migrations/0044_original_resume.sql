ALTER TABLE resume_versions ADD COLUMN original_file INTEGER NOT NULL DEFAULT 0 CHECK (original_file IN (0, 1));
