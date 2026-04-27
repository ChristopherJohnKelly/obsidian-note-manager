"""Unit tests for create_github_pr activity."""
from apps.vault_worker.activities.github_ops import (
    CreatePRInput,
    configure_github_client,
    create_github_pr,
)
from tests.mocks.fake_github import FakeGitHubClient


def test_create_github_pr_with_fake_client():
    """create_github_pr should work with FakeGitHubClient injected via factory."""
    try:
        configure_github_client(lambda token: FakeGitHubClient())

        input_data = CreatePRInput(
            repo_owner="test-owner",
            repo_name="test-repo",
            token="fake-token",
            pr_branch="feature-branch",
            title="Test PR",
            body="Test PR body",
            base_branch="main"
        )

        result = create_github_pr(input_data)

        assert isinstance(result, str)
        assert result.startswith("https://")
    finally:
        configure_github_client(None)


def test_create_github_pr_uses_input_parameters():
    """create_github_pr should pass input parameters to create_pull."""
    fake_client = FakeGitHubClient()

    try:
        configure_github_client(lambda token: fake_client)

        input_data = CreatePRInput(
            repo_owner="my-owner",
            repo_name="my-repo",
            token="test-token-123",
            pr_branch="feature-x",
            title="Add new feature",
            body="This PR adds feature X",
            base_branch="develop"
        )

        create_github_pr(input_data)

        assert len(fake_client.prs_created) == 1
        call = fake_client.prs_created[0]
        assert call["title"] == "Add new feature"
        assert call["body"] == "This PR adds feature X"
        assert call["head"] == "feature-x"
        assert call["base"] == "develop"
    finally:
        configure_github_client(None)


def test_create_github_pr_returns_pr_html_url():
    """create_github_pr should return the PR's html_url."""
    fake_client = FakeGitHubClient()

    try:
        configure_github_client(lambda token: fake_client)

        input_data = CreatePRInput(
            repo_owner="owner",
            repo_name="repo",
            token="token",
            pr_branch="branch",
            title="Title",
            body="Body",
            base_branch="main"
        )

        url = create_github_pr(input_data)

        assert isinstance(url, str)
        assert len(url) > 0
        assert len(fake_client.prs_created) == 1
    finally:
        configure_github_client(None)


def test_configure_github_client_resets_factory():
    """configure_github_client(None) should reset the factory for cleanup."""
    fake_client1 = FakeGitHubClient()

    try:
        configure_github_client(lambda token: fake_client1)

        input_data = CreatePRInput(
            repo_owner="owner",
            repo_name="repo",
            token="token",
            pr_branch="branch",
            title="Title",
            body="Body",
            base_branch="main"
        )

        create_github_pr(input_data)
        assert len(fake_client1.prs_created) == 1
    finally:
        configure_github_client(None)
