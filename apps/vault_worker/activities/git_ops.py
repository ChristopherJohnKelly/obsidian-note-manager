"""Git operations as Temporal Activities.

All four functions are synchronous ``def`` (not ``async def``).  GitPython's
clone_from, pull, commit, and push are fully blocking calls that can each take
several seconds.  Defining the Activity as ``def`` causes the Temporal Python
SDK to execute it automatically in a ``ThreadPoolExecutor``, keeping the
asyncio event loop free for heartbeats and signal processing during the
blocking work.

PAT authentication is applied only to ``https://`` URLs.  Local ``file://``
paths and bare repo paths used in tests are passed through unchanged.
"""

from __future__ import annotations

from temporalio import activity
from git import Repo
from git.exc import GitCommandError


def _sanitize_git_error(exc: GitCommandError, pat: str) -> GitCommandError:
    """Return a new GitCommandError with the PAT redacted from the command line.

    GitPython's GitCommandError includes the full command line in its ``args``
    attribute, which for clone operations contains the authenticated URL with the
    PAT visible.  This function replaces any occurrence of the PAT in the command
    list with ``***`` before returning a new exception with the same class and
    message but sanitized command.
    """
    # exc.args is a tuple: (command, status, stderr, stdout?)
    # where command is a list of strings.
    if len(exc.args) >= 1 and isinstance(exc.args[0], list):
        cmd = exc.args[0].copy()
        sanitized = False
        for i, part in enumerate(cmd):
            if pat in part:
                cmd[i] = part.replace(pat, "***")
                sanitized = True
        if sanitized:
            new_args = (cmd,) + exc.args[1:]
            return exc.__class__(*new_args)
    return exc


@activity.defn
def git_clone(repo_url: str, target_path: str, pat: str) -> None:
    """Clone *repo_url* into *target_path*.

    For ``https://`` URLs the PAT is injected into the URL so the clone
    authenticates without an interactive prompt::

        https://<pat>@github.com/owner/repo.git

    Non-https URLs (local paths, ``file://``) are used as-is — no PAT
    injection — which allows tests to clone from a local bare repository.

    Synchronous def: Temporal runs this in a ThreadPoolExecutor automatically.
    Do not convert to async def — GitPython is blocking and clone can take
    many seconds on large repositories.
    """
    if repo_url.startswith("https://"):
        authed_url = repo_url.replace("https://", f"https://{pat}@", 1)
    else:
        authed_url = repo_url
    try:
        Repo.clone_from(authed_url, target_path)
    except GitCommandError as exc:
        # Redact PAT from the error to avoid credential leaks
        raise _sanitize_git_error(exc, pat) from None


@activity.defn
def git_pull(vault_path: str) -> None:
    """Pull the latest commits from origin into the local repository at *vault_path*.

    Calling this on an already up-to-date repository is safe (idempotent).

    Synchronous def — see :func:`git_clone` docstring for rationale.
    """
    repo = Repo(vault_path)
    repo.remotes.origin.pull()


@activity.defn
def git_commit(vault_path: str, message: str) -> str:
    """Stage all working-tree changes and create a commit with *message*.

    Returns the full 40-character hex SHA of the new commit.

    Raises :class:`ValueError` if there is nothing to commit (no modified,
    added, or deleted files).  This prevents silent no-ops that would leave the
    caller believing a commit was made when none was.

    Synchronous def — see :func:`git_clone` docstring for rationale.
    """
    repo = Repo(vault_path)

    # Check for any uncommitted changes (tracked or untracked) before staging.
    if not repo.is_dirty(untracked_files=True):
        raise ValueError(
            "Nothing to commit: repository has no staged or unstaged changes."
        )

    # Stage everything — mirrors `git add -A`.
    repo.git.add(A=True)

    commit = repo.index.commit(message)
    return commit.hexsha


@activity.defn
def git_push(vault_path: str) -> None:
    """Push all local commits to origin.

    Synchronous def — see :func:`git_clone` docstring for rationale.

    Raises:
        GitCommandError: If the push is rejected by the remote (non‑fast‑forward,
            insufficient permissions, etc.) or any other Git error occurs.
    """
    repo = Repo(vault_path)
    push_results = repo.remotes.origin.push()
    for info in push_results:
        # Check for error flags that indicate push failure
        error_flags = (
            info.ERROR
            | info.REJECTED
            | info.REMOTE_REJECTED
            | info.REMOTE_FAILURE
            | info.NO_MATCH
        )
        if info.flags & error_flags:
            # Construct an error message similar to GitPython's own exception
            # The summary often contains a short status like "[rejected]"
            raise GitCommandError(
                command=["git", "push", "origin", "HEAD"],
                status=1,
                stderr=info.summary.strip() if info.summary else "Push rejected",
            )
