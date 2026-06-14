# Discussions

Use the Kaggle CLI directly for ordinary discussion *browsing* (listing topics,
a quick look at a thread). To **fetch a full discussion** — all content plus the
complete comment tree with reply nesting and author names — use
`scripts/disc_get.py` (see `refs/scripts/disc_get.md`); no single CLI command
returns all three together.

Competition topics:

```bash
kaggle competitions topics list SLUG --page 1 --csv
kaggle competitions topics show SLUG TOPIC_ID
kaggle competitions topic-messages SLUG TOPIC_ID --sort-by top --page-size -1 --csv
```

CLI trade-offs for reading a single thread:

- `topics show` renders a nested reply tree with author names, but **truncates**
  long comment bodies to a preview.
- `topic-messages --page-size -1 --csv` returns **full untruncated** bodies and
  votes for every message (replies included), but the rows are **flat** (no
  reply/parent column) and the `authorName` column comes back empty.
- `scripts/disc_get.py` returns full bodies **and** the reply nesting **and**
  author names in one artifact (authenticated discussions API). Prefer it when
  the task is to fetch/archive a discussion rather than just glance at it.

General forum topics:

```bash
kaggle forums list --csv
kaggle forums topics list getting-started --sort-by hot --page-size 20 --csv
kaggle forums topics show getting-started TOPIC_ID
```

Dataset topics:

```bash
kaggle datasets topics list OWNER/DATASET --sort-by recent --page-size 20 --csv
kaggle datasets topics show OWNER/DATASET TOPIC_ID
```

Model and benchmark topic commands follow the same `topics list/show` shape.

Use `scripts/disc_list.py` for a topic list with pinned/official flags,
preserved raw payloads, and durable author identity fields. Use
`scripts/disc_get.py` to fetch a single thread in full (nested comments + author
names) as a stable JSON/MD artifact for cache/search.

Use OpenCLI browser fallback only for write operations or UI-only actions such
as posting topics, replying, editing, voting, bookmarking, or notebook comments.
