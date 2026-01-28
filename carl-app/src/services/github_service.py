"""GitHub API service for infrastructure repository management."""
import requests
import json
from typing import Optional
from datetime import datetime


class GitHubService:
    """Service for GitHub repository operations via REST API."""

    def __init__(self, token: str, repo_owner: str, repo_name: str):
        self.token = token
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28"
        }

    def create_branch(self, branch_name: str, base_branch: str = "develop") -> dict:
        """Create a new branch from base branch."""
        # Get base branch SHA
        ref_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/ref/heads/{base_branch}"
        ref_resp = requests.get(ref_url, headers=self.headers, timeout=10)
        ref_resp.raise_for_status()
        base_sha = ref_resp.json()["object"]["sha"]

        # Create new branch
        create_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/refs"
        payload = {
            "ref": f"refs/heads/{branch_name}",
            "sha": base_sha
        }
        resp = requests.post(create_url, headers=self.headers, json=payload, timeout=10)
        resp.raise_for_status()
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
        ref_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/ref/heads/{branch}"
        ref_resp = requests.get(ref_url, headers=self.headers, timeout=10)
        ref_resp.raise_for_status()
        base_commit_sha = ref_resp.json()["object"]["sha"]

        # Get base tree
        commit_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/commits/{base_commit_sha}"
        commit_resp = requests.get(commit_url, headers=self.headers, timeout=10)
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
            blob_resp = requests.post(blob_url, headers=self.headers, json=blob_payload, timeout=10)
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
        tree_resp = requests.post(tree_url, headers=self.headers, json=tree_payload, timeout=10)
        tree_resp.raise_for_status()
        new_tree_sha = tree_resp.json()["sha"]

        # Create commit
        commit_create_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/commits"
        commit_payload = {
            "message": message,
            "tree": new_tree_sha,
            "parents": [base_commit_sha]
        }
        commit_create_resp = requests.post(commit_create_url, headers=self.headers, json=commit_payload, timeout=10)
        commit_create_resp.raise_for_status()
        new_commit_sha = commit_create_resp.json()["sha"]

        # Update branch reference
        update_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/refs/heads/{branch}"
        update_payload = {
            "sha": new_commit_sha,
            "force": False
        }
        update_resp = requests.patch(update_url, headers=self.headers, json=update_payload, timeout=10)
        update_resp.raise_for_status()

        return new_commit_sha

    def create_pull_request(self, title: str, body: str, head: str, base: str = "develop") -> dict:
        """Create a pull request."""
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls"
        payload = {
            "title": title,
            "body": body,
            "head": head,
            "base": base
        }
        resp = requests.post(url, headers=self.headers, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()
