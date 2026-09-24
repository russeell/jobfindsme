CREATE TABLE desktop_source_capabilities (
    source_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    name TEXT NOT NULL,
    login_required INTEGER NOT NULL,
    session_status TEXT NOT NULL,
    list_status TEXT NOT NULL,
    detail_status TEXT NOT NULL,
    fields_status TEXT NOT NULL,
    pagination_status TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0,
    last_verified_at TEXT,
    notes TEXT NOT NULL DEFAULT '',
    CHECK (source_type IN ('platform', 'company')),
    CHECK (login_required IN (0, 1)),
    CHECK (enabled IN (0, 1))
);

CREATE INDEX idx_desktop_source_capabilities_type
ON desktop_source_capabilities (source_type, name);
