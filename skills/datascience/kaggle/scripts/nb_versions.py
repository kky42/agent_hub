#!/usr/bin/env python3
"""Fetch Kaggle notebook version/update metadata and score signals."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import http.client
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def normalize_ref(ref: str) -> str:
    ref = ref.strip().strip("/")
    if ref.startswith("https://www.kaggle.com/"):
        ref = ref.removeprefix("https://www.kaggle.com/")
    if ref.startswith("code/"):
        ref = ref.removeprefix("code/")
    return ref


def fetch(url: str, timeout: float, cookie: str | None = None, attempts: int = 3) -> tuple[int | None, str, str | None]:
    headers = {"User-Agent": "Mozilla/5.0 kaggle-skill/1.0", "Accept": "text/html,application/json"}
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(url, headers=headers)
    last_error: str | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read().decode("utf-8", errors="replace"), None
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code not in {400, 429, 500, 502, 503, 504} or attempt + 1 >= attempts:
                return exc.code, body, body or str(exc)
            last_error = body or str(exc)
        except http.client.IncompleteRead as exc:
            last_error = str(exc)
        except urllib.error.URLError as exc:
            last_error = str(exc)
        if attempt + 1 < attempts:
            time.sleep(0.5 * (attempt + 1))
    return None, "", last_error


def api_get(path: str, params: dict[str, Any], timeout: float, cookie: str | None = None) -> tuple[int | None, dict[str, Any] | None, str | None]:
    url = "https://www.kaggle.com/api/i/" + path + "?" + urllib.parse.urlencode(params)
    status, body, error = fetch(url, timeout, cookie)
    if error:
        return status, None, body or error
    try:
        return status, json.loads(body), None
    except json.JSONDecodeError as exc:
        return status, None, str(exc)


def split_ref(ref: str) -> tuple[str | None, str]:
    parts = ref.split("/", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return None, ref


def json_blocks(source: str) -> list[Any]:
    blocks: list[Any] = []
    for pattern in (
        r"<script[^>]+type=[\"']application/json[\"'][^>]*>(.*?)</script>",
        r"<script[^>]+id=[\"']__NEXT_DATA__[\"'][^>]*>(.*?)</script>",
    ):
        for match in re.finditer(pattern, source, re.I | re.S):
            raw = html.unescape(match.group(1)).strip()
            try:
                blocks.append(json.loads(raw))
            except json.JSONDecodeError:
                pass
    return blocks


def flatten(value: Any) -> list[Any]:
    out = [value]
    if isinstance(value, dict):
        for item in value.values():
            out.extend(flatten(item))
    elif isinstance(value, list):
        for item in value:
            out.extend(flatten(item))
    return out


def pick_versionish(blocks: list[Any]) -> list[dict[str, Any]]:
    versions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in blocks:
        if not isinstance(item, dict):
            continue
        keys = {str(k).lower() for k in item}
        if not ({"versionnumber", "versionid", "scriptversionid", "kernelversionid", "runinfo"} & keys):
            continue
        version_id = item.get("versionId") or item.get("scriptVersionId") or item.get("kernelVersionId") or item.get("id")
        number = item.get("versionNumber") or item.get("number")
        key = str(version_id or number or json.dumps(item, sort_keys=True)[:200])
        if key in seen:
            continue
        seen.add(key)
        versions.append({
            "id": version_id,
            "version": number,
            "title": item.get("title") or item.get("name"),
            "status": item.get("status") or item.get("runStatus"),
            "created_at": item.get("dateCreated") or item.get("createdAt") or item.get("creationDate"),
            "run_time": item.get("lastRunTime") or item.get("runTime") or item.get("dateRun"),
            "score": item.get("score") or item.get("publicScore") or item.get("bestPublicScore"),
            "raw": item,
        })
    return versions


def score_claims(text: str) -> list[str]:
    patterns = [
        r"(?i)(?:public\s*)?(?:lb|score)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)",
        r"(?i)([0-9]+(?:\.[0-9]+)?)\s*(?:public\s*)?(?:lb|score)",
    ]
    claims: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            value = match.group(1)
            if value not in claims:
                claims.append(value)
    return claims[:20]


def legacy_version_summary(item: dict[str, Any]) -> dict[str, Any]:
    kernel = item.get("kernel") or {}
    run = item.get("kernelRun") or {}
    submission = item.get("submission") or {}
    best = item.get("bestSubmissionScore") or {}
    return {
        "version": run.get("kernelVersionNumber") or item.get("currentVersionNumber"),
        "kernel_run_id": run.get("id"),
        "title": run.get("title") or kernel.get("title"),
        "status": run.get("status"),
        "created_at": run.get("dateCreated"),
        "evaluated_at": run.get("dateEvaluated"),
        "submission_id": submission.get("id"),
        "submission_score": submission.get("scoreFormatted"),
        "best_score": best.get("scoreFormatted") or kernel.get("bestPublicScore"),
        "best_score_version": best.get("kernelVersionNumber"),
        "raw": item,
    }


def normalize_author(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    profile_url = raw.get("profileUrl") or raw.get("url")
    if isinstance(profile_url, str) and profile_url.startswith("/"):
        profile_url = "https://www.kaggle.com" + profile_url
    return {
        "id": raw.get("id") or raw.get("userId"),
        "user_name": raw.get("userName"),
        "display_name": raw.get("displayName") or raw.get("name"),
        "profile_url": profile_url,
        "thumbnail_url": raw.get("thumbnailUrl"),
        "tier": raw.get("performanceTier") or raw.get("tier"),
        "raw": raw,
    }


def fetch_legacy_versions(ref: str, timeout: float, cookie: str | None = None) -> dict[str, Any]:
    owner, slug = split_ref(ref)
    if not owner:
        return {"error": "Legacy GetKernelViewModel requires OWNER/KERNEL", "versions": []}
    base_params = {
        "authorUserName": owner,
        "kernelSlug": slug,
        "kernelVersionId": 0,
    }
    status, current, error = api_get(
        "kernels.LegacyKernelsService/GetKernelViewModel",
        base_params,
        timeout,
        cookie,
    )
    result: dict[str, Any] = {"status": status, "error": error, "current": current, "versions": []}
    if not isinstance(current, dict):
        return result
    total = current.get("totalVersionCount") or current.get("currentVersionNumber") or 0
    result["total_version_count"] = total
    for version in range(1, int(total) + 1):
        params = dict(base_params)
        params["versionNumber"] = version
        v_status, data, v_error = api_get(
            "kernels.LegacyKernelsService/GetKernelViewModel",
            params,
            timeout,
            cookie,
        )
        if isinstance(data, dict):
            summary = legacy_version_summary(data)
            summary["fetch_status"] = v_status
            summary["fetch_error"] = v_error
            result["versions"].append(summary)
        else:
            result["versions"].append({
                "version": version,
                "fetch_status": v_status,
                "fetch_error": v_error,
            })
        time.sleep(0.2)
    return result


def stable_snapshot(legacy: dict[str, Any]) -> dict[str, Any]:
    current = legacy.get("current") if isinstance(legacy.get("current"), dict) else {}
    kernel = current.get("kernel") or {}
    run = current.get("kernelRun") or {}
    submission = current.get("submission") or {}
    best = current.get("bestSubmissionScore") or {}
    return {
        "kernel_id": kernel.get("id"),
        "title": kernel.get("title") or run.get("title"),
        "slug": kernel.get("slug"),
        "url": "https://www.kaggle.com" + kernel.get("url") if isinstance(kernel.get("url"), str) and kernel.get("url", "").startswith("/") else kernel.get("url"),
        "author_identity": normalize_author(kernel.get("author")),
        "current_run_id": kernel.get("currentRunId") or run.get("id"),
        "current_version": current.get("currentVersionNumber") or run.get("kernelVersionNumber"),
        "version_count": legacy.get("total_version_count") or current.get("totalVersionCount"),
        "latest_lb_score": submission.get("scoreFormatted") or best.get("scoreFormatted") or kernel.get("bestPublicScore"),
        "best_lb_score": best.get("scoreFormatted") or kernel.get("bestPublicScore"),
        "best_lb_score_version": best.get("kernelVersionNumber"),
        "latest_status": run.get("status"),
        "latest_created_at": run.get("dateCreated"),
        "latest_evaluated_at": run.get("dateEvaluated"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notebook", required=True, help="OWNER/KERNEL or Kaggle code URL")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    ref = normalize_ref(args.notebook)
    status, data, api_error = api_get(
        "kernels.KernelsService/ListKernelVersions",
        {"kernelSlug": ref},
        args.timeout,
    )
    url = f"https://www.kaggle.com/code/{ref}"
    page_status, source, page_error = fetch(url, args.timeout)
    blocks = json_blocks(source)
    version_candidates = flatten(data) if isinstance(data, (dict, list)) else []
    version_candidates.extend(flatten(block) for block in blocks)
    flat: list[Any] = []
    for item in version_candidates:
        if isinstance(item, list):
            flat.extend(item)
        else:
            flat.append(item)
    legacy = fetch_legacy_versions(ref, args.timeout)
    record = {
        "schema_version": "kaggle.notebook_versions.v1",
        "operation": "nb_versions",
        "notebook": ref,
        "url": url,
        "fetched_at": now_iso(),
        "snapshot": stable_snapshot(legacy),
        "version_history": legacy.get("versions", []),
        "api": {"status": status, "error": api_error, "data": data},
        "legacy_api": legacy,
        "page": {"status": page_status, "error": page_error},
        "versions": pick_versionish(flat),
        "score_claims": score_claims(source),
    }
    output = json.dumps(record, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
