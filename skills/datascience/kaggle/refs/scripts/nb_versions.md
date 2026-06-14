# `nb_versions.py`

Track notebook version/update metadata and mutable score signals. The Kaggle
CLI can list current notebooks, pull source, and download latest output, but it
does not expose complete version/LB history.

```bash
python3 .agents/skills/datascience/kaggle/scripts/nb_versions.py \
  --notebook OWNER/KERNEL \
  --out PATH
```

The script fetches version history via the legacy notebook view endpoint and
page metadata. It does not require authentication for public notebooks. Record
`fetched_at`, notebook ref, versions, version ids, run timestamps, current
score/LB claims, and errors.

For stable tracking, consume `schema_version`, `snapshot`, and
`version_history`. `snapshot.author_identity` preserves notebook author user id,
user name, display name, profile URL, and raw payload when available.

When syncing many notebooks, fetch `nb_versions.py` only for new/changed/high-signal refs after a fast list snapshot and delta comparison. Choose the source version after this script runs; list snapshots can have stale or incomplete best-version metadata.
