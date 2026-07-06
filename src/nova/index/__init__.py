"""T2 derived index: SQLite + FTS5 (SPEC §4).

Never the source of truth — `rm -rf ~/.nova/index.db && nova reindex` must
always be safe (§14 self-check); rebuild fully from T0 (Claude transcripts)
+ T1 (Nova canonical files). No migration discipline: delete on schema change.
"""
