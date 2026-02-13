# wp-claude-monitor

`wp-claude-monitor` tracks new or updated posts on a WordPress site and sends a concise summary request to Claude.

## What it does

- Polls `wp-json/wp/v2/posts` from a WordPress site
- Stores the latest known `modified` timestamp per post
- Detects newly published or updated posts
- Sends a structured prompt to Claude (Anthropic API) for an actionable summary

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

```bash
export ANTHROPIC_API_KEY=your_key_here
wp-claude-monitor --site-url https://example.com --state-file .state.json
```

Run without Claude (change detection only):

```bash
wp-claude-monitor --site-url https://example.com --state-file .state.json --no-claude
```

## Development

```bash
pip install pytest ruff
ruff check .
pytest
```
