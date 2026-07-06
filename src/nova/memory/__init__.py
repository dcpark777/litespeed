"""Memory pipeline pieces: notes and versioned prompt artifacts (SPEC §6, §3.6, §3.4.3).

notes: byte-deterministic note serialization (frontmatter per §3.6, links by
id, never path). artifacts: loader for versioned prompt files under artifacts/
— every use records {artifact_id, version}. The distiller -> inbox -> PR
promotion flow is Phase 3; the PR gate is the DLP boundary.
"""
