# orchestra

**English** · [한국어](README.ko.md)

Claude plans, Codex builds and verifies, Claude checks — in one command: `/orchestra <task>`.

```
Haiku scouts → Sonnet plan → Opus plan review → you approve
  → Codex ×N build (N chosen by Claude, parallel, same folder) → Codex verify → (opt-in: Codex advisor, astra)
  → Sonnet re-check → Opus final review
```
No Codex? The workers and the verifier become `claude -p` runs (Claude-only mode).

## Install
```bash
git clone git@github.com:alexjeon5/claude-codex-orchestra.git && cd claude-codex-orchestra
./install.sh                  # asks how to behave without Codex
./install.sh --mode claude    # Claude-only, never touch Codex
./install.sh --no-rc          # don't start Remote Control
```
`install.sh` copies the skill + agents to `~/.claude`, the CLI to `/usr/local/bin` (or `~/.local/bin`),
then runs `orchestra setup`, which **starts Claude Remote Control** (tmux session `rc`) and **Codex Remote Control**
(`codex remote-control start`) and saves the default mode in `~/.config/orchestra/config.env`.

## Requirements
- Claude Code ≥ 2.1.294 (Sonnet 5.5 / Haiku 5.5, skill `effort`), logged in
- `tmux`, `git`, `python3`
- Optional: `codex` CLI, logged in (`codex login`) — needs access to `gpt-6.1-sol` and `gpt-6-astra` (override with `ORCH_CODEX_MODEL`; `gpt-6-astra` is only used when you opt in)

## Modes
| `ORCH_MODE` | Behaviour |
|---|---|
| `auto` (default) | Codex if installed + logged in, else Claude-only (the skill asks you first) |
| `codex` | require Codex, fail otherwise |
| `claude` | Claude-only |

Check with `orchestra mode`; change with `orchestra setup --no-rc --mode claude`.
Claude-only jobs are headless `claude -p`: not visible in Remote Control (use `tmux attach -t orch-<id>-r<N>` / logs).

## Commands
`orchestra init|run|diff|status|setup|mode` — `orchestra setup --help` for RC options.

## Options (env)
`ORCH_MODE`, `ORCH_CLAUDE_MODEL` (claude-sonnet-5-5), `ORCH_CLAUDE_EFFORT` (high), `ORCH_CODEX_MODEL`, `ORCH_CODEX_EFFORT`,
`ORCH_CODEX_ADVISOR` (off by default; `on` = gpt-6-astra, or a model name), `ORCH_CODEX_ADVISOR_EFFORT` (medium), `ORCH_CODEX_VERIFY` (1),
`ORCH_MAX_WORKERS` (6), `ORCH_TIMEOUT` (3600), `ORCH_NETWORK` (1), `ORCH_BACKEND` (auto|daemon|exec), `ORCH_GRACE` (600).

## Keep Claude Remote Control alive across reboots (optional)
Wrap `tmux new-session -d -s rc -c <dir> 'claude remote-control --name <name>'` in a systemd unit
(`Type=forking`, `Restart=on-failure`). Codex's daemon manages itself.

## Files
`bin/orchestra` · `lib/daemon_worker.py` · `claude/skills/orchestra/SKILL.md` · `claude/agents/orchestra-{scout,advisor}.md`
