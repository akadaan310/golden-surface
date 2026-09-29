-- v3: where a session's health is verified.
--   twin  : the session was shared into the twin browser profile; checked there.
--   phone : the twin mirrors state only (site challenges VM sessions, or the
--           build can't export cookies); checked by a probe on Abed's phone.
ALTER TABLE sessions ADD COLUMN check_via TEXT NOT NULL DEFAULT 'phone';
