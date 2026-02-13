from pathlib import Path

from wp_claude_monitor.monitor import build_prompt, detect_changes, run_monitor


def test_detect_changes_new_and_updated() -> None:
    previous = {"1": "2026-01-10T10:00:00"}
    posts = [
        {
            "id": "1",
            "title": "Updated Post",
            "modified": "2026-01-11T10:00:00",
            "link": "https://example.com/updated",
        },
        {
            "id": "2",
            "title": "New Post",
            "modified": "2026-01-11T09:00:00",
            "link": "https://example.com/new",
        },
    ]
    changes = detect_changes(previous_state=previous, posts=posts)
    assert len(changes) == 2
    assert changes[0]["change_type"] == "updated"
    assert changes[1]["change_type"] == "new"


def test_run_monitor_updates_state_and_uses_summarizer(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    summarized = {"called": False}

    def fake_fetcher(_: str) -> list[dict[str, str]]:
        return [
            {
                "id": "10",
                "title": "Monitor Launch",
                "modified": "2026-02-01T08:00:00",
                "link": "https://example.com/launch",
            }
        ]

    def fake_summarizer(api_key: str, prompt: str) -> str:
        assert api_key == "test-key"
        assert "Monitor Launch" in prompt
        summarized["called"] = True
        return "Summary ready."

    result = run_monitor(
        site_url="https://example.com",
        state_file=state_file,
        use_claude=True,
        api_key="test-key",
        fetcher=fake_fetcher,
        summarizer=fake_summarizer,
    )

    assert summarized["called"] is True
    assert result["summary"] == "Summary ready."
    assert result["changes"][0]["change_type"] == "new"
    assert state_file.exists()


def test_build_prompt_contains_change_metadata() -> None:
    prompt = build_prompt(
        site_url="https://example.com",
        changes=[
            {
                "id": "7",
                "title": "Security Patch",
                "modified": "2026-02-12T10:00:00",
                "link": "https://example.com/security-patch",
                "change_type": "updated",
            }
        ],
    )
    assert "Security Patch" in prompt
    assert "[updated]" in prompt
    assert "https://example.com/security-patch" in prompt
