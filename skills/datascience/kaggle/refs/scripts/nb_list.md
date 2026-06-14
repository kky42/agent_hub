# `nb_list.py`

List Kaggle notebooks with stable JSON output. Use this instead of ad hoc CLI
CSV parsing when tracking public sources over time.

```bash
python3 .agents/skills/datascience/kaggle/scripts/nb_list.py \
  --competition SLUG \
  --search QUERY \
  --sort scoreDescending \
  --sort dateRun \
  --page-size 50 \
  --with-meta \
  --out PATH
```

Supported sorts mirror Kaggle CLI: `hotness`, `commentCount`, `dateCreated`,
`dateRun`, `relevance`, `scoreAscending`, `scoreDescending`, `viewCount`, and
`voteCount`.

The script writes `schema_version`, query parameters, command provenance, raw
CLI output, normalized items, `author_identity`, and optional notebook snapshot
metadata including latest/best LB score and version count.

For broad periodic syncs, prefer fast list-only snapshots across several sorts,
then run version/source metadata only for new, changed, or high-signal refs.
`--with-meta` performs per-notebook page/API calls and can be slow for large
multi-sort sweeps.
