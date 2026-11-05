## What and why

<!-- One concern per PR. Link the issue if there is one. -->

## Evidence

<!-- The commands you ran and what they printed. Required. -->

```
uv run python -m pytest -q
bash tests/hook-test.sh
```

## Checklist

- [ ] PR title follows Conventional Commits (`fix(scope): ...`); it becomes the squash commit
- [ ] No real customer, consultant, room or person names, camera addresses, device IDs, serials, stream keys or recordings in code, fixtures or this PR
- [ ] No internal messages, customer data, CRM figures or document contents in code, docs or commits
- [ ] EC20 behavior is cited from kb.epiphan.com, or marked as a bench test in docs/test-plan.md
- [ ] Bench runs used the bench EC20 only
- [ ] No claim about timing or alignment across cameras or devices, in code, comments, docs or chat
- [ ] Edge write guard and redaction unchanged, or changed in the Epiphan Edge Claude Kit first
- [ ] Prose passed the Epiphan Brand check
- [ ] Docs updated if behavior or setup changed
