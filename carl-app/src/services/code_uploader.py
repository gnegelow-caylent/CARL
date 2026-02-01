"""Orchestrates Terraform code upload to GitHub and Slack."""
import json
import re
from datetime import datetime
from typing import Any
from services.github_service import GitHubService
from services.slack_service import SlackService


class CodeUploader:
    """Handles uploading generated Terraform code to GitHub and posting to Slack."""

    def __init__(self, github: GitHubService, slack: SlackService):
        self.github = github
        self.slack = slack

    def upload_and_notify(
        self,
        channel_id: str,
        user_id: str,
        blueprint_name: str,
        terraform_files: dict = None,
        terraform_code: str = None,  # Deprecated - for backwards compatibility
        metadata: dict[str, Any] = None
    ) -> dict:
        """
        Complete upload flow:
        1. Create GitHub branch
        2. Commit Terraform files
        3. Create Pull Request
        4. Post summary to Slack channel
        5. Post code to thread
        6. Upload file to Slack

        Args:
            terraform_files: Dict with keys: variables, main, outputs, tfvars_example, readme
            terraform_code: (Deprecated) Single main.tf content - for backwards compatibility

        Returns dict with GitHub and Slack info.
        """
        if metadata is None:
            metadata = {}

        # Handle backwards compatibility
        if terraform_files is None and terraform_code is not None:
            terraform_files = {'main': terraform_code}

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        blueprint_short = blueprint_name.replace("/", "-")

        # 1. Get or create branch (without timestamp to avoid duplicates)
        # If branch exists, we'll just commit to it (no delete/recreate)
        branch_name = f"feature/{user_id}/{blueprint_short}"

        # Check if branch exists
        branch_existed = self.github.branch_exists(branch_name)
        if not branch_existed:
            # Create new branch from default branch
            self.github.create_branch(branch_name, base_branch=None, force=False)
        # If branch exists, we'll just commit to it (updates it automatically)

        # 2. Prepare files (no timestamp in path - overwrites previous version)
        deployment_path = f"deployments/users/{user_id}/{blueprint_short}"
        files = {}

        # Add Terraform files (standard structure)
        if 'variables' in terraform_files:
            files[f"{deployment_path}/variables.tf"] = terraform_files['variables']
        if 'main' in terraform_files:
            files[f"{deployment_path}/main.tf"] = terraform_files['main']
        if 'outputs' in terraform_files:
            files[f"{deployment_path}/outputs.tf"] = terraform_files['outputs']
        if 'tfvars_example' in terraform_files:
            files[f"{deployment_path}/terraform.tfvars.example"] = terraform_files['tfvars_example']
        if 'readme' in terraform_files:
            files[f"{deployment_path}/README.md"] = terraform_files['readme']
        if 'providers' in terraform_files:
            files[f"{deployment_path}/providers.tf"] = terraform_files['providers']
        if 'versions' in terraform_files:
            files[f"{deployment_path}/versions.tf"] = terraform_files['versions']

        # Handle files with path separators (e.g., "account-requests/security.tf")
        for key, content in terraform_files.items():
            if '/' in key and key not in ['variables', 'main', 'outputs', 'tfvars_example', 'readme', 'providers', 'versions']:
                files[f"{deployment_path}/{key}"] = content

        # Add standard files
        files[f"{deployment_path}/backend.tf"] = self._generate_backend_config(deployment_path)
        files[f"{deployment_path}/.gitignore"] = self._generate_gitignore()
        files[f"{deployment_path}/metadata.json"] = json.dumps(metadata, indent=2)

        # 3. Commit files
        action = "Update" if branch_existed else "Add"
        commit_message = self._format_commit_message(user_id, blueprint_name, metadata, action, timestamp)
        commit_sha = self.github.commit_files(branch_name, files, commit_message)

        # 4. Create PR (target default branch)
        pr_title = f"Deploy {blueprint_name}"
        pr_body = self._format_pr_body(blueprint_name, metadata)
        base_branch = self.github.get_default_branch()
        pr = self.github.create_pull_request(pr_title, pr_body, branch_name, base=base_branch)

        # 5. Post to Slack channel (summary)
        summary_msg = self.slack.post_message(
            channel_id,
            blocks=self._build_summary_blocks(blueprint_name, pr, metadata)
        )

        # 6. Post code to thread (adaptive: full for small, summary for large)
        thread_ts = summary_msg.get("ts")
        main_tf_code = terraform_files.get('main', '')
        self._post_code_to_thread(channel_id, thread_ts, main_tf_code, blueprint_name, metadata, terraform_files)

        # 7. Upload files to Slack (optional - if this fails, we still succeed)
        try:
            action_text = "Updated" if branch_existed else "Created"
            # Upload main.tf as primary file
            if main_tf_code:
                self.slack.upload_file(
                    channels=[channel_id],
                    content=main_tf_code,
                    filename=f"{blueprint_short}_{timestamp}_main.tf",
                    title=f"Terraform main.tf: {blueprint_name} ({action_text})",
                    initial_comment=f"{action_text} code for PR #{pr['number']}: {pr['html_url']}\n\n📁 Complete module includes: variables.tf, main.tf, outputs.tf, README.md"
                )
        except Exception as e:
            # Log error but don't fail the whole operation
            # Code is still in GitHub PR and Slack thread
            logger = __import__('utils.logger', fromlist=['get_logger']).get_logger(__name__)
            logger.warning(f"Failed to upload file to Slack: {e}")

        return {
            "branch": branch_name,
            "commit_sha": commit_sha,
            "pr_number": pr["number"],
            "pr_url": pr["html_url"],
            "slack_ts": thread_ts
        }

    def _generate_backend_config(self, deployment_path: str) -> str:
        """Generate S3 backend configuration."""
        return f"""terraform {{
  backend "s3" {{
    bucket         = "carl-tfstate-${{data.aws_caller_identity.current.account_id}}"
    key            = "{deployment_path}/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "carl-tfstate-locks"
  }}
}}
"""

    def _generate_gitignore(self) -> str:
        """Generate .gitignore for Terraform."""
        return """# Local .terraform directories
**/.terraform/*

# .tfstate files
*.tfstate
*.tfstate.*

# Crash log files
crash.log
crash.*.log

# Exclude all .tfvars files, which are likely to contain sensitive data
*.tfvars
*.tfvars.json

# Ignore override files as they are usually used to override resources locally
override.tf
override.tf.json
*_override.tf
*_override.tf.json

# Ignore CLI configuration files
.terraformrc
terraform.rc

# Ignore lock file (should be committed, but excluding for generated code)
.terraform.lock.hcl
"""

    def _format_commit_message(self, user_id: str, blueprint: str, metadata: dict, action: str = "Add", timestamp: str = None) -> str:
        """Format commit message."""
        return f"""{action.lower()}(infra): {blueprint}

Generated by: CARL Infrastructure Builder
User: {user_id}
Blueprint: {blueprint}
Timestamp: {timestamp or datetime.now().isoformat()}
Config: {metadata.get('config', {})}

Compliance: {', '.join(metadata.get('compliance_notes', [])[:3])}

Co-Authored-By: CARL Bot <noreply@carl.ai>
"""

    def _format_pr_body(self, blueprint: str, metadata: dict) -> str:
        """Format PR description."""
        soc2_controls = metadata.get('soc2_controls', [])
        security_practices = metadata.get('security_practices', [])
        notes = metadata.get('compliance_notes', [])

        pr_body = f"""## Infrastructure Deployment: {blueprint}

### Generated by CARL

**Requirement:** {metadata.get('requirement', 'N/A')}

"""

        # Add SOC 2 controls section if available
        if soc2_controls:
            pr_body += f"""### 🔐 SOC 2 Controls Addressed

{chr(10).join([f'- {control}' for control in sorted(soc2_controls)])}

"""

        # Add security practices section if available
        if security_practices:
            pr_body += f"""### ✅ Security Best Practices Implemented

{chr(10).join([f'- {practice}' for practice in security_practices[:10]])}

"""

        # Add compliance notes if available
        if notes:
            pr_body += f"""### 📋 Additional Compliance Notes

{chr(10).join([f'- {n}' for n in notes[:5]])}

"""

        pr_body += """### Next Steps

1. Review the Terraform code in this PR
2. Check README.md for SOC 2 controls and security recommendations
3. GitHub Actions will validate and generate a plan
4. Review the plan output carefully
5. Update terraform.tfvars with environment-specific values
6. Merge this PR to deploy to dev
7. Run `apply-dev` workflow manually to apply changes

---
🤖 Generated by [CARL Infrastructure Builder](https://github.com/your-org/CARL)
"""
        return pr_body

    def _build_summary_blocks(self, blueprint: str, pr: dict, metadata: dict) -> list[dict]:
        """Build Slack blocks for summary message."""
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"✅ Infrastructure Code Generated"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Blueprint:*\n{blueprint}"},
                    {"type": "mrkdwn", "text": f"*Pull Request:*\n<{pr['html_url']}|#{pr['number']}>"}
                ]
            }
        ]

        # Add SOC 2 controls if available
        soc2_controls = metadata.get('soc2_controls', [])
        if soc2_controls:
            controls_text = ", ".join(sorted(soc2_controls)[:8])
            if len(soc2_controls) > 8:
                controls_text += f" +{len(soc2_controls) - 8} more"
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🔐 SOC 2 Controls:*\n{controls_text}"
                }
            })

        # Add security practices if available
        security_practices = metadata.get('security_practices', [])
        if security_practices:
            practices_text = "\n".join([f"• {p}" for p in security_practices[:5]])
            if len(security_practices) > 5:
                practices_text += f"\n• +{len(security_practices) - 5} more practices"
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*✅ Security Best Practices:*\n{practices_text}"
                }
            })

        # Add compliance notes if available (legacy)
        compliance_notes = metadata.get('compliance_notes', [])
        if compliance_notes:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📋 Additional Notes:*\n" + "\n".join([f"• {n}" for n in compliance_notes[:3]])
                }
            })

        blocks.extend([
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*📋 Next Steps:*\n1. Review code and README in GitHub PR\n2. Check SOC 2 controls and security practices\n3. Review terraform plan output\n4. Update terraform.tfvars with your values\n5. Merge PR and deploy"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "📂 View Pull Request"},
                        "url": pr["html_url"],
                        "style": "primary"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "📄 View Code"},
                        "url": f"{pr['html_url']}/files"
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "ℹ️ Complete code with security best practices. Review README for SOC 2 controls and recommendations."}
                ]
            }
        ])

        return blocks

    def _post_code_to_thread(self, channel: str, thread_ts: str, code: str, blueprint: str, metadata: dict, terraform_files: dict = None):
        """Post code to thread - adaptive based on size."""
        code_length = len(code)
        small_code_threshold = 3000  # Slack block limit is ~3000 chars

        # Show file structure
        if terraform_files:
            file_list = []
            if 'variables' in terraform_files:
                file_list.append(f"📝 `variables.tf` ({len(terraform_files['variables'])} chars)")
            if 'main' in terraform_files:
                file_list.append(f"📄 `main.tf` ({len(terraform_files['main'])} chars)")
            if 'outputs' in terraform_files:
                file_list.append(f"📤 `outputs.tf` ({len(terraform_files['outputs'])} chars)")
            if 'tfvars_example' in terraform_files:
                file_list.append(f"⚙️ `terraform.tfvars.example`")
            if 'readme' in terraform_files:
                file_list.append(f"📖 `README.md`")

            file_structure = "\n".join(file_list)

            self.slack.post_message(
                channel,
                thread_ts=thread_ts,
                blocks=[
                    {"type": "section", "text": {"type": "mrkdwn", "text": f"*📁 Generated Files:*\n{file_structure}\n\n_View complete module in GitHub PR_"}}
                ]
            )

        if code_length <= small_code_threshold:
            # Small code: Show full main.tf
            self.slack.post_message(
                channel,
                thread_ts=thread_ts,
                blocks=[
                    {"type": "section", "text": {"type": "mrkdwn", "text": f"*📄 main.tf Preview*\n({code_length} chars)"}},
                    {"type": "section", "text": {"type": "mrkdwn", "text": f"```terraform\n{code}\n```"}}
                ]
            )
        else:
            # Large code: Generate and show summary instead
            summary = self._generate_code_summary(code, blueprint, metadata)
            self.slack.post_message(
                channel,
                thread_ts=thread_ts,
                blocks=[
                    {"type": "section", "text": {"type": "mrkdwn", "text": f"*📊 Code Summary*\n(Full code: {code_length} chars - see GitHub PR)"}},
                    {"type": "section", "text": {"type": "mrkdwn", "text": summary}}
                ]
            )

    def _generate_code_summary(self, code: str, blueprint: str, metadata: dict) -> str:
        """Generate a summary of large Terraform code."""
        # Count resources by type
        resource_pattern = r'resource\s+"([^"]+)"\s+"([^"]+)"'
        resources = re.findall(resource_pattern, code)
        resource_counts = {}
        for resource_type, resource_name in resources:
            resource_counts[resource_type] = resource_counts.get(resource_type, 0) + 1

        # Count data sources
        data_pattern = r'data\s+"([^"]+)"\s+"([^"]+)"'
        data_sources = re.findall(data_pattern, code)
        data_count = len(data_sources)

        # Count modules
        module_pattern = r'module\s+"([^"]+)"'
        modules = re.findall(module_pattern, code)
        module_count = len(modules)

        # Count variables
        variable_pattern = r'variable\s+"([^"]+)"'
        variables = re.findall(variable_pattern, code)
        var_count = len(variables)

        # Count outputs
        output_pattern = r'output\s+"([^"]+)"'
        outputs = re.findall(output_pattern, code)
        output_count = len(outputs)

        # Build summary
        summary_parts = [
            f"*Blueprint:* `{blueprint}`",
            "",
            "*📦 Resources:*"
        ]

        if resource_counts:
            for resource_type, count in sorted(resource_counts.items()):
                summary_parts.append(f"  • `{resource_type}` × {count}")
        else:
            summary_parts.append("  • No resources defined")

        summary_parts.append("")
        summary_parts.append("*📊 Components:*")
        summary_parts.append(f"  • Data Sources: {data_count}")
        summary_parts.append(f"  • Modules: {module_count}")
        summary_parts.append(f"  • Variables: {var_count}")
        summary_parts.append(f"  • Outputs: {output_count}")

        # Add compliance notes if available
        compliance_notes = metadata.get('compliance_notes', [])
        if compliance_notes:
            summary_parts.append("")
            summary_parts.append("*🔐 Compliance:*")
            for note in compliance_notes[:3]:
                summary_parts.append(f"  • {note}")

        summary_parts.append("")
        summary_parts.append("_→ Download file attachment or view in GitHub PR for full code_")

        return "\n".join(summary_parts)
