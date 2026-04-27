"""Fake GitHub client for unit testing."""
from dataclasses import dataclass


@dataclass
class FakePR:
    html_url: str


class FakeGitHubClient:
    def __init__(self):
        self.prs_created: list[dict] = []
        self._counter = 0

    def create_pull(self, title: str, body: str, head: str, base: str) -> FakePR:
        self._counter += 1
        self.prs_created.append({"title": title, "body": body, "head": head, "base": base})
        return FakePR(html_url=f"https://fake.invalid/owner/repo/pull/{self._counter}")
