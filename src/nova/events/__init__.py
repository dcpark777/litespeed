"""Normalized event schema and the dual-source normalizer — C0 contract (SPEC §3.1).

Everything downstream (UI, index, automation) consumes NovaEvents, never raw
SDK messages or raw JSONL. Belongs here: models (NovaEvent, EventKind),
sdk_translator (live stream half), jsonl_replayer (replay half), store (T1
append-only JSONL). Both halves must produce identical
normalization_identity_key sequences for the same session.

Changes require a SPEC.md edit in the same commit. Fixture-first: new message
shapes get a golden fixture in tests/fixtures/golden/ before any mapping change.
"""
