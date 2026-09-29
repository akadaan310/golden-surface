# Design amendments — from Abed, 2026-09-28 (recorded by ر during build run 1)

## 1. The fingers are a capability, never a gate.

No human-in-the-loop bottleneck — ever, no matter what. Not even a
review queue. Abed's fingers (logins, approvals, signups) are
capabilities the system may request, never gates it blocks on.

Consequences for the build:

- `login_needed` is an EVENT, not a blocking call. The relay emits it
  (the app shows the "your fingers only" banner) and moves on.
  Everything that can proceed without that session proceeds.
- Graceful degradation: a site with no live session is marked
  unavailable (or the twin mirrors state only); the rest of the system
  works normally.
- Nothing polls Abed. Nothing waits on him. No review queues.
- When fingers arrive (login_done), the session flips to alive and
  anything parked on it resumes automatically.
- Watchers keep watching regardless; they emit alerts, they don't wait.

This amends the login-handoff section of SPEC.md: the handoff stays,
the waiting goes.
