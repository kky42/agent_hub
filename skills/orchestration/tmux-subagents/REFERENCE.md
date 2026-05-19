# Tmux Subagents Reference

This protocol is for an orchestrator agent that controls other CLI agents as
worker processes. Prefer structured non-interactive turns for machine
orchestration, and use tmux for long-lived interactive workers that need visual
monitoring or manual steering. Durable state lives in task prompts, worktrees,
files, diffs, tests, structured events, and explicit final markers.

## 1. Lifecycle

### Session Naming

Use predictable names:

```text
<project>-<agent>-<tag>-<task>
```

Examples:

```bash
agenthub-pi-map-skill-sync
agenthub-codex-impl-sync-flags
agenthub-claude-review-sync-flags
```

The name is only a tmux/orchestrator label. The subagent does not see it, and
it does not grant instructions or permissions. Keep tags short and descriptive:
`map`, `impl`, `review`, `debug`, `verify`.

### Permission Modes

Choose permissions for the concrete task before starting the worker. The helper
exposes three explicit modes:

```text
read-only: inspect files, logs, diffs, and command output; no edits
workspace-write: allow scoped edits in the assigned cwd or worktree
danger-full-access: no filesystem sandbox / permission bypass; isolated workers only
```

Permission and sandbox settings are process launch/resume parameters. Assume a
running worker cannot safely change its own authority. If permission level must
change while preserving context, stop the worker and resume the same agent
session with new flags, or start a new worker and pass a summary when resume is
not available.

Codex launch shapes:

```bash
# inspect or review
codex --no-alt-screen --sandbox read-only --ask-for-approval on-request

# scoped implementation in a worktree
codex --no-alt-screen --sandbox workspace-write --ask-for-approval on-request

# unsandboxed disposable worker, only in externally safe worktrees
codex --no-alt-screen --sandbox danger-full-access --ask-for-approval on-request
```

Claude Code launch shapes:

```bash
# read-only maps to planning mode when suitable
claude --permission-mode plan

# read-only-ish review with a narrow tool surface; confirm exact tool names locally
claude --tools Read --disallowedTools Edit,Write,MultiEdit,Bash

# workspace-write maps to edit acceptance, still use only in a scoped worktree
claude --permission-mode acceptEdits

# danger-full-access maps to permission bypass, isolated workers only
claude --permission-mode bypassPermissions
```

Avoid broad bypass modes unless the user explicitly asks and the worker is
isolated from important data.

Pi launch shapes:

```bash
# inspect or review
pi --sandbox read-only

# scoped implementation
pi --sandbox workspace-write

# unsandboxed disposable worker, isolated workers only
pi --sandbox danger-full-access
```

Pi's sandbox flag is supplied by the local sandbox extension, not Pi core. Check
`pi --help` for `--sandbox` before using it; otherwise restrict Pi with
`--tools read,grep,find,ls` for read-only work.

If a CLI version does not support a listed flag, fall back to the closest safer
mode and record the difference in the task ledger.

The local `anyagent` repo uses the same conceptual ladder. This skill names the
permissions directly:

```text
read-only: Codex/Pi --sandbox read-only; Claude --permission-mode plan
workspace-write: Codex/Pi --sandbox workspace-write; Claude --permission-mode acceptEdits
danger-full-access: Codex/Pi --sandbox danger-full-access; Claude --permission-mode bypassPermissions
```

Do not assume these are equivalent security boundaries across agents. Codex
and Pi expose sandbox modes. Claude exposes permission modes and tool controls,
so read-only review is better expressed with plan mode or a narrow tool surface.

For tmux subagents, prefer `danger-full-access` only for disposable or strongly
isolated workers after explicit user approval.

### Session IDs And Permission Changes

Prefer recording a session id for every worker. It lets the orchestrator
preserve context while changing launch permissions through resume.

Known resume shapes:

```bash
# Codex interactive resume with different sandbox
codex resume --no-alt-screen --sandbox workspace-write \
  --ask-for-approval on-request <session-id>

# Codex non-interactive resume, useful for structured capture
codex exec --json --sandbox workspace-write resume <session-id> '<prompt>'

# Claude interactive resume with different permission mode
claude --permission-mode acceptEdits --resume <session-id>

# Claude non-interactive resume, useful for structured capture
claude -p --output-format stream-json --resume <session-id> \
  --permission-mode acceptEdits '<prompt>'

# Pi interactive or non-interactive resume; json mode is JSONL events
pi --session <session-id> --sandbox workspace-write
pi -p --mode json --session <session-id> --sandbox workspace-write '<prompt>'
```

Session-id discovery differs:

```text
codex: JSON event `thread.started.thread_id`; persisted rollout filenames under ~/.codex/sessions also include ids.
claude: stream-json system init event includes `session_id`; interactive resume picker can also find recent sessions.
pi: JSON event `type=session` has `id`; persisted session filenames under ~/.pi/agent/sessions include ids.
```

Interactive panes may not show a clean session id, and the worker itself may
not be able to introspect it. The orchestrator should recover it from one of
these places instead:

1. Pane output after a `/status`-style command or an initial bootstrap reply.
2. Structured event output from a fresh turn.
3. Persisted session files under the agent's local session directory.

If a resumable permission change is likely, start the worker with a tiny
bootstrap turn that prints or records the session id, or run a structured
non-interactive probe first and then resume interactively by id.

### Start

Default to structured one-turn workers:

```bash
codex exec --json --sandbox read-only '<prompt>'
claude -p --output-format stream-json --permission-mode plan '<prompt>'
pi -p --mode json --sandbox read-only '<prompt>'
```

These commands emit event streams. Do not parse stdout as a single final JSON
object.

Use tmux for interactive workers when a human or orchestrator needs to watch
and steer the TUI:

Use default model and reasoning unless the user explicitly asks otherwise.

```bash
tmux new-session -d -s agenthub-pi-map -c "$PWD" 'pi --sandbox read-only'
tmux new-session -d -s agenthub-claude-review -c "$PWD" \
  'claude --permission-mode plan'
tmux new-session -d -s agenthub-codex-impl -c "$WORKTREE" \
  'codex --no-alt-screen --sandbox workspace-write --ask-for-approval on-request'
```

For edit workers, prefer an isolated worktree:

```bash
git worktree add ../agenthub-impl-sync -b worker/impl-sync
tmux new-session -d -s agenthub-codex-impl-sync \
  -c ../agenthub-impl-sync \
  'codex --no-alt-screen --sandbox workspace-write --ask-for-approval on-request'
```

### Track

Keep a small local run ledger in the orchestrator notes or a scratch file:

```text
task_id:
session:
agent:
cwd:
scope:
status:
permissions:
session_id:
started_at:
last_poll:
```

### Stop

Try graceful exit first when the worker is idle:

```bash
tmux send-keys -t <session> '/exit' Enter
tmux send-keys -t <session> C-d
```

Force cleanup when the session is no longer needed:

```bash
tmux kill-session -t <session>
```

Check leftovers:

```bash
tmux list-sessions
```

## 2. Status And Final Result

There is no universal reliable "done" signal across `codex`, `claude`, and
`pi`. Use an explicit protocol in the worker prompt and verify from outside.

### Helper Script

Use the skill-local helper to normalize the common operations:

```bash
node skills/orchestration/tmux-subagents/scripts/agent-worker.mjs run \
  --agent pi --sandbox read-only --cwd "$PWD" --prompt 'Reply exactly: OK'

node skills/orchestration/tmux-subagents/scripts/agent-worker.mjs run \
  --agent codex --sandbox read-only --model gpt-5.5 --reasoning low \
  --cwd "$PWD" --prompt 'Reply exactly: OK'

node skills/orchestration/tmux-subagents/scripts/agent-worker.mjs launch \
  --agent codex --sandbox read-only --name agenthub-codex-review --cwd "$PWD"

node skills/orchestration/tmux-subagents/scripts/agent-worker.mjs session \
  --agent codex --name agenthub-codex-review

node skills/orchestration/tmux-subagents/scripts/agent-worker.mjs capture \
  --name agenthub-codex-review --lines 200

node skills/orchestration/tmux-subagents/scripts/agent-worker.mjs close \
  --name agenthub-codex-review
```

`run` prints a normalized JSON object:

```json
{
  "agent": "pi",
  "sandbox": "read-only",
  "sessionId": "...",
  "done": true,
  "ok": true,
  "errors": [],
  "stderr": [],
  "finalText": "OK",
  "eventTypes": ["session", "message_end", "turn_end", "agent_end"]
}
```

The helper intentionally lives inside this skill, not repo-root `scripts/`, so
it does not expand the repository's user-facing script surface.

### Structured Event Extraction

For non-interactive workers, parse one JSON event per stdout line and ignore
noise. The local `anyagent` repo uses this shape:

```text
codex exec --json:
  session id: event type `thread.started`, field `thread_id`
  final text: `item.completed` where `item.type == agent_message`, field `item.text`
  done: `turn.completed`
  error: `turn.failed` or `error`

claude -p --output-format stream-json:
  session id: `system` event with `subtype == init`, field `session_id`
  final text: `assistant.message.content[]` text blocks
  done: `result`
  error: `result.is_error` or `error`

pi -p --mode json:
  session id: `session` event, field `id`
  final text: assistant `message_end` event, concatenate content text blocks
  done: `turn_end` or `agent_end`
  error: assistant `message_end.message.stopReason == error`,
         `compaction_end.errorMessage`, or failed `auto_retry_end`
```

Pi `--mode json` is especially chatty: it can include `message_update` deltas,
thinking blocks, retries, compaction events, tool events, and final agent
state. Extract the assistant answer from `message_end`, not from partial
updates.

### Send A Task

Use clear boundaries and a final marker:

```bash
tmux send-keys -t agenthub-pi-map \
  'TASK map-001: Read-only. Find where skill-sync discovers private skills. Do not edit. End with STATUS/SUMMARY/CHANGED_FILES/TESTS/NEXT.' \
  Enter
```

For multi-line prompts, paste bracketed text or send from a temp file through
terminal paste mode if the CLI supports it. Keep prompts short enough that
terminal quoting cannot corrupt them.

### Poll

Capture recent pane text:

```bash
tmux capture-pane -pt <session> -S -300
```

Useful poll states:

```text
running: output is changing, spinner/thinking text visible, command executing
idle: prompt/input line visible and no recent output changes
blocked: approval prompt, login prompt, trust prompt, error prompt, or question
done: final STATUS marker appears
failed: final STATUS failed or process exited unexpectedly
unknown: pane text cannot distinguish running from idle
```

Quiet output is not completion. The worker is complete only when one of these is
true:

- final `STATUS:` marker appears
- session process exits after a one-shot task
- worker-created status file says done and the orchestrator verifies it

### Better Than Pane Scraping

For long tasks, ask the worker to write a status file in its worktree or scratch
dir:

```text
.agent-tasks/<task-id>/status.md
```

Required content:

```text
STATUS: running|done|blocked|failed
UPDATED_AT: <timestamp>
SUMMARY: <current state>
CHANGED_FILES: <paths or none>
TESTS: <commands or none>
NEEDS: <question/approval or none>
```

Then poll both:

```bash
tmux capture-pane -pt <session> -S -120
cat .agent-tasks/<task-id>/status.md
git -C <worker-cwd> status --short
```

## 3. Steering

Steering changes instructions. It does not change the worker process
permissions. Permission changes require stop/relaunch or resume.

### While Idle

Send a normal follow-up:

```bash
tmux send-keys -t <session> \
  'Update TASK tmux-001: narrow the search to scripts only. Keep read-only. End with STATUS marker.' \
  Enter
```

Use this for:

- clarifying requirements
- adding constraints
- asking for final answer again
- asking for a smaller scope
- requesting tests or review after an implementation

Do not use this to grant broader filesystem or shell authority.

### While Running

Only interrupt when the current run is obsolete, dangerous, or blocking other
work. First capture the current pane and note why the interruption is needed.

Common interrupt keys:

```bash
tmux send-keys -t <session> Escape
tmux send-keys -t <session> C-c
```

Then send the replacement instruction:

```bash
tmux send-keys -t <session> \
  'INTERRUPT: Stop the prior task. New goal: only inspect README.md and report inconsistencies. Do not edit.' \
  Enter
```

For agents with different interrupt semantics, prefer the agent's visible UI
hint if known. For example, Pi advertises `escape interrupt`; terminal CLIs
commonly treat `Ctrl-C` as interrupt/exit depending on state.

### Abort And Replace

Use when a worker is wedged, has wrong context, or is editing the wrong scope:

```bash
tmux capture-pane -pt <session> -S -200
tmux kill-session -t <session>
tmux new-session -d -s <new-session> -c <correct-cwd> '<agent command>'
```

If the worker had an edit worktree, inspect before reusing:

```bash
git -C <worker-cwd> status --short
git -C <worker-cwd> diff --stat
```

Do not delete worktrees or reset changes unless the user explicitly asks or the
orchestrator owns that scratch worktree and has recorded that it is disposable.

### Relaunch With Different Permissions

Use this when a read-only diagnosis found a scoped edit to make:

```bash
# 1. Capture current state and session id.
tmux capture-pane -pt <session> -S -200

# 2. Stop the old worker if it is idle, or interrupt/kill it if obsolete.
tmux send-keys -t <session> C-d

# 3. Resume in a new tmux session with the stronger mode.
tmux new-session -d -s <new-session> -c <worker-cwd> \
  'codex resume --no-alt-screen --sandbox workspace-write --ask-for-approval on-request <session-id>'
```

For Claude and Pi:

```bash
tmux new-session -d -s <new-session> -c <worker-cwd> \
  'claude --permission-mode acceptEdits --resume <session-id>'

tmux new-session -d -s <new-session> -c <worker-cwd> \
  'pi --session <session-id> --sandbox workspace-write'
```

If no session id is available, start a fresh worker and include the captured
summary plus files/status it should inspect.

## 4. Use Case Patterns

### Read-Only Mapping

Best worker: cheap/fast agent.

Prompt:

```text
TASK map-001. Read-only. Find the files that implement third-party skill
sync. Report paths and short responsibilities. Do not edit. End with STATUS.
```

Verify:

```bash
tmux capture-pane -pt <session> -S -300
```

### Implementation Worker

Best worker: strong coding agent in a separate worktree.

Prompt:

```text
TASK impl-001. Implement <change>. You own only scripts/skill-sync and tests
under tests/skill-sync. Do not commit. Run relevant tests. End with STATUS and
changed files.
```

Verify:

```bash
git -C <worker-cwd> diff --stat
git -C <worker-cwd> diff
```

### Review Worker

Best worker: different agent from implementer.

Prompt:

```text
TASK review-001. Review the diff in <path>. Findings first, with file/line
references. Do not edit. End with STATUS.
```

Verify by checking the referenced files yourself.

### Long Diagnosis

Best worker: persistent session with a status file.

Prompt:

```text
TASK diagnose-001. Reproduce the failure, minimize it, instrument if needed,
then propose a fix. Keep .agent-tasks/diagnose-001/status.md updated. Ask before
editing outside <scope>. End with STATUS.
```

Poll status file and pane output. Interrupt only if the diagnosis path becomes
irrelevant.

### Parallel Work

Split only when scopes are independent:

```text
worker A: read-only architecture map
worker B: implementation in worktree B, owns files X/Y
worker C: review of existing diff, read-only
```

Never assign two edit workers the same files unless explicitly experimenting
with alternatives in separate worktrees.

## 5. Agent Notes

### Codex

Use `codex --no-alt-screen` for tmux orchestration. It preserves more useful
scrollback for `capture-pane` and does not change model or reasoning.

### Claude

Plain `claude` starts interactive mode. First run in a repo may ask for
workspace trust. Claude also has native worktree/tmux options, but external
tmux sessions are sufficient for cross-agent orchestration.

### Pi

Plain `pi` starts interactive mode. It exposes startup context and loaded
skills/extensions clearly. If key handling is awkward in tmux, configure:

```bash
set -g extended-keys-format csi-u
```

## 6. Safety Rules

- Do not delegate secrets, credentials, or destructive operations unless the
  user explicitly asked.
- Do not let workers auto-commit by default.
- Prefer read-only tasks for shared working trees.
- Use worktrees for editing workers.
- Trust final prose only after verifying files, diffs, tests, and logs.
- If workers disagree, use the disagreement as input; the orchestrator decides.
