# Bedrock Compliance Agent Module
# Creates AWS Bedrock Agent for autonomous SOC 2 compliance assessment

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.18"
    }
  }
}

# IAM Role for Bedrock Agent
resource "aws_iam_role" "agent" {
  name = "${var.name_prefix}-bedrock-agent-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "bedrock.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
          ArnLike = {
            "aws:SourceArn" = "arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:agent/*"
          }
        }
      }
    ]
  })

  tags = var.tags
}

# Policy for Bedrock Agent to invoke Lambda tools
resource "aws_iam_role_policy" "agent_lambda" {
  name = "bedrock-agent-lambda-invoke"
  role = aws_iam_role.agent.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = var.tool_lambda_arn
      }
    ]
  })
}

# Policy for Bedrock model access
resource "aws_iam_role_policy" "agent_bedrock" {
  name = "bedrock-agent-model-invoke"
  role = aws_iam_role.agent.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = "arn:aws:bedrock:${var.region}::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0"
      }
    ]
  })
}

data "aws_caller_identity" "current" {}

# Bedrock Agent
resource "aws_bedrockagent_agent" "compliance" {
  agent_name              = "${var.name_prefix}-compliance-agent"
  agent_resource_role_arn = aws_iam_role.agent.arn
  foundation_model        = "anthropic.claude-3-5-sonnet-20241022-v2:0"

  description = "Autonomous SOC 2 compliance assessment agent"

  instruction = <<-EOT
You are a compliance assessment agent for AWS environments.

Your goal is to assess SOC 2 compliance readiness by:
1. Intelligently scanning AWS resources with prioritization
2. Detecting patterns and root causes (not just symptoms)
3. Mapping findings to SOC 2 controls (43 total)
4. Generating phased remediation plans with dependencies
5. Creating Jira tickets for tracking

Guidelines:
- Be thorough but efficient - prioritize production resources
- Look for systemic issues (pipeline bugs, automation problems)
- Consider dependencies (e.g., CloudTrail before AWS Config)
- Estimate effort realistically (hours per task)
- Group related issues (don't create 20 tickets for 1 root cause)
- Focus on actionable insights, not noise

IMPORTANT CONSTRAINTS:
- Only READ from AWS - never make changes to resources
- Create plans and tickets, but do not apply fixes
- If unsure about anything, explain your reasoning
- Be specific with resource names and IDs
EOT

  idle_session_ttl_in_seconds = 1800 # 30 minutes

  tags = var.tags
}

# Action Group for Agent Tools
resource "aws_bedrockagent_agent_action_group" "compliance_tools" {
  agent_id                   = aws_bedrockagent_agent.compliance.agent_id
  agent_version              = "DRAFT"
  action_group_name          = "ComplianceTools"
  description                = "Tools for compliance assessment and remediation planning"
  skip_resource_in_use_check = true

  action_group_executor {
    lambda = var.tool_lambda_arn
  }

  # OpenAPI schema defining available tools
  api_schema {
    payload = jsonencode({
      openapi = "3.0.0"
      info = {
        title       = "CARL Compliance Agent Tools"
        version     = "1.0.0"
        description = "Tools for compliance assessment and remediation"
      }
      paths = {
        "/tools/scan-environment" = {
          post = {
            summary     = "Scan AWS environment intelligently"
            description = "Scan AWS resources with smart prioritization and sampling"
            operationId = "scanEnvironment"
            requestBody = {
              required = true
              content = {
                "application/json" = {
                  schema = {
                    type = "object"
                    properties = {
                      prioritize_production = {
                        type        = "boolean"
                        description = "Focus on production resources first"
                      }
                      sample_dev = {
                        type        = "boolean"
                        description = "Sample dev resources (don't scan all)"
                      }
                      max_resources = {
                        type        = "integer"
                        description = "Maximum resources to scan deeply"
                      }
                    }
                  }
                }
              }
            }
            responses = {
              "200" = {
                description = "Scan results"
                content = {
                  "application/json" = {
                    schema = {
                      type = "object"
                      properties = {
                        success           = { type = "boolean" }
                        scanned_resources = { type = "integer" }
                        evidence          = { type = "object" }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        "/tools/detect-patterns" = {
          post = {
            summary     = "Detect patterns and root causes in evidence"
            description = "Use AI to analyze evidence and identify systemic issues"
            operationId = "detectPatterns"
            requestBody = {
              required = true
              content = {
                "application/json" = {
                  schema = {
                    type = "object"
                    properties = {
                      evidence = {
                        type        = "object"
                        description = "Evidence data from scan"
                      }
                    }
                    required = ["evidence"]
                  }
                }
              }
            }
            responses = {
              "200" = {
                description = "Detected patterns"
                content = {
                  "application/json" = {
                    schema = {
                      type = "object"
                      properties = {
                        success  = { type = "boolean" }
                        patterns = { type = "array" }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        "/tools/analyze-soc2" = {
          post = {
            summary     = "Analyze SOC 2 control coverage"
            description = "Map findings to SOC 2 controls and calculate coverage"
            operationId = "analyzeSoc2Controls"
            requestBody = {
              required = true
              content = {
                "application/json" = {
                  schema = {
                    type = "object"
                    properties = {
                      evidence = { type = "object" }
                      patterns = { type = "array" }
                    }
                  }
                }
              }
            }
            responses = {
              "200" = {
                description = "Control coverage analysis"
              }
            }
          }
        }
        "/tools/generate-plan" = {
          post = {
            summary     = "Generate phased remediation plan"
            description = "Create 4-phase plan with dependencies and effort estimates"
            operationId = "generateRemediationPlan"
            requestBody = {
              required = true
              content = {
                "application/json" = {
                  schema = {
                    type = "object"
                    properties = {
                      gaps     = { type = "array" }
                      patterns = { type = "array" }
                    }
                  }
                }
              }
            }
            responses = {
              "200" = {
                description = "Remediation plan"
              }
            }
          }
        }
        "/tools/create-jira-epic" = {
          post = {
            summary     = "Create Jira epic with stories"
            description = "Create compliance epic and child stories for tracking"
            operationId = "createJiraEpic"
            requestBody = {
              required = true
              content = {
                "application/json" = {
                  schema = {
                    type = "object"
                    properties = {
                      remediation_plan = { type = "object" }
                      coverage_percent = { type = "integer" }
                    }
                  }
                }
              }
            }
            responses = {
              "200" = {
                description = "Epic and stories created"
              }
            }
          }
        }
      }
    })
  }
}

# Prepare the agent (creates working draft)
resource "aws_bedrockagent_agent_alias" "prod" {
  agent_alias_name = "PROD"
  agent_id         = aws_bedrockagent_agent.compliance.agent_id
  description      = "Production alias for compliance agent"

  tags = var.tags

  depends_on = [
    aws_bedrockagent_agent_action_group.compliance_tools
  ]
}

# Lambda permission for Bedrock Agent to invoke tools
resource "aws_lambda_permission" "bedrock_agent" {
  statement_id  = "AllowBedrockAgentInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.tool_lambda_name
  principal     = "bedrock.amazonaws.com"
  source_arn    = aws_bedrockagent_agent.compliance.agent_arn
}
