"""Secret redaction and credential-reference resolution — C0 contract (SPEC §16).

Nova never stores secret values at rest: config/T1/T3/logs hold references
(env:, keyring:, aws-sm:, aws-ssm:) resolved to values in memory only at use
time (resolver). The redaction patterns (redaction) are the single DLP
definition, enforced at event ingestion, memory promotion, and pre-commit
(scripts/check_staged.py). If you see a secret value anywhere, stop and surface it.
"""
