# Versioned prompt/skill artifacts (SPEC §3.4.3)

Prompts are files in git, never string literals in code. Each artifact is a
markdown file with YAML frontmatter, loaded by `nova.memory.artifacts.load()`,
which returns `{id, version}` alongside the body so every use can be recorded
in the audit/provenance trail ("which distiller version wrote this note?").

```markdown
---
id: distiller-default        # stable; referenced from config
version: "1"                 # bump on ANY prompt change
model_hint: small            # optional: main | small
inputs: [transcript]         # what the caller must supply
---
(prompt body)
```

Layout:

- `distillers/` — session → memory-inbox candidate prompts (SPEC §6).
  `distiller-default.md` is the shipped v0 baseline; Phase 3 iterates on it
  (bump `version` on any prompt change). Keep non-artifact files (READMEs)
  out of artifact subdirectories — `load_dir` globs every `*.md`.
- playbooks, classifiers, and edit-templates get sibling directories when the
  first one exists (SPEC §5.4, §3.4.2)

Resolution order: this directory ships the defaults; memory repos may override
by id (`load_dir` later-wins, mirroring config precedence §3.5). Which artifact
a workstream uses is config (`distiller artifact id/version`), not code.
