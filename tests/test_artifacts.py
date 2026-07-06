from pathlib import Path

from nova.memory.artifacts import load, load_dir

SHIPPED = Path(__file__).parent.parent / "artifacts"


def test_load_artifact(tmp_path):
    (tmp_path / "distill.md").write_text(
        "---\nid: distiller.default\nversion: '1.0'\nmodel_hint: haiku\n---\nSummarize the session.")
    art = load(tmp_path / "distill.md")
    assert (art.id, art.version) == ("distiller.default", "1.0")
    assert "Summarize" in art.body


def test_later_dir_overrides_by_id(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "x.md").write_text("---\nid: d\nversion: '1'\n---\nold")
    (b / "x.md").write_text("---\nid: d\nversion: '2'\n---\nnew")
    merged = load_dir(a) | load_dir(b)
    assert merged["d"].version == "2"


def test_shipped_artifacts_all_load():
    """Every artifact shipped under artifacts/ must satisfy the §3.4.3 schema.

    Guards against frontmatter drift: a prompt edit that breaks the schema
    fails here, not at runtime inside the memory pipeline.
    """
    subdirs = [d for d in SHIPPED.iterdir() if d.is_dir()]
    assert subdirs, "artifacts/ has no artifact subdirectories"
    loaded = {}
    for d in subdirs:
        loaded |= load_dir(d)
    assert "distiller-default" in loaded
    art = loaded["distiller-default"]
    assert art.version == "0"
    assert art.inputs == ["transcript"]
    assert "NO_NOTE" in art.body  # the abstain path is part of the contract
