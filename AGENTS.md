# AGENTS.md

Instructions for AI coding assistants (Claude Code, Codex, Cursor and others) working in this repo. Humans:
[README.md](README.md) and the same rules apply.

## What this is

ec20-voice-steer tests whether a ceiling microphone array can steer an Epiphan EC20 on its own, by sending a VISCA
over IP preset recall when a talker speaks in a zone. A laptop plays the array until a real one is on the bench.
Python 3.12, uv, ruff, pytest. Package in `src/ec20_voice_steer/`, command `ec20-steer`. Epiphan-owned, Apache 2.0,
not an officially supported Epiphan product. Status: proof of concept, not yet run against a real EC20.

## Commands

```bash
uv sync --group dev
uv run pytest -q                       # unit tests, no network
bash tests/hook-test.sh                # Edge write guard, redaction, secrets hook, permission rules
uv run ruff check . && uv run ruff format --check .
uv run ec20-steer --help
```

## Hard rules

1. **VISCA goes to a bench EC20 only.** Every `ec20-steer` command except `--help` and `listen` sends UDP to one
   camera and can move it or overwrite a preset. Run those commands only against a camera the maintainer named in
   that session, never a camera in a room someone is using. `save` overwrites a preset with no undo. `listen` sends
   nothing to a camera: it binds a local UDP port and replies only to whoever sent to it. Run it on the bench network.
2. **Epiphan product facts come from the docs.** Use `kb_search` and `kb_fetch` or the Epiphan Knowledge connector,
   never memory, and cite the page id beside the claim. If a page doesn't cover it, it's a bench test or an open
   question in `docs/test-plan.md`. Third-party products (the Audio-Technica array, Dante) are cited the same way
   from their makers' published docs.
3. **Epiphan Edge writes need a person.** Never call an Edge write tool without the maintainer's approval in that
   session, naming device, channel and effect. Never weaken `.claude/hooks/epiphan-write-guard.sh`,
   `.claude/hooks/epiphan-redact.sh` or the `permissions` in `.claude/settings.json`. Those hooks are copied from
   the Edge Claude Kit and are fixed there first. Run `get_devices_in_my_team` and confirm the team is the sandbox
   before any write. The visible Edge team may be Epiphan's shared demo fleet.
4. **Settings stay in `.env`**, read through one `Settings` class, never `os.environ`. The camera address has no
   default, so a command never guesses which camera to move.
5. **No real data in the repo.** No customer, consultant, school, room or person names, camera IP addresses,
   serials, device IDs, recordings, frames, internal messages, CRM figures or documents in code, fixtures, docs,
   issues, PRs or commit messages. Use placeholders like `192.0.2.10` (TEST-NET-1) and "Room 204". `docs/run.log`
   and real bench notes are gitignored and stay on the machine they were made on.
6. **Python cannot call MCP tools.** Anything on the Epiphan Edge side (checking the Pearl Mini recording, sharing
   the clip) is a Claude session step, not code.
7. **Async for every network and blocking disk call; type hints on every function.** No network in tests: inject
   a fake datagram transport (`tests/conftest.py`).
8. **No OpenAI.** If a model is ever needed: Anthropic direct, or DeepSeek, Qwen or Groq via OpenRouter.
9. **Unannounced hardware is not a spec.** Nothing in code or docs states or depends on specs or firmware Product
   hasn't published. "Product said the firmware side isn't implemented" is the reason this repo exists, not a fact
   to repeat.
10. **No timing claims across devices.** Recall latency, lip sync, and alignment between the camera, the array and
    an encoder are bench notes in the test plan, never claims in code or docs.
11. **Ownership.** Copyright Epiphan Systems Inc. (NOTICE). Keep the trademark line and "not an officially supported
    Epiphan product" wherever licensing is described.
12. **Prose goes through the Epiphan Brand connector.** Call `get_writing_style` before writing README or docs
    prose, and run `check_my_copy` and fix every flag before committing it. Sentence-case headings, no em dashes,
    no bold for emphasis.

## Style

- Conventional Commits with scopes (`feat(visca):`, `feat(router):`, `docs(test-plan):`). One concern per PR.
- Work on a branch and open a PR; CI must be green. The PR's Evidence section shows commands you actually ran.
- Plain words in docs. Say what is documented, what is a bench test and what is unknown.
- Main needs a second reviewer. Never merge your own PR without a review, and never push to main.

## Map

| Path | What it does |
|---|---|
| `src/ec20_voice_steer/visca.py` | VISCA over IP packets, reply parsing, and the async camera client |
| `src/ec20_voice_steer/router.py` | Zone to preset mapping and the debounce |
| `src/ec20_voice_steer/listener.py` | The fake EC20 behind `ec20-steer listen`: decodes and answers what an array sends |
| `src/ec20_voice_steer/cli.py` | The `ec20-steer` command, with the key and mic stand-ins for the array |
| `src/ec20_voice_steer/settings.py` | The camera address and timeout from `.env` |
| `docs/test-plan.md` | The bench tests T1 to T5 and the open questions |
| `.claude/agents/` | The bench team: runner, fact-checker, Edge observer, results scribe, rules reviewer (see `CLAUDE.md`) |
| `.claude/hooks/` | Edge write guard and redaction (from the Edge Claude Kit), secrets hook |
| `.claude/settings.json` | Permissions: reads allowed, writes ask, bypass mode off |
| `tests/hook-test.sh`, `tests/redaction-cases.json` | Hook and permission tests; redaction cases shared with Fleetwatch |
