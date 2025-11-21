import sys
from types import ModuleType
from typing import Optional

from agentor.tools.base import BaseTool, capability

try:
    import git
except ImportError:
    git = ModuleType("git")

    class _MissingGitDependency(Exception):
        """Raised when gitpython dependency is not installed."""

    class Repo:  # type: ignore
        def __init__(self, *args, **kwargs):
            raise _MissingGitDependency(
                "Git dependency is missing. Please install it with `pip install agentor[git]`."
            )

    git.Repo = Repo  # type: ignore[attr-defined]
    sys.modules["git"] = git


class GitTool(BaseTool):
    name = "git"
    description = "Execute Git commands on a repository."

    def __init__(self, api_key: Optional[str] = None):
        if git is None:
            raise ImportError(
                "Git dependency is missing. Please install it with `pip install agentor[git]`."
            )
        super().__init__(api_key)

    @capability
    def clone(self, repo_url: str, to_path: str) -> str:
        """Clone a repository."""
        try:
            git.Repo.clone_from(repo_url, to_path)
            return f"Cloned {repo_url} to {to_path}"
        except Exception as e:
            return f"Error cloning repository: {str(e)}"

    @capability
    def pull(self, repo_path: str) -> str:
        """Pull changes from remote."""
        try:
            repo = git.Repo(repo_path)
            origin = repo.remotes.origin
            origin.pull()
            return "Successfully pulled changes."
        except Exception as e:
            return f"Error pulling changes: {str(e)}"

    @capability
    def commit(self, repo_path: str, message: str) -> str:
        """Commit changes."""
        try:
            repo = git.Repo(repo_path)
            repo.git.add(A=True)
            repo.index.commit(message)
            return f"Committed with message: {message}"
        except Exception as e:
            return f"Error committing changes: {str(e)}"

    @capability
    def push(self, repo_path: str) -> str:
        """Push changes to remote."""
        try:
            repo = git.Repo(repo_path)
            origin = repo.remotes.origin
            origin.push()
            return "Successfully pushed changes."
        except Exception as e:
            return f"Error pushing changes: {str(e)}"

    @capability
    def status(self, repo_path: str) -> str:
        """Get repository status."""
        try:
            repo = git.Repo(repo_path)
            return repo.git.status()
        except Exception as e:
            return f"Error getting status: {str(e)}"
