# Contributing

ec20-voice-steer is a small Epiphan proof of concept. Contributions that keep it honest (documented facts only),
safe (only a bench camera moves) and small are the most welcome.

## What helps most

1. Bench results for the rows in `docs/test-plan.md`, with the firmware version and what you saw.
2. Facts about the EC20's VISCA over IP behavior, quoted from kb.epiphan.com with the page id.
3. What a real ceiling array sends, quoted from its maker's published docs.
4. Anything else: open an issue first for anything large.

## Set up

```bash
uv sync --group dev
uv run pytest -q
bash tests/hook-test.sh
uvx pre-commit install      # runs gitleaks, ruff, shellcheck, actionlint and zizmor on every commit
```

All of the code can be worked on without a camera. Tests use a fake datagram transport and make no network calls.
For bench work, copy `.env.example` to `.env` and set the bench EC20's address there.

## Rules

1. Documented facts only. Epiphan behavior comes from kb.epiphan.com, cited beside the code. If the docs don't
   cover it, it's a bench test or an open question.
2. Only a bench camera moves. Never point `ec20-steer` at a camera in a room someone is using. Changing anything
   through Epiphan Edge needs approval that names the device and the effect. Don't weaken the Edge write guard, the
   redaction hook or the permissions in `.claude/settings.json`. They come from the Epiphan Edge Claude Kit, so
   change them there first.
3. No real data. No customer, consultant, school, room or person names, camera addresses, serials, recordings,
   internal messages, customer data or CRM figures in code, fixtures, issues or PRs. Use placeholders.
4. Settings in `.env` only, read through one `Settings` class. gitleaks runs in pre-commit and CI.
5. Code style: Python 3.12+, async for all I/O, type hints on every function, `ruff` clean, no OpenAI.
6. Prose: sentence-case headings, no em dashes, no bold for emphasis. Run the Epiphan Brand check on READMEs and docs.

## Commits and pull requests

- Use [Conventional Commits](https://www.conventionalcommits.org/) with a scope: `feat(visca): ...`,
  `docs(test-plan): ...`, `ci: ...`, `test(router): ...`.
- One concern per PR, from a branch. Fill in the Evidence section of the PR template with commands you ran and
  what they printed. CI must be green: lint, tests on Linux and macOS, the hook tests, and the secrets scan.
- Main needs a second reviewer.

## Using an AI assistant

Fine and welcome. Point it at [AGENTS.md](AGENTS.md). You are responsible for every line you submit.

## Security issues

See [SECURITY.md](SECURITY.md). Contributions are made as Epiphan work, belong to Epiphan Systems Inc., and are
licensed under the Apache License 2.0 (see [LICENSE](LICENSE)).
