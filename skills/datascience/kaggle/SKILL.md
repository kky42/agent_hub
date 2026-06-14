---
name: kaggle
description: Use when working on Kaggle competitions or maintaining reusable Kaggle methodology, including autonomous competition intake, submissions, dataset updates, public notebook/discussion research, validation design, leakage control, and private-LB discipline.
---

# kaggle

Reusable Kaggle operating skill.

Use this skill for Kaggle competition work and reusable Kaggle methodology.
Keep competition-specific facts, paths, commands, scores, deadlines, notebook
inventories, discussion findings, and host quirks in the active repo's docs or
refs, not in this skill.

## Autonomy

Once the user asks for a Kaggle workflow, operate end to end. Submissions and
dataset create/version actions are allowed when they are part of the requested
objective. Record source, command, timestamp, artifact path, and feedback for
any external Kaggle action.

After recording a leaderboard result, refresh the competition context and
verify no stale blockers remain before the next cycle. A completed submission
can be the current best while cached context still tells the next agent to
verify it.

## Core Kaggle Principles

- Optimize for private leaderboard performance; public LB is evidence, not
  truth.
- Start from official rules, metric, data, runtime, and submission contract.
- Build trustworthy validation before adding capacity.
- Label leakage risk for public notebooks, discussions, features, and artifacts.
- Prefer robust, reproducible candidates over brittle public-LB tuning.
- Record provenance for data, code, configs, seeds, artifacts, and submissions.

## Router

Open only the reference needed for the current operation.

CLI-only operations:

- Verify Kaggle access: `refs/cli/auth.md`
- List/download competition data: `refs/cli/data.md`
- Submit and check feedback: `refs/cli/submit.md`
- List/pull/publish notebook source/output: `refs/cli/notebooks.md`
- Create/version datasets: `refs/cli/datasets.md`
- Browse discussion topics/comments with official CLI support:
  `refs/cli/discussions.md`

Script-backed operations, only where the Kaggle CLI is insufficient:

- Local routine cache/search: `refs/scripts/cache.md`
- Competition page sections: `refs/scripts/comp_page.md`
- Notebook search snapshots: `refs/scripts/nb_list.md`
- Notebook version artifact download: `refs/scripts/nb_download.md`
- Discussion topic list/filter with preserved raw metadata:
  `refs/scripts/disc_list.md`
- Fetch a full discussion thread (opening post + nested comment tree with
  author names, votes, dates): `refs/scripts/disc_get.md`
- Notebook official/pinned flags: `refs/scripts/nb_flags.md`
- Notebook version/score updates: `refs/scripts/nb_versions.md`

Browser-backed operations (requires OpenCLI, see `refs/opencli-setup.md`):

- Fallback for any interactive task not supported by the CLI or scripts
  (post discussion topics, reply to comments, notebook comments, etc.):
  `refs/kaggle-interaction.md`

Long-running public source tracking must preserve author identities where
available: user id, user name, display name, profile URL, tier, and raw source
payload. Do this for notebooks, discussion topics, and comments so later
user-centric clue gathering can join across sources.

For ongoing competition work, prefer caching routine Kaggle evidence under the
active repo's `.kaggle-skill/cache/` directory and keep that path ignored by git.
Search the local cache first when the user asks for previously refreshed
competition brief, notebook, discussion, or submission information; refresh
manually when the user asks for current data.

For periodic public notebook/discussion syncs, use a delta-first workflow: fast
list snapshots, compare stable signatures, fetch details only for new/changed or
high-signal items, and summarize only those deltas. For large changed sets, split
items into batches and use read-only subagents rather than rereading everything
in the main context.

Methodology:

- General Kaggle principles: `refs/general/README.md`

## Update Boundary

Add to this skill only when the lesson is reusable across Kaggle competitions
and does not depend on one repo's scripts, file layout, model format, or
competition-specific metric details.

Examples that belong here:

- how to reason about public/private leaderboard mismatch
- how to design out-of-fold or group/time-aware validation
- how to evaluate public notebook claims
- how to record artifact provenance and prevent accidental leakage

Examples that belong in the repo:

- competition slug, task ids, paths, scripts, solver ids, submission ids
- exact package pins, host helper quirks, dated leaderboard observations
- downloaded notebook/discussion inventories
- local tool commands and workflow conventions

## Maintenance Rules

- Keep `SKILL.md` as the first-layer index and boundary contract.
- Use CLI docs for simple Kaggle CLI operations; do not add scripts for them.
- Add scripts only for scraping, comment extraction, official/pinned detection,
  or structured aggregation that the CLI cannot reliably do.
- Keep scripts independent and single-purpose.
- Add lessons to the narrowest existing reference file when possible.
- Add a new subfolder only for a reusable Kaggle methodology area that does not
  fit the current second-layer index.
- Replace repeated examples with one generalized rule.
- Move competition-specific or stale operational details into the active repo's
  docs, not this skill.
