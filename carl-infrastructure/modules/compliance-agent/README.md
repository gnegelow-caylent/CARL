# Compliance Agent Terraform Module

This module creates an AWS Bedrock Agent for autonomous SOC 2 compliance assessment.

## What It Creates

- **AWS Bedrock Agent** - Agent configured with Claude 3.5 Sonnet
- **Agent Alias** - "PROD" alias for production use
- **Action Group** - Tools the agent can call (scan, analyze, plan, create tickets)
- **IAM Role** - Agent execution role with Lambda and Bedrock permissions
- **Lambda Permission** - Allows agent to invoke tool Lambda functions

## Usage

```hcl
module "compliance_agent" {
  source = "../modules/compliance-agent"

  name_prefix       = "carl-dev"
  region            = "us-east-1"
  tool_lambda_arn   = aws_lambda_function.carl.arn
  tool_lambda_name  = aws_lambda_function.carl.function_name

  tags = {
    Project = "CARL"
    Feature = "compliance_agent"
  }
}
```

## Agent Tools

The agent can call these tools (implemented in the CARL Lambda function):

1. **scan-environment** - Scan AWS resources with prioritization
2. **detect-patterns** - Use AI to find root causes
3. **analyze-soc2** - Map findings to SOC 2 controls
4. **generate-plan** - Create 4-phase remediation plan
5. **create-jira-epic** - Generate epic + stories in Jira

## Inputs

| Name | Description | Type | Required |
|------|-------------|------|----------|
| `name_prefix` | Prefix for resource names | string | Yes |
| `region` | AWS region | string | Yes |
| `tool_lambda_arn` | ARN of tool Lambda function | string | Yes |
| `tool_lambda_name` | Name of tool Lambda function | string | Yes |
| `tags` | Resource tags | map(string) | No |

## Outputs

| Name | Description |
|------|-------------|
| `agent_id` | Bedrock Agent ID |
| `agent_arn` | Bedrock Agent ARN |
| `agent_alias_id` | Agent Alias ID (PROD) |
| `agent_alias_arn` | Agent Alias ARN |
| `agent_role_arn` | IAM role ARN for agent |

## How It Works

1. User runs `/carl compliance assess` in Slack
2. CARL Lambda calls `bedrock:InvokeAgent` with agent ID
3. Agent autonomously:
   - Calls `scan-environment` tool → Gets AWS resource data
   - Calls `detect-patterns` tool → Finds root causes
   - Calls `analyze-soc2` tool → Calculates compliance coverage
   - Calls `generate-plan` tool → Creates remediation roadmap
   - Calls `create-jira-epic` tool → Creates tickets
4. Agent returns results to Lambda
5. Lambda posts results to Slack

## Cost

- **Agent invocation**: $0.002 per assessment
- **Tool calls**: $0.001-0.005 per call (6-10 calls per assessment)
- **AI reasoning**: $0.03-0.05 per assessment
- **Total**: ~$0.05-0.10 per assessment
- **Monthly (20 assessments)**: ~$1-2/month

## Requirements

- AWS Provider >= 5.11 (Bedrock Agent support)
- Lambda function must implement agent tool handlers
- Lambda execution role needs `bedrock:InvokeAgent` permission

## Notes

- Agent uses Claude 3.5 Sonnet for reasoning
- Agent is read-only - never makes AWS changes
- All changes require human approval
- Agent maintains conversation context across tool calls
- Session timeout: 30 minutes
