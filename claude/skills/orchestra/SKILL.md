---
name: orchestra
description: Pipeline - Sonnet 5.5 leads, Haiku 5.5 scouts explore, Opus advises at 3 checkpoints, 3 parallel Codex workers code in the same folder, Codex verifies, then Claude checks. Use when the user runs /orchestra or asks to work "with Codex" ("Codex랑 같이", "오케스트라로").
argument-hint: <만들 기능/작업 설명>
model: claude-sonnet-5-5
effort: high
---

# Orchestra

Request: $ARGUMENTS

Roles: you (Sonnet 5.5) lead and decide. `orchestra-scout` (Haiku 5.5) explores. `orchestra-advisor` (Opus) is on call ONLY at checkpoints A/B/C. Codex writes the code (gpt-6.1-sol) and verifies it first; Claude checks last. A read-only `gpt-6-astra` Codex advisor on top of the verifier is OPT-IN: only when the user explicitly asks for astra / a stronger Codex review.
CLI: `orchestra init|run|diff|status`. Talk to the user in Korean (반말).
Context budget: keep your own context lean. Delegate exploration to scouts. Read only the files you must reason about. Never call the advisor outside A/B/C.

## 0. Setup
- Target = cwd unless the user names another dir. It must be a git repo. If it isn't, ask before running `git init`.
- Run `orchestra mode`. It prints `mode: codex` or `mode: claude`, plus the reason.
  - `codex`: the normal pipeline below.
  - `claude` (Codex missing, not logged in, or `ORCH_MODE=claude`): Claude-only pipeline. If the reason says it fell back (not an explicit choice), tell the user and ask with `AskUserQuestion`: "Claude만으로 진행" / "취소" (the user may instead install/login Codex: `codex login`). Explicit `ORCH_MODE=claude`: just tell the user, no question.
  - In Claude-only mode the workers and the verifier are `claude -p` runs (model `ORCH_CLAUDE_MODEL`, default claude-sonnet-5-5) instead of Codex; phase 3 (Codex advisor) is skipped. Everything else (scouts, plan, Opus checkpoints, user approval, fix rounds) is unchanged. The verifier's report is still `r<N>/codex-verify.md` (its title says "Claude verification").
- Run `orchestra init <dir>`. It prints RUN (`<repo>/.orchestra/<id>`) and snapshots the tree. Diffs are taken against this snapshot.

## 1. Explore (Haiku 5.5 swarm)
- Launch 2–4 `orchestra-scout` agents in parallel, in ONE message, each with one focused question. For example: where X lives and its interfaces; test/build commands and conventions; callers of Y; external API/library docs for Z.
- Use their summaries. Open files yourself only to settle specific doubts.

## 2. Plan (you)
- Split the work into exactly 3 Codex tasks (fewer if 3 would be forced; tell the user). Each task file = one Codex worker.
- The workers edit the same folder concurrently, so:
  - Owned files never overlap between tasks. Each shared touchpoint (router, index exports, package.json, ...) belongs to exactly one task.
  - Write every cross-task contract (signatures, schemas, types, paths) into "Shared interfaces" in plan.md.
- Write these files in English, concrete and unambiguous:
  - `RUN/plan.md`: goal, context, shared interfaces, invariants that must not break, task split, **acceptance criteria** (a checkable list with exact commands), out of scope.
  - `RUN/r1/task-{1..3}.md`: title, goal, **Owned files** (marked new/modify), implementation details, read-only references, self-check commands, done criteria.

## 3. Checkpoint A: advisor plan-review
- Call `orchestra-advisor` with: `mode: plan-review, RUN=<path>`, plus a 3-line summary of the risks you're unsure about.
- If it says REVISE, apply the edits you agree with. If you reject one, note why in your summary to the user.

## 4. Approval (user)
- Show a short summary: goal, one line per task plus its owned files, acceptance criteria, the advisor's verdict, and file paths.
- Ask with `AskUserQuestion`. Options: "승인하고 Codex 실행" / "수정 필요" / "취소". On 수정 필요, revise (re-run A only if the change is structural), then ask again. Never run Codex without approval.

## 5. Codex build + Codex verify
- Run `orchestra run <RUN> <round>` via Bash with `run_in_background: true`. You get a notification when it exits. Don't poll.
  - Phase 1: the workers run in parallel.
  - Phase 2: one Codex verifier reviews the combined result, runs the build/tests/acceptance commands, may fix small integration glue, and writes `r<N>/codex-verify.md`.
  - Phase 3 (OPT-IN, off by default): a read-only Codex advisor (`gpt-6-astra`) reviews the verifier's work and writes `r<N>/codex-advice.md` (AGREE | CONCERNS). Enable it ONLY if the user explicitly asked for astra / an extra Codex advisor review, by running `ORCH_CODEX_ADVISOR=on orchestra run …` (or `ORCH_CODEX_ADVISOR=<model>`). Never enable it on your own.
- (Claude-only mode: jobs are headless `claude -p`, NOT visible in Remote Control. Watch via tmux `orch-<id>-r<N>` and `RUN/r<N>/logs/`; stderr is in `*.err`. Skip the Remote Control notes below.)
- Default backend is the Codex daemon. Jobs show in Codex Remote Control as `[orch <repo> r<N>] task-N: …` and `[orch <repo> r<N>] verify`. If the run fell back to exec (see the first line `backend:`), they aren't visible there. Tell the user where to watch: the Remote Control names, the tmux session `orch-<id>-r<N>`, and `RUN/r<N>/logs/`.
- The user may interrupt or steer jobs from the Codex app. An interrupted job waits `ORCH_GRACE` (600s) for a follow-up, else exits 130.
- Exit codes: 0 ok, 1 failed, 2 daemon error, 124 timeout, 130 interrupted.

## 6. Claude check (you)
- Read `codex-verify.md`, `codex-advice.md` (only exists if phase 3 ran), and the diff stat. Treat advisor CONCERNS as leads to check, not verdicts.
- Re-run the acceptance-criteria commands yourself and compare the results with Codex's claims. Look at the diff for any file Codex reported fixing.
- If the results clearly FAIL, skip C and go to step 8. If they look PASS, continue to C.

## 7. Checkpoint C: advisor final-review
- Call `orchestra-advisor` with: `mode: final-review, RUN=<path>, round=<N>`, your step-6 command results, any worker failures, and the Codex advisor verdict if phase 3 ran (`r<N>/codex-advice.md`).
- It writes `RUN/r<N>/verify.md` with the final verdict.
- Report to the user: verdict, acceptance criteria results, the main issues, where Codex, the Codex advisor, and Claude disagreed, changed files, and report paths.

## 8. Fix rounds (on FAIL)
- Checkpoint B: if the same acceptance criterion or issue failed in two consecutive rounds, call `orchestra-advisor` with `mode: stuck, RUN=<path>, round=<N>` and the failing output BEFORE you write the next tasks. Follow its root-cause call, or stop and ask the user if it says so.
- Write `RUN/r<N+1>/task-*.md` (1–3 tasks, owned files still not overlapping). Get approval as in step 4, then repeat steps 5–7.
- At most 2 fix rounds (up to r3). If it still fails, hand the remaining issues to the user.

## Finish
- Don't commit. Leave the changes in the working tree.
- Final report: verdict, changed files, remaining issues, RUN path.
