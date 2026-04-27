"""GitHub PR activity for vault worker."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from temporalio import activity

_client_factory: Callable[[str], Any] | None = None


def configure_github_client(factory: Callable[[str], Any] | None) -> None:
    global _client_factory
    _client_factory = factory


@dataclass
class CreatePRInput:
    repo_owner: str
    repo_name: str
    token: str
    pr_branch: str
    title: str
    body: str
    base_branch: str = "main"


@activity.defn
def create_github_pr(input: CreatePRInput) -> str:
    factory = _client_factory
    if factory is None:
        raise RuntimeError("GitHub client factory not configured; call configure_github_client() first")
    client = factory(input.token)
    pr = client.create_pull(
        title=input.title,
        body=input.body,
        head=input.pr_branch,
        base=input.base_branch,
    )
    return pr.html_url
