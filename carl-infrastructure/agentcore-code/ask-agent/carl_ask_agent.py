"""
CARL Ask Agent - AWS Bedrock AgentCore Runtime

This agent handles intelligent Q&A about AWS environments for compliance
and architecture questions. It scans AWS resources dynamically and uses
Claude to generate informed responses.

Deployed to: AWS Bedrock AgentCore Runtime
Entry Point: carl_ask_agent.py
"""

import os
import json
import logging
import boto3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

# AgentCore Runtime imports
from bedrock_agentcore import BedrockAgentCoreApp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize AgentCore app
app = BedrockAgentCoreApp()

# Environment variables (set by Terraform)
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
FOUNDATION_MODEL = os.environ.get("FOUNDATION_MODEL", "anthropic.claude-sonnet-4-20250514-v1:0")
TOOL_LAMBDA_ARN = os.environ.get("TOOL_LAMBDA_ARN", "")


@dataclass
class ResourceScanResult:
    """Represents a scanned AWS resource."""
    service: str
    resource_type: str
    resource_id: str
    resource_name: str
    region: str
    account_id: str
    data: dict[str, Any] = field(default_factory=dict)
    scanned_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    tags: dict[str, str] = field(default_factory=dict)


class AWSResourceScanner:
    """
    Lightweight AWS resource scanner for AgentCore runtime.
    Collects raw data from AWS APIs without storage overhead.
    """

    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self._account_id: Optional[str] = None

        # Initialize boto3 clients
        self.iam = boto3.client("iam", region_name=region)
        self.s3 = boto3.client("s3", region_name=region)
        self.ec2 = boto3.client("ec2", region_name=region)
        self.sts = boto3.client("sts", region_name=region)
        self.rds = boto3.client("rds", region_name=region)
        self.cloudtrail = boto3.client("cloudtrail", region_name=region)
        self.guardduty = boto3.client("guardduty", region_name=region)
        self.securityhub = boto3.client("securityhub", region_name=region)

    @property
    def account_id(self) -> str:
        """Get AWS account ID (cached)."""
        if self._account_id is None:
            self._account_id = self.sts.get_caller_identity()["Account"]
        return self._account_id

    def scan_iam(self) -> list[ResourceScanResult]:
        """Scan IAM users, policies, and MFA status."""
        results = []

        try:
            # Scan IAM users with MFA status
            users = self.iam.list_users().get("Users", [])
            for user in users:
                username = user["UserName"]
                user_id = user["UserId"]

                # Check MFA devices
                mfa_devices = self.iam.list_mfa_devices(UserName=username).get("MFADevices", [])

                results.append(ResourceScanResult(
                    service="iam",
                    resource_type="AWS::IAM::User",
                    resource_id=user_id,
                    resource_name=username,
                    region="global",
                    account_id=self.account_id,
                    data={
                        "mfa_enabled": len(mfa_devices) > 0,
                        "mfa_device_count": len(mfa_devices),
                        "create_date": user.get("CreateDate", "").isoformat() if user.get("CreateDate") else None,
                    }
                ))

            # Scan password policy
            try:
                policy = self.iam.get_account_password_policy()["PasswordPolicy"]
                results.append(ResourceScanResult(
                    service="iam",
                    resource_type="AWS::IAM::PasswordPolicy",
                    resource_id="account-password-policy",
                    resource_name="Account Password Policy",
                    region="global",
                    account_id=self.account_id,
                    data={
                        "minimum_password_length": policy.get("MinimumPasswordLength", 8),
                        "require_uppercase": policy.get("RequireUppercaseCharacters", False),
                        "require_lowercase": policy.get("RequireLowercaseCharacters", False),
                        "require_numbers": policy.get("RequireNumbers", False),
                        "require_symbols": policy.get("RequireSymbols", False),
                        "max_password_age": policy.get("MaxPasswordAge"),
                        "password_reuse_prevention": policy.get("PasswordReusePrevention"),
                    }
                ))
            except self.iam.exceptions.NoSuchEntityException:
                results.append(ResourceScanResult(
                    service="iam",
                    resource_type="AWS::IAM::PasswordPolicy",
                    resource_id="account-password-policy",
                    resource_name="Account Password Policy",
                    region="global",
                    account_id=self.account_id,
                    data={"configured": False, "note": "No custom password policy set"}
                ))

        except Exception as e:
            logger.warning(f"IAM scan error: {e}")

        return results

    def scan_s3(self) -> list[ResourceScanResult]:
        """Scan S3 buckets for encryption and public access."""
        results = []

        try:
            buckets = self.s3.list_buckets().get("Buckets", [])
            for bucket in buckets:
                bucket_name = bucket["Name"]

                # Check encryption
                encryption = "unknown"
                try:
                    enc_config = self.s3.get_bucket_encryption(Bucket=bucket_name)
                    rules = enc_config.get("ServerSideEncryptionConfiguration", {}).get("Rules", [])
                    if rules:
                        encryption = rules[0].get("ApplyServerSideEncryptionByDefault", {}).get("SSEAlgorithm", "unknown")
                except self.s3.exceptions.ClientError:
                    encryption = "none"

                # Check public access block
                public_access = {}
                try:
                    pab = self.s3.get_public_access_block(Bucket=bucket_name)["PublicAccessBlockConfiguration"]
                    public_access = {
                        "block_public_acls": pab.get("BlockPublicAcls", False),
                        "ignore_public_acls": pab.get("IgnorePublicAcls", False),
                        "block_public_policy": pab.get("BlockPublicPolicy", False),
                        "restrict_public_buckets": pab.get("RestrictPublicBuckets", False),
                    }
                except self.s3.exceptions.ClientError:
                    public_access = {"configured": False}

                # Check versioning
                versioning = "disabled"
                try:
                    v = self.s3.get_bucket_versioning(Bucket=bucket_name)
                    versioning = v.get("Status", "disabled").lower()
                except Exception:
                    pass

                results.append(ResourceScanResult(
                    service="s3",
                    resource_type="AWS::S3::Bucket",
                    resource_id=bucket_name,
                    resource_name=bucket_name,
                    region="global",
                    account_id=self.account_id,
                    data={
                        "encryption": encryption,
                        "public_access_block": public_access,
                        "versioning": versioning,
                    }
                ))

        except Exception as e:
            logger.warning(f"S3 scan error: {e}")

        return results

    def scan_vpc(self) -> list[ResourceScanResult]:
        """Scan VPCs, security groups, and flow logs."""
        results = []

        try:
            # Scan VPCs
            vpcs = self.ec2.describe_vpcs().get("Vpcs", [])
            for vpc in vpcs:
                vpc_id = vpc["VpcId"]
                vpc_name = next((t["Value"] for t in vpc.get("Tags", []) if t["Key"] == "Name"), vpc_id)

                results.append(ResourceScanResult(
                    service="vpc",
                    resource_type="AWS::EC2::VPC",
                    resource_id=vpc_id,
                    resource_name=vpc_name,
                    region=self.region,
                    account_id=self.account_id,
                    data={
                        "cidr_block": vpc.get("CidrBlock"),
                        "state": vpc.get("State"),
                        "is_default": vpc.get("IsDefault", False),
                    },
                    tags={t["Key"]: t["Value"] for t in vpc.get("Tags", [])}
                ))

            # Scan security groups
            sgs = self.ec2.describe_security_groups().get("SecurityGroups", [])
            for sg in sgs:
                sg_id = sg["GroupId"]

                results.append(ResourceScanResult(
                    service="vpc",
                    resource_type="AWS::EC2::SecurityGroup",
                    resource_id=sg_id,
                    resource_name=sg.get("GroupName", sg_id),
                    region=self.region,
                    account_id=self.account_id,
                    data={
                        "vpc_id": sg.get("VpcId"),
                        "description": sg.get("Description"),
                        "ingress_rules_count": len(sg.get("IpPermissions", [])),
                        "egress_rules_count": len(sg.get("IpPermissionsEgress", [])),
                        "has_open_ingress": any(
                            "0.0.0.0/0" in [r.get("CidrIp", "") for r in rule.get("IpRanges", [])]
                            for rule in sg.get("IpPermissions", [])
                        ),
                    },
                    tags={t["Key"]: t["Value"] for t in sg.get("Tags", [])}
                ))

            # Scan VPC flow logs
            flow_logs = self.ec2.describe_flow_logs().get("FlowLogs", [])
            for fl in flow_logs:
                results.append(ResourceScanResult(
                    service="vpc",
                    resource_type="AWS::EC2::FlowLog",
                    resource_id=fl["FlowLogId"],
                    resource_name=fl.get("LogGroupName", fl["FlowLogId"]),
                    region=self.region,
                    account_id=self.account_id,
                    data={
                        "resource_id": fl.get("ResourceId"),
                        "traffic_type": fl.get("TrafficType"),
                        "log_destination_type": fl.get("LogDestinationType"),
                        "status": fl.get("FlowLogStatus"),
                    },
                    tags={t["Key"]: t["Value"] for t in fl.get("Tags", [])}
                ))

        except Exception as e:
            logger.warning(f"VPC scan error: {e}")

        return results

    def scan_ec2(self) -> list[ResourceScanResult]:
        """Scan EC2 instances."""
        results = []

        try:
            reservations = self.ec2.describe_instances().get("Reservations", [])
            for reservation in reservations:
                for instance in reservation.get("Instances", []):
                    instance_id = instance["InstanceId"]
                    instance_name = next(
                        (t["Value"] for t in instance.get("Tags", []) if t["Key"] == "Name"),
                        instance_id
                    )

                    results.append(ResourceScanResult(
                        service="ec2",
                        resource_type="AWS::EC2::Instance",
                        resource_id=instance_id,
                        resource_name=instance_name,
                        region=self.region,
                        account_id=self.account_id,
                        data={
                            "instance_type": instance.get("InstanceType"),
                            "state": instance.get("State", {}).get("Name"),
                            "launch_time": instance.get("LaunchTime", "").isoformat() if instance.get("LaunchTime") else None,
                            "vpc_id": instance.get("VpcId"),
                            "subnet_id": instance.get("SubnetId"),
                            "public_ip": instance.get("PublicIpAddress"),
                            "private_ip": instance.get("PrivateIpAddress"),
                        },
                        tags={t["Key"]: t["Value"] for t in instance.get("Tags", [])}
                    ))

        except Exception as e:
            logger.warning(f"EC2 scan error: {e}")

        return results

    def scan_all(self) -> dict[str, list[ResourceScanResult]]:
        """Scan all supported AWS services."""
        logger.info("Starting comprehensive AWS scan...")

        results = {
            "iam": self.scan_iam(),
            "s3": self.scan_s3(),
            "vpc": self.scan_vpc(),
            "ec2": self.scan_ec2(),
        }

        total = sum(len(r) for r in results.values())
        logger.info(f"Scan complete: {total} resources across {len(results)} services")

        return results


def scan_results_to_context(scan_results: dict[str, list[ResourceScanResult]]) -> str:
    """Convert scan results to a text context for the AI model."""
    lines = ["## AWS Environment Scan Results\n"]

    for service, resources in scan_results.items():
        if not resources:
            continue

        lines.append(f"### {service.upper()} ({len(resources)} resources)\n")

        for r in resources:
            lines.append(f"- **{r.resource_type}**: {r.resource_name} ({r.resource_id})")
            # Include key data points
            for key, value in r.data.items():
                if value is not None:
                    lines.append(f"  - {key}: {value}")
            lines.append("")

    return "\n".join(lines)


def classify_question(question: str) -> str:
    """
    Classify the question type using simple heuristics.
    Returns: 'architecture' or 'compliance'
    """
    architecture_keywords = [
        "design", "architect", "build", "create", "setup", "recommend",
        "pattern", "best practice", "how should", "what's the best",
        "implement", "deploy", "migrate", "scale", "structure"
    ]

    question_lower = question.lower()

    for keyword in architecture_keywords:
        if keyword in question_lower:
            return "architecture"

    return "compliance"


def generate_response(question: str, context: str, question_type: str) -> str:
    """Generate AI response using Bedrock."""
    bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)

    if question_type == "architecture":
        system_prompt = """You are CARL (Cloud Automated Risk & Compliance Logic), an expert AWS architect.
You help users design secure, compliant, and cost-effective AWS architectures.

Based on the AWS environment context provided, give specific, actionable recommendations.
Consider SOC 2 compliance requirements in your recommendations.
Include cost considerations when relevant.
Be concise but thorough."""
    else:
        system_prompt = """You are CARL (Cloud Automated Risk & Compliance Logic), an AWS compliance expert.
You help users understand their AWS environment's security and compliance posture.

Based on the AWS environment scan results, answer the user's question with specific details.
Reference actual resources found in the scan.
Highlight any compliance gaps or security concerns.
Map issues to SOC 2 controls when relevant.
Be direct and actionable."""

    messages = [
        {
            "role": "user",
            "content": f"""Context from AWS environment scan:

{context}

Question: {question}

Please provide a detailed, helpful response based on the actual AWS environment data above."""
        }
    ]

    try:
        response = bedrock.invoke_model(
            modelId=FOUNDATION_MODEL,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "system": system_prompt,
                "messages": messages,
            })
        )

        result = json.loads(response["body"].read())
        return result["content"][0]["text"]

    except Exception as e:
        logger.error(f"Bedrock invocation failed: {e}")
        return f"I apologize, but I encountered an error generating a response: {str(e)}"


@app.entrypoint
def invoke(payload: dict, context: Any = None) -> dict:
    """
    AgentCore Runtime entrypoint.

    Payload structure:
    {
        "prompt": "user question here"
    }

    Returns:
    {
        "result": "agent response here"
    }
    """
    logger.info(f"Received payload: {json.dumps(payload, default=str)[:500]}...")

    # Extract user input - AgentCore uses "prompt" key
    question = payload.get("prompt", "")

    if not question:
        return {
            "result": "Please provide a question. Example: 'What's my current MFA status?' or 'How should I design my VPC?'"
        }

    logger.info(f"Processing question: {question}")

    # Classify the question
    question_type = classify_question(question)
    logger.info(f"Question type: {question_type}")

    # Scan AWS environment
    try:
        scanner = AWSResourceScanner(region=AWS_REGION)
        scan_results = scanner.scan_all()
        env_context = scan_results_to_context(scan_results)
    except Exception as e:
        logger.error(f"AWS scan failed: {e}")
        env_context = f"Note: AWS environment scan failed with error: {str(e)}\n\nProceeding with general knowledge."

    # Generate response
    response_text = generate_response(question, env_context, question_type)

    return {
        "result": response_text
    }


# AgentCore entry point
if __name__ == "__main__":
    app.run()
