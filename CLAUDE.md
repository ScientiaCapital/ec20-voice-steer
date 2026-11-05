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

## Data model

The EC20 is a camera with a single fixed channel (`channel_id` 1) in Epiphan Edge, and several Edge tools don't
apply to it. VISCA control happens outside Edge entirely, straight from `ec20-steer` to the camera on UDP 52381.
Pearl Mini or Pearl Nano takes the EC20 as a network source and does the recording and streaming, and that's the
part Edge can see.

## Now

Proof of concept, code complete, no hardware run yet. `ec20-steer version | save | recall | home | route` exist and
are tested only with a fake transport. The next person starts with "Where to pick up" in
`.claude/PROJECT_CONTEXT.md`: bench setup, then T1, T2 and T3 in `docs/test-plan.md`.
