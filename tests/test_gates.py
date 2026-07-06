from nova.gates.decisions import (GATE_DECISION_VERSION, GateDecision, Outcome,
                                  ProposedChange, append, load)


def _decision(**kw):
    defaults = dict(
        workstream_id="ws1", session_id="s1", outcome=Outcome.accept,
        changes=[ProposedChange(path="src/app.py", proposed_content="print('hi')\n",
                                base_hash="abc123")],
    )
    return GateDecision(**{**defaults, **kw})


def test_decision_roundtrip(tmp_path):
    path = tmp_path / "ws1" / "decisions.jsonl"
    d = _decision()
    append(path, d)
    (loaded,) = load(path)
    assert loaded == d
    assert loaded.gate_decision_version == GATE_DECISION_VERSION
    # change-set level: the full proposed content survives, no line references
    assert loaded.changes[0].proposed_content == "print('hi')\n"
    assert "line" not in GateDecision.model_fields
    assert "line" not in ProposedChange.model_fields


def test_revise_carries_feedback(tmp_path):
    path = tmp_path / "decisions.jsonl"
    append(path, _decision(outcome=Outcome.revise,
                           feedback="split the migration out of this change"))
    (loaded,) = load(path)
    assert loaded.outcome == Outcome.revise
    assert "split the migration" in loaded.feedback


def test_append_only_history(tmp_path):
    path = tmp_path / "decisions.jsonl"
    append(path, _decision(outcome=Outcome.revise, feedback="tighten tests"))
    append(path, _decision(outcome=Outcome.accept))
    outcomes = [d.outcome for d in load(path)]
    assert outcomes == [Outcome.revise, Outcome.accept]  # history preserved in order


def test_load_missing_file_is_empty(tmp_path):
    assert load(tmp_path / "never-written.jsonl") == []


def test_deletion_is_none_content(tmp_path):
    path = tmp_path / "decisions.jsonl"
    append(path, _decision(changes=[ProposedChange(path="old.py", proposed_content=None)]))
    (loaded,) = load(path)
    assert loaded.changes[0].proposed_content is None
