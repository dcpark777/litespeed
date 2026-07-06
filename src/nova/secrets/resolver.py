"""Credential-reference resolution — SPEC §16 (C0).

Nova never stores secret values at rest. Config carries references with a scheme
prefix; this resolver turns a reference into a value at use time, in memory only.

Schemes: env:NAME · keyring:service/name · aws-sm:secret-id · aws-ssm:param-name
"""
from __future__ import annotations

import os


class CredentialError(Exception):
    pass


def resolve(ref: str) -> str:
    scheme, _, rest = ref.partition(":")
    if not rest:
        raise CredentialError(f"malformed credential reference: {ref!r}")
    if scheme == "env":
        val = os.environ.get(rest)
        if val is None:
            raise CredentialError(f"env var {rest} not set")
        return val
    if scheme == "keyring":
        import keyring  # local import: optional backend availability
        service, _, name = rest.partition("/")
        val = keyring.get_password(service, name)
        if val is None:
            raise CredentialError(f"no keychain entry for {rest}")
        return val
    if scheme in ("aws-sm", "aws-ssm"):
        import boto3  # [aws] extra; ambient IAM chain — no stored AWS creds
        if scheme == "aws-sm":
            resp = boto3.client("secretsmanager").get_secret_value(SecretId=rest)
            return resp["SecretString"]
        resp = boto3.client("ssm").get_parameter(Name=rest, WithDecryption=True)
        return resp["Parameter"]["Value"]
    raise CredentialError(f"unknown credential scheme: {scheme!r}")
