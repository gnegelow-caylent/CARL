"""
CARL Architect Agent - AWS Bedrock AgentCore Runtime

This agent handles architecture recommendations, providing options with
cost estimates, compliance considerations, and the ability to generate
Terraform code.

Deployed to: AWS Bedrock AgentCore Runtime
Entry Point: carl_architect_agent.py
"""

import os
import sys
import json
import logging
import traceback
from typing import Any

# Configure logging early
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

logger.info("=== CARL Architect Agent Starting ===")
logger.info(f"Python version: {sys.version}")

# Import boto3
try:
    import boto3
    logger.info(f"boto3 imported successfully, version: {boto3.__version__}")
except Exception as e:
    logger.error(f"Failed to import boto3: {e}")
    traceback.print_exc()

# AgentCore Runtime imports
try:
    from bedrock_agentcore.runtime import BedrockAgentCoreApp
    logger.info("BedrockAgentCoreApp imported successfully")
except Exception as e:
    logger.error(f"Failed to import BedrockAgentCoreApp: {e}")
    traceback.print_exc()
    raise

# Initialize AgentCore app
logger.info("Initializing BedrockAgentCoreApp...")
app = BedrockAgentCoreApp(debug=True)
logger.info("BedrockAgentCoreApp initialized successfully")

# Environment variables
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
FOUNDATION_MODEL = os.environ.get("FOUNDATION_MODEL", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")

logger.info(f"Configuration: AWS_REGION={AWS_REGION}, FOUNDATION_MODEL={FOUNDATION_MODEL}")


# ============================================================================
# Architecture Patterns (embedded for AgentCore - no external dependencies)
# ============================================================================

STATIC_WEBSITE_PATTERNS = {
    "s3_cloudfront_basic": {
        "name": "S3 + CloudFront (Basic)",
        "description": "Simple static website hosting with S3 origin and CloudFront CDN",
        "components": ["S3 bucket", "CloudFront distribution", "Origin Access Control"],
        "cost_estimate": "$1-5/month for small sites",
        "pros": ["Simple setup", "Low cost", "Global CDN", "HTTPS included"],
        "cons": ["No server-side processing", "Limited to static content"],
        "soc2_controls": ["CC6.1 - Access controls", "CC6.7 - Encryption in transit"],
        "recommended_for": "Marketing sites, documentation, landing pages"
    },
    "s3_cloudfront_waf": {
        "name": "S3 + CloudFront + WAF (Production)",
        "description": "Production-ready static site with WAF protection and custom domain",
        "components": ["S3 bucket", "CloudFront", "WAF", "ACM certificate", "Route 53"],
        "cost_estimate": "$10-50/month depending on traffic",
        "pros": ["DDoS protection", "Bot mitigation", "Custom domain", "Enterprise-ready"],
        "cons": ["Higher cost", "More complex setup"],
        "soc2_controls": ["CC6.1", "CC6.6", "CC6.7", "CC7.2"],
        "recommended_for": "Production websites, e-commerce, customer-facing apps"
    },
    "amplify_hosting": {
        "name": "AWS Amplify Hosting",
        "description": "Managed hosting with CI/CD, preview deployments, and easy setup",
        "components": ["Amplify Hosting", "Git integration", "Automatic HTTPS"],
        "cost_estimate": "$0-15/month (generous free tier)",
        "pros": ["Git-based deployments", "Preview branches", "Zero config", "Free tier"],
        "cons": ["Less control", "Amplify lock-in", "Limited customization"],
        "soc2_controls": ["CC6.1", "CC6.7", "CC8.1 - Change management"],
        "recommended_for": "Developer teams, rapid iteration, JAMstack apps"
    }
}

ETL_PATTERNS = {
    "glue_serverless": {
        "name": "AWS Glue Serverless ETL",
        "description": "Serverless ETL with automatic scaling and no infrastructure management",
        "components": ["Glue Jobs", "Glue Catalog", "S3 data lake"],
        "cost_estimate": "$0.44/DPU-hour, typically $50-200/month",
        "pros": ["No servers to manage", "Auto-scaling", "Built-in catalog"],
        "cons": ["Cold start latency", "Spark learning curve"],
        "soc2_controls": ["CC6.1", "CC6.7", "CC7.2"],
        "recommended_for": "Batch ETL, data lakes, analytics pipelines"
    },
    "step_functions_orchestration": {
        "name": "Step Functions + Lambda",
        "description": "Orchestrated ETL with visual workflow and fine-grained control",
        "components": ["Step Functions", "Lambda functions", "S3", "DynamoDB"],
        "cost_estimate": "$25/million state transitions + Lambda costs",
        "pros": ["Visual workflow", "Error handling", "Parallel processing"],
        "cons": ["More components", "Lambda time limits"],
        "soc2_controls": ["CC6.1", "CC7.2", "CC8.1"],
        "recommended_for": "Complex workflows, multi-step processing"
    }
}

SERVERLESS_API_PATTERNS = {
    "api_gateway_lambda": {
        "name": "API Gateway + Lambda (Basic)",
        "description": "Serverless REST API with Lambda backend",
        "components": ["API Gateway REST/HTTP", "Lambda functions", "CloudWatch"],
        "cost_estimate": "$3.50/million requests + Lambda",
        "pros": ["No servers", "Auto-scaling", "Pay per request"],
        "cons": ["Cold starts", "29 second timeout"],
        "soc2_controls": ["CC6.1", "CC6.2", "CC6.7"],
        "recommended_for": "APIs, webhooks, microservices"
    },
    "api_gateway_cognito": {
        "name": "API Gateway + Cognito + Lambda (Authenticated)",
        "description": "Secure API with user authentication and authorization",
        "components": ["API Gateway", "Cognito User Pool", "Lambda", "WAF"],
        "cost_estimate": "$10-100/month depending on users",
        "pros": ["Built-in auth", "JWT tokens", "MFA support"],
        "cons": ["Cognito complexity", "Vendor lock-in"],
        "soc2_controls": ["CC6.1", "CC6.2", "CC6.3", "CC6.7"],
        "recommended_for": "SaaS apps, authenticated APIs, B2C apps"
    }
}

CONTAINER_PATTERNS = {
    "ecs_fargate": {
        "name": "ECS Fargate (Serverless)",
        "description": "Serverless containers with no EC2 management",
        "components": ["ECS Cluster", "Fargate tasks", "ALB", "ECR"],
        "cost_estimate": "$30-200/month for small workloads",
        "pros": ["No EC2 management", "Auto-scaling", "Easy deployment", "AWS handles patching"],
        "cons": ["Higher per-unit cost (~50% more than EC2)", "Less infrastructure control", "Cold start delays"],
        "soc2_controls": ["CC6.1", "CC6.7", "CC7.2"],
        "recommended_for": "Microservices, variable workloads, small teams without ops expertise"
    },
    "ecs_ec2": {
        "name": "ECS on EC2 (Cost-Optimized)",
        "description": "ECS tasks on self-managed EC2 instances - cheaper at scale",
        "components": ["ECS Cluster", "EC2 Auto Scaling Group", "ECS agent", "ALB", "ECR"],
        "cost_estimate": "$90-500/month (50% cheaper than Fargate at high utilization)",
        "pros": ["Lower cost at scale", "Full instance control", "Reserved Instance savings", "Persistent storage"],
        "cons": ["Manage EC2 instances (patching, scaling)", "More operational overhead", "More SOC 2 controls needed"],
        "soc2_controls": ["CC6.1", "CC6.7", "CC7.2", "CC8.1 - patch management"],
        "recommended_for": "High utilization workloads (>70% CPU), cost-sensitive deployments, teams with EC2 expertise"
    },
    "eks_managed": {
        "name": "EKS Managed Kubernetes",
        "description": "Managed Kubernetes with full K8s compatibility",
        "components": ["EKS Cluster", "Node groups", "ALB Ingress", "ECR"],
        "cost_estimate": "$75 + node costs ($150-500+/month total)",
        "pros": ["Full K8s", "Ecosystem", "Portability"],
        "cons": ["Complexity", "Cluster cost", "Learning curve"],
        "soc2_controls": ["CC6.1", "CC6.7", "CC7.2", "CC8.1"],
        "recommended_for": "K8s teams, complex apps, multi-cloud strategy"
    }
}

# Pricing data (static fallback)
STATIC_PRICING = {
    "ec2": {
        "t3.micro": "$7.59/month",
        "t3.small": "$15.18/month",
        "t3.medium": "$30.37/month",
        "t3.large": "$60.74/month",
        "m5.large": "$70.08/month",
    },
    "rds": {
        "db.t3.micro": "$12.41/month",
        "db.t3.small": "$24.82/month",
        "db.t3.medium": "$49.64/month",
    },
    "s3": {
        "storage": "$0.023/GB/month",
        "requests": "$0.005 per 1,000 PUT, $0.0004 per 1,000 GET"
    },
    "cloudfront": {
        "data_transfer": "$0.085/GB first 10TB",
        "requests": "$0.0075 per 10,000 HTTPS requests"
    },
    "lambda": {
        "requests": "$0.20 per million",
        "duration": "$0.0000166667 per GB-second"
    }
}


def get_patterns_for_requirement(requirement: str) -> dict:
    """Get relevant architecture patterns based on requirement keywords."""
    requirement_lower = requirement.lower()

    patterns = {}

    if any(kw in requirement_lower for kw in ["static", "website", "landing", "marketing", "docs"]):
        patterns["static_website"] = STATIC_WEBSITE_PATTERNS

    if any(kw in requirement_lower for kw in ["etl", "data", "pipeline", "transform", "glue"]):
        patterns["etl"] = ETL_PATTERNS

    if any(kw in requirement_lower for kw in ["api", "serverless", "lambda", "rest", "webhook"]):
        patterns["serverless_api"] = SERVERLESS_API_PATTERNS

    if any(kw in requirement_lower for kw in ["container", "docker", "ecs", "eks", "kubernetes"]):
        patterns["containers"] = CONTAINER_PATTERNS

    # Default to showing common patterns if nothing specific matched
    if not patterns:
        patterns = {
            "static_website": STATIC_WEBSITE_PATTERNS,
            "serverless_api": SERVERLESS_API_PATTERNS,
            "containers": CONTAINER_PATTERNS
        }

    return patterns


def get_pricing_info(services: list[str]) -> dict:
    """Get pricing for requested services."""
    pricing = {}
    for service in services:
        service_lower = service.lower()
        for key, value in STATIC_PRICING.items():
            if key in service_lower:
                pricing[key] = value
    return pricing if pricing else STATIC_PRICING


def generate_recommendation(requirement: str, patterns: dict) -> str:
    """Generate AI recommendation using Bedrock."""
    bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)

    # Build context from patterns
    patterns_context = json.dumps(patterns, indent=2, default=str)

    system_prompt = """You are CARL's architecture advisor, helping design AWS solutions.

Your job: Provide 2-3 OPTIONS with clear tradeoffs, costs, and a recommendation.

RESPONSE FORMAT (use this exact structure):

*Option 1: [Name]* (Recommended)
Best for: [One sentence]
Cost: $X-Y/month
- Key component 1
- Key component 2
- Compliance: [SOC 2 controls met]

*Option 2: [Name]*
Best for: [One sentence]
Cost: $X-Y/month
- Key component 1
- Key component 2

*My Recommendation:* [State which option and why in 1-2 sentences]

FORMATTING RULES:
- Use *text* for bold (single asterisks)
- Use backticks for resource names: `bucket-name`, `my-api`
- NO pound signs (#) for headers
- NO double asterisks (**)
- NO tildes (~) - they cause strikethrough in Slack
- Keep it concise - this displays in Slack"""

    messages = [
        {
            "role": "user",
            "content": f"""User requirement: {requirement}

Available architecture patterns:
{patterns_context}

Provide 2-3 options based on these patterns. Include costs and a clear recommendation."""
        }
    ]

    try:
        response = bedrock.invoke_model(
            modelId=FOUNDATION_MODEL,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2048,
                "system": system_prompt,
                "messages": messages,
            })
        )

        result = json.loads(response["body"].read())
        return result["content"][0]["text"]

    except Exception as e:
        logger.error(f"Bedrock invocation failed: {e}")
        return f"Error generating recommendation: {str(e)}"


@app.entrypoint
def invoke(payload: dict, context: Any = None) -> dict:
    """
    AgentCore Runtime entrypoint.

    Payload structure:
    {
        "prompt": "architecture requirement here"
    }

    Returns:
    {
        "result": "architecture recommendation"
    }
    """
    logger.info("=== ARCHITECT AGENT INVOKE ===")
    logger.info(f"Payload: {json.dumps(payload, default=str)[:500]}")

    try:
        requirement = payload.get("prompt", "")

        if not requirement:
            return {
                "result": "Please provide an architecture requirement. Example: 'I need to host a static website' or 'Design an API for user authentication'"
            }

        logger.info(f"Processing requirement: {requirement}")

        # Get relevant patterns
        patterns = get_patterns_for_requirement(requirement)
        logger.info(f"Found patterns: {list(patterns.keys())}")

        # Generate recommendation
        recommendation = generate_recommendation(requirement, patterns)
        logger.info(f"Generated recommendation: {len(recommendation)} chars")

        return {"result": recommendation}

    except Exception as e:
        logger.error(f"Error in invoke: {e}")
        traceback.print_exc()
        return {"result": f"Error processing request: {str(e)}"}


if __name__ == "__main__":
    logger.info("=== Starting CARL Architect Agent Server ===")
    try:
        app.run(port=8080)
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        traceback.print_exc()
        sys.exit(1)
