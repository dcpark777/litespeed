"""Session runner and concurrency leases (SPEC §5.3, §3.2).

runner wraps claude_agent_sdk.query() (start/resume/fork), translating the
stream through nova.events.sdk_translator and persisting to the EventStore.
leases enforce the single-writer-per-cwd invariant in SQLite (pid + heartbeat;
stale leases reaped on backend start). Sessions start ONLY through the runner.
"""
