---
name: hipaa-eligible-check
description: Verify AWS services are HIPAA-eligible for handling ePHI. Checks architectures, Terraform, and service lists against the official AWS BAA-covered services. Use when designing or reviewing healthcare workloads.
---

# HIPAA Eligible Service Check

Validate that AWS services used in an architecture are covered under the AWS Business Associate Addendum (BAA) for handling electronic Protected Health Information (ePHI).

## Why This Matters

- AWS signs a BAA that covers **specific services only**
- Using non-eligible services for ePHI = **HIPAA violation**
- New services are added quarterly — this list is current as of Q1 2026

## HIPAA Eligible AWS Services

### Compute
| Service | Service ID | Notes |
|---------|------------|-------|
| Amazon EC2 | `ec2` | Including Dedicated Hosts, Spot |
| AWS Lambda | `lambda` | |
| Amazon ECS | `ecs` | |
| Amazon EKS | `eks` | |
| AWS Fargate | `fargate` | |
| AWS Batch | `batch` | |
| Amazon Lightsail | `lightsail` | |
| AWS Elastic Beanstalk | `elasticbeanstalk` | |
| AWS App Runner | `apprunner` | |
| Amazon EC2 Auto Scaling | `autoscaling` | |
| AWS Outposts | `outposts` | |
| Amazon EC2 Image Builder | `imagebuilder` | |
| AWS Wavelength | `wavelength` | |

### Containers
| Service | Service ID | Notes |
|---------|------------|-------|
| Amazon ECR | `ecr` | |
| Amazon ECS Anywhere | `ecs-anywhere` | |
| Amazon EKS Anywhere | `eks-anywhere` | |
| Amazon EKS Distro | `eks-distro` | |

### Storage
| Service | Service ID | Notes |
|---------|------------|-------|
| Amazon S3 | `s3` | Including S3 Glacier |
| Amazon EBS | `ebs` | |
| Amazon EFS | `efs` | |
| Amazon FSx | `fsx` | All variants (Lustre, Windows, NetApp, OpenZFS) |
| AWS Storage Gateway | `storagegateway` | |
| AWS Backup | `backup` | |
| Amazon S3 Glacier | `glacier` | |
| AWS Snow Family | `snow` | Snowball, Snowcone, Snowmobile |

### Database
| Service | Service ID | Notes |
|---------|------------|-------|
| Amazon RDS | `rds` | All engines (MySQL, PostgreSQL, Oracle, SQL Server, MariaDB) |
| Amazon Aurora | `aurora` | MySQL and PostgreSQL compatible |
| Amazon DynamoDB | `dynamodb` | |
| Amazon DocumentDB | `docdb` | |
| Amazon ElastiCache | `elasticache` | Redis and Memcached |
| Amazon Neptune | `neptune` | |
| Amazon Redshift | `redshift` | |
| Amazon Keyspaces | `keyspaces` | Cassandra compatible |
| Amazon QLDB | `qldb` | |
| Amazon Timestream | `timestream` | |
| Amazon MemoryDB | `memorydb` | |

### Networking & Content Delivery
| Service | Service ID | Notes |
|---------|------------|-------|
| Amazon VPC | `vpc` | Including subnets, NACLs, security groups |
| Elastic Load Balancing | `elb` | ALB, NLB, CLB, GLB |
| Amazon CloudFront | `cloudfront` | |
| Amazon Route 53 | `route53` | |
| AWS Direct Connect | `directconnect` | |
| AWS Transit Gateway | `transitgateway` | |
| AWS PrivateLink | `privatelink` | |
| Amazon API Gateway | `apigateway` | |
| AWS Global Accelerator | `globalaccelerator` | |
| Amazon VPC Lattice | `vpc-lattice` | |
| AWS App Mesh | `appmesh` | |
| AWS Cloud Map | `cloudmap` | |

### Security, Identity & Compliance
| Service | Service ID | Notes |
|---------|------------|-------|
| AWS IAM | `iam` | |
| AWS IAM Identity Center | `sso` | Formerly AWS SSO |
| Amazon Cognito | `cognito` | |
| AWS KMS | `kms` | |
| AWS Secrets Manager | `secretsmanager` | |
| AWS Certificate Manager | `acm` | |
| AWS WAF | `waf` | |
| AWS Shield | `shield` | Standard and Advanced |
| Amazon GuardDuty | `guardduty` | |
| AWS Security Hub | `securityhub` | |
| Amazon Inspector | `inspector` | |
| Amazon Macie | `macie` | |
| AWS Firewall Manager | `fms` | |
| Amazon Detective | `detective` | |
| AWS Audit Manager | `auditmanager` | |
| AWS CloudHSM | `cloudhsm` | |
| AWS Directory Service | `ds` | |
| AWS Resource Access Manager | `ram` | |
| Amazon Verified Permissions | `verifiedpermissions` | |

### Management & Governance
| Service | Service ID | Notes |
|---------|------------|-------|
| Amazon CloudWatch | `cloudwatch` | Including Logs, Metrics, Alarms |
| AWS CloudTrail | `cloudtrail` | |
| AWS Config | `config` | |
| AWS Systems Manager | `ssm` | |
| AWS Organizations | `organizations` | |
| AWS Control Tower | `controltower` | |
| AWS Service Catalog | `servicecatalog` | |
| AWS Trusted Advisor | `trustedadvisor` | |
| AWS Health | `health` | |
| AWS License Manager | `license-manager` | |
| AWS Compute Optimizer | `compute-optimizer` | |
| AWS Launch Wizard | `launchwizard` | |

### Analytics
| Service | Service ID | Notes |
|---------|------------|-------|
| Amazon Athena | `athena` | |
| Amazon EMR | `emr` | |
| Amazon Kinesis | `kinesis` | Data Streams, Firehose, Analytics, Video Streams |
| Amazon OpenSearch | `opensearch` | Formerly Elasticsearch |
| AWS Glue | `glue` | |
| Amazon QuickSight | `quicksight` | |
| AWS Data Pipeline | `datapipeline` | |
| AWS Lake Formation | `lakeformation` | |
| Amazon MSK | `msk` | Managed Kafka |
| AWS Data Exchange | `dataexchange` | |
| Amazon DataZone | `datazone` | |

### Application Integration
| Service | Service ID | Notes |
|---------|------------|-------|
| Amazon SNS | `sns` | |
| Amazon SQS | `sqs` | |
| Amazon EventBridge | `eventbridge` | |
| AWS Step Functions | `stepfunctions` | |
| Amazon MQ | `mq` | |
| Amazon AppFlow | `appflow` | |

### Machine Learning
| Service | Service ID | Notes |
|---------|------------|-------|
| Amazon SageMaker | `sagemaker` | |
| Amazon Comprehend | `comprehend` | Including Medical |
| Amazon Transcribe | `transcribe` | Including Medical |
| Amazon Rekognition | `rekognition` | |
| Amazon Textract | `textract` | |
| Amazon Translate | `translate` | |
| Amazon Polly | `polly` | |
| Amazon Lex | `lex` | |
| Amazon Personalize | `personalize` | |
| Amazon Forecast | `forecast` | |
| Amazon Kendra | `kendra` | |
| Amazon Bedrock | `bedrock` | |
| Amazon Q | `amazon-q` | |
| AWS HealthLake | `healthlake` | FHIR-compliant |
| Amazon HealthScribe | `healthscribe` | |

### Developer Tools
| Service | Service ID | Notes |
|---------|------------|-------|
| AWS CodeCommit | `codecommit` | |
| AWS CodeBuild | `codebuild` | |
| AWS CodeDeploy | `codedeploy` | |
| AWS CodePipeline | `codepipeline` | |
| AWS CodeArtifact | `codeartifact` | |
| AWS Cloud9 | `cloud9` | |
| AWS X-Ray | `xray` | |
| Amazon CodeGuru | `codeguru` | |
| Amazon CodeCatalyst | `codecatalyst` | |

### End User Computing
| Service | Service ID | Notes |
|---------|------------|-------|
| Amazon WorkSpaces | `workspaces` | |
| Amazon AppStream 2.0 | `appstream` | |
| Amazon WorkDocs | `workdocs` | |
| Amazon WorkLink | `worklink` | |
| Amazon Connect | `connect` | |
| Amazon Chime | `chime` | SDK only |
| Amazon Pinpoint | `pinpoint` | |

### Migration & Transfer
| Service | Service ID | Notes |
|---------|------------|-------|
| AWS DMS | `dms` | Database Migration Service |
| AWS Transfer Family | `transfer` | SFTP, FTPS, FTP |
| AWS DataSync | `datasync` | |
| AWS Migration Hub | `migrationhub` | |
| AWS Application Migration | `mgn` | |
| AWS Mainframe Modernization | `m2` | |

### Media Services
| Service | Service ID | Notes |
|---------|------------|-------|
| Amazon Elastic Transcoder | `elastictranscoder` | |
| AWS Elemental MediaConvert | `mediaconvert` | |
| AWS Elemental MediaLive | `medialive` | |
| AWS Elemental MediaPackage | `mediapackage` | |
| AWS Elemental MediaStore | `mediastore` | |
| Amazon Interactive Video Service | `ivs` | |

---

## NOT HIPAA Eligible (Common Mistakes)

These services are **NOT** covered under the AWS BAA:

| Service | Alternative |
|---------|-------------|
| Amazon Lightsail Databases | Use Amazon RDS |
| AWS Amplify Hosting | Use S3 + CloudFront |
| Amazon GameLift | N/A |
| AWS RoboMaker | N/A |
| Amazon Sumerian | N/A |
| AWS Ground Station | N/A |
| Amazon Braket | N/A |

---

## Validation Process

### 1. Identify Services in Use

Extract all AWS services from:
- Terraform resources (`aws_*` → service name)
- CloudFormation resources (`AWS::ServiceName::*`)
- Architecture diagrams
- Service lists

### 2. Check Against Eligible List

For each service:
```
IF service in HIPAA_ELIGIBLE_SERVICES:
    ✅ Eligible - OK for ePHI
ELSE:
    ❌ NOT Eligible - Cannot use for ePHI
```

### 3. Check Service Configuration

Even eligible services need proper configuration:
- Encryption at rest enabled
- Encryption in transit enabled
- Audit logging enabled
- Access controls configured

---

## Output Format

**CRITICAL RULE**: For every non-eligible service or configuration warning, provide the Terraform code to fix it.

```markdown
## HIPAA Eligibility Check Results

**Services Analyzed**: [count]
**Eligible**: [count]
**Not Eligible**: [count]

### ✅ Eligible Services
| Service | Resource | Notes |
|---------|----------|-------|
| Amazon S3 | aws_s3_bucket.data | Ensure encryption enabled |
| Amazon RDS | aws_db_instance.main | Ensure encryption enabled |

### ❌ Not Eligible - ACTION REQUIRED

For each non-eligible service, provide the replacement code:

#### [Non-Eligible Service] → [Alternative Service]

**Current (Non-Compliant)**:
```hcl
[The current Terraform code using non-eligible service]
```

**Replacement (HIPAA Eligible)**:
```hcl
[Complete Terraform code using the eligible alternative]
```

**Migration Notes**: [Any data migration or configuration changes needed]

---

### ⚠️ Configuration Warnings

Services are eligible but need configuration changes to be HIPAA compliant:

#### [Service Name] - [Issue]

**Current Code**:
```hcl
[Current configuration that's missing HIPAA requirements]
```

**Required Fix**:
```hcl
[Complete configuration with all HIPAA requirements met]
[Include encryption, logging, access controls, etc.]
```

---

### Complete Fix Script

```hcl
# ============================================
# HIPAA COMPLIANCE FIXES
# Add these resources/changes to your Terraform
# ============================================

[All fixes consolidated in one copy-paste block]
```
```

---

## Common Non-Eligible Service Replacements

### AWS Amplify Hosting → S3 + CloudFront

**Non-Eligible**:
```hcl
resource "aws_amplify_app" "frontend" {
  name       = "my-healthcare-app"
  repository = "https://github.com/org/repo"
}
```

**HIPAA-Eligible Replacement**:
```hcl
# S3 bucket for static hosting
resource "aws_s3_bucket" "frontend" {
  bucket = "my-healthcare-app-frontend"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# CloudFront distribution
resource "aws_cloudfront_distribution" "frontend" {
  origin {
    domain_name = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id   = "S3-${aws_s3_bucket.frontend.id}"

    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.frontend.cloudfront_access_identity_path
    }
  }

  enabled             = true
  default_root_object = "index.html"

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-${aws_s3_bucket.frontend.id}"
    viewer_protocol_policy = "redirect-to-https"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.frontend.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  logging_config {
    bucket = aws_s3_bucket.logs.bucket_domain_name
    prefix = "cloudfront/"
  }
}
```

---

## Terraform Resource to Service Mapping

| Terraform Resource | AWS Service | Eligible? |
|-------------------|-------------|-----------|
| `aws_instance` | EC2 | ✅ |
| `aws_lambda_function` | Lambda | ✅ |
| `aws_s3_bucket` | S3 | ✅ |
| `aws_db_instance` | RDS | ✅ |
| `aws_dynamodb_table` | DynamoDB | ✅ |
| `aws_sqs_queue` | SQS | ✅ |
| `aws_sns_topic` | SNS | ✅ |
| `aws_kinesis_stream` | Kinesis | ✅ |
| `aws_elasticsearch_domain` | OpenSearch | ✅ |
| `aws_opensearch_domain` | OpenSearch | ✅ |
| `aws_ecs_cluster` | ECS | ✅ |
| `aws_eks_cluster` | EKS | ✅ |
| `aws_cloudwatch_*` | CloudWatch | ✅ |
| `aws_cloudtrail` | CloudTrail | ✅ |
| `aws_kms_key` | KMS | ✅ |
| `aws_secretsmanager_secret` | Secrets Manager | ✅ |
| `aws_cognito_*` | Cognito | ✅ |
| `aws_api_gateway_*` | API Gateway | ✅ |
| `aws_apigatewayv2_*` | API Gateway | ✅ |
| `aws_lb` | ELB | ✅ |
| `aws_amplify_app` | Amplify | ❌ |
| `aws_gamelift_*` | GameLift | ❌ |

---

## When to Use This Skill

- Designing new healthcare applications
- Reviewing existing architectures for HIPAA compliance
- Pre-deployment validation
- Vendor/third-party service assessment
- Audit preparation
