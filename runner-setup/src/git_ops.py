import os
from git import Repo, Actor
from git.exc import GitCommandError


class GitOps:
    def __init__(self, repo_path: str):
        """
        Initialize GitOps with the repository path.
        
        Args:
            repo_path: Path to the git repository root
        """
        self.repo = Repo(repo_path)
        # Configure the "user" for these commits
        self.actor = Actor("Obsidian Librarian", "librarian@automation.local")

    def has_changes(self) -> bool:
        """
        Check if the repository has uncommitted changes.
        
        Returns:
            bool: True if there are changes, False otherwise
        """
        return self.repo.is_dirty(untracked_files=True)

    def commit_and_push(self, message: str):
        """
        Stages all changes, commits, and pushes to remote.
        
        Args:
            message: Commit message
            
        Raises:
            GitCommandError: If git operations fail
        """
        if not self.has_changes():
            print("💤 No changes to commit.")
            return

        try:
            print(f"📦 Committing: {message}")
            # Stage all changes (including deletions and untracked files)
            self.repo.git.add(A=True)
            
            # Commit with custom actor
            self.repo.index.commit(message, author=self.actor, committer=self.actor)
            
            print("🚀 Pushing to remote...")
            origin = self.repo.remote(name='origin')
            origin.push()
            print("✅ Push complete.")
            
        except GitCommandError as e:
            print(f"❌ Git operation failed: {e}")
            raise e
