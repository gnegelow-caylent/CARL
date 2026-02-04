"""
GitHub MCP Server for CARL
Provides tools for GitHub repository operations, PR creation, and code management.
"""

import os
import json
import base64
from typing import Optional
import boto3
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server


# Initialize MCP server
mcp = Server("github-mcp")

# AWS clients
secrets_client = boto3.client("secretsmanager")


def get_github_token() -> str:
    """Retrieve GitHub token from Secrets Manager."""
    secret_arn = os.environ.get("GITHUB_TOKEN_SECRET_ARN", "")
    if not secret_arn:
        raise ValueError("GITHUB_TOKEN_SECRET_ARN not configured")

    response = secrets_client.get_secret_value(SecretId=secret_arn)
    return response["SecretString"]


def github_request(method: str, endpoint: str, data: Optional[dict] = None) -> dict:
    """Make authenticated request to GitHub API."""
    import urllib.request
    import urllib.error

    token = get_github_token()
    url = f"https://api.github.com{endpoint}"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "CARL-MCP-GitHub"
    }

    request_data = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=request_data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        raise Exception(f"GitHub API error: {e.code} - {error_body}")


@mcp.tool()
def list_repositories(org: Optional[str] = None, user: Optional[str] = None) -> str:
    """
    List repositories for an organization or user.

    Args:
        org: Organization name (optional)
        user: Username (optional, defaults to authenticated user)

    Returns:
        JSON list of repositories with name, url, and description
    """
    if org:
        endpoint = f"/orgs/{org}/repos"
    elif user:
        endpoint = f"/users/{user}/repos"
    else:
        endpoint = "/user/repos"

    repos = github_request("GET", endpoint)

    result = [
        {
            "name": repo["name"],
            "full_name": repo["full_name"],
            "url": repo["html_url"],
            "description": repo.get("description", ""),
            "default_branch": repo["default_branch"],
            "private": repo["private"]
        }
        for repo in repos
    ]

    return json.dumps(result, indent=2)


@mcp.tool()
def get_file_contents(owner: str, repo: str, path: str, ref: Optional[str] = None) -> str:
    """
    Get contents of a file from a repository.

    Args:
        owner: Repository owner
        repo: Repository name
        path: Path to file in repository
        ref: Branch, tag, or commit SHA (optional)

    Returns:
        File contents as string
    """
    endpoint = f"/repos/{owner}/{repo}/contents/{path}"
    if ref:
        endpoint += f"?ref={ref}"

    response = github_request("GET", endpoint)

    if response.get("type") != "file":
        raise ValueError(f"Path {path} is not a file")

    content = base64.b64decode(response["content"]).decode("utf-8")
    return content


@mcp.tool()
def create_or_update_file(
    owner: str,
    repo: str,
    path: str,
    content: str,
    message: str,
    branch: Optional[str] = None
) -> str:
    """
    Create or update a file in a repository.

    Args:
        owner: Repository owner
        repo: Repository name
        path: Path for the file
        content: File content
        message: Commit message
        branch: Branch name (optional, uses default branch)

    Returns:
        JSON with commit details
    """
    endpoint = f"/repos/{owner}/{repo}/contents/{path}"

    # Check if file exists to get SHA
    sha = None
    try:
        existing = github_request("GET", endpoint + (f"?ref={branch}" if branch else ""))
        sha = existing.get("sha")
    except Exception:
        pass  # File doesn't exist, will create new

    data = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode()
    }

    if sha:
        data["sha"] = sha
    if branch:
        data["branch"] = branch

    result = github_request("PUT", endpoint, data)

    return json.dumps({
        "sha": result["commit"]["sha"],
        "url": result["content"]["html_url"],
        "message": "File created" if not sha else "File updated"
    }, indent=2)


@mcp.tool()
def create_branch(owner: str, repo: str, branch_name: str, from_branch: Optional[str] = None) -> str:
    """
    Create a new branch in a repository.

    Args:
        owner: Repository owner
        repo: Repository name
        branch_name: Name for the new branch
        from_branch: Source branch (optional, uses default branch)

    Returns:
        JSON with branch details
    """
    # Get source branch SHA
    if not from_branch:
        repo_info = github_request("GET", f"/repos/{owner}/{repo}")
        from_branch = repo_info["default_branch"]

    ref_info = github_request("GET", f"/repos/{owner}/{repo}/git/refs/heads/{from_branch}")
    sha = ref_info["object"]["sha"]

    # Create new branch
    result = github_request("POST", f"/repos/{owner}/{repo}/git/refs", {
        "ref": f"refs/heads/{branch_name}",
        "sha": sha
    })

    return json.dumps({
        "branch": branch_name,
        "sha": result["object"]["sha"],
        "url": f"https://github.com/{owner}/{repo}/tree/{branch_name}"
    }, indent=2)


@mcp.tool()
def create_pull_request(
    owner: str,
    repo: str,
    title: str,
    head: str,
    base: str,
    body: Optional[str] = None,
    draft: bool = False
) -> str:
    """
    Create a pull request.

    Args:
        owner: Repository owner
        repo: Repository name
        title: PR title
        head: Branch with changes
        base: Target branch
        body: PR description (optional)
        draft: Create as draft PR

    Returns:
        JSON with PR details including URL
    """
    data = {
        "title": title,
        "head": head,
        "base": base,
        "draft": draft
    }

    if body:
        data["body"] = body

    result = github_request("POST", f"/repos/{owner}/{repo}/pulls", data)

    return json.dumps({
        "number": result["number"],
        "url": result["html_url"],
        "state": result["state"],
        "draft": result["draft"],
        "mergeable": result.get("mergeable")
    }, indent=2)


@mcp.tool()
def list_pull_requests(
    owner: str,
    repo: str,
    state: str = "open",
    base: Optional[str] = None
) -> str:
    """
    List pull requests in a repository.

    Args:
        owner: Repository owner
        repo: Repository name
        state: Filter by state (open, closed, all)
        base: Filter by base branch (optional)

    Returns:
        JSON list of pull requests
    """
    endpoint = f"/repos/{owner}/{repo}/pulls?state={state}"
    if base:
        endpoint += f"&base={base}"

    prs = github_request("GET", endpoint)

    result = [
        {
            "number": pr["number"],
            "title": pr["title"],
            "url": pr["html_url"],
            "state": pr["state"],
            "draft": pr["draft"],
            "user": pr["user"]["login"],
            "head": pr["head"]["ref"],
            "base": pr["base"]["ref"],
            "created_at": pr["created_at"]
        }
        for pr in prs
    ]

    return json.dumps(result, indent=2)


@mcp.tool()
def create_terraform_pr(
    owner: str,
    repo: str,
    terraform_code: str,
    file_path: str,
    description: str,
    branch_prefix: str = "carl"
) -> str:
    """
    Create a PR with generated Terraform code.
    This is a convenience function that creates a branch, commits code, and opens a PR.

    Args:
        owner: Repository owner
        repo: Repository name
        terraform_code: The Terraform code to commit
        file_path: Path for the Terraform file (e.g., "modules/security/main.tf")
        description: Description of what this Terraform does
        branch_prefix: Prefix for branch name (default: carl)

    Returns:
        JSON with PR details
    """
    import time

    # Generate unique branch name
    timestamp = int(time.time())
    branch_name = f"{branch_prefix}/terraform-{timestamp}"

    # Create branch
    create_branch(owner, repo, branch_name)

    # Commit Terraform code
    commit_message = f"feat: Add Terraform configuration\n\n{description}"
    create_or_update_file(owner, repo, file_path, terraform_code, commit_message, branch_name)

    # Create PR
    pr_body = f"""## Summary
{description}

## Changes
- Added/updated Terraform configuration at `{file_path}`

## Generated by CARL
This PR was automatically generated by CARL (Cloud Automated Risk & Compliance Logic).

## Checklist
- [ ] Review Terraform code
- [ ] Run `terraform plan` to verify changes
- [ ] Approve and merge when ready
"""

    result = create_pull_request(
        owner=owner,
        repo=repo,
        title=f"[CARL] {description[:50]}",
        head=branch_name,
        base="main",
        body=pr_body
    )

    return result


# Run MCP server
if __name__ == "__main__":
    import asyncio
    asyncio.run(stdio_server(mcp))
