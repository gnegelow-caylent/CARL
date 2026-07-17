"""GitHub API service for infrastructure repository management."""
import requests
import json
from typing import Optional, Callable
from datetime import datetime


class GitHubService:
    """Service for GitHub repository operations via REST API."""

    def __init__(self, token_or_provider, repo_owner: str, repo_name: str):
        """
        Initialize GitHub service.

        Args:
            token_or_provider: Either a static token (str) or a callable that returns a token
            repo_owner: GitHub organization or user
            repo_name: Repository name
        """
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.base_url = "https://api.github.com"

        # Support both static token and token provider (for GitHub App)
        if callable(token_or_provider):
            self._token_provider = token_or_provider
            self._static_token = None
        else:
            self._token_provider = None
            self._static_token = token_or_provider

    def _get_headers(self) -> dict:
        """Get headers with fresh token."""
        token = self._static_token if self._static_token else self._token_provider()
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28"
        }

    def is_repository_empty(self) -> bool:
        """
        Check if repository is empty (no commits).

        Returns True if the default branch doesn't exist yet.
        """
        default_branch = self.get_default_branch()
        branch_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/branches/{default_branch}"
        resp = requests.get(branch_url, headers=self._get_headers(), timeout=10)
        # 404 = branch doesn't exist = empty repo
        # 200 = branch exists = repo has commits
        return resp.status_code == 404

    def get_default_branch(self) -> str:
        """Get the repository's default branch name."""
        repo_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}"
        resp = requests.get(repo_url, headers=self._get_headers(), timeout=10)
        resp.raise_for_status()
        return resp.json().get("default_branch", "main")

    def initialize_repository(self, initial_message: str = "chore: Initialize infrastructure repository") -> str:
        """
        Initialize an empty repository with a README using Contents API.

        The Contents API works on empty repos, unlike the Git API which requires
        an existing commit.

        Returns:
            SHA of the initial commit
        """
        import base64

        # Create initial README content
        readme_content = f"# {self.repo_name}\n\nInfrastructure deployments managed by CARL.\n"
        encoded_content = base64.b64encode(readme_content.encode()).decode()

        # Get default branch name
        default_branch = self.get_default_branch()

        # Create README using Contents API (works on empty repos)
        contents_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/contents/README.md"
        payload = {
            "message": initial_message,
            "content": encoded_content,
            "branch": default_branch
        }
        resp = requests.put(contents_url, headers=self._get_headers(), json=payload, timeout=10)
        resp.raise_for_status()

        # Return commit SHA
        return resp.json()["commit"]["sha"]

    def branch_exists(self, branch_name: str) -> bool:
        """Check if a branch exists."""
        from urllib.parse import quote
        # URL encode branch name (forward slashes must be %2F)
        encoded_branch = quote(branch_name, safe='')
        branch_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/branches/{encoded_branch}"
        resp = requests.get(branch_url, headers=self._get_headers(), timeout=10)
        return resp.status_code == 200

    def delete_branch(self, branch_name: str) -> None:
        """Delete a branch."""
        from urllib.parse import quote
        # URL encode branch name (forward slashes must be %2F)
        encoded_branch = quote(branch_name, safe='')
        ref_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/refs/heads/{encoded_branch}"
        resp = requests.delete(ref_url, headers=self._get_headers(), timeout=10)
        resp.raise_for_status()

    def create_branch(self, branch_name: str, base_branch: str = None, force: bool = False) -> dict:
        """
        Create a new branch from base branch.

        Args:
            branch_name: Name of the new branch
            base_branch: Base branch to branch from. If None, uses default branch.
                        If repository is empty, initializes it first.
            force: If True and branch exists, delete and recreate it

        Returns:
            Branch info dict
        """
        # Check if repository is empty
        if self.is_repository_empty():
            # Initialize repository with first commit
            self.initialize_repository("chore: Initialize infrastructure repository")

        # Use default branch if not specified
        if base_branch is None:
            base_branch = self.get_default_branch()

        # Check if branch already exists
        if self.branch_exists(branch_name):
            if force:
                # Delete existing branch and recreate
                self.delete_branch(branch_name)
            else:
                # Branch exists and force=False, return existing branch info
                branch_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/branches/{branch_name}"
                resp = requests.get(branch_url, headers=self._get_headers(), timeout=10)
                resp.raise_for_status()
                return resp.json()

        # Get base branch SHA
        ref_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/refs/heads/{base_branch}"
        ref_resp = requests.get(ref_url, headers=self._get_headers(), timeout=10)
        ref_resp.raise_for_status()
        base_sha = ref_resp.json()["object"]["sha"]

        # Create new branch
        create_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/refs"
        payload = {
            "ref": f"refs/heads/{branch_name}",
            "sha": base_sha
        }
        resp = requests.post(create_url, headers=self._get_headers(), json=payload, timeout=10)
        if resp.status_code != 201:
            # Log detailed error for debugging
            error_detail = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
            raise requests.exceptions.HTTPError(
                f"{resp.status_code} {resp.reason} for url: {resp.url}. "
                f"GitHub said: {error_detail}. "
                f"Payload: {payload}",
                response=resp
            )
        return resp.json()

    def commit_files(self, branch: str, files: dict[str, str], message: str) -> str:
        """
        Commit multiple files to a branch.

        Args:
            branch: Branch name
            files: Dict of {file_path: file_content}
            message: Commit message

        Returns:
            Commit SHA
        """
        # Get latest commit on branch
        ref_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/refs/heads/{branch}"
        ref_resp = requests.get(ref_url, headers=self._get_headers(), timeout=10)
        ref_resp.raise_for_status()
        base_commit_sha = ref_resp.json()["object"]["sha"]

        # Get base tree
        commit_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/commits/{base_commit_sha}"
        commit_resp = requests.get(commit_url, headers=self._get_headers(), timeout=10)
        commit_resp.raise_for_status()
        base_tree_sha = commit_resp.json()["tree"]["sha"]

        # Create blobs for each file
        tree_items = []
        for file_path, content in files.items():
            blob_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/blobs"
            blob_payload = {
                "content": content,
                "encoding": "utf-8"
            }
            blob_resp = requests.post(blob_url, headers=self._get_headers(), json=blob_payload, timeout=10)
            blob_resp.raise_for_status()
            blob_sha = blob_resp.json()["sha"]

            tree_items.append({
                "path": file_path,
                "mode": "100644",
                "type": "blob",
                "sha": blob_sha
            })

        # Create tree
        tree_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/trees"
        tree_payload = {
            "base_tree": base_tree_sha,
            "tree": tree_items
        }
        tree_resp = requests.post(tree_url, headers=self._get_headers(), json=tree_payload, timeout=10)
        tree_resp.raise_for_status()
        new_tree_sha = tree_resp.json()["sha"]

        # Create commit
        commit_create_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/commits"
        commit_payload = {
            "message": message,
            "tree": new_tree_sha,
            "parents": [base_commit_sha]
        }
        commit_create_resp = requests.post(commit_create_url, headers=self._get_headers(), json=commit_payload, timeout=10)
        commit_create_resp.raise_for_status()
        new_commit_sha = commit_create_resp.json()["sha"]

        # Update branch reference
        update_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/refs/heads/{branch}"
        update_payload = {
            "sha": new_commit_sha,
            "force": False
        }
        update_resp = requests.patch(update_url, headers=self._get_headers(), json=update_payload, timeout=10)
        update_resp.raise_for_status()

        return new_commit_sha

    def create_pull_request(self, title: str, body: str, head: str, base: str = "develop") -> dict:
        """
        Create a pull request, or return existing PR if one already exists for this branch.

        Args:
            title: PR title
            body: PR description
            head: Head branch name
            base: Base branch name

        Returns:
            PR info dict
        """
        # Check if PR already exists for this head branch
        list_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls"
        list_params = {"head": f"{self.repo_owner}:{head}", "base": base, "state": "open"}
        list_resp = requests.get(list_url, headers=self._get_headers(), params=list_params, timeout=10)
        list_resp.raise_for_status()
        existing_prs = list_resp.json()

        if existing_prs:
            # PR already exists, update it
            pr = existing_prs[0]
            update_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls/{pr['number']}"
            update_payload = {"title": title, "body": body}
            update_resp = requests.patch(update_url, headers=self._get_headers(), json=update_payload, timeout=10)
            update_resp.raise_for_status()
            return update_resp.json()

        # Create new PR
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls"
        payload = {
            "title": title,
            "body": body,
            "head": head,
            "base": base
        }
        resp = requests.post(url, headers=self._get_headers(), json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()
