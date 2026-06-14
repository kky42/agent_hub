# `nb_download.py`

Download a Kaggle notebook version's source, Kaggle dataset inputs, and output
zip with a stable manifest.

```bash
python3 .agents/skills/datascience/kaggle/scripts/nb_download.py \
  --notebook OWNER/KERNEL \
  --version 26 \
  --all \
  --out-dir PATH \
  --manifest PATH/manifest.json
```

The script uses the legacy notebook view endpoint to resolve version metadata,
downloads source from `scriptcontent/KERNEL_RUN_ID/download`, downloads dataset
inputs declared in notebook `metadata.kaggle.dataSources`, and downloads output
from `code/svzip/KERNEL_RUN_ID`.

The manifest records `schema_version`, requested version, resolved
`kernel_run_id`, title, status, evaluated time, source/input/output paths,
hashes, command output, and zip manifest. Failed or private artifacts remain in
the manifest with status/error rather than being silently skipped.

For routine public-source review, download source only (`--source`) for the best
visible LB version. Avoid `--all` unless inputs/outputs are explicitly needed,
because outputs and dataset inputs can be large.
