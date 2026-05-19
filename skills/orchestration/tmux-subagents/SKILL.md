---
name: tmux-subagents
description: Orchestrate long-lived CLI coding agents through tmux as worker sessions with explicit lifecycle, status, steering, and verification rules. Use when delegating work to other installed CLI agents such as codex, claude, or pi through tmux, especially for parallel exploration, implementation, review, or cheap-model tasks.
---

# Tmux Subagents

Use CLI agents as worker processes with explicit lifecycle, permissions, and
result parsing. Use tmux only when interactive steering is useful.

## Default Mode

Prefer structured turns for automation and long-lived interactive workers when
a human needs to watch or steer. Pick the permission mode before launch:

```bash
# structured one-turn workers
codex exec --json --sandbox read-only '<prompt>'
claude -p --output-format stream-json --permission-mode plan '<prompt>'
pi -p --mode json --sandbox read-only '<prompt>'

# interactive worker when visual steering is useful
tmux new-session -d -s worker-codex -c "$PWD" \
  'codex --no-alt-screen --sandbox read-only --ask-for-approval on-request'
```

Structured outputs are event streams, not clean final JSON objects. Parse
session ids, assistant messages, errors, and terminal events explicitly.

Use [scripts/agent-worker.mjs](scripts/agent-worker.mjs) for normalized runs,
tmux launch/capture/session display, cleanup, and requested model overrides.

## Permission Modes

This skill does not provide built-in role prompts. The orchestrator writes the
task prompt and passes one explicit mode to the helper:

- `read-only`: inspect files, logs, and diffs; no edits.
- `workspace-write`: allow scoped edits in the assigned cwd or worktree.
- `danger-full-access`: no filesystem sandbox / permission bypass; only use in
  isolated disposable worktrees after explicit user intent.

The helper maps those modes to native flags: Codex/Pi use `--sandbox`; Claude
uses `--permission-mode plan|acceptEdits|bypassPermissions`.

Permission and sandbox flags are launch/resume parameters. Do not assume they
can be changed safely inside a running worker. To change permissions while
preserving context, stop the worker and relaunch a resumed session id when the
CLI supports it:

```bash
codex resume --no-alt-screen --sandbox workspace-write <session-id>
claude --resume <session-id> --permission-mode acceptEdits
pi --session <session-id> --sandbox workspace-write
```

## Worker Contract

Every delegated task must include:

- task id and objective
- allowed working directory and edit boundaries
- expected output format
- stop condition
- required final marker:

```text
STATUS: done|blocked|failed
SUMMARY: <one paragraph>
CHANGED_FILES: <paths or none>
TESTS: <commands run or not run>
NEXT: <needed follow-up or none>
```

For Claude read-only workers, prefer `--permission-mode plan` or a narrow tool
set rather than auto-accepting edits. See [REFERENCE.md](REFERENCE.md) for
lifecycle, polling, steering, and abort procedures.

## Use Cases

- Exploration: ask a cheap/fast worker to map files, summarize modules, or find
  risks. Keep this read-only.
- Implementation: create a separate git worktree and assign a narrow write set.
- Review: ask a different worker to inspect a diff for bugs and missing tests.

## Orchestrator Rules

1. Start workers with stable tmux session names and record their task ids.
2. Record the CLI session id when the agent exposes one; it may allow resume
   with a different permission mode after restart.
3. Send structured prompts as CLI args; use `tmux send-keys` for TUI workers.
4. Poll for the final `STATUS:` marker, not just a quiet pane.
5. To change permission level, stop/relaunch or resume; do not mutate a live
   worker.
6. If a worker is drifting, send a steering message when idle; interrupt first
   only when it is actively running and the new goal supersedes the old one.
7. Verify worker results locally before integrating.
8. Kill temporary sessions when no longer needed.
