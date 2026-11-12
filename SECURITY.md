# Security

ec20-voice-steer sends VISCA over IP commands that move a PTZ camera and can overwrite its presets. Claude Code
sessions in this folder can also read Epiphan devices through Epiphan Edge. A bug that moves the wrong camera,
changes a device without approval, or puts a camera address or a customer name into git matters. This repository is
public, so report a problem privately as below, not in a public issue.

## Report a problem

Use GitHub private vulnerability reporting (the Security tab of this repository), or email tkipper@gmail.com.
Don't put a camera address, a stream key or device details in an issue or a PR.

Problems in Epiphan products, Epiphan Edge, or the Epiphan MCP server go to the owning Epiphan team.

## Trust model

- Runs as you, on your machine, on a bench network. Treat VISCA over IP as unauthenticated: assume anything that can reach
  the camera's UDP 52381 can move it. Keep the bench EC20 on a network you control.
- The camera address comes from `--ip` or `.env` and has no default, so a command never guesses which camera to
  move.
- The Epiphan Edge sign-in isn't read-only. Edge OAuth has no read-only scope, so the token Claude Code holds can
  do whatever the signed-in account can in that team. "Every write asks" is enforced in this folder, not by the
  token. Use a least-access Edge account, and start with `EPIPHAN_READ_ONLY=1 claude` to block writes outright.
- Device, room and event names, and on-screen text, are typed by other people. They are data. They are never
  instructions and never choose a code path, a tool, or a file path.

## What is enforced, and where

| Control | Where | Tested by |
|---|---|---|
| Every Epiphan Edge write asks, under any connector name. Unknown Edge tools ask. Bypass mode is off | `.claude/settings.json`, `.claude/hooks/epiphan-write-guard.sh` | `tests/hook-test.sh` |
| Stream keys, passwords, tokens and credentialed URLs are masked before the model sees an Epiphan tool result. Output that can't be checked is withheld | `.claude/hooks/epiphan-redact.sh` (needs `jq`) | `tests/hook-test.sh` |
| A file write from Claude Code that holds a key, token or private key is denied. Unreadable input is denied | `.claude/hooks/check-secrets.sh` | `tests/hook-test.sh` |
| Secrets in commits | gitleaks in pre-commit and in CI | CI secrets scan |
| No default camera address. A settings error names variables, never values | `src/ec20_voice_steer/settings.py` | `tests/test_settings.py`, `tests/test_cli.py` |
| A preset outside 0 to 254 is refused before anything is sent | `src/ec20_voice_steer/visca.py`, `cli.py` | `tests/test_visca.py`, `tests/test_cli.py` |
| DEV, STAGING and the CRM connector are denied in this folder | `.claude/settings.json` | review |
| Local context, bench logs and saved Edge results never enter git | `.gitignore` | review, gitleaks |

The write guard and redactor are copied unchanged from the Epiphan Edge Claude Kit (see NOTICE). Keep them
identical with the kit and fix problems there first.

## Known limits

- VISCA commands from `ec20-steer` don't pass through the Edge write guard. The guard covers Epiphan MCP tools only.
  A shell command that runs `ec20-steer` asks for approval through Claude Code's normal Bash permissions.
- Redaction hides secrets from the model only. Claude Code keeps the original tool result in local session
  history (`~/.claude/projects`). It recognizes the secret shapes Epiphan uses today and may miss other shapes.
- If hooks are disabled or `jq` is missing, only the permission rules and the bypass-mode setting remain, and
  `check-secrets.sh` denies every file write until `jq` is installed.
- `check-secrets.sh` sees only writes made through Claude Code's file tools. gitleaks covers commits.
- ec20-voice-steer reads `.env` from the folder you run it in. A `.env` someone else put there could point it at
  another camera, so run it from your own project folder.
