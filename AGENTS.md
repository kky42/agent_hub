# AGENTS

This repo manages global agent skills for this user's machines.

`README.md` is for humans. Keep it short and friendly. This file is for agents
operating in the repo. Put execution rules here.

## Core Model

- `skills/` is the source of truth for self-created private skills.
- `thirdparty-skills.yml` is the desired state for third-party global skills.
- Agent runtime skill folders are generated links/installs, not source of truth.
- Codex uses `~/.agents/skills`; Pi can also read `~/.agents/skills`.
- Claude Code reads `~/.claude/skills`.
- Pi's native `npx skills` target is `~/.pi/agent/skills`, but this repo avoids
  that target by default to prevent duplicate Pi loading.

Private skills are linked as flat top-level folders into runtime folders:

```text
./skills/**/<skill>/SKILL.md -> ~/.agents/skills/<skill>
./skills/**/<skill>/SKILL.md -> ~/.claude/skills/<skill>
```

The private skill target roots come from `AGENT_HUB_SKILL_TARGETS`, defaulting
to `~/.agents/skills:~/.claude/skills`.

Third-party skills are installed with `npx skills`. Use the default symlink
behavior unless the user explicitly asks for `copy: true`.
`thirdparty-skills.yml` is the complete desired state for npx-managed global
skills. Skills installed with `npx skills` but not listed there are stale and
may be removed by `./scripts/skill-sync`.

## Scripts

Use only these user-facing scripts in docs and commands:

```bash
./scripts/skill-migrate
./scripts/skill-sync
```

Do not add helper wrappers such as `bootstrap`, `apply-thirdparty`,
`skills-bootstrap`, or `skills-apply-thirdparty` unless the user explicitly asks
for a larger script surface.

## Scenarios

### Set Up Or Refresh This Machine

Run:

```bash
./scripts/skill-sync
```

This is intended to be idempotent. It refreshes private-skill symlinks, removes
stale agent_hub-owned private symlinks, and applies the third-party manifest.

On an existing machine with third-party skills installed before `agent_hub`,
run migration before the first full apply:

```bash
./scripts/skill-migrate
```

If `thirdparty-skills.yml` is empty but `npx skills` has global skills in its
lock file, `skill-sync` stops instead of deleting everything. Only
set `AGENT_HUB_CONFIRM_EMPTY_THIRDPARTY=1` when the user explicitly wants no
npx-managed global skills.

For personal/private skill changes only, run:

```bash
./scripts/skill-sync --personal-only
```

This links private skills and skips the slower third-party `npx skills` phase.

### Add A Private Skill

1. Create a directory under `skills/`.
2. Add `SKILL.md`.
3. Ensure the `SKILL.md` frontmatter `name` exactly matches the skill directory
   name.
4. Run `./scripts/skill-sync`.
5. If behavior changed materially, update `README.md` only if the user-facing
   quick start needs to change.

Do not edit private skills through agent runtime folders. `skills/` is the
source of truth, and the runtime entries are symlinks back into this repo.
Because they are symlinks, edits to active skills under `skills/` are visible to
agents immediately. Keep draft skills outside `skills/`, or omit `SKILL.md`,
until they should become active.

### Update Or Remove A Private Skill

Edit, move, or delete the skill under `skills/`.

Run:

```bash
./scripts/skill-sync
```

Runtime symlinks are refreshed from `skills/`. Stale symlinks pointing into this
repo are removed. Real folders and unmanaged symlinks are not removed.

### Add A Third-Party Skill

1. Discover exact upstream skill names with:

   ```bash
   npx skills add <source> --list
   ```

2. Add an entry to `thirdparty-skills.yml`:

   ```yaml
   skills:
     - skill: example-skill
       source: owner/repo
       agents:
         - codex
         - claude-code
   ```

3. Run:

   ```bash
   ./scripts/skill-sync
   ```

Use `skill` as the real skill name. Do not invent a separate local name.

### Remove A Third-Party Skill

Remove its entry from `thirdparty-skills.yml`, then run:

```bash
./scripts/skill-sync
```

The script removes stale npx-managed global skills by comparing
`thirdparty-skills.yml` with `npx skills`' global lock file.

### Sync Another Computer

After cloning or pulling this repo, run:

```bash
./scripts/skill-sync
```

This applies private skill symlinks and the third-party manifest to that
machine.

## Third-Party Policy

- Prefer `npx skills` default symlink behavior.
- Use `copy: true` only when the user explicitly wants copied third-party
  installs.
- Prefer `codex` and `claude-code` in this repo. `codex` covers
  `~/.agents/skills`, which Pi can also load here; adding `pi` creates a second
  install under `~/.pi/agent/skills`.
- Do not edit third-party installed skill folders directly.
- Do not vendor third-party skill source into `skills/`.
- Treat `thirdparty-skills.yml` as the complete desired state.
- Treat `npx skills` as the installer/updater for third-party skill content.
- If an upstream third-party skill is removed but still listed in
  `thirdparty-skills.yml`, `skill-sync` should warn, continue through the rest
  of the manifest, and print a failure summary at the end.
- `AGENT_HUB_THIRDPARTY_SYNC_SLEEP_SECONDS` controls the pause between
  third-party installs. The default is `5` seconds to reduce GitHub rate-limit
  pressure during repeated syncs.
- Before switching an existing machine to this repo, run
  `./scripts/skill-migrate` to import existing npx-managed skills.

## Validation

After changing scripts or manifests, run:

```bash
bash -n scripts/skill-migrate scripts/skill-sync
```

If adding private skills, also inspect that each skill has a valid `SKILL.md`.
