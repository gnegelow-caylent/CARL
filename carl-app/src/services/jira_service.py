"""
Jira Cloud API integration for CARL.

Handles bi-directional sync between CARL and Jira for:
- Security findings
- Risk exceptions
- Configuration drift
- Feature requests
- Infrastructure changes
"""
import os
import json
import boto3
import requests
from base64 import b64encode
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from botocore.exceptions import ClientError

from utils.logger import get_logger

logger = get_logger(__name__)


class JiraService:
    """Service for Jira Cloud API integration."""

    # Issue type IDs (set after project creation)
    ISSUE_TYPE_SECURITY_FINDING = "Security Finding"
    ISSUE_TYPE_RISK_EXCEPTION = "Risk Exception"
    ISSUE_TYPE_DRIFT = "Configuration Drift"
    ISSUE_TYPE_FEATURE = "Feature Request"
    ISSUE_TYPE_BUG = "Bug"
    ISSUE_TYPE_INFRA_CHANGE = "Infrastructure Change"

    # Project keys
    PROJECT_SECURITY = "CARLSEC"
    PROJECT_DEVELOPMENT = "CARLDEV"
    PROJECT_INFRASTRUCTURE = "CARLINFRA"

    def __init__(self):
        """Initialize Jira service with credentials from Secrets Manager."""
        self.jira_url = self._get_secret("/carl/prod/jira-url")
        self.jira_email = self._get_secret("/carl/prod/jira-email")
        api_token = self._get_secret("/carl/prod/jira-api-token")

        # Create Basic Auth header
        auth_str = f"{self.jira_email}:{api_token}"
        auth_bytes = b64encode(auth_str.encode()).decode()

        self.headers = {
            "Authorization": f"Basic {auth_bytes}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        self.base_url = f"{self.jira_url}/rest/api/3"

    def _get_secret(self, secret_name: str) -> str:
        """Get secret from AWS Secrets Manager."""
        try:
            secretsmanager = boto3.client('secretsmanager')
            response = secretsmanager.get_secret_value(SecretId=secret_name)
            return response['SecretString']
        except ClientError as e:
            logger.error(f"Error getting secret {secret_name}: {e}")
            raise

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make authenticated request to Jira API with error handling."""
        url = f"{self.base_url}/{endpoint}"

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                params=params,
                timeout=30
            )

            response.raise_for_status()

            # Some Jira endpoints return empty response
            if response.status_code == 204:
                return {"status": "success"}

            return response.json()

        except requests.exceptions.HTTPError as e:
            logger.error(f"Jira API error: {e.response.status_code} - {e.response.text}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            raise

    def _request(
        self,
        method: str,
        path: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make authenticated request to Jira API (handles full paths).

        This is an alias for _make_request that handles full REST API paths.
        """
        # Strip /rest/api/3 prefix if present to get endpoint
        endpoint = path
        if path.startswith("/rest/api/3/"):
            endpoint = path.replace("/rest/api/3/", "", 1)
        elif path.startswith("/rest/api/2/"):
            # Handle API v2 endpoints
            url = f"{self.jira_url}{path}"
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    json=data,
                    params=params,
                    timeout=30
                )
                response.raise_for_status()
                if response.status_code == 204:
                    return {"status": "success"}
                return response.json()
            except requests.exceptions.RequestException as e:
                logger.error(f"Jira API error: {e}")
                raise

        return self._make_request(method, endpoint, data, params)

    # ========================================================================
    # Security Findings
    # ========================================================================

    def create_security_finding(
        self,
        finding_id: str,
        title: str,
        severity: str,
        description: str,
        resource_arn: str,
        account_id: str,
        region: str,
        soc2_controls: List[str],
        compliance_status: str,
        first_detected: str
    ) -> str:
        """
        Create a Security Finding issue in Jira.

        Returns:
            Jira issue key (e.g., "CARLSEC-123")
        """
        # Map severity to Jira priority
        priority_map = {
            "CRITICAL": "Highest",
            "HIGH": "High",
            "MEDIUM": "Medium",
            "LOW": "Low",
            "INFORMATIONAL": "Lowest"
        }

        issue_data = {
            "fields": {
                "project": {"key": self.PROJECT_SECURITY},
                "summary": f"[{severity}] {title}",
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "heading",
                            "attrs": {"level": 2},
                            "content": [{"type": "text", "text": "Finding Details"}]
                        },
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": description}]
                        },
                        {
                            "type": "heading",
                            "attrs": {"level": 3},
                            "content": [{"type": "text", "text": "Affected Resource"}]
                        },
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": f"ARN: {resource_arn}"}]
                        },
                        {
                            "type": "heading",
                            "attrs": {"level": 3},
                            "content": [{"type": "text", "text": "SOC 2 Controls"}]
                        },
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": ", ".join(soc2_controls)}]
                        }
                    ]
                },
                "issuetype": {"name": self.ISSUE_TYPE_SECURITY_FINDING},
                "priority": {"name": priority_map.get(severity, "Medium")},
                "labels": ["security", "soc2", severity.lower()],
                # Custom fields (IDs will be set after field creation)
                # "customfield_10001": account_id,  # AWS Account ID
                # "customfield_10002": region,      # AWS Region
                # "customfield_10003": resource_arn, # Resource ARN
                # "customfield_10004": finding_id,   # Finding ID
                # "customfield_10005": soc2_controls, # SOC 2 Controls
                # "customfield_10006": compliance_status, # Compliance Status
                # "customfield_10007": first_detected, # First Detected
            }
        }

        result = self._make_request("POST", "issue", data=issue_data)
        issue_key = result.get("key")

        logger.info(f"Created Jira issue {issue_key} for finding {finding_id}")
        return issue_key

    def update_finding_status(self, issue_key: str, status: str) -> None:
        """Update the status of a Security Finding issue."""
        # Get available transitions
        transitions = self._make_request("GET", f"issue/{issue_key}/transitions")

        # Find transition ID for target status
        transition_id = None
        for transition in transitions.get("transitions", []):
            if transition["name"].lower() == status.lower():
                transition_id = transition["id"]
                break

        if not transition_id:
            logger.warning(f"No transition found for status: {status}")
            return

        # Perform transition
        self._make_request(
            "POST",
            f"issue/{issue_key}/transitions",
            data={"transition": {"id": transition_id}}
        )

        logger.info(f"Updated {issue_key} to status: {status}")

    def close_security_finding(self, issue_key: str, resolution: str = "Fixed") -> None:
        """Close a Security Finding issue."""
        self.update_finding_status(issue_key, "Closed")
        self.add_comment(issue_key, f"Finding resolved in AWS. Resolution: {resolution}")

    def update_finding_last_seen(self, issue_key: str) -> None:
        """Update the Last Seen timestamp for a finding."""
        # Update custom field for Last Seen
        # self._make_request(
        #     "PUT",
        #     f"issue/{issue_key}",
        #     data={
        #         "fields": {
        #             "customfield_10008": datetime.now(timezone.utc).isoformat()
        #         }
        #     }
        # )
        pass

    # ========================================================================
    # Risk Exceptions
    # ========================================================================

    def create_exception_request(
        self,
        finding_title: str,
        requested_by: str,
        business_justification: str,
        compensating_controls: str,
        expiration_date: str,
        risk_level: str,
        related_finding_key: Optional[str] = None
    ) -> str:
        """
        Create a Risk Exception request in Jira.

        Returns:
            Jira issue key
        """
        issue_data = {
            "fields": {
                "project": {"key": self.PROJECT_SECURITY},
                "summary": f"Exception Request: {finding_title}",
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "heading",
                            "attrs": {"level": 2},
                            "content": [{"type": "text", "text": "Business Justification"}]
                        },
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": business_justification}]
                        },
                        {
                            "type": "heading",
                            "attrs": {"level": 2},
                            "content": [{"type": "text", "text": "Compensating Controls"}]
                        },
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": compensating_controls}]
                        }
                    ]
                },
                "issuetype": {"name": self.ISSUE_TYPE_RISK_EXCEPTION},
                "labels": ["exception", "risk-acceptance", risk_level.lower()],
                # Custom fields
                # "customfield_10020": requested_by,
                # "customfield_10021": business_justification,
                # "customfield_10022": compensating_controls,
                # "customfield_10023": expiration_date,
                # "customfield_10024": risk_level,
            }
        }

        # Link to related finding if provided
        result = self._make_request("POST", "issue", data=issue_data)
        issue_key = result.get("key")

        if related_finding_key:
            self.link_issues(issue_key, related_finding_key, "relates to")

        logger.info(f"Created exception request {issue_key}")
        return issue_key

    def approve_exception(self, issue_key: str, approved_by: str, comments: str) -> None:
        """Approve a risk exception request."""
        self.update_finding_status(issue_key, "Approved")
        self.add_comment(issue_key, f"Approved by {approved_by}: {comments}")

        logger.info(f"Approved exception {issue_key}")

    def deny_exception(self, issue_key: str, denied_by: str, reason: str) -> None:
        """Deny a risk exception request."""
        self.update_finding_status(issue_key, "Denied")
        self.add_comment(issue_key, f"Denied by {denied_by}: {reason}")

        logger.info(f"Denied exception {issue_key}")

    def mark_exception_expiring(self, issue_key: str, days_remaining: int) -> None:
        """Mark exception as expiring soon."""
        self.update_finding_status(issue_key, "Expiring")
        self.add_comment(
            issue_key,
            f"⚠️ This exception will expire in {days_remaining} days. "
            "Please review and renew if necessary."
        )

    # ========================================================================
    # Configuration Drift
    # ========================================================================

    def create_drift_ticket(
        self,
        resource_type: str,
        resource_id: str,
        expected_state: str,
        actual_state: str,
        drift_type: str,
        impact_level: str,
        environment: str
    ) -> str:
        """
        Create a Configuration Drift ticket in Jira.

        Returns:
            Jira issue key
        """
        issue_data = {
            "fields": {
                "project": {"key": self.PROJECT_SECURITY},
                "summary": f"Drift Detected: {resource_type} - {resource_id}",
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "heading",
                            "attrs": {"level": 2},
                            "content": [{"type": "text", "text": "Expected State"}]
                        },
                        {
                            "type": "codeBlock",
                            "content": [{"type": "text", "text": expected_state}]
                        },
                        {
                            "type": "heading",
                            "attrs": {"level": 2},
                            "content": [{"type": "text", "text": "Actual State"}]
                        },
                        {
                            "type": "codeBlock",
                            "content": [{"type": "text", "text": actual_state}]
                        }
                    ]
                },
                "issuetype": {"name": self.ISSUE_TYPE_DRIFT},
                "labels": ["drift", "configuration", environment],
                # Custom fields
                # "customfield_10030": resource_type,
                # "customfield_10031": resource_id,
                # "customfield_10032": expected_state,
                # "customfield_10033": actual_state,
                # "customfield_10034": drift_type,
                # "customfield_10035": impact_level,
                # "customfield_10036": environment,
            }
        }

        result = self._make_request("POST", "issue", data=issue_data)
        issue_key = result.get("key")

        logger.info(f"Created drift ticket {issue_key} for {resource_id}")
        return issue_key

    def acknowledge_drift(self, issue_key: str, acknowledged_by: str, reason: str) -> None:
        """Acknowledge drift as expected."""
        self.update_finding_status(issue_key, "Acknowledged")
        self.add_comment(issue_key, f"Acknowledged by {acknowledged_by}: {reason}")

    def mark_drift_remediated(self, issue_key: str) -> None:
        """Mark drift as remediated (triggers verification)."""
        self.update_finding_status(issue_key, "Remediated")
        self.add_comment(issue_key, "Drift has been remediated. Awaiting verification.")

    # ========================================================================
    # Feature Requests (CARL Development)
    # ========================================================================

    def create_feature_request(
        self,
        title: str,
        description: str,
        requested_by: str,
        use_case: str,
        expected_benefit: str
    ) -> str:
        """
        Create a Feature Request in CARLDEV project.

        Returns:
            Jira issue key
        """
        issue_data = {
            "fields": {
                "project": {"key": self.PROJECT_DEVELOPMENT},
                "summary": title,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "heading",
                            "attrs": {"level": 2},
                            "content": [{"type": "text", "text": "Description"}]
                        },
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": description}]
                        },
                        {
                            "type": "heading",
                            "attrs": {"level": 2},
                            "content": [{"type": "text", "text": "Use Case"}]
                        },
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": use_case}]
                        },
                        {
                            "type": "heading",
                            "attrs": {"level": 2},
                            "content": [{"type": "text", "text": "Expected Benefit"}]
                        },
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": expected_benefit}]
                        }
                    ]
                },
                "issuetype": {"name": self.ISSUE_TYPE_FEATURE},
                "labels": ["feature", "user-request"],
                # Custom fields
                # "customfield_10040": requested_by,
                # "customfield_10041": use_case,
                # "customfield_10042": expected_benefit,
                # "customfield_10043": 1,  # Initial vote count
            }
        }

        result = self._make_request("POST", "issue", data=issue_data)
        issue_key = result.get("key")

        logger.info(f"Created feature request {issue_key}")
        return issue_key

    def vote_on_feature(self, issue_key: str) -> int:
        """
        Increment vote count on a feature request.

        Returns:
            New vote count
        """
        # Jira has a built-in voting system
        self._make_request("POST", f"issue/{issue_key}/votes")

        # Get updated vote count
        issue = self._make_request("GET", f"issue/{issue_key}")
        votes = issue.get("fields", {}).get("votes", {}).get("votes", 0)

        logger.info(f"Voted on {issue_key}, new count: {votes}")
        return votes

    # ========================================================================
    # Infrastructure Changes
    # ========================================================================

    def create_infrastructure_change(
        self,
        pr_number: int,
        pr_title: str,
        pr_url: str,
        author: str,
        repository: str,
        branch: str,
        environment: str,
        resources_changed: int,
        terraform_plan: str
    ) -> str:
        """
        Create an Infrastructure Change ticket linked to GitHub PR.

        Returns:
            Jira issue key
        """
        issue_data = {
            "fields": {
                "project": {"key": self.PROJECT_INFRASTRUCTURE},
                "summary": f"PR #{pr_number}: {pr_title}",
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": "GitHub PR: "},
                                {"type": "text", "text": pr_url, "marks": [{"type": "link", "attrs": {"href": pr_url}}]}
                            ]
                        },
                        {
                            "type": "heading",
                            "attrs": {"level": 2},
                            "content": [{"type": "text", "text": "Terraform Plan Summary"}]
                        },
                        {
                            "type": "codeBlock",
                            "content": [{"type": "text", "text": terraform_plan[:5000]}]  # Limit size
                        }
                    ]
                },
                "issuetype": {"name": self.ISSUE_TYPE_INFRA_CHANGE},
                "labels": ["infrastructure", "terraform", environment],
                # Custom fields
                # "customfield_10050": pr_url,
                # "customfield_10051": pr_number,
                # "customfield_10052": author,
                # "customfield_10053": repository,
                # "customfield_10054": branch,
                # "customfield_10055": environment,
                # "customfield_10056": resources_changed,
                # "customfield_10057": terraform_plan,
            }
        }

        result = self._make_request("POST", "issue", data=issue_data)
        issue_key = result.get("key")

        logger.info(f"Created infrastructure change {issue_key} for PR #{pr_number}")
        return issue_key

    def update_deployment_status(
        self,
        issue_key: str,
        status: str,
        result: Optional[str] = None
    ) -> None:
        """Update deployment status for infrastructure change."""
        self.update_finding_status(issue_key, status)

        if result:
            self.add_comment(issue_key, f"Deployment result: {result}")

    # ========================================================================
    # Common Operations
    # ========================================================================

    def add_comment(self, issue_key: str, comment: str) -> None:
        """Add a comment to an issue."""
        comment_data = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": comment}]
                    }
                ]
            }
        }

        self._make_request("POST", f"issue/{issue_key}/comment", data=comment_data)
        logger.info(f"Added comment to {issue_key}")

    def link_issues(
        self,
        inward_issue: str,
        outward_issue: str,
        link_type: str = "relates to"
    ) -> None:
        """Create a link between two issues."""
        link_data = {
            "type": {"name": link_type},
            "inwardIssue": {"key": inward_issue},
            "outwardIssue": {"key": outward_issue}
        }

        self._make_request("POST", "issueLink", data=link_data)
        logger.info(f"Linked {inward_issue} to {outward_issue}")

    def get_issue(self, issue_key: str) -> Dict[str, Any]:
        """Get issue details."""
        return self._make_request("GET", f"issue/{issue_key}")

    def search_issues(self, jql: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Search for issues using JQL."""
        params = {
            "jql": jql,
            "maxResults": max_results
        }

        result = self._make_request("GET", "search", params=params)
        return result.get("issues", [])

    def test_connection(self) -> Dict[str, Any]:
        """Test Jira API connectivity."""
        try:
            result = self._make_request("GET", "myself")
            return {
                "status": "ok",
                "user": result.get("displayName"),
                "email": result.get("emailAddress")
            }
        except Exception as e:
            logger.error(f"Jira connection test failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
