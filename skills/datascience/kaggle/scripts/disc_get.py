#!/usr/bin/env python3
"""Fetch a full Kaggle discussion thread: opening post plus the complete nested
comment tree with author identities, votes, and dates.

Primary path uses Kaggle's authenticated discussions API
(``discussions.DiscussionApiService`` ``GetTopic`` + ``ListComments``), which
returns every comment, the reply nesting, and author names in one place. It
needs Kaggle credentials (``~/.kaggle/kaggle.json`` or ``KAGGLE_USERNAME`` /
``KAGGLE_KEY`` / ``KAGGLE_API_TOKEN``). Without credentials it degrades to an
unauthenticated page-title + visible-text scrape so it still returns something.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import html
from html.parser import HTMLParser
import http.client
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

API_ROOT = "https://api.kaggle.com/v1/discussions.DiscussionApiService"
USER_AGENT = "Mozilla/5.0 kaggle-skill/1.0"


class TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "svg", "noscript"}:
            self.skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "svg", "noscript"} and self.skip:
            self.skip -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip:
            text = " ".join(data.split())
            if text:
                self.parts.append(text)


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value)).split())
    return text or None


def html_to_text(value: Any) -> str | None:
    """Convert comment/post HTML into readable plain text, preserving line
    breaks, list bullets, links, and image markers."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|h[1-6]|tr|blockquote)>", "\n\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "\n- ", text)
    text = re.sub(r"(?i)<img[^>]*\bsrc=[\"']([^\"']+)[\"'][^>]*>", r"![](\1)", text)
    text = re.sub(
        r"(?i)<a[^>]*\bhref=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
        lambda m: m.group(2).strip() or m.group(1),
        text,
        flags=re.S,
    )
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text or None


def page_title(source: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", source, flags=re.I | re.S)
    return clean_text(match.group(1)) if match else None


def visible_text(source: str) -> str:
    parser = TextParser()
    parser.feed(source)
    return "\n".join(parser.parts)


def as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        match = re.search(r"-?\d+", value.replace(",", ""))
        if match:
            return int(match.group(0))
    return None


# ── credentials / API ────────────────────────────────────────────────────────


def load_credentials() -> tuple[str, str, str | None] | None:
    """Return (scheme, secret_a, secret_b). scheme is 'basic' (user, key) or
    'bearer' (token, None). None when no credentials are available."""
    user = os.environ.get("KAGGLE_USERNAME")
    key = os.environ.get("KAGGLE_KEY")
    if user and key:
        return ("basic", user, key)
    token = os.environ.get("KAGGLE_API_TOKEN")
    if token:
        return ("bearer", token, None)
    cfg_dir = os.environ.get("KAGGLE_CONFIG_DIR") or os.path.expanduser("~/.kaggle")
    path = Path(cfg_dir) / "kaggle.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if data.get("username") and data.get("key"):
            return ("basic", str(data["username"]), str(data["key"]))
        if data.get("api_token"):
            return ("bearer", str(data["api_token"]), None)
    return None


def auth_header(creds: tuple[str, str, str | None]) -> str:
    if creds[0] == "basic":
        raw = f"{creds[1]}:{creds[2]}".encode()
        return "Basic " + base64.b64encode(raw).decode()
    return "Bearer " + creds[1]


def api_call(
    method: str, payload: dict[str, Any], creds: tuple[str, str, str | None], timeout: float
) -> tuple[int | None, dict[str, Any] | None, str | None]:
    url = f"{API_ROOT}/{method}"
    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": auth_header(creds),
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            try:
                body = resp.read().decode("utf-8", errors="replace")
            except http.client.IncompleteRead as exc:
                return resp.status, None, str(exc)
            return resp.status, json.loads(body), None
    except urllib.error.HTTPError as exc:
        return exc.code, None, exc.read().decode("utf-8", errors="replace") or str(exc)
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        return None, None, str(exc)


def fetch(url: str, timeout: float) -> tuple[int | None, str, str | None]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            try:
                return resp.status, resp.read().decode("utf-8", errors="replace"), None
            except http.client.IncompleteRead as exc:
                return resp.status, exc.partial.decode("utf-8", errors="replace"), str(exc)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace"), str(exc)
    except urllib.error.URLError as exc:
        return None, "", str(exc)


# ── normalization ────────────────────────────────────────────────────────────


def normalize_author(name: Any, url: Any) -> dict[str, Any]:
    profile_url = url if isinstance(url, str) and url.strip() else None
    if isinstance(profile_url, str) and profile_url.startswith("/"):
        profile_url = "https://www.kaggle.com" + profile_url
    user_name = profile_url.rstrip("/").split("/")[-1] if profile_url else None
    return {
        "display_name": clean_text(name),
        "user_name": user_name,
        "profile_url": profile_url,
    }


def normalize_comment(obj: dict[str, Any], depth: int, parent_id: Any) -> dict[str, Any]:
    author = normalize_author(obj.get("authorName"), obj.get("authorUrl"))
    children = obj.get("replies") if isinstance(obj.get("replies"), list) else []
    replies = [normalize_comment(child, depth + 1, obj.get("id")) for child in children]
    return {
        "id": obj.get("id"),
        "parent_id": parent_id,
        "depth": depth,
        "author": author.get("display_name"),
        "author_identity": author,
        "post_date": clean_text(obj.get("postDate")),
        "votes": as_int(obj.get("votes")),
        "content": html_to_text(obj.get("content")),
        "content_html": obj.get("content") or None,
        "replies": replies,
        "raw": obj,
    }


def count_comments(comments: list[dict[str, Any]]) -> int:
    return sum(1 + count_comments(c["replies"]) for c in comments)


def normalize_topic(topic: dict[str, Any]) -> dict[str, Any]:
    author = normalize_author(topic.get("authorName"), topic.get("authorUrl"))
    raw_url = topic.get("url")
    url = "https://www.kaggle.com" + raw_url if isinstance(raw_url, str) and raw_url.startswith("/") else raw_url
    return {
        "id": topic.get("id"),
        "url": url,
        "title": clean_text(topic.get("title")),
        "author": author.get("display_name"),
        "author_identity": author,
        "votes": as_int(topic.get("votes")),
        "comment_count": as_int(topic.get("commentCount")),
        "post_date": clean_text(topic.get("postDate")),
        "last_comment_date": clean_text(topic.get("lastCommentDate")),
        "forum_id": topic.get("forumId"),
        "forum_name": clean_text(topic.get("forumName")),
        "content": html_to_text(topic.get("content")),
        "content_html": topic.get("content") or None,
        "raw": topic,
    }


# ── input handling ───────────────────────────────────────────────────────────


def topic_id_from_url(url: str) -> str | None:
    match = re.search(r"/discussion/(\d+)", url) or re.search(r"/(\d+)(?:\?|$)", url)
    return match.group(1) if match else None


def resolve_inputs(args: argparse.Namespace) -> tuple[str, str | None]:
    if args.url:
        return args.url, args.topic_id or topic_id_from_url(args.url)
    if args.topic_id:
        if args.competition:
            url = f"https://www.kaggle.com/competitions/{args.competition}/discussion/{args.topic_id}"
        else:
            url = f"https://www.kaggle.com/discussions/general/{args.topic_id}"
        return url, args.topic_id
    raise SystemExit("Provide --url, or --topic-id (optionally with --competition)")


# ── rendering ────────────────────────────────────────────────────────────────


def render_comment_md(comment: dict[str, Any], number: str, lines: list[str]) -> None:
    author = comment.get("author") or "unknown"
    votes = comment.get("votes")
    vote_str = f" · ▲{votes}" if votes else ""
    date = comment.get("post_date") or ""
    lines.append(f"### [{number}] {author}{vote_str} · {date}".rstrip(" ·"))
    lines.append("")
    lines.append(comment.get("content") or "_(no text)_")
    lines.append("")
    for idx, reply in enumerate(comment.get("replies") or [], start=1):
        render_comment_md(reply, f"{number}.{idx}", lines)


def render_md(record: dict[str, Any]) -> str:
    topic = record.get("topic") or {}
    title = topic.get("title") or record.get("title") or "Kaggle Discussion"
    lines = [f"# {title}", ""]
    meta = []
    if topic.get("author"):
        meta.append(f"Author: {topic['author']}")
    if topic.get("votes") is not None:
        meta.append(f"▲{topic['votes']}")
    if record.get("comment_count") is not None:
        meta.append(f"{record['comment_count']} comments")
    if topic.get("post_date"):
        meta.append(f"Posted: {topic['post_date']}")
    if meta:
        lines.append(" · ".join(meta))
    lines.append(f"URL: {record['source_url']}")
    if topic.get("forum_name"):
        lines.append(f"Forum: {topic['forum_name']}")
    lines.append(f"Fetched: {record['fetched_at']} (auth: {record['auth']})")
    lines.append("")
    if topic.get("content"):
        lines.extend([topic["content"], ""])
    comments = record.get("comments") or []
    if comments:
        lines.extend(["---", "", f"## Comments ({record.get('comment_count')})", ""])
        for idx, comment in enumerate(comments, start=1):
            render_comment_md(comment, str(idx), lines)
    elif record.get("visible_text"):
        lines.extend(["---", "", "## Visible Text (unauthenticated fallback)", "", record["visible_text"]])
    return "\n".join(lines).rstrip() + "\n"


# ── main ─────────────────────────────────────────────────────────────────────


def fetch_via_api(
    topic_id: str, creds: tuple[str, str, str | None], timeout: float
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], dict[str, Any]]:
    meta: dict[str, Any] = {}
    topic_status, topic_data, topic_error = api_call("GetTopic", {"id": int(topic_id)}, creds, timeout)
    meta["topic"] = {"status": topic_status, "error": topic_error}
    topic = None
    if isinstance(topic_data, dict) and isinstance(topic_data.get("topic"), dict):
        topic = normalize_topic(topic_data["topic"])

    comments: list[dict[str, Any]] = []
    page_token: str | None = None
    pages = 0
    last_status = last_error = None
    while True:
        payload: dict[str, Any] = {"topicId": int(topic_id)}
        if page_token:
            payload["pageToken"] = page_token
        status, data, error = api_call("ListComments", payload, creds, timeout)
        last_status, last_error = status, error
        pages += 1
        if not isinstance(data, dict):
            break
        for obj in data.get("comments") or []:
            if isinstance(obj, dict):
                comments.append(normalize_comment(obj, 0, None))
        page_token = data.get("nextPageToken") or None
        if not page_token or pages >= 50:
            break
    meta["comments"] = {"status": last_status, "error": last_error, "pages": pages}
    return topic, comments, meta


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url")
    parser.add_argument("--competition")
    parser.add_argument("--topic-id")
    parser.add_argument("--format", choices=["json", "md"], default="json")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    url, topic_id = resolve_inputs(args)
    creds = load_credentials()

    topic: dict[str, Any] | None = None
    comments: list[dict[str, Any]] = []
    api_meta: dict[str, Any] = {}
    auth = "unauthenticated"
    visible: str | None = None
    page_status: int | None = None
    page_error: str | None = None

    if creds and topic_id:
        auth = "kaggle-api"
        topic, comments, api_meta = fetch_via_api(topic_id, creds, args.timeout)

    if not comments and not topic:
        # No credentials, or API returned nothing — degrade to a page scrape so
        # the caller still gets the title and visible text.
        page_status, source, page_error = fetch(url, args.timeout)
        visible = visible_text(source)[:12000] if source else None
        if topic is None and source:
            topic = {"title": page_title(source)}

    record = {
        "schema_version": "kaggle.discussion_thread.v2",
        "source_url": url,
        "topic_id": topic_id,
        "auth": auth,
        "fetched_at": now_iso(),
        "api": api_meta or None,
        "page_status": page_status,
        "page_error": page_error,
        "topic": topic,
        "title": (topic or {}).get("title"),
        "comment_count": count_comments(comments) if comments else (topic or {}).get("comment_count"),
        "comments": comments,
        "visible_text": visible if not comments else None,
    }

    output = render_md(record) if args.format == "md" else json.dumps(record, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
