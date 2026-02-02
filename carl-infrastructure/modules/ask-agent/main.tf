# Bedrock Ask Agent Module
# Creates AWS Bedrock Agent for /carl ask command
# Part of AgentCore Migration Phase 1

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

data "aws_caller_identity" "current" {}

# IAM Role for Bedrock Agent
resource "aws_iam_role" "agent" {
  name = "${var.name_prefix}-ask-agent-role"

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
        Resource = "arn:aws:bedrock:${var.region}::foundation-model/${var.foundation_model}"
      }
    ]
  })
}

# Bedrock Agent for /carl ask
resource "aws_bedrockagent_agent" "ask" {
  agent_name              = "${var.name_prefix}-ask-agent"
  agent_resource_role_arn = aws_iam_role.agent.arn
  foundation_model        = var.foundation_model

  description = "Advisory agent for /carl ask - intelligent Q&A with AWS environment scanning"

  instruction = <<-EOT
You are CARL's Advisory Agent, helping users understand their AWS environment and SOC 2 compliance.

Your capabilities:
1. **Scan AWS Resources** - Use scanning tools to get real data about the user's environment
2. **Answer Questions** - Provide specific answers based on actual AWS configuration
3. **SOC 2 Guidance** - Factor in compliance requirements when giving advice

Guidelines:
- ALWAYS scan relevant resources before answering infrastructure questions
- Be specific - use actual resource IDs, names, and configurations from scans
- Explain SOC 2 implications when relevant
- If you need more information, ask clarifying questions
- Keep responses concise but complete

Available scanning tools:
- scan_iam: Check IAM users, roles, policies, MFA status
- scan_vpc: Check VPCs, subnets, security groups, flow logs
- scan_s3: Check S3 buckets, encryption, public access
- scan_cloudtrail: Check CloudTrail configuration and logging
- scan_security_hub: Check Security Hub findings and compliance

CONSTRAINTS:
- Only READ from AWS - never suggest making changes without explicit request
- If unsure, explain your reasoning
- Be specific with resource names and IDs from scan results
EOT

  idle_session_ttl_in_seconds = 1800 # 30 minutes

  tags = var.tags
}

# Action Group for Scanning Tools
resource "aws_bedrockagent_agent_action_group" "scanning_tools" {
  agent_id                   = aws_bedrockagent_agent.ask.agent_id
  agent_version              = "DRAFT"
  action_group_name          = "ScanningTools"
  description                = "Tools for scanning AWS resources"
  skip_resource_in_use_check = true

  action_group_executor {
    lambda = var.tool_lambda_arn
  }

  # OpenAPI schema defining scanning tools
  api_schema {
    payload = jsonencode({
      openapi = "3.0.0"
      info = {
        title       = "CARL Scanning Tools"
        version     = "1.0.0"
        description = "Tools for scanning AWS resources"
      }
      paths = {
        "/tools/scan-iam" = {
          post = {
            summary     = "Scan IAM configuration"
            description = "Check IAM users, roles, policies, password policy, and MFA status"
            operationId = "scanIam"
            requestBody = {
              required = false
              content = {
                "application/json" = {
                  schema = {
                    type = "object"
                    properties = {
                      include_policies = {
                        type        = "boolean"
                        description = "Include detailed policy analysis"
                        default     = false
                      }
                    }
                  }
                }
              }
            }
            responses = {
              "200" = {
                description = "IAM scan results"
                content = {
                  "application/json" = {
                    schema = {
                      type = "object"
                      properties = {
                        users           = { type = "array" }
                        roles           = { type = "array" }
                        mfa_status      = { type = "object" }
                        password_policy = { type = "object" }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        "/tools/scan-vpc" = {
          post = {
            summary     = "Scan VPC configuration"
            description = "Check VPCs, subnets, security groups, NACLs, and flow logs"
            operationId = "scanVpc"
            requestBody = {
              required = false
              content = {
                "application/json" = {
                  schema = {
                    type = "object"
                    properties = {
                      vpc_id = {
                        type        = "string"
                        description = "Specific VPC ID to scan (optional, scans all if not provided)"
                      }
                    }
                  }
                }
              }
            }
            responses = {
              "200" = {
                description = "VPC scan results"
                content = {
                  "application/json" = {
                    schema = {
                      type = "object"
                      properties = {
                        vpcs            = { type = "array" }
                        subnets         = { type = "array" }
                        security_groups = { type = "array" }
                        flow_logs       = { type = "array" }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        "/tools/scan-s3" = {
          post = {
            summary     = "Scan S3 buckets"
            description = "Check S3 buckets for encryption, public access, versioning"
            operationId = "scanS3"
            requestBody = {
              required = false
              content = {
                "application/json" = {
                  schema = {
                    type = "object"
                    properties = {
                      bucket_name = {
                        type        = "string"
                        description = "Specific bucket to scan (optional, scans all if not provided)"
                      }
                    }
                  }
                }
              }
            }
            responses = {
              "200" = {
                description = "S3 scan results"
                content = {
                  "application/json" = {
                    schema = {
                      type = "object"
                      properties = {
                        buckets       = { type = "array" }
                        public_access = { type = "object" }
                        encryption    = { type = "object" }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        "/tools/scan-cloudtrail" = {
          post = {
            summary     = "Scan CloudTrail configuration"
            description = "Check CloudTrail trails, logging status, and S3 delivery"
            operationId = "scanCloudtrail"
            requestBody = {
              required = false
              content = {
                "application/json" = {
                  schema = {
                    type       = "object"
                    properties = {}
                  }
                }
              }
            }
            responses = {
              "200" = {
                description = "CloudTrail scan results"
                content = {
                  "application/json" = {
                    schema = {
                      type = "object"
                      properties = {
                        trails         = { type = "array" }
                        logging_status = { type = "object" }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        "/tools/scan-security-hub" = {
          post = {
            summary     = "Scan Security Hub findings"
            description = "Get Security Hub findings and compliance status"
            operationId = "scanSecurityHub"
            requestBody = {
              required = false
              content = {
                "application/json" = {
                  schema = {
                    type = "object"
                    properties = {
                      severity = {
                        type        = "string"
                        description = "Filter by severity (CRITICAL, HIGH, MEDIUM, LOW)"
                        enum        = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
                      }
                      max_findings = {
                        type        = "integer"
                        description = "Maximum findings to return"
                        default     = 50
                      }
                    }
                  }
                }
              }
            }
            responses = {
              "200" = {
                description = "Security Hub findings"
                content = {
                  "application/json" = {
                    schema = {
                      type = "object"
                      properties = {
                        findings          = { type = "array" }
                        compliance_status = { type = "object" }
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    })
  }
}

# Agent Alias for production use
resource "aws_bedrockagent_agent_alias" "prod" {
  agent_alias_name = "PROD"
  agent_id         = aws_bedrockagent_agent.ask.agent_id
  description      = "Production alias for ask agent"

  tags = var.tags

  depends_on = [
    aws_bedrockagent_agent_action_group.scanning_tools
  ]
}

# Lambda permission for Bedrock Agent to invoke tools
resource "aws_lambda_permission" "bedrock_agent" {
  statement_id  = "AllowBedrockAskAgentInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.tool_lambda_name
  principal     = "bedrock.amazonaws.com"
  source_arn    = aws_bedrockagent_agent.ask.agent_arn
}
