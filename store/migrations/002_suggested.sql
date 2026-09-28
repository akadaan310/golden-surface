-- v2: suggested-accounts queue. One row per service (no quota games).
CREATE TABLE IF NOT EXISTS suggested (
  service     TEXT PRIMARY KEY,
  signup_url  TEXT NOT NULL,
  why         TEXT,
  added_by    TEXT NOT NULL,        -- r | n
  added_at    TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'open',  -- open | opened | done
  opened_at   TEXT
);
