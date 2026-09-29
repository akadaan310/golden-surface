-- v4: the surface shard. Every change to the Golden Surface, compiled into one
-- entry in Luna's record format ({seq, ts, kind, from, text, id}), hash-chained:
-- each entry's hash covers the previous entry's hash. Append-only, like events.
CREATE TABLE IF NOT EXISTS shard (
  seq   INTEGER PRIMARY KEY AUTOINCREMENT,
  ts    TEXT NOT NULL,
  kind  TEXT NOT NULL,     -- surface.compiled | bridge.step | llm.engaged | llm.asked | app.lifecycle | ...
  frm   TEXT NOT NULL,     -- abed | r | n | system | bridge
  text  TEXT NOT NULL,     -- JSON body
  id    TEXT NOT NULL,     -- idstamp: sha256(time_ns|text)[:16], as in Luna's shell
  prev  TEXT NOT NULL,     -- hash of the previous entry ('0' for the first)
  hash  TEXT NOT NULL      -- sha256(prev|seq|ts|kind|frm|text)
);
CREATE TRIGGER IF NOT EXISTS shard_no_update BEFORE UPDATE ON shard
  BEGIN SELECT RAISE(ABORT, 'shard is append-only'); END;
CREATE TRIGGER IF NOT EXISTS shard_no_delete BEFORE DELETE ON shard
  BEGIN SELECT RAISE(ABORT, 'shard is append-only'); END
