#!/usr/bin/env python3
"""
Git sync script for an Obsidian vault.
- Pulls if remote has new commits
- Pushes if local has new commits
- Handles merge conflicts by renaming conflicted files
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# --- Load configuration ---
load_dotenv()

VAULT_DIR = Path(os.getenv("VAULT_DIR", str(Path.home() / "vault")))
LOGFILE = Path(os.getenv("LOGFILE", "/tmp/vault_git_sync.log"))
GITHUB_URL = os.getenv("GITHUB_URL")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
BRANCH = os.getenv("BRANCH", "main")


def log(message: str, also_print: bool = False) -> None:
    """Append a timestamped message to the log file and optionally print to stdout."""
    with LOGFILE.open("a") as f:
        timestamp = datetime.now().isoformat(timespec="seconds")
        f.write(f"[{timestamp}] {message}\n")
    if also_print:
        print(message)


def run_git_command(
    args: list[str], allow_fail: bool = False
) -> subprocess.CompletedProcess:
    """Run a git command in the vault directory and return the result."""
    return subprocess.run(
        ["git"] + args,
        cwd=VAULT_DIR,
        check=not allow_fail,
        text=True,
        capture_output=True,
    )


def check_vault_dir() -> None:
    """Ensure VAULT_DIR exists and is a git repository."""
    if not VAULT_DIR.exists():
        log(f"[ERROR] VAULT_DIR does not exist: {VAULT_DIR}")
        sys.exit(1)
    if not (VAULT_DIR / ".git").exists():
        log(f"[ERROR] VAULT_DIR is not a git repository: {VAULT_DIR}")
        sys.exit(1)


def set_authenticated_remote() -> None:
    """Ensure that the remote origin URL includes the token for HTTPS auth."""
    if not GITHUB_URL or not GITHUB_TOKEN:
        log("[ERROR] GITHUB_URL and GITHUB_TOKEN must be defined in the environment.")
        sys.exit(1)
    # Avoid logging the token
    authenticated_url = GITHUB_URL.replace("https://", f"https://{GITHUB_TOKEN}@")
    run_git_command(["remote", "set-url", "origin", authenticated_url])


def get_commit_delta() -> tuple[int, int]:
    """Return the number of commits (ahead, behind) local is relative to origin."""
    run_git_command(["fetch"])
    ahead = int(
        run_git_command(
            ["rev-list", "--count", f"origin/{BRANCH}..{BRANCH}"]
        ).stdout.strip()
    )
    behind = int(
        run_git_command(
            ["rev-list", "--count", f"{BRANCH}..origin/{BRANCH}"]
        ).stdout.strip()
    )
    return ahead, behind


def has_uncommitted_changes() -> bool:
    """Return True if there are any uncommitted changes."""
    result = subprocess.run(
        ["git", "status", "--porcelain"], cwd=VAULT_DIR, capture_output=True, text=True
    )
    return bool(result.stdout.strip())


def stash_local_changes() -> None:
    """Stash any local changes (tracked or untracked)."""
    run_git_command(
        ["stash", "--include-untracked", "-m", "Auto-stash before pull"],
        allow_fail=True,
    )


def restore_stash_if_needed() -> None:
    """Attempt to pop only the stash created by this script, if present."""
    stash_list = run_git_command(["stash", "list"], allow_fail=True).stdout
    for line in stash_list.splitlines():
        if "Auto-stash before pull" in line:
            stash_ref = line.split(":")[0]
            run_git_command(["stash", "pop", stash_ref], allow_fail=True)
            break


def handle_merge_conflicts() -> None:
    """Rename conflicted files with a '_conflicted' suffix and mark as resolved."""
    status = run_git_command(["status", "--porcelain"], allow_fail=True).stdout
    for line in status.splitlines():
        if line.startswith("UU "):
            file_path = line[3:].strip()
            src = VAULT_DIR / file_path
            dest = src.with_name(src.stem + "_conflicted" + src.suffix)
            if src.exists():
                src.rename(dest)
                run_git_command(["add", str(dest)])


def get_first_diff_line() -> str:
    """Return the first non-empty line of the staged diff, or empty string if none."""
    result = run_git_command(["diff", "--cached", "--unified=0"], allow_fail=True)
    for line in result.stdout.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            content = line[1:].strip()
            if content:
                return content
    return ""


def get_commit_message() -> str:
    """Build a commit message with the first diff line and a timestamp."""
    first_line = get_first_diff_line()
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M")
    if first_line:
        return f"{first_line} [{timestamp}]"
    else:
        return f"EVENTLOG update [{timestamp}]"


def sync_vault() -> None:
    """Main sync routine."""
    log("=== Starting vault sync ===", also_print=True)
    check_vault_dir()
    set_authenticated_remote()

    # If there are uncommitted changes, commit and push them first
    if has_uncommitted_changes():
        log("Uncommitted changes found; committing and pushing...", also_print=True)
        run_git_command(["add", "-A"])
        try:
            commit_msg = get_commit_message()
            run_git_command(["commit", "-m", commit_msg])
        except subprocess.CalledProcessError:
            log("Nothing to commit.", also_print=True)
        run_git_command(["push", "origin", BRANCH])
        log("Push completed.", also_print=True)

    ahead, behind = get_commit_delta()
    log(f"Commits ahead: {ahead}, behind: {behind}", also_print=True)

    if behind > 0:
        log("Pulling from remote...", also_print=True)
        try:
            run_git_command(["pull", "--rebase", "origin", BRANCH])
        except subprocess.CalledProcessError:
            log(
                "Merge conflict during pull. Renaming conflicted files.",
                also_print=True,
            )
            handle_merge_conflicts()

    # If there are new commits after pull, push them
    ahead, _ = get_commit_delta()
    if ahead > 0:
        log("Pushing new commits after pull...", also_print=True)
        run_git_command(["push", "origin", BRANCH])
        log("Push completed.", also_print=True)

    restore_stash_if_needed()
    log("=== Vault sync complete ===\n", also_print=True)
    print(f"See log file for details: {LOGFILE}")


if __name__ == "__main__":
    import sys

    try:
        sync_vault()
    except Exception as e:
        log(f"[ERROR] {str(e)}", also_print=True)
        sys.exit(1)
