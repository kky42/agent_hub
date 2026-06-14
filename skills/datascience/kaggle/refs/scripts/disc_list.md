# `disc_list.py`

List competition discussion topics with metadata that the Kaggle CLI may omit.
Use `refs/cli/discussions.md` first for ordinary discussion browsing.

```bash
python3 .agents/skills/datascience/kaggle/scripts/disc_list.py \
  --competition SLUG \
  --sort votes \
  --limit 20 \
  --format json \
  --out PATH
```

Supported sorts: `recent`, `votes`, `comments`, `hot`.

The script writes `schema_version`, topic URL/id, title, author, `author_identity`
with user id/user name/profile URL when visible, votes, comments, last activity,
official flag, pinned flag, raw topic payload, and `fetched_at`.

For periodic syncs, compare topic signatures first and fetch/summarize only new
or updated threads. Preserve one canonical Markdown file per topic id; refreshed
slugs can otherwise create duplicate local files for the same discussion.
