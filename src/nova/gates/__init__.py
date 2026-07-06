"""Review gates: diff review + revise-with-feedback (SPEC §5.5) — hackathon Track 4.

decisions: the persistent GateDecision record (change-set level with full
proposed content, never line-keyed) — the data foundation is settled; build
on it. Still to come in Track 4: the git-diff endpoints backing the
@codemirror/merge panel and the revise-with-feedback session resume.
Design around accept-all / reject-and-revise; per-hunk is a UI nicety.
"""
