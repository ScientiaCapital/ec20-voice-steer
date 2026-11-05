# ec20-voice-steer

@AGENTS.md

AGENTS.md (imported above) has the commands, hard rules, style and map for any assistant. This file adds what
Claude Code needs. Read `.claude/PROJECT_CONTEXT.md` at session start. If `.claude/context.local.md` exists, read it
too, but never copy names, camera addresses or dates from it into a tracked file.

## Epiphan tools

- Fleet: the `epiphan` MCP server in `.mcp.json` (tools `mcp__epiphan__*`) or the claude.ai Epiphan connector under
  another name. Read tools are allowed. Every write asks first and names device and channel.
- The sign-in picks one Edge team. Confirm it is the sandbox with `get_devices_in_my_team` before any write. Never
  write to a shared demo fleet. Don't write its device, room or group names into this repo.
- Product facts: the Epiphan Knowledge connector or `kb_search` and `kb_fetch`. If a page doesn't cover it, say so.
- Prose: the Epiphan Brand connector (`get_writing_style`, `check_my_copy`). Product names are EC20, Pearl Mini,
  Pearl Nano, Pearl-2, Epiphan Edge.

## Bench team

`.claude/agents/` holds five roles for the bench phase, and this session is the lead. The lead names the bench camera
and the sandbox Edge team, hands each step to one role with the Agent tool, relays what the person at the bench saw,
and opens the PR. Nothing merges without a person's review.

| Role | Does | Can't |
|---|---|---|
| `bench-runner` | Runs the `ec20-steer` rows of T1 and T2 and reports each reply | Pick a camera, read `.env`, edit docs |
| `fact-checker` | Checks product claims against kb.epiphan.com and returns page ids | Write anything |
| `edge-observer` | Reads Pearl state in Epiphan Edge for T3 and T5 after confirming the sandbox team | Any Edge write |
| `results-scribe` | Fills the test plan and project context, scrubs, runs `check_my_copy`, commits on the branch | Change code, touch main |
| `repo-rules-reviewer` | Reviews the branch diff against the hard rules before the PR | Fix, approve, or merge |

Order for each test: bench-runner (or edge-observer for T3 and T5), then results-scribe, then fact-checker on any new
product sentence, then repo-rules-reviewer, then the PR. `tests/test_agents.py` fails if a role ever lists an Edge
write tool, a wildcard MCP tool, or a bypass mode. The hooks and `permissions` in `.claude/settings.json` still apply
to every role.

To start a test: "The bench EC20 is the one in `.env`, the sandbox Edge team is the one you see, branch `bench/t1`.
Run T1 with the bench team." Say the camera and the team out loud in the session every time. The roles refuse
without it.

## Data model

The EC20 is a camera with a single fixed channel (`channel_id` 1) in Epiphan Edge, and several Edge tools don't
apply to it. VISCA control happens outside Edge entirely, straight from `ec20-steer` to the camera on UDP 52381.
Pearl Mini or Pearl Nano takes the EC20 as a network source and does the recording and streaming, and that's the
part Edge can see.

## Now

Proof of concept, code complete, no hardware run yet. `ec20-steer version | save | recall | home | route` exist and
are tested only with a fake transport. The next person starts with "Where to pick up" in
`.claude/PROJECT_CONTEXT.md`: bench setup, then T1, T2 and T3 in `docs/test-plan.md`.
