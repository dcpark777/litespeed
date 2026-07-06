import pytest

from nova.secrets.redaction import contains_secret, scrub, REDACTED
from nova.secrets.resolver import CredentialError, resolve


def test_env_resolution(monkeypatch):
    monkeypatch.setenv("JIRA_TOKEN", "sekret")
    assert resolve("env:JIRA_TOKEN") == "sekret"


def test_missing_env_raises():
    with pytest.raises(CredentialError):
        resolve("env:DOES_NOT_EXIST_123")


def test_unknown_scheme_raises():
    with pytest.raises(CredentialError):
        resolve("vault:whatever")


def test_redaction_catches_common_shapes():
    leaky = "key AKIAABCDEFGHIJKLMNOP and token ghp_abcdefghij0123456789XYZ"
    assert contains_secret(leaky)
    clean = scrub(leaky)
    assert "AKIA" not in clean and "ghp_" not in clean and REDACTED in clean


def test_clean_text_untouched():
    text = "bumped kubekit to 2.3; retried snowflake pull"
    assert not contains_secret(text)
    assert scrub(text) == text
