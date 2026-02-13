from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib import parse, request


def _strip_html(raw: str) -> str:
    return raw.replace("<p>", "").replace("</p>", "").strip()


def normalize_post(post: dict[str, Any]) -> dict[str, str]:
    title_block = post.get("title", {})
    title = title_block.get("rendered", "") if isinstance(title_block, dict) else ""
    return {
        "id": str(post["id"]),
        "title": _strip_html(title),
        "modified": str(post.get("modified", "")),
        "link": str(post.get("link", "")),
    }


def build_posts_url(site_url: str, limit: int) -> str:
    base = site_url.rstrip("/")
    query = parse.urlencode({"per_page": str(limit), "orderby": "modified", "order": "desc"})
    return f"{base}/wp-json/wp/v2/posts?{query}"


def fetch_posts(site_url: str, limit: int = 20, timeout: int = 15) -> list[dict[str, str]]:
    url = build_posts_url(site_url=site_url, limit=limit)
    with request.urlopen(url, timeout=timeout) as response:  # nosec: B310
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Expected a list of posts from WordPress API.")
    return [normalize_post(item) for item in payload if isinstance(item, dict)]


def load_state(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("State file must contain an object.")
    return {str(k): str(v) for k, v in raw.items()}


def save_state(path: Path, state: dict[str, str]) -> None:
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def detect_changes(
    previous_state: dict[str, str], posts: list[dict[str, str]]
) -> list[dict[str, str]]:
    changes: list[dict[str, str]] = []
    for post in posts:
        post_id = post["id"]
        previous_modified = previous_state.get(post_id)
        current_modified = post["modified"]
        if previous_modified is None:
            changes.append({**post, "change_type": "new"})
            continue
        if previous_modified != current_modified:
            changes.append({**post, "change_type": "updated"})
    return changes


def build_prompt(site_url: str, changes: list[dict[str, str]]) -> str:
    lines = [
        f"WordPress site: {site_url}",
        "You are monitoring content changes.",
        "Summarize what changed and provide 3 operational recommendations.",
        "",
        "Changed posts:",
    ]
    for item in changes:
        lines.append(
            f"- [{item['change_type']}] {item['title']} ({item['modified']}) {item['link']}"
        )
    return "\n".join(lines)


def summarize_with_claude(
    api_key: str,
    prompt: str,
    model: str = "claude-3-5-sonnet-latest",
    timeout: int = 30,
) -> str:
    body = {
        "model": model,
        "max_tokens": 600,
        "messages": [{"role": "user", "content": prompt}],
    }
    req = request.Request(
        url="https://api.anthropic.com/v1/messages",
        method="POST",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with request.urlopen(req, timeout=timeout) as response:  # nosec: B310
        payload = json.loads(response.read().decode("utf-8"))
    blocks = payload.get("content", [])
    if not isinstance(blocks, list):
        raise ValueError("Unexpected Claude response format.")
    text_blocks = [
        block.get("text", "")
        for block in blocks
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    return "\n".join(part for part in text_blocks if part).strip()


def run_monitor(
    site_url: str,
    state_file: Path,
    use_claude: bool,
    api_key: str | None,
    fetcher: Any = fetch_posts,
    summarizer: Any = summarize_with_claude,
) -> dict[str, Any]:
    previous_state = load_state(state_file)
    posts = fetcher(site_url)
    changes = detect_changes(previous_state=previous_state, posts=posts)

    new_state = {post["id"]: post["modified"] for post in posts}
    save_state(state_file, new_state)

    summary = ""
    if changes and use_claude:
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when Claude summarization is enabled.")
        prompt = build_prompt(site_url=site_url, changes=changes)
        summary = summarizer(api_key=api_key, prompt=prompt)
    return {"changes": changes, "summary": summary}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Monitor WordPress updates and summarize with Claude."
    )
    parser.add_argument("--site-url", required=True, help="WordPress site base URL.")
    parser.add_argument("--state-file", required=True, help="Path to local state JSON file.")
    parser.add_argument(
        "--no-claude",
        action="store_true",
        help="Disable Claude call and only report detected changes.",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    result = run_monitor(
        site_url=args.site_url,
        state_file=Path(args.state_file),
        use_claude=not args.no_claude,
        api_key=None if args.no_claude else __import__("os").environ.get("ANTHROPIC_API_KEY"),
    )

    print(f"Detected changes: {len(result['changes'])}")
    for item in result["changes"]:
        print(f"- [{item['change_type']}] {item['title']} ({item['modified']})")

    if result["summary"]:
        print("\nClaude summary:\n")
        print(result["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
