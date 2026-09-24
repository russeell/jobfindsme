CREATE TABLE model_connections (
    connection_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    protocol TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    model_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unverified',
    last_error TEXT,
    last_tested_at TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (protocol IN ('openai_compatible', 'anthropic', 'gemini')),
    CHECK (status IN ('unverified', 'testing', 'verified', 'failed', 'cancelled'))
);
