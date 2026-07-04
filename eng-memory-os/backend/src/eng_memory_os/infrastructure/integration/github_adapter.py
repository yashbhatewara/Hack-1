"""
Concrete GitHub integration adapter.

Uses HTTPX to fetch issues, pull requests, and their discussion threads
from a GitHub repository. Converts them into IngestedItem domain objects.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import httpx
import structlog

from eng_memory_os.domain.integration.interfaces import (
    IngestedItem,
    IntegrationAdapter,
    IntegrationType,
)
from eng_memory_os.domain.memory.entities import MemorySource

logger = structlog.get_logger(__name__)


class GitHubAdapter(IntegrationAdapter):
    """Adapter for syncing engineering memories from GitHub repositories."""

    BASE_API_URL = "https://api.github.com"

    def __init__(
        self,
        repo_owner: str,
        repo_name: str,
        github_token: str | None = None,
    ) -> None:
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.github_token = github_token

        # Set up default headers (GitHub requires a User-Agent)
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Engineering-Memory-OS",
        }
        if github_token:
            self.headers["Authorization"] = f"token {github_token}"

    async def _run_git_command(self, *args: str, cwd: str | None = None) -> str:
        """Run a git CLI command asynchronously and return its output."""
        import asyncio
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Git command failed: {' '.join(args)}. Error: {stderr.decode().strip()}")
        return stdout.decode("utf-8", errors="replace")

    @classmethod
    def from_url(cls, repo_url: str, github_token: str | None = None) -> GitHubAdapter:
        """Helper to instantiate adapter from a GitHub repo URL."""
        # Match URL formats:
        # https://github.com/owner/repo
        # github.com/owner/repo
        # git@github.com:owner/repo.git
        match = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", repo_url)
        if not match:
            raise ValueError(f"Invalid GitHub repository URL: {repo_url}")

        owner, repo = match.group(1), match.group(2)
        return cls(repo_owner=owner, repo_name=repo, github_token=github_token)

    async def test_connection(self) -> bool:
        """Verify that the repository is accessible."""
        url = f"{self.BASE_API_URL}/repos/{self.repo_owner}/{self.repo_name}"
        async with httpx.AsyncClient(headers=self.headers, timeout=10.0) as client:
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    logger.info("github_connection_successful", repo=f"{self.repo_owner}/{self.repo_name}")
                    return True
                else:
                    logger.warning(
                        "github_connection_failed",
                        status_code=response.status_code,
                        response=response.text,
                    )
                    return False
            except Exception as e:
                logger.exception("github_connection_exception", error=str(e))
                return False

    async def fetch_recent(
        self,
        since: datetime | None = None,
        limit: int = 30,
    ) -> list[IngestedItem]:
        """Fetch recent issues, pull requests, and commits, merging their discussions/changes."""
        items: list[IngestedItem] = []

        async with httpx.AsyncClient(headers=self.headers, timeout=20.0) as client:
            # 1. Fetch Issues and PRs
            issues_url = f"{self.BASE_API_URL}/repos/{self.repo_owner}/{self.repo_name}/issues"
            params_issues: dict[str, str | int] = {
                "state": "all",
                "sort": "updated",
                "direction": "desc",
                "per_page": min(limit, 100),
            }
            if since:
                params_issues["since"] = since.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

            try:
                logger.info("fetching_github_issues_list", url=issues_url, params=params_issues)
                response = await client.get(issues_url, params=params_issues)
                if response.status_code == 200:
                    raw_issues = response.json()
                    logger.info("fetched_github_issues", count=len(raw_issues))

                    for issue in raw_issues[:limit]:
                        try:
                            number = issue.get("number")
                            title = issue.get("title", "")
                            body = issue.get("body") or ""
                            author = issue.get("user", {}).get("login", "unknown")
                            html_url = issue.get("html_url", "")
                            created_at_str = issue.get("created_at")

                            if not created_at_str:
                                continue
                            created_at = datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)

                            # Determine if it's a Pull Request or a standard Issue
                            is_pr = "pull_request" in issue
                            source_type = MemorySource.GITHUB_PR if is_pr else MemorySource.GITHUB_ISSUE

                            # Fetch comments
                            comments_url = issue.get("comments_url")
                            comments_text = ""
                            if comments_url:
                                comments_response = await client.get(comments_url)
                                if comments_response.status_code == 200:
                                    raw_comments = comments_response.json()
                                    comments_list = []
                                    for comment in raw_comments:
                                        c_author = comment.get("user", {}).get("login", "unknown")
                                        c_body = comment.get("body", "")
                                        c_date = comment.get("created_at", "")
                                        comments_list.append(f"### Comment by @{c_author} at {c_date}\n\n{c_body}\n")
                                    if comments_list:
                                        comments_text = "\n## Discussion Thread\n\n" + "\n".join(comments_list)

                            # Build Markdown content representing the full history
                            state = issue.get("state", "open").upper()
                            markdown_content = f"# [{source_type.upper()}] {title} (#{number})\n\n"
                            markdown_content += f"**Repository:** {self.repo_owner}/{self.repo_name}\n"
                            markdown_content += f"**URL:** {html_url}\n"
                            markdown_content += f"**Author:** @{author}\n"
                            markdown_content += f"**Status:** {state}\n"
                            markdown_content += f"**Created At:** {created_at_str}\n\n"
                            markdown_content += f"## Description\n\n{body}\n"
                            if comments_text:
                                markdown_content += comments_text

                            # Gather labels/tags
                            tags = [label.get("name") for label in issue.get("labels", []) if label.get("name")]
                            tags.append(source_type.value)
                            tags.append(self.repo_name.lower())

                            ingested_item = IngestedItem(
                                source_uri=html_url,
                                source_type=source_type,
                                title=f"GitHub #{number}: {title}",
                                content=markdown_content,
                                author=author,
                                external_id=str(number),
                                external_timestamp=created_at,
                                tags=tags,
                            )
                            items.append(ingested_item)

                        except Exception as e:
                            logger.warning("failed_to_parse_github_issue", number=issue.get("number"), error=str(e))
                            continue
                else:
                    logger.warning("failed_to_fetch_github_issues", status_code=response.status_code, error=response.text)
            except Exception as e:
                logger.warning("failed_to_request_github_issues", error=str(e))

            # 2. Fetch Commits and Files using Local Git Clone (0 Rate Limits!)
            import os
            import shutil
            import tempfile

            clone_url = f"https://github.com/{self.repo_owner}/{self.repo_name}.git"
            if self.github_token:
                # Inject token for authentication (works for private repos too)
                clone_url = f"https://x-access-token:{self.github_token}@github.com/{self.repo_owner}/{self.repo_name}.git"

            temp_dir = tempfile.mkdtemp(prefix="emo-sync-")
            try:
                logger.info("local_git_clone_started", repo=f"{self.repo_owner}/{self.repo_name}", limit=limit)
                # Standard clone with depth = limit (pulls active files and recent commit history)
                await self._run_git_command("clone", f"--depth={limit}", clone_url, temp_dir)

                # 2a. Ingest README.md first (if exists)
                readme_item = None
                for filename in os.listdir(temp_dir):
                    if filename.lower() == "readme.md":
                        readme_path = os.path.join(temp_dir, filename)
                        try:
                            with open(readme_path, encoding="utf-8", errors="replace") as f:
                                readme_content = f.read()
                            html_url = f"https://github.com/{self.repo_owner}/{self.repo_name}/blob/main/{filename}"
                            content = f"# README.md\n\n**Repository:** {self.repo_owner}/{self.repo_name}\n\n{readme_content}"
                            readme_item = IngestedItem(
                                source_uri=html_url,
                                source_type=MemorySource.ARCHITECTURE_DOC,
                                title="GitHub Repo: README.md",
                                content=content,
                                author="repository",
                                external_id="readme",
                                external_timestamp=datetime.now(UTC),
                                tags=["readme", "github_file", self.repo_name.lower()],
                            )
                            logger.info("found_and_queued_readme", path=readme_path)
                        except Exception as e:
                            logger.warning("failed_to_read_readme", error=str(e))
                        break

                if readme_item:
                    items.append(readme_item)

                # 2b. Scan and ingest source files (limit to 20 files to keep vector DB ingestion fast)
                code_extensions = {".py", ".js", ".ts", ".json", ".yml", ".yaml", ".sh", ".sql", ".dockerfile", "Dockerfile"}
                file_count = 0
                for root, dirs, files_in_dir in os.walk(temp_dir):
                    # Prune excluded directories to avoid walking down them
                    dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "venv", "__pycache__", ".idea", ".vscode", "dist", "build"}]
                    for file in files_in_dir:
                        if file_count >= 20:
                            break
                        ext = os.path.splitext(file)[1].lower()
                        if ext in code_extensions or file == "Dockerfile":
                            if file.lower() == "readme.md":
                                continue
                            file_path = os.path.join(root, file)
                            try:
                                with open(file_path, encoding="utf-8", errors="replace") as f:
                                    file_content = f.read()
                                rel_path = os.path.relpath(file_path, temp_dir).replace("\\", "/")
                                html_url = f"https://github.com/{self.repo_owner}/{self.repo_name}/blob/main/{rel_path}"
                                content = f"# Source File: {rel_path}\n\n**Repository:** {self.repo_owner}/{self.repo_name}\n\n```python\n{file_content}\n```"
                                ingested_item = IngestedItem(
                                    source_uri=html_url,
                                    source_type=MemorySource.ARCHITECTURE_DOC,
                                    title=rel_path,
                                    content=content,
                                    author="repository",
                                    external_id=rel_path,
                                    external_timestamp=datetime.now(UTC),
                                    tags=["source_file", self.repo_name.lower()],
                                )
                                items.append(ingested_item)
                                file_count += 1
                            except Exception as e:
                                logger.warning("failed_to_read_code_file", path=file_path, error=str(e))
                                continue
                    if file_count >= 20:
                        break
                logger.info("scanned_github_repo_files", count=file_count)

                # 2c. Fetch commit log output
                log_output = await self._run_git_command(
                    "log", "-n", str(limit), "--pretty=format:%H|%an|%ae|%at|%s", cwd=temp_dir
                )

                if log_output.strip():
                    commit_count = 0
                    for line in log_output.strip().split("\n"):
                        try:
                            parts = line.split("|", 4)
                            if len(parts) < 5:
                                continue
                            sha, author_name, author_email, timestamp_str, subject = parts

                            created_at = datetime.fromtimestamp(int(timestamp_str), tz=UTC)

                            # Fetch commit details (message and diff) using the worktree cwd
                            diff_output = await self._run_git_command(
                                "show", "--stat", "-p", sha, cwd=temp_dir
                            )

                            html_url = f"https://github.com/{self.repo_owner}/{self.repo_name}/commit/{sha}"

                            markdown_content = f"# [COMMIT] {subject}\n\n"
                            markdown_content += f"**Repository:** {self.repo_owner}/{self.repo_name}\n"
                            markdown_content += f"**URL:** {html_url}\n"
                            markdown_content += f"**Author:** {author_name} <{author_email}>\n"
                            markdown_content += f"**SHA:** {sha}\n"
                            markdown_content += f"**Date:** {created_at.isoformat()}\n\n"
                            markdown_content += f"## Changes and Diff\n\n```diff\n{diff_output}\n```\n"

                            ingested_item = IngestedItem(
                                source_uri=html_url,
                                source_type=MemorySource.GITHUB_COMMIT,
                                title=f"Commit {sha[:7]}: {subject}",
                                content=markdown_content,
                                author=author_name,
                                external_id=sha,
                                external_timestamp=created_at,
                                tags=["github_commit", self.repo_name.lower(), sha[:7]],
                            )
                            items.append(ingested_item)
                            commit_count += 1
                        except Exception as e:
                            logger.warning("failed_to_parse_local_git_commit", error=str(e))
                            continue
                logger.info("local_git_clone_completed", total_ingested_items=len(items))
            except Exception as e:
                logger.exception("local_git_clone_failed", error=str(e))
            finally:
                # Clean up local worktree clone directory
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)

        return items

    async def fetch_by_id(self, external_id: str) -> IngestedItem | None:
        """Fetch a specific issue or pull request by number."""
        url = f"{self.BASE_API_URL}/repos/{self.repo_owner}/{self.repo_name}/issues/{external_id}"
        async with httpx.AsyncClient(headers=self.headers, timeout=15.0) as client:
            response = await client.get(url)
            if response.status_code != 200:
                return None

            issue = response.json()
            title = issue.get("title", "")
            body = issue.get("body") or ""
            author = issue.get("user", {}).get("login", "unknown")
            html_url = issue.get("html_url", "")
            created_at_str = issue.get("created_at", "")
            created_at = datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC) if created_at_str else datetime.now(UTC)
            is_pr = "pull_request" in issue
            source_type = MemorySource.GITHUB_PR if is_pr else MemorySource.GITHUB_ISSUE

            return IngestedItem(
                source_uri=html_url,
                source_type=source_type,
                title=f"GitHub #{external_id}: {title}",
                content=f"# {title}\n\n{body}",
                author=author,
                external_id=external_id,
                external_timestamp=created_at,
                tags=[source_type.value, self.repo_name.lower()],
            )

    def get_integration_type(self) -> IntegrationType:
        return IntegrationType.GITHUB
