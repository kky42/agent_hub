# `disc_get.py`

Fetch a full discussion thread: the opening post plus the **complete nested
comment tree** with author names, votes, and dates. Use this when the task is
"fetch a discussion" / "get its content and comments" — it returns everything
in one artifact, with reply nesting and author identity preserved.

```bash
python3 .agents/skills/datascience/kaggle/scripts/disc_get.py \
  --url "https://www.kaggle.com/competitions/SLUG/discussion/TOPIC_ID" \
  --format md          # or: json (default)
  --out PATH           # optional; prints to stdout otherwise
```

Alternatively pass `--topic-id TOPIC_ID` (optionally with `--competition SLUG`
for a nicer source URL). The topic id is global, so a bare `--topic-id` works
for competition, dataset, forum, kernel, and model discussions alike.

## How it works

The primary path calls Kaggle's authenticated discussions API
(`discussions.DiscussionApiService/GetTopic` for the opening post, then
`ListComments` paginated until exhausted for the full comment tree). This is
the same data `kaggle competitions topics show` uses, but the script keeps the
**full untruncated bodies**, the **reply nesting**, and the **author names**
together — none of which the flat `topic-messages` CSV or the truncated
`topics show` tree give you on their own.

Credentials are required for the full thread. They are read from, in order:

- `KAGGLE_USERNAME` + `KAGGLE_KEY` env vars
- `KAGGLE_API_TOKEN` env var (bearer)
- `$KAGGLE_CONFIG_DIR/kaggle.json` or `~/.kaggle/kaggle.json`

Without credentials the script degrades gracefully to an unauthenticated
page-title + visible-text scrape (`auth: "unauthenticated"`, no comments).

## Output

`--format md` renders the opening post followed by comments under a
hierarchical number that encodes the reply tree (`[1]`, `[1.1]`, `[1.1.1]`),
each with author, votes, and date. Inline images become `![](url)`.

`--format json` (schema `kaggle.discussion_thread.v2`) preserves:

- `topic`: id, url, title, author identity (display name + profile URL),
  votes, comment_count, post_date, forum, opening-post `content` (plain text)
  and `content_html`, plus the `raw` payload.
- `comments`: a nested list; each node has `id`, `parent_id`, `depth`,
  `author`, `author_identity`, `post_date`, `votes`, `content`, `content_html`,
  `replies`, and `raw`.
- `comment_count`: the actual number of comments fetched (sum over the tree).
- `auth`: `kaggle-api` or `unauthenticated`.

Comment author profile URLs are not exposed by the comments endpoint, so
`author_identity.profile_url` may be null for comments (it is populated for the
topic author).
