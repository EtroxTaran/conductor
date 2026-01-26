"""Git integration router for project git operations."""

import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..config import get_settings

router = APIRouter(prefix="/projects/{project_name}/git", tags=["git"])


class GitInfo(BaseModel):
    """Git repository information."""

    branch: str
    commit: str
    is_dirty: bool
    repo_url: str | None = None
    last_commit_msg: str | None = None
    dirty_files: list[str] = []
    ahead: int = 0
    behind: int = 0


class GitCommit(BaseModel):
    """Git commit information."""

    hash: str
    short_hash: str
    message: str
    author: str
    author_email: str
    date: str
    files_changed: int = 0


class GitLog(BaseModel):
    """Git log response."""

    commits: list[GitCommit]
    total: int


class GitDiff(BaseModel):
    """Git diff response."""

    diff: str
    files: list[str]
    insertions: int
    deletions: int


def _get_project_dir(project_name: str) -> Path:
    """Get project directory path."""
    settings = get_settings()
    project_dir = settings.projects_path / project_name
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")
    return project_dir


def _run_git(project_dir: Path, args: list[str]) -> str:
    """Run a git command in the project directory."""
    try:
        return subprocess.check_output(
            ["git"] + args,
            cwd=project_dir,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Git command failed: {' '.join(args)}") from e


def _is_git_repo(project_dir: Path) -> bool:
    """Check if directory is a git repository."""
    return (project_dir / ".git").exists()


@router.get("/info", response_model=GitInfo)
async def get_git_info(project_name: str) -> GitInfo:
    """Get git repository information for a project."""
    project_dir = _get_project_dir(project_name)

    if not _is_git_repo(project_dir):
        raise HTTPException(status_code=400, detail="Project is not a git repository")

    # Get branch
    try:
        branch = _run_git(project_dir, ["rev-parse", "--abbrev-ref", "HEAD"])
    except HTTPException:
        branch = "unknown"

    # Get commit hash
    try:
        commit = _run_git(project_dir, ["rev-parse", "--short", "HEAD"])
    except HTTPException:
        commit = "unknown"

    # Get dirty status and files
    try:
        status = _run_git(project_dir, ["status", "--porcelain"])
        is_dirty = bool(status)
        dirty_files = [line[3:] for line in status.split("\n") if line] if status else []
    except HTTPException:
        is_dirty = False
        dirty_files = []

    # Get remote URL
    try:
        repo_url = _run_git(project_dir, ["remote", "get-url", "origin"])
    except HTTPException:
        repo_url = None

    # Get last commit message
    try:
        last_commit_msg = _run_git(project_dir, ["log", "-1", "--pretty=%s"])
    except HTTPException:
        last_commit_msg = None

    # Get ahead/behind
    ahead = 0
    behind = 0
    try:
        tracking = _run_git(
            project_dir, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]
        )
        if tracking:
            rev_list = _run_git(
                project_dir, ["rev-list", "--left-right", "--count", f"HEAD...{tracking}"]
            )
            parts = rev_list.split()
            if len(parts) == 2:
                ahead = int(parts[0])
                behind = int(parts[1])
    except HTTPException:
        pass

    return GitInfo(
        branch=branch,
        commit=commit,
        is_dirty=is_dirty,
        repo_url=repo_url,
        last_commit_msg=last_commit_msg,
        dirty_files=dirty_files,
        ahead=ahead,
        behind=behind,
    )


@router.get("/log", response_model=GitLog)
async def get_git_log(
    project_name: str,
    limit: int = Query(default=20, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
) -> GitLog:
    """Get git commit history for a project."""
    project_dir = _get_project_dir(project_name)

    if not _is_git_repo(project_dir):
        raise HTTPException(status_code=400, detail="Project is not a git repository")

    # Get total commit count
    try:
        total_str = _run_git(project_dir, ["rev-list", "--count", "HEAD"])
        total = int(total_str)
    except (HTTPException, ValueError):
        total = 0

    # Get commit log with formatting
    # Format: hash|short_hash|message|author|email|date
    format_str = "%H|%h|%s|%an|%ae|%ci"
    try:
        log_output = _run_git(
            project_dir,
            ["log", f"--skip={skip}", f"-{limit}", f"--pretty=format:{format_str}"],
        )
    except HTTPException:
        return GitLog(commits=[], total=0)

    commits = []
    for line in log_output.split("\n"):
        if not line:
            continue
        parts = line.split("|", 5)
        if len(parts) >= 6:
            # Get files changed for this commit
            try:
                stat = _run_git(
                    project_dir,
                    ["diff-tree", "--no-commit-id", "--name-only", "-r", parts[0]],
                )
                files_changed = len([f for f in stat.split("\n") if f])
            except HTTPException:
                files_changed = 0

            commits.append(
                GitCommit(
                    hash=parts[0],
                    short_hash=parts[1],
                    message=parts[2],
                    author=parts[3],
                    author_email=parts[4],
                    date=parts[5],
                    files_changed=files_changed,
                )
            )

    return GitLog(commits=commits, total=total)


@router.get("/diff", response_model=GitDiff)
async def get_git_diff(
    project_name: str,
    staged: bool = Query(default=False, description="Show only staged changes"),
) -> GitDiff:
    """Get git diff for uncommitted changes."""
    project_dir = _get_project_dir(project_name)

    if not _is_git_repo(project_dir):
        raise HTTPException(status_code=400, detail="Project is not a git repository")

    # Get diff
    diff_args = ["diff"]
    if staged:
        diff_args.append("--staged")

    try:
        diff_output = _run_git(project_dir, diff_args)
    except HTTPException:
        diff_output = ""

    # Get changed files
    name_args = ["diff", "--name-only"]
    if staged:
        name_args.append("--staged")

    try:
        files_output = _run_git(project_dir, name_args)
        files = [f for f in files_output.split("\n") if f]
    except HTTPException:
        files = []

    # Get stat
    stat_args = ["diff", "--stat"]
    if staged:
        stat_args.append("--staged")

    insertions = 0
    deletions = 0
    try:
        stat_output = _run_git(project_dir, stat_args)
        # Parse the summary line like "3 files changed, 10 insertions(+), 5 deletions(-)"
        for line in stat_output.split("\n"):
            if "insertion" in line or "deletion" in line:
                parts = line.split(",")
                for part in parts:
                    if "insertion" in part:
                        insertions = int("".join(filter(str.isdigit, part)) or "0")
                    elif "deletion" in part:
                        deletions = int("".join(filter(str.isdigit, part)) or "0")
    except HTTPException:
        pass

    return GitDiff(
        diff=diff_output,
        files=files,
        insertions=insertions,
        deletions=deletions,
    )
