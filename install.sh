#!/usr/bin/env bash
# Install orchestra (Claude skill + agents + CLI), enable Remote Control, pick the Codex/Claude-only mode.
#
#   ./install.sh [--mode auto|codex|claude] [--no-rc] [--no-claude-rc] [--no-codex-rc]
#                [--prefix DIR] [--claude-dir DIR] [--name NAME] [--dir DIR] [-y]
#
# --mode  auto   (default) Codex if installed and logged in, otherwise Claude-only
#         codex  require Codex (fail if missing)
#         claude never use Codex; workers/verifier are `claude -p`
# --prefix  where bin/ and lib/ go (default /usr/local, or ~/.local if not writable)
set -euo pipefail
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
mode="" prefix="" claude_dir=${CLAUDE_CONFIG_DIR:-$HOME/.claude} yes=0 setup_args=()
while (($#)); do
  case $1 in
    --mode) mode=${2:?}; shift ;;
    --prefix) prefix=${2:?}; shift ;;
    --claude-dir) claude_dir=${2:?}; shift ;;
    --no-rc | --no-claude-rc | --no-codex-rc) setup_args+=("$1") ;;
    --name | --dir) setup_args+=("$1" "${2:?}"); shift ;;
    -y | --yes) yes=1 ;;
    -h | --help) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

say() { printf '==> %s\n' "$*"; }
missing=()
for c in git tmux python3; do command -v "$c" >/dev/null || missing+=("$c"); done
((${#missing[@]} == 0)) || { echo "missing required tools: ${missing[*]}" >&2; exit 1; }
command -v claude >/dev/null || { echo "claude (Claude Code) is required: https://claude.com/claude-code" >&2; exit 1; }
cv=$(claude --version 2>/dev/null | awk '{print $1}')
say "claude $cv"
if [[ $(printf '%s\n2.1.294\n' "$cv" | sort -V | head -1) != 2.1.294 ]]; then
  echo "    warning: Claude Code < 2.1.294 doesn't know Sonnet 5.5 / Haiku 5.5 (run: claude update)" >&2
fi

codex_ok=0
if command -v codex >/dev/null && codex login status >/dev/null 2>&1; then codex_ok=1; say "codex available"
elif command -v codex >/dev/null; then say "codex installed but not logged in (codex login)"
else say "codex not installed"; fi

if [[ -z $mode ]]; then
  if [[ -t 0 && $yes == 0 ]]; then
    cat <<MENU

How should orchestra work when Codex is not available?
  1) auto   - use Codex when available, otherwise Claude-only   [default]
  2) codex  - always require Codex
  3) claude - never use Codex (Claude-only)
MENU
    read -r -p "Choose [1-3]: " ans
    case ${ans:-1} in 2) mode=codex ;; 3) mode=claude ;; *) mode=auto ;; esac
  else
    mode=auto
  fi
fi
if [[ $mode == codex && $codex_ok == 0 ]]; then echo "mode=codex but Codex isn't ready; install/login first or use --mode auto" >&2; exit 1; fi

if [[ -z $prefix ]]; then
  if [[ -w /usr/local/bin && -w /usr/local ]] || [[ $(id -u) == 0 ]]; then prefix=/usr/local; else prefix=$HOME/.local; fi
fi
say "installing to $prefix and $claude_dir"
mkdir -p "$prefix/bin" "$prefix/lib/orchestra" "$claude_dir/skills/orchestra" "$claude_dir/agents"
install -m 0755 "$here/lib/daemon_worker.py" "$prefix/lib/orchestra/daemon_worker.py"
install -m 0755 "$here/bin/orchestra" "$prefix/bin/orchestra"
sed -i "s|:-/usr/local/lib/orchestra/daemon_worker.py|:-$prefix/lib/orchestra/daemon_worker.py|" "$prefix/bin/orchestra"
install -m 0644 "$here/claude/skills/orchestra/SKILL.md" "$claude_dir/skills/orchestra/SKILL.md"
install -m 0644 "$here"/claude/agents/*.md "$claude_dir/agents/"
case ":$PATH:" in *":$prefix/bin:"*) ;; *) echo "    note: add $prefix/bin to PATH (the /orchestra skill calls 'orchestra')" ;; esac

say "setup (Remote Control + mode)"
"$prefix/bin/orchestra" setup --mode "$mode" ${setup_args[@]+"${setup_args[@]}"}
say "done. In any project (git repo): /orchestra <task>"
