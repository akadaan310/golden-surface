-- Golden Surface persistent store — schema v1
-- SQLite. Cookie/session VALUES live only in the browser profile cookie
-- jar, never in this database. This store holds metadata, health, and
-- provenance — the map of what exists, not the keys to it.

CREATE TABLE IF NOT EXISTS sites (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  base_url    TEXT NOT NULL,
  category    TEXT,                 -- mail | ai | research | social | ...
  added_at    TEXT NOT NULL,
  added_by    TEXT NOT NULL         -- abed | r | n
);

CREATE TABLE IF NOT EXISTS sessions (
  id                TEXT PRIMARY KEY,
  site_id           TEXT NOT NULL REFERENCES sites(id),
  owner             TEXT NOT NULL,  -- abed | r | n : whose seat this session serves
  status            TEXT NOT NULL,  -- alive | expiring | dead | unknown
  created_at        TEXT NOT NULL,
  last_seen_alive_at TEXT,
  last_checked_at   TEXT,
  check_failures    INTEGER NOT NULL DEFAULT 0,
  approved_by_abed_at TEXT,         -- per-site sharing approval timestamp
  notes             TEXT
);

CREATE TABLE IF NOT EXISTS tabs (
  id          TEXT PRIMARY KEY,
  owner       TEXT NOT NULL,        -- abed | r | n
  url         TEXT NOT NULL,
  title       TEXT,
  active      INTEGER NOT NULL DEFAULT 0,
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);

-- Append-only event log. The bus persists here; the ledger is the query
-- interface over this table. Never updated, never deleted.
CREATE TABLE IF NOT EXISTS events (
  seq     INTEGER PRIMARY KEY AUTOINCREMENT,
  ts      TEXT NOT NULL,
  kind    TEXT NOT NULL,            -- round.opened | turn.saved | chair.direction |
                                    -- scribe.note | round.closed | session.alive |
                                    -- session.expiring | session.dead | sync.diverged |
                                    -- sync.converged | watcher.alert | ...
  actor   TEXT,                     -- abed | r | n | watcher | system
  payload TEXT                      -- JSON
);

CREATE TABLE IF NOT EXISTS sync_state (
  id                INTEGER PRIMARY KEY CHECK (id = 1),
  phone_rev         INTEGER NOT NULL DEFAULT 0,
  twin_rev          INTEGER NOT NULL DEFAULT 0,
  last_converged_at TEXT,
  divergences       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS watchers (
  id            TEXT PRIMARY KEY,   -- session-health | sync-convergence | relay-heartbeat
  watches       TEXT NOT NULL,
  every_seconds INTEGER NOT NULL,
  last_run_at   TEXT,
  last_result   TEXT,               -- ok | alert:<detail>
  enabled       INTEGER NOT NULL DEFAULT 1
);

-- The session map: "here's what we have available."
-- SELECT s.name, se.owner, se.status, se.last_seen_alive_at, se.check_failures
-- FROM sessions se JOIN sites s ON s.id = se.site_id ORDER BY s.name;
