from nova.memory.notes import Note, NoteType


def test_roundtrip_is_byte_identical():
    n = Note(type=NoteType.decision, title="Use worktrees for Type 1", body="Because parallel tasks.")
    once = n.serialize()
    again = Note.parse(once).serialize()
    assert once == again  # byte-deterministic (SPEC §3.6)


def test_canonical_shape():
    s = Note(type=NoteType.standard, title="t", body="b").serialize()
    assert s.startswith("---\nid:")          # declared key order, id first
    assert s.endswith("b\n") and not s.endswith("\n\n")  # exactly one trailing newline
    assert "\r" not in s


def test_write_and_parse_file(tmp_path):
    n = Note(type=NoteType.distillate, title="x", body="y")
    path = n.write(tmp_path)
    assert path.name == f"{n.id}.md"
    assert Note.parse(path.read_text()).id == n.id
