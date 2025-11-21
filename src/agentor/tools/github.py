from typing import Optional

from agentor.tools.base import BaseTool, capability

try:
    from github import Github as PyGithub
    from github import GithubException
except ImportError:
    PyGithub = None
    GithubException = Exception


class GitHubTool(BaseTool):
    name = "github"
    description = "Interact with GitHub repositories."

    def __init__(self, access_token: str, api_key: Optional[str] = None):
        if PyGithub is None:
            raise ImportError(
                "GitHub dependency is missing. Please install it with `pip install agentor[github]`."
            )
        super().__init__(api_key)
        self.client = PyGithub(access_token)

    @capability
    def get_issue(self, repo_name: str, issue_number: int) -> str:
        """Get details of a GitHub issue."""
        try:
            repo = self.client.get_repo(repo_name)
            issue = repo.get_issue(issue_number)
            return f"Title: {issue.title}\nBody: {issue.body}\nState: {issue.state}"
        except GithubException as e:
            return f"GitHub Error: {e.data.get('message', str(e))}"
        except Exception as e:
            return f"Error: {str(e)}"

    @capability
    def create_issue(self, repo_name: str, title: str, body: str = "") -> str:
        """Create a new issue in a repository."""
        try:
            repo = self.client.get_repo(repo_name)
            issue = repo.create_issue(title=title, body=body)
            return f"Issue created: {issue.html_url}"
        except GithubException as e:
            return f"GitHub Error: {e.data.get('message', str(e))}"
        except Exception as e:
            return f"Error: {str(e)}"

    @capability
    def create_pr(
        self,
        repo_name: str,
        title: str,
        head: str,
        base: str = "main",
        body: str = "",
    ) -> str:
        """Create a pull request."""
        try:
            repo = self.client.get_repo(repo_name)
            pr = repo.create_pull(title=title, body=body, head=head, base=base)
            return f"PR created: {pr.html_url}"
        except GithubException as e:
            return f"GitHub Error: {e.data.get('message', str(e))}"
        except Exception as e:
            return f"Error: {str(e)}"
