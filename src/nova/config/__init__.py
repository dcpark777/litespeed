"""Layered config precedence resolver — C0 contract (SPEC §3.5).

org (managed) -> commons -> team -> user -> workstream; later wins except
org-locked keys. Carries config_version; readers support N and N-1.
TODO(phase-1): loading, lock enforcement, effective-config report live here too.
"""
