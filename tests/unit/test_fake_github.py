"""Unit tests for FakeGitHubClient mock."""
from tests.mocks.fake_github import FakeGitHubClient, FakePR


def test_fake_pr_has_html_url():
    """FakePR should have an html_url attribute."""
    pr = FakePR(html_url="https://fake.invalid/owner/repo/pull/1")
    assert pr.html_url == "https://fake.invalid/owner/repo/pull/1"
    assert isinstance(pr.html_url, str)


def test_create_pull_records_call():
    """create_pull should record the call in prs_created."""
    client = FakeGitHubClient()
    assert len(client.prs_created) == 0

    pr = client.create_pull(
        title="Test PR",
        body="Test body",
        head="feature-branch",
        base="main"
    )

    assert len(client.prs_created) == 1
    assert client.prs_created[0]["title"] == "Test PR"
    assert client.prs_created[0]["body"] == "Test body"
    assert client.prs_created[0]["head"] == "feature-branch"
    assert client.prs_created[0]["base"] == "main"


def test_create_pull_returns_fake_pr():
    """create_pull should return a FakePR with non-empty html_url."""
    client = FakeGitHubClient()
    pr = client.create_pull(
        title="Test PR",
        body="Test body",
        head="feature-branch",
        base="main"
    )

    assert isinstance(pr, FakePR)
    assert isinstance(pr.html_url, str)
    assert len(pr.html_url) > 0


def test_create_pull_increments_url():
    """create_pull should return different URLs for each call."""
    client = FakeGitHubClient()

    pr1 = client.create_pull(
        title="PR 1",
        body="Body 1",
        head="branch-1",
        base="main"
    )
    pr2 = client.create_pull(
        title="PR 2",
        body="Body 2",
        head="branch-2",
        base="main"
    )

    assert pr1.html_url != pr2.html_url
    assert len(client.prs_created) == 2
