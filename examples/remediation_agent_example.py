"""
Example: Remediation Agent using AWS Bedrock Agents

This shows how to build an autonomous remediation agent that:
1. Investigates findings
2. Determines remediation approach
3. Generates fixes (Terraform/CLI)
4. Creates PRs
5. Verifies fixes

Uses AWS Bedrock Agents (native service) - no custom orchestration needed.

Estimated Effort: 2 weeks
Cost: ~$0.01 per remediation
Impact: HIGH - autonomous fixing of security issues
"""

import json
import boto3
from typing import Dict, Any


class RemediationAgent:
    """
    Autonomous remediation agent using AWS Bedrock Agents.

    This wraps the Bedrock Agent service and provides CARL-specific
    tools for investigating and fixing security findings.
    """

    def __init__(self, agent_id: str, agent_alias_id: str = "PROD"):
        """
        Initialize remediation agent.

        Args:
            agent_id: Bedrock Agent ID (created in AWS console or CDK)
            agent_alias_id: Agent alias (PROD, DEV, etc.)
        """
        self.client = boto3.client('bedrock-agent-runtime')
        self.agent_id = agent_id
        self.agent_alias_id = agent_alias_id

    def remediate_finding(
        self,
        finding_id: str,
        account_id: str,
        auto_apply: bool = False,
        session_id: str = None
    ) -> Dict[str, Any]:
        """
        Autonomously remediate a security finding.

        The agent will:
        1. Retrieve finding details
        2. Investigate current resource state
        3. Determine remediation approach
        4. Generate fix (Terraform/CLI)
        5. Create PR or apply directly (if auto_apply=True)
        6. Verify fix

        Args:
            finding_id: CARL finding ID
            account_id: AWS account ID
            auto_apply: If True, apply fix directly (requires approval workflow)
            session_id: Optional session ID for continuity

        Returns:
            Dict with remediation results including PR URL, status, etc.
        """
        session_id = session_id or self._generate_session_id()

        # Invoke Bedrock Agent with task
        task = self._build_remediation_task(finding_id, account_id, auto_apply)

        response = self.client.invoke_agent(
            agentId=self.agent_id,
            agentAliasId=self.agent_alias_id,
            sessionId=session_id,
            inputText=task
        )

        # Process agent's streaming response
        result = self._process_agent_response(response)

        return result

    def _build_remediation_task(
        self,
        finding_id: str,
        account_id: str,
        auto_apply: bool
    ) -> str:
        """Build natural language task for agent."""
        task = f"""Please remediate finding {finding_id} in AWS account {account_id}.

Steps to follow:
1. Use get_finding tool to retrieve finding details
2. Use check_resource_state tool to verify current configuration
3. Analyze the issue and determine best remediation approach
4. Use generate_fix tool to create Terraform or CLI fix
5. Use create_github_pr tool to create a pull request with the fix
6. Provide a summary of what was done

{'IMPORTANT: This is a dry-run. Create PR but do not apply changes.' if not auto_apply else 'IMPORTANT: After creating PR, also apply the fix if it is safe to do so.'}

Be thorough in your analysis. If you're unsure about anything, ask for clarification."""

        return task

    def _process_agent_response(self, response: dict) -> Dict[str, Any]:
        """Process streaming response from Bedrock Agent."""
        result = {
            "status": "in_progress",
            "steps_taken": [],
            "pr_url": None,
            "applied": False,
            "error": None,
            "agent_reasoning": [],
            "tool_calls": []
        }

        # Process event stream
        event_stream = response.get('completion', [])

        for event in event_stream:
            if 'chunk' in event:
                # Agent output chunk
                chunk = event['chunk']
                if 'bytes' in chunk:
                    text = chunk['bytes'].decode('utf-8')
                    result["steps_taken"].append(text)

            elif 'trace' in event:
                # Tool invocation or reasoning trace
                trace = event['trace']['trace']

                if 'orchestrationTrace' in trace:
                    # Agent reasoning
                    reasoning = trace['orchestrationTrace']
                    if 'rationale' in reasoning:
                        result["agent_reasoning"].append(reasoning['rationale']['text'])

                elif 'invocationInput' in trace:
                    # Tool being called
                    invocation = trace['invocationInput']
                    if 'actionGroupInvocationInput' in invocation:
                        action = invocation['actionGroupInvocationInput']
                        result["tool_calls"].append({
                            "tool": action.get('actionGroupName'),
                            "function": action.get('function'),
                            "parameters": action.get('parameters', [])
                        })

                elif 'observation' in trace:
                    # Tool result
                    observation = trace['observation']
                    if 'actionGroupInvocationOutput' in observation:
                        output = observation['actionGroupInvocationOutput']
                        # Extract PR URL if present
                        if 'pr_url' in str(output):
                            # Parse JSON response from tool
                            try:
                                tool_response = json.loads(output.get('text', '{}'))
                                result["pr_url"] = tool_response.get('pr_url')
                            except:
                                pass

        result["status"] = "completed" if not result.get("error") else "failed"
        return result

    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        import uuid
        return f"carl-remediation-{uuid.uuid4()}"


# ============================================================================
# Agent Tools (Lambda Functions)
# ============================================================================
# These are Lambda functions registered with the Bedrock Agent
# Each tool has a specific purpose and is called by the agent as needed

def get_finding_tool(finding_id: str, account_id: str) -> Dict[str, Any]:
    """
    Tool: Get finding details from DynamoDB.

    This is called by the Bedrock Agent to retrieve finding information.
    """
    from services.findings_service import FindingsService

    findings_service = FindingsService()
    finding = findings_service.get_finding(finding_id, account_id)

    if not finding:
        return {
            "success": False,
            "error": f"Finding {finding_id} not found"
        }

    return {
        "success": True,
        "finding": {
            "id": finding.get("id"),
            "title": finding.get("title"),
            "severity": finding.get("severity"),
            "resource_type": finding.get("resource_type"),
            "resource_id": finding.get("resource_id"),
            "resource_arn": finding.get("resource_arn"),
            "description": finding.get("description"),
            "remediation_steps": finding.get("remediation_steps"),
            "control_ids": finding.get("control_ids", [])
        }
    }


def check_resource_state_tool(resource_arn: str) -> Dict[str, Any]:
    """
    Tool: Check current state of AWS resource.

    Queries AWS API to get current configuration.
    """
    import boto3

    # Parse ARN to determine resource type
    # arn:aws:s3:::bucket-name
    # arn:aws:iam::123456789012:user/username
    # etc.

    parts = resource_arn.split(':')
    service = parts[2]
    resource = ':'.join(parts[5:]) if len(parts) > 5 else parts[-1]

    try:
        if service == 's3':
            # Check S3 bucket configuration
            s3 = boto3.client('s3')
            bucket_name = resource

            # Check encryption
            try:
                encryption = s3.get_bucket_encryption(Bucket=bucket_name)
                has_encryption = True
            except s3.exceptions.ServerSideEncryptionConfigurationNotFoundError:
                has_encryption = False

            # Check versioning
            versioning = s3.get_bucket_versioning(Bucket=bucket_name)
            has_versioning = versioning.get('Status') == 'Enabled'

            # Check public access block
            try:
                pab = s3.get_public_access_block(Bucket=bucket_name)
                public_access_blocked = all([
                    pab['PublicAccessBlockConfiguration'].get('BlockPublicAcls'),
                    pab['PublicAccessBlockConfiguration'].get('IgnorePublicAcls'),
                    pab['PublicAccessBlockConfiguration'].get('BlockPublicPolicy'),
                    pab['PublicAccessBlockConfiguration'].get('RestrictPublicBuckets')
                ])
            except:
                public_access_blocked = False

            return {
                "success": True,
                "resource_type": "s3_bucket",
                "resource_id": bucket_name,
                "current_state": {
                    "encryption_enabled": has_encryption,
                    "versioning_enabled": has_versioning,
                    "public_access_blocked": public_access_blocked
                }
            }

        elif service == 'iam':
            # Check IAM user/role/policy
            iam = boto3.client('iam')

            if 'user' in resource:
                username = resource.split('/')[-1]
                user = iam.get_user(UserName=username)

                # Check MFA
                mfa_devices = iam.list_mfa_devices(UserName=username)
                has_mfa = len(mfa_devices['MFADevices']) > 0

                # Check access keys
                access_keys = iam.list_access_keys(UserName=username)
                key_ages = []
                for key in access_keys['AccessKeyMetadata']:
                    age_days = (datetime.now() - key['CreateDate'].replace(tzinfo=None)).days
                    key_ages.append(age_days)

                return {
                    "success": True,
                    "resource_type": "iam_user",
                    "resource_id": username,
                    "current_state": {
                        "mfa_enabled": has_mfa,
                        "access_key_count": len(access_keys['AccessKeyMetadata']),
                        "oldest_key_age_days": max(key_ages) if key_ages else 0
                    }
                }

        # Add more resource types as needed...

        return {
            "success": False,
            "error": f"Resource type {service} not yet supported"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def generate_fix_tool(
    finding: Dict[str, Any],
    current_state: Dict[str, Any],
    fix_type: str = "terraform"
) -> Dict[str, Any]:
    """
    Tool: Generate Terraform or CLI fix for finding.

    Uses AI to generate appropriate fix based on finding and current state.
    """
    from services.bedrock_service import BedrockService

    bedrock = BedrockService()

    prompt = f"""Generate a {fix_type} fix for this security finding:

FINDING:
Title: {finding['title']}
Resource: {finding['resource_type']} - {finding['resource_id']}
Issue: {finding['description']}

CURRENT STATE:
{json.dumps(current_state, indent=2)}

EXPECTED STATE:
{finding.get('remediation_steps', 'Follow AWS best practices')}

Generate a complete, working {fix_type} {'script' if fix_type == 'cli' else 'configuration'} that:
1. Fixes the security issue
2. Is safe to apply (no data loss)
3. Follows AWS best practices
4. Includes comments explaining what it does

{'For Terraform: Use proper resource names, include provider config, add depends_on if needed.' if fix_type == 'terraform' else 'For CLI: Use aws CLI commands, include error handling, verify success.'}

Output ONLY the code, no explanations before or after."""

    fix_code = bedrock.invoke_model(prompt, max_tokens=2048, temperature=0.3)

    return {
        "success": True,
        "fix_type": fix_type,
        "fix_code": fix_code,
        "safe_to_apply": True,  # Could add safety checks here
        "estimated_time_seconds": 30
    }


def create_github_pr_tool(
    finding_id: str,
    title: str,
    description: str,
    fix_code: str,
    fix_type: str
) -> Dict[str, Any]:
    """
    Tool: Create GitHub pull request with fix.

    Creates PR in infrastructure repository.
    """
    # This would use GitHub API or gh CLI
    # Simplified example:

    import subprocess
    import tempfile
    import os

    try:
        # Create temporary directory
        with tempfile.TemporaryDirectory() as tmpdir:
            # Clone repo
            repo_url = os.environ.get('GITHUB_INFRA_REPO_URL')
            subprocess.run(['git', 'clone', repo_url, tmpdir], check=True)

            # Create branch
            branch_name = f"carl-fix-{finding_id}"
            subprocess.run(['git', 'checkout', '-b', branch_name], cwd=tmpdir, check=True)

            # Write fix file
            filename = f"carl-fix-{finding_id}.{' tf' if fix_type == 'terraform' else 'sh'}"
            filepath = os.path.join(tmpdir, 'fixes', filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            with open(filepath, 'w') as f:
                f.write(fix_code)

            # Commit and push
            subprocess.run(['git', 'add', filepath], cwd=tmpdir, check=True)
            subprocess.run(['git', 'commit', '-m', f'fix: {title}\n\n{description}'], cwd=tmpdir, check=True)
            subprocess.run(['git', 'push', 'origin', branch_name], cwd=tmpdir, check=True)

            # Create PR using gh CLI
            result = subprocess.run(
                ['gh', 'pr', 'create', '--title', title, '--body', description],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                check=True
            )

            pr_url = result.stdout.strip()

            return {
                "success": True,
                "pr_url": pr_url,
                "branch_name": branch_name
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================================
# Example Usage
# ============================================================================

def example_remediation_workflow():
    """Example of using remediation agent."""

    # Initialize agent (assumes agent is created in AWS)
    agent = RemediationAgent(
        agent_id="AGENT123456",  # From AWS Bedrock Agents console
        agent_alias_id="PROD"
    )

    # Remediate a finding
    finding_id = "finding-abc123"
    account_id = "123456789012"

    print(f"🤖 Starting remediation for {finding_id}...")

    result = agent.remediate_finding(
        finding_id=finding_id,
        account_id=account_id,
        auto_apply=False  # Dry-run: create PR but don't apply
    )

    print(f"\n✅ Remediation Status: {result['status']}")
    print(f"\n📋 Agent Reasoning:")
    for reasoning in result['agent_reasoning']:
        print(f"  - {reasoning}")

    print(f"\n🔧 Tool Calls Made:")
    for tool_call in result['tool_calls']:
        print(f"  - {tool_call['tool']}.{tool_call['function']}()")

    if result.get('pr_url'):
        print(f"\n🔗 Pull Request: {result['pr_url']}")

    print(f"\n📝 Steps Taken:")
    for step in result['steps_taken']:
        print(f"  {step}")


if __name__ == "__main__":
    example_remediation_workflow()
