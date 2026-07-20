# Outputs for MCP Configuration
# Copy these values to your Claude Desktop config

output "mcp_configuration" {
  description = "Complete MCP server configuration"
  value = {
    # AgentCore ARNs
    ask_agent_arn       = module.agentcore_ask.runtime_arn
    architect_agent_arn = module.agentcore_architect.agent_runtime_arn
    remediate_agent_arn = module.agentcore_remediate.runtime_arn

    # Storage
    evidence_bucket = module.foundation.evidence_bucket_name
    reports_bucket  = module.foundation.reports_bucket_name

    # DynamoDB Tables
    findings_table     = module.foundation.findings_table_name
    evidence_table     = module.foundation.evidence_table_name
    scan_history_table = module.foundation.scan_history_table_name

    # Configuration
    aws_region  = var.region
    environment = var.environment
  }
}

output "claude_desktop_config" {
  description = "Copy this to your Claude Desktop config file"
  value = jsonencode({
    mcpServers = {
      carl = {
        command = "python"
        args    = ["-m", "carl_mcp_server"]
        env = {
          AWS_PROFILE                  = "YOUR_AWS_PROFILE"
          AWS_REGION                   = var.region
          CARL_AGENTCORE_ASK_ARN       = module.agentcore_ask.runtime_arn
          CARL_AGENTCORE_ARCHITECT_ARN = module.agentcore_architect.agent_runtime_arn
          CARL_AGENTCORE_REMEDIATE_ARN = module.agentcore_remediate.runtime_arn
          CARL_DYNAMODB_PREFIX         = "carl-${var.environment}"
          CARL_S3_EVIDENCE_BUCKET      = module.foundation.evidence_bucket_name
          CARL_S3_REPORTS_BUCKET       = module.foundation.reports_bucket_name
        }
      }
    }
  })
}

output "ecr_repository_url" {
  description = "ECR repository URL for agent containers"
  value       = aws_ecr_repository.agents.repository_url
}

output "next_steps" {
  description = "What to do next"
  value       = <<-EOT

    ✅ CARL Infrastructure Deployed!

    Next Steps:

    1. Build and push agent containers:
       cd ../agentcore-code
       ./build-and-push.sh ${aws_ecr_repository.agents.repository_url} ${var.environment}

    2. Install MCP server:
       pip install carl-mcp-server

    3. Configure Claude Desktop:
       Copy the 'claude_desktop_config' output above to:
       ~/Library/Application Support/Claude/claude_desktop_config.json

       (Update YOUR_AWS_PROFILE with your AWS profile name)

    4. Restart Claude Desktop

    5. Test:
       Ask Claude: "Use carl_ask to check my AWS security posture"

    AgentCore ARNs:
    - Ask:        ${module.agentcore_ask.runtime_arn}
    - Architect:  ${module.agentcore_architect.agent_runtime_arn}
    - Remediate:  ${module.agentcore_remediate.runtime_arn}
  EOT
}
