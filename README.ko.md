# orchestra

[English](README.md) · **한국어**

Claude가 계획하고, Codex가 구현·검증하고, Claude가 최종 확인하는 파이프라인입니다. 명령은 `/orchestra <작업>` 하나입니다.

```
Haiku 탐색 → Sonnet 계획 → Opus 계획 검토 → 사용자 승인
  → Codex ×N 구현(N은 Claude가 판단, 병렬, 같은 폴더) → Codex 검증 → (선택: Codex advisor, astra)
  → Sonnet 재확인 → Opus 최종 검토
```
Codex가 없으면 worker와 verifier가 `claude -p`로 대체됩니다(Claude-only 모드).

## 설치
```bash
git clone git@github.com:alexjeon5/claude-codex-orchestra.git && cd claude-codex-orchestra
./install.sh                  # Codex가 없을 때의 동작을 묻습니다
./install.sh --mode claude    # Claude-only, Codex는 쓰지 않음
./install.sh --no-rc          # Remote Control을 켜지 않음
```
`install.sh`는 skill과 agent를 `~/.claude`에, CLI를 `/usr/local/bin`(쓰기 불가면 `~/.local/bin`)에 복사한 뒤
`orchestra setup`을 실행합니다. `orchestra setup`은 **Claude Remote Control**(tmux 세션 `rc`)과
**Codex Remote Control**(`codex remote-control start`)을 켜고, 기본 모드를 `~/.config/orchestra/config.env`에 저장합니다.
이미 켜져 있으면 건너뜁니다. Claude Remote Control이 처음 뜰 때 로그인이나 trust 확인이 나오면 `tmux attach -t rc`로 한 번 답해야 합니다.

## 요구 사항
- Claude Code 2.1.294 이상(Sonnet 5.5 / Haiku 5.5, skill `effort` 지원), 로그인 상태
- `tmux`, `git`, `python3`
- 선택: `codex` CLI와 로그인(`codex login`). `gpt-6.1-sol`, `gpt-6-astra`를 쓸 수 있어야 하며 기본은 `gpt-6.1-sol` / `medium`이며 `~/.codex/config.toml`과 무관하게 고정됩니다. `ORCH_CODEX_MODEL`, `ORCH_CODEX_EFFORT`로 바꿀 수 있습니다. `gpt-6-astra`는 직접 켰을 때만 쓰입니다.

## 모드
| `ORCH_MODE` | 동작 |
|---|---|
| `auto` (기본) | Codex가 설치되어 있고 로그인돼 있으면 Codex, 아니면 Claude-only (skill이 먼저 묻습니다) |
| `codex` | Codex 필수, 없으면 실패 |
| `claude` | Claude-only |

`orchestra mode`로 확인하고, `orchestra setup --no-rc --mode claude`처럼 기본값을 바꿉니다.
Claude-only 작업은 헤드리스 `claude -p`라 Remote Control에는 보이지 않습니다(`tmux attach -t orch-<id>-r<N>`이나 로그로 확인).

## 명령
`orchestra init|run|diff|status|setup|mode`. Remote Control 옵션은 `orchestra setup --help`를 참고하세요.

## 옵션 (환경변수)
`ORCH_MODE`, `ORCH_CLAUDE_MODEL`(claude-sonnet-5-5), `ORCH_CLAUDE_EFFORT`(high), `ORCH_CODEX_MODEL`(gpt-6.1-sol), `ORCH_CODEX_EFFORT`(medium),
`ORCH_CODEX_ADVISOR`(기본 꺼짐, `on`이면 gpt-6-astra, 모델명도 가능), `ORCH_CODEX_ADVISOR_EFFORT`(medium), `ORCH_CODEX_VERIFY`(1),
`ORCH_MAX_WORKERS`(6), `ORCH_TIMEOUT`(3600), `ORCH_NETWORK`(1), `ORCH_BACKEND`(auto|daemon|exec), `ORCH_GRACE`(600).

## 재부팅 후에도 Claude Remote Control 유지(선택)
`tmux new-session -d -s rc -c <dir> 'claude remote-control --name <name>'`을 systemd unit(`Type=forking`, `Restart=on-failure`)으로 감싸세요.
Codex daemon은 스스로 관리됩니다.

## 파일
`bin/orchestra` · `lib/daemon_worker.py` · `claude/skills/orchestra/SKILL.md` · `claude/agents/orchestra-{scout,advisor}.md`
