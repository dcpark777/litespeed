from nova.memory.artifacts import load, load_dir


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
