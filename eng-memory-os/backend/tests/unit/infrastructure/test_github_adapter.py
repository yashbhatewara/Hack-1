"""
Unit tests for the GitHubAdapter.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from eng_memory_os.domain.memory.entities import MemorySource
from eng_memory_os.infrastructure.integration.github_adapter import GitHubAdapter


def test_github_adapter_url_parsing():
    """Verify that repo owner and name are correctly parsed from different URL formats."""
    test_cases = [
        ("https://github.com/owner/repo", "owner", "repo"),
        ("https://github.com/owner/repo.git", "owner", "repo"),
        ("github.com/owner/repo", "owner", "repo"),
        ("git@github.com:owner/repo.git", "owner", "repo"),
    ]
    for url, expected_owner, expected_repo in test_cases:
        adapter = GitHubAdapter.from_url(url)
        assert adapter.repo_owner == expected_owner
        assert adapter.repo_name == expected_repo

    with pytest.raises(ValueError):
        GitHubAdapter.from_url("https://gitlab.com/owner/repo")


@pytest.mark.asyncio
async def test_github_adapter_test_connection_success():
    """Verify test_connection returns True on 200 OK."""
    adapter = GitHubAdapter("owner", "repo")

    mock_response = AsyncMock()
    mock_response.status_code = 200

    with patch("httpx.AsyncClient.get", return_value=mock_response) as mock_get:
        connected = await adapter.test_connection()
        assert connected is True
        mock_get.assert_called_once_with("https://api.github.com/repos/owner/repo")


@pytest.mark.asyncio
async def test_github_adapter_test_connection_failure():
    """Verify test_connection returns False on non-200."""
    adapter = GitHubAdapter("owner", "repo")

    mock_response = AsyncMock()
    mock_response.status_code = 404
    mock_response.text = "Not Found"

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        connected = await adapter.test_connection()
        assert connected is False


@pytest.mark.asyncio
async def test_github_adapter_fetch_recent():
    """Verify fetch_recent successfully parses issues and comments into IngestedItem."""
    adapter = GitHubAdapter("owner", "repo")

    mock_issues = [
        {
            "number": 42,
            "title": "Bug in setup script",
            "body": "Running setup fails with permission error.",
            "user": {"login": "alice"},
            "html_url": "https://github.com/owner/repo/issues/42",
            "created_at": "2026-07-03T12:00:00Z",
            "state": "open",
            "labels": [{"name": "bug"}, {"name": "setup"}],
            "comments_url": "https://api.github.com/repos/owner/repo/issues/42/comments",
        }
    ]

    mock_comments = [
        {
            "user": {"login": "bob"},
            "body": "Try running with sudo or check user group permission.",
            "created_at": "2026-07-03T12:30:00Z"
        }
    ]

    async def mock_get(url, *args, **kwargs):
        resp = AsyncMock()
        resp.status_code = 200
        if "comments" in url:
            resp.json = lambda: mock_comments
        else:
            resp.json = lambda: mock_issues
        return resp

    async def mock_git_cmd(*args, **kwargs):
        if "clone" in args:
            return ""
        elif "log" in args:
            return ""  # Empty commits log
        return ""

    with patch("httpx.AsyncClient.get", side_effect=mock_get), \
         patch.object(GitHubAdapter, "_run_git_command", side_effect=mock_git_cmd):
        items = await adapter.fetch_recent(limit=5)

        assert len(items) == 1
        item = items[0]
        assert item.external_id == "42"
        assert item.source_type == MemorySource.GITHUB_ISSUE
        assert item.author == "alice"
        assert item.title == "GitHub #42: Bug in setup script"
        assert "Bug in setup script" in item.content
        assert "Try running with sudo" in item.content
        assert "bug" in item.tags
        assert "setup" in item.tags
        assert "repo" in item.tags


@pytest.mark.asyncio
async def test_github_adapter_fetch_recent_with_commits():
    """Verify fetch_recent successfully parses commits and file diff patches into IngestedItem."""
    adapter = GitHubAdapter("owner", "repo")

    async def mock_get(url, *args, **kwargs):
        resp = AsyncMock()
        resp.status_code = 200
        resp.json = lambda: []  # No issues
        return resp

    async def mock_git_cmd(*args, **kwargs):
        if "clone" in args:
            return ""
        elif "log" in args:
            # Format: SHA|AuthorName|AuthorEmail|AuthorTimestamp|Subject
            return "ffd0ac3244f88ba142d5c6b96ef718bfea7a3dfa|Ayush-1-7|ayush17v@gmail.com|1777700000|feat: enhance health check for monitoring and production setup"
        elif "show" in args:
            return "File: src/main.py\nChanges: +3 -2\n@@ -1,3 +1,4 @@\n+print('hello')\n-print('hi')"
        return ""

    with patch("httpx.AsyncClient.get", side_effect=mock_get), \
         patch.object(GitHubAdapter, "_run_git_command", side_effect=mock_git_cmd):
        items = await adapter.fetch_recent(limit=5)

        assert len(items) == 1
        item = items[0]
        assert item.source_type == MemorySource.GITHUB_COMMIT
        assert item.author == "Ayush-1-7"
        assert item.external_id == "ffd0ac3244f88ba142d5c6b96ef718bfea7a3dfa"
        assert "enhance health check" in item.title
        assert "src/main.py" in item.content
        assert "print('hello')" in item.content
        assert "github_commit" in item.tags
        assert "repo" in item.tags


