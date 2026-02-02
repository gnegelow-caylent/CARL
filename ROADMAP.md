# CARL Development Roadmap

This document outlines the priority roadmap for CARL development based on the gap analysis and strategic goals.

---

## ✅ Completed (Current Release)

### Foundation Module Deployment (January 29-30, 2026)
- ✅ Complete foundation module deployed to AWS
- ✅ KMS customer-managed key with comprehensive policy
- ✅ 10 DynamoDB tables (findings, evidence, preferences, approvals, remediations, conversations, exceptions, AI feedback, foundation, scan_history, resource_graph, pricing_cache)
- ✅ 3 Lambda functions (pricing-prefetch, pattern-analyzer, api)
- ✅ EventBridge schedules (monthly pricing refresh, daily pattern analysis)
- ✅ Secrets Manager integration with KMS encryption
- ✅ SNS topics for notifications
- ✅ CloudWatch Logs with KMS encryption
- ✅ S3 buckets with KMS encryption (evidence, reports, terraform state)
- ✅ All manual KMS policy changes captured in Terraform code
- ✅ Pricing prefetch system (366 items across 3 regions, 100+ services)
- ✅ Comprehensive deployment documentation (DEPLOYMENT_NOTES.md, 500+ lines)
- ✅ Cost verification: $2.61/month actual measured cost

**Impact:** CARL's foundation infrastructure is now fully deployed and operational. Real-time pricing cache enables <3 second architecture recommendations. All resources properly encrypted with customer-managed KMS key. Fresh deployments work without manual setup.

### Real-Time Pricing Tool (January 29, 2026)
- ✅ AWS Price List API integration for real-time pricing
- ✅ Pricing tool for AgentCore (any agent can use)
- ✅ Support for EC2, RDS, S3, Glue, DMS, Lambda, DynamoDB, Redshift, EMR, Kinesis, VPC, ELB
- ✅ Region-aware pricing with instance-specific queries
- ✅ Design Principle #3 documented: Cost-Aware Recommendations
- ✅ Updated AI prompts to always include cost analysis
- ✅ 330+ lines of new code (pricing_tool.py)

**Impact:** CARL now provides real-time AWS pricing data in all recommendations. Agents can autonomously query pricing when answering cost questions. Implements "always show cost" principle.

### Intelligent Scanning System (January 29, 2026)
- ✅ AI-driven scan decisions via AgentCore (replaces static keyword matching)
- ✅ Scanning tools for AgentCore: scan_iam, scan_s3, scan_vpc, scan_cloudtrail, scan_security_hub, scan_all
- ✅ Refactored `/carl ask` to use Agent-based intelligent scanning
- ✅ Removed 114 lines of static keyword matching
- ✅ Design Principle #4 documented: Continuous Learning & Environment Adaptation
- ✅ Natural language understanding for scan decisions
- ✅ 340+ lines of new code (scanning_tools.py)
- ✅ Scalable to 200+ AWS services without code changes

**Impact:** CARL now uses AI to intelligently decide what to scan based on user questions. No more brittle keyword matching. System continuously learns and adapts to your environment. Implements "continuous learning" principle.

### Continuous Learning System - Phase 2 (January 29, 2026)
- ✅ Scan history DynamoDB table for logging interactions
- ✅ Resource knowledge graph table for tracking AWS resources
- ✅ LearningService for interaction logging and pattern analysis
- ✅ User feedback buttons (👍 👎) on all `/carl ask` responses
- ✅ Feedback handler integration with Slack interactions
- ✅ Pattern analyzer Lambda function (runs daily at 2am UTC)
- ✅ CloudWatch metrics for learning progress tracking
- ✅ Learned context injection into agent instructions
- ✅ EventBridge schedule for automated pattern analysis
- ✅ Complete documentation (CONTINUOUS_LEARNING.md)
- ✅ 580+ lines of learning service code
- ✅ 200+ lines of pattern analysis code

**Impact:** CARL now learns from every interaction! Tracks which scans are useful, builds resource knowledge graph, adapts to your environment, and improves automatically over time. Feedback loop enables true continuous learning. Cost: ~$0.67/month.

### Smart Infrastructure Generation (January 28, 2026)
- ✅ Resource detection service (scans AWS before generating code)
- ✅ Environment-aware code generation (only creates missing resources)
- ✅ Security resource detection (GuardDuty, Security Hub, Config, CloudTrail)
- ✅ Networking resource detection (VPC, subnets, NAT gateways)
- ✅ Dynamic Terraform generation (data sources for existing, resources for missing)
- ✅ Smart compliance notes (reflects actual environment)
- ✅ Zero manual configuration (no more create_XXX variables)
- ✅ Updated blueprints: security/basic-stack, security/soc2-stack, networking/basic-vpc
- ✅ 300+ lines of new code (resource_detector.py)
- ✅ 2,000+ lines refactored (infrastructure_builder.py)

**Impact:** CARL now scans your AWS environment and generates intelligent infrastructure code. No duplicate resources, no manual configuration, cleaner code.

### Pattern Expansion (January 27, 2026)
- ✅ VPC Endpoints & PrivateLink patterns (3 patterns)
- ✅ KMS key management patterns (4 patterns)
- ✅ Pattern count increased: 36 → 43+

**Note:** Bootstrap automation code was removed (Feb 1, 2026) as redundant with Account Factory and Foundation Builder.

### Jira Integration - Phase 1A (January 28, 2026)
- ✅ Core Jira service (Jira Cloud REST API integration)
- ✅ Jira security sync service (bi-directional CARL ↔ Jira)
- ✅ Webhook handler for Jira → CARL updates
- ✅ Slack commands: `/carl jira test`, `/carl jira sync`, `/carl jira status`
- ✅ Enhanced `/carl findings` with Jira ticket links
- ✅ DynamoDB schema design (GSIs for ticket lookup)
- ✅ Complete documentation (3 guides, 2,000+ lines)
- ✅ 1,000+ lines of new code

**Impact:** CARL can now sync security findings, exceptions, and drift to Jira for tracking and collaboration. Ready for Jira Cloud instance setup.

### Comprehensive Pattern Library Expansion (January 30, 2026)
- ✅ **ETL & Data Processing patterns** (4 patterns): AWS Glue ETL (serverless vs provisioned), Step Functions orchestration, Glue Data Quality validation, complete production ETL pipeline with monitoring
- ✅ **Serverless API patterns** (4 patterns): API Gateway+Lambda basics, complete production API with Cognito+WAF+monitoring, AppSync GraphQL with real-time subscriptions, AWS Amplify full-stack development
- ✅ **Container Application patterns** (4 patterns): ALB+ECS deployment options, ECS Fargate production apps, complete ECS with blue/green deployment and CI/CD, EKS vs ECS decision framework
- ✅ **Backup & Disaster Recovery patterns** (3 patterns): AWS Backup centralized management with tag-based policies, DR strategies comparison (Backup & Restore/Pilot Light/Warm Standby/Hot Standby), complete backup+DR solution with cross-region replication
- ✅ **CI/CD Pipeline patterns** (5 patterns): GitHub Actions+OIDC (free, secure), AWS CodePipeline with approval gates, ECS Fargate deployment with blue/green, Lambda deployment with SAM canary, complete production CI/CD with security scanning
- ✅ **File Storage patterns** (3 patterns): EFS shared storage with lifecycle policies, FSx for Windows File Server with Active Directory, FSx for Lustre for HPC workloads
- ✅ **Streaming & Real-Time patterns** (3 patterns): Kinesis Data Streams vs Firehose decision framework, real-time stream processing (Lambda vs Kinesis Data Analytics), complete production streaming pipeline with monitoring and data lake
- ✅ **Additional AWS Services** (4 patterns): Redshift data warehouse (Serverless vs Provisioned cost comparison), DocumentDB (MongoDB-compatible) vs MongoDB Atlas, AWS Network Firewall for compliance, Cognito user authentication with MFA
- ✅ **Pattern integration into AI** - Updated slack_router.py Terraform generation prompt with comprehensive examples from all new patterns
- ✅ **Validation checklist expansion** - Added checks for Serverless APIs, Container apps, ETL, Backup & DR, CI/CD, and Streaming
- ✅ 8 new pattern files created (2,800+ lines of code)
- ✅ Pattern count increased: **43 → 130+ patterns across 35 files**

**Impact:** CARL now has comprehensive coverage of all major AWS infrastructure types. AI can generate production-ready Terraform for Serverless APIs, Container apps, ETL pipelines, CI/CD, Streaming, and more - all with security best practices, monitoring, cost estimates, and SOC 2 control mappings. This completes the core pattern library needed for most enterprise AWS deployments.

### AI-Enhanced Compliance Reports (January 31, 2026)
- ✅ **AI-Generated Executive Summaries** (3-4 sentences, business-focused)
- ✅ **AI-Generated Full Report Summaries** (5-7 sentences with technical context)
- ✅ **AI-Generated Key Insights** (pattern identification, systemic issues)
- ✅ **AI-Generated Priority Recommendations** (3-4 actionable items with effort estimates)
- ✅ **Professional PDF Generation** (WeasyPrint + Matplotlib, no blank pages)
- ✅ **Clean Slack Formatting** (removed all markdown from status messages)
- ✅ **Compliance Score Calculation** (findings-based scoring, not just coverage)
- ✅ **Control Name Extraction** (meaningful descriptions extracted from SOC2_CONTROL_DESCRIPTIONS)
- ✅ **Status Filtering** (only shows OPEN findings, excludes remediated/closed)
- ✅ **Smart Page Breaks** (conditional logic prevents blank pages)
- ✅ 300+ lines of new AI code (AI summary, insights, recommendations)
- ✅ Executive reports: 3-4 pages, concise
- ✅ Full reports: 8-10 pages with Summary, Insights, Recommendations sections

**Impact:** CARL now generates professional, AI-enhanced compliance reports that provide actionable insights and recommendations. Executive reports are concise and business-focused (3-4 pages), while full audit reports are detailed with AI-powered pattern analysis and remediation guidance (8-10 pages). All Slack status messages now use clean formatting without markdown. Cost: ~$0.10-0.30 per report generation.

---

## 🔴 High Priority (Next 4-8 weeks)

### Phase 1: Missing Security Patterns & AgentCore Migration

#### 1.1 Migrate to AWS Bedrock AgentCore (Week 1-4)
**Goal:** Refactor custom AgentCore to use AWS Bedrock AgentCore managed platform (Design Principle #7: Use AWS Managed Services)

**Why:**
- **Follows Design Principle #7**: Use AWS managed services wherever possible
- **Reduces operational overhead**: AWS manages agentic orchestration, scaling, monitoring
- **Enterprise features CARL needs**: Persistent memory, 8-hour task support, session isolation, code interpreter, browser automation, built-in evaluators
- **Cost-effective**: ~$0.40/month platform fee (acceptable for removing ~2,000 lines of custom code)
- **Better compliance**: AWS-managed security, audit trails, enterprise-grade isolation

**Current State:**
- CARL uses custom `AgentCore` class (~500 lines in agent_core.py)
- Custom session management via DynamoDB (foundation table)
- Custom learning system (scan_history, resource_graph tables, 580+ lines)
- Manual threading for long-running tasks
- Limited to 15-minute Lambda timeout

**Target State:**
- Use AWS Bedrock AgentCore Runtime for agent execution
- Use AgentCore Memory for persistent learning (replaces scan_history/resource_graph)
- Use AgentCore Gateway for tool management (replaces manual tool registration)
- Use AgentCore Observability for monitoring (replaces custom CloudWatch logging)
- Use AgentCore Policy for access control (enterprise security)

**Tasks:**
- [ ] **Phase 1: POC (Week 3)** - Migrate `/carl ask` agent to AgentCore Runtime
  - [ ] Set up AgentCore Runtime environment
  - [ ] Convert scanning tools to AgentCore Gateway format
  - [ ] Test persistent memory vs. custom learning tables
  - [ ] Compare costs (custom vs. AgentCore)
  - [ ] A/B test: custom vs. AgentCore for 1 week

- [ ] **Phase 2: Evaluation (Week 4)** - Measure benefits and limitations
  - [ ] Performance comparison (response time, accuracy)
  - [ ] Cost analysis (actual spend vs. estimates)
  - [ ] Feature comparison (persistent memory, long tasks, code interpreter)
  - [ ] Decision point: proceed or stay with custom?

- [ ] **Phase 3: Full Migration (Week 5-6)** - If POC succeeds
  - [ ] Migrate architecture agent to AgentCore
  - [ ] Migrate compliance agent to AgentCore
  - [ ] Remove custom tables (scan_history, resource_graph, foundation - if AgentCore Memory replaces them)
  - [ ] Update documentation (CARL_DESIGN_PRINCIPLES.md, ARCHITECTURE.md)
  - [ ] Remove ~2,000 lines of custom agent code

**Deliverables:**
- POC demonstrating AgentCore Runtime with CARL's scanning tools
- Cost/benefit analysis comparing custom vs. managed
- Decision document: migrate or stay custom
- If migrating: All agents running on AgentCore, custom code removed

**Estimated Effort:** 3-4 weeks

**Risk Mitigation:**
- Keep custom AgentCore as fallback during migration
- A/B test before full switchover
- Can abort migration if AgentCore doesn't meet needs

---

#### 1.2 Remaining Critical Security Patterns ~~(Week 3-4)~~ ✅ **COMPLETED January 31, 2026**
**Goal:** Complete security service coverage

**Tasks:**
- ✅ **CloudWatch Alerting Patterns** (High Priority) - **COMPLETED**
  - ✅ CloudWatch Alarms patterns (3 patterns: Basic Metric, Composite, Anomaly Detection)
  - ✅ Notification Strategies patterns (3 patterns: SNS to Email, SNS to Slack, PagerDuty)
  - ✅ Cost: Free + SNS charges
  - ✅ 850+ lines (cloudwatch_alerting_patterns.py)

- ✅ **AWS WAF Patterns** (High Priority) - **COMPLETED**
  - ✅ WAF Deployment patterns (3 patterns: Managed Rules Only, Rate Limiting + Geo-Blocking, Advanced Bot Management)
  - ✅ WAF Location patterns (2 patterns: ALB WAF (Regional), CloudFront WAF (Global))
  - ✅ Cost: $5-100/mo
  - ✅ 650+ lines (waf_patterns.py)

- ✅ **AWS Certificate Manager Patterns** - **COMPLETED**
  - ✅ Certificate patterns (3 patterns: Single Domain, Wildcard, Multi-Domain SAN)
  - ✅ Certificate Location patterns (2 patterns: Regional ALB/NLB, Global CloudFront)
  - ✅ Certificate Monitoring patterns (2 patterns: CloudWatch Alarms, AWS Config Rules)
  - ✅ Cost: Free
  - ✅ 720+ lines (certificate_manager_patterns.py)

- [ ] **Secrets Manager Lifecycle Patterns** - **DEFERRED to next milestone**
  - Secret rotation strategies
  - Lambda rotation functions
  - Application integration
  - Cost: $0.40/secret/mo

**Deliverables:**
- ✅ **18 new security patterns** (exceeded goal of 8+)
- ✅ **Pattern count: 130 → 148+** (added 18 patterns across 3 new files)
- ✅ **Modular pattern loading system** - Auto-discovers new pattern files, no manual imports needed
- ✅ **Complete monitoring & security coverage** (CloudWatch, WAF, Certificates)
- ✅ 2,220+ lines of production-ready pattern code

**Estimated Effort:** 2 weeks → **Actual: 1 day** (January 31, 2026)

---

#### ~~1.3 Account Baseline Deployment Automation~~ ✅ **COVERED BY EXISTING FEATURES**

**Status:** Functionality covered by Foundation Builder (single account) and Account Factory (multi-account with AFT).

---

#### 1.5 CARL Uninstall & Cleanup Process (Week 7-8)
**Goal:** Provide a clean, safe way to uninstall CARL and remove all AWS resources

**Problem:**
- No documented process for uninstalling CARL infrastructure
- Long-running operations (account factory, foundation builder) lack detailed status tracking
- Users need visibility into what resources will be deleted
- Risk of orphaned resources or incomplete cleanup

**Tasks:**
- [ ] **Uninstall Command**
  - Create `/carl uninstall` command with confirmation workflow
  - List all resources that will be deleted
  - Require multi-step confirmation (type "DELETE CARL" to proceed)
  - Generate Terraform destroy plan before execution
  - Option to preserve data (findings, evidence, reports) in S3

- [ ] **Resource Inventory**
  - Scan and list all CARL-managed resources
  - Show resource dependencies and deletion order
  - Estimate time for complete cleanup
  - Warn about potential costs during cleanup

- [ ] **Enhanced Status Tracking for Long Operations**
  - Add detailed status updates for Account Factory AFT generation:
    * "⏳ Step 1/5: Analyzing account requirements..."
    * "⏳ Step 2/5: Generating AFT Terraform configuration..."
    * "⏳ Step 3/5: Validating Terraform syntax..."
    * "⏳ Step 4/5: Uploading to GitHub..."
    * "✅ Step 5/5: Complete - PR created"
  - Add progress bars for Foundation Builder steps
  - Add ETA estimates for operations >30 seconds
  - Store operation logs in DynamoDB for troubleshooting

- [ ] **Cleanup Verification**
  - Post-uninstall verification script
  - Check for orphaned resources
  - Confirm all DynamoDB tables deleted
  - Confirm all S3 buckets deleted or preserved
  - Confirm all Lambda functions deleted
  - Generate uninstall report with any manual cleanup steps needed

- [ ] **Documentation**
  - UNINSTALL.md guide with step-by-step instructions
  - FAQ for common uninstall scenarios
  - Troubleshooting guide for failed cleanup
  - Cost implications of uninstall (final AWS charges)

**Deliverables:**
- `/carl uninstall` command with safety confirmations
- Improved status tracking for account factory (slack_router.py:1017)
- Uninstall verification script
- Complete uninstall documentation

**Estimated Effort:** 1-2 weeks

**Priority:** Medium - Not urgent but important for production deployments

---

#### 1.7 AI-Driven Terraform Generation Migration (Week 9-10)
**Goal:** Migrate all remaining Terraform generators to use AI-driven generation with architecture patterns as grounding

**Background:**
Per CLAUDE.md Design Principle: "Dynamic Processing Over Static Rules" - CARL should not maintain static Terraform templates. Instead, AI generates Terraform code dynamically using architecture patterns from `knowledge/` as grounding context.

**Completed (February 1, 2026):**
- ✅ Created `ai_terraform_generator.py` - Core AI-driven Terraform generation service
- ✅ Added `generate_terraform` tool to `architecture_tools.py` - Agents can now generate Terraform
- ✅ Refactored Account Factory (`account_factory_service.py`) to use AI-driven generation
- ✅ Refactored Foundation Builder (`foundation_builder.py`) to use AI-driven generation

**Remaining Tasks:**
- [ ] Refactor `terraform_generator.py` to use AI-driven generation
- [ ] Refactor `infrastructure_builder.py` to use AI-driven generation
- [ ] Remove static template methods from Foundation Builder (currently unused)
- [ ] Remove old `aft_generator.py` static templates (replaced by AI)
- [ ] Update `/carl build` command to use AI-driven generation
- [ ] Add validation layer to ensure AI-generated Terraform is syntactically correct
- [ ] Add `terraform validate` integration for generated code
- [ ] Update pattern files to include more Terraform-specific examples for grounding

**Architecture:**
```
User Request → Agent decides what to generate → generate_terraform tool
                                                      ↓
                                            AITerraformGenerator
                                                      ↓
                                  Architecture Patterns (grounding context)
                                                      ↓
                                         BedrockService (Claude)
                                                      ↓
                                        Generated Terraform Code
                                                      ↓
                                        Validation (syntax check)
                                                      ↓
                                              Return to Agent
```

**Benefits:**
- No more 2000+ line static template files to maintain
- AI adapts to new AWS services without code changes
- Patterns provide grounding to prevent hallucinations
- Consistent with CARL's AI-first design philosophy

**Estimated Effort:** 2 weeks (remaining tasks)

---

#### 1.8 Terraform Module Generation (Week 11-12)
**Goal:** Generate Terraform code for infrastructure modules

**Tasks:**
- [ ] Organizations Terraform module generator
- [ ] Identity Center Terraform module generator
- [ ] Security services Terraform module generator
- [ ] VPC endpoints Terraform module generator
- [ ] KMS keys Terraform module generator
- [ ] Account baseline Terraform module generator
- [ ] Complete environment Terraform generator (orchestrated)

**Deliverables:**
- Terraform generation for Account Factory modules
- Complete Terraform codebase for multi-account environment
- Modular, reusable Terraform modules

**Estimated Effort:** 2 weeks

---

#### 1.9 Regression Testing Framework (Week 13-14)
**Goal:** Ensure changes don't break existing functionality

**Problem:**
- Major features being added (framework-aware foundation, compliance reports, etc.)
- No automated tests to catch regressions
- Manual testing is time-consuming and incomplete
- Risk of breaking production features with new changes

**Tasks:**
- [ ] **Core Feature Regression Tests**
  - Test AI-enhanced compliance reports (executive, full, control-specific)
  - Test framework-aware foundation flow (SOC 2 framework selection → gap analysis → Terraform generation)
  - Test blueprint generation (security/basic-stack, security/soc2-stack, networking/basic-vpc)
  - Test `/carl ask` with intelligent scanning
  - Test Jira integration (sync, ticket creation, deduplication)
  - Test findings management (create, update, status filtering)

- [ ] **Integration Testing**
  - Test Bedrock API integration (AI summaries, insights, recommendations)
  - Test DynamoDB operations (findings, evidence, exceptions, scan history)
  - Test S3 operations (evidence collection, report uploads)
  - Test Slack interactions (messages, buttons, file uploads)
  - Test GitHub integration (PR creation, code uploads)

- [ ] **PDF Generation Testing**
  - Test executive reports (3-4 pages, no blank pages)
  - Test full audit reports (8-10 pages with insights/recommendations)
  - Test control-specific reports
  - Test chart generation (compliance score, findings by severity)
  - Test page breaks logic (no blank pages regression)

- [ ] **Framework Testing**
  - Test FrameworkLoader (YAML parsing, service lookup)
  - Test FrameworkGapAnalyzer (gap detection, validation checks)
  - Test compliance Terraform generation (CloudTrail, GuardDuty, Config, etc.)
  - Test framework questions flow

- [ ] **Test Infrastructure**
  - Set up pytest framework
  - Create mock AWS responses (boto3 mocking)
  - Create test fixtures for reports, findings, frameworks
  - Add GitHub Actions workflow for automated test runs
  - Add test coverage reporting

**Deliverables:**
- Comprehensive regression test suite (100+ tests)
- CI/CD integration (tests run on every PR)
- Test coverage report (target: 70%+ coverage)
- Automated nightly test runs
- Regression test documentation

**Estimated Effort:** 2 weeks

**Priority:** High - Critical for maintaining quality as we add features

---

## 🟡 Medium Priority (8-16 weeks)

### Phase 2: Missing Architecture Patterns

#### 2.1 Compute Security Patterns (Week 9-10)
**Goal:** Add patterns for compute services

**Tasks:**
- [ ] **EC2 Security Patterns** (3 patterns)
  - Instance types & sizing strategy
  - Security group design
  - Patch management (Systems Manager)
  - AMI hardening (CIS benchmarks)
  - IMDSv2 enforcement

- [ ] **ECS/Fargate Security Patterns** (3 patterns)
  - Task definition security
  - Secrets injection
  - Network mode selection
  - IAM task roles
  - ECR image scanning

- [ ] **EKS Security Patterns** (3 patterns)
  - Node groups vs Fargate
  - IRSA (IAM Roles for Service Accounts)
  - Pod security policies
  - Network policies
  - Secrets management (External Secrets Operator)

- [ ] **Lambda Security Patterns** (3 patterns)
  - VPC configuration
  - Layer security
  - Environment variable encryption
  - IAM least privilege
  - Runtime security

**Deliverables:**
- 12 new compute patterns
- Pattern count: 138 → 150+

**Estimated Effort:** 2 weeks

---

#### 2.2 Database Deployment Patterns (Week 11-12)
**Goal:** Add patterns for database services

**Tasks:**
- [ ] **RDS Patterns** (3 patterns)
  - Multi-AZ vs read replicas
  - Encryption at rest
  - Backup and PITR
  - Parameter groups
  - Performance insights

- [ ] **Aurora Patterns** (3 patterns)
  - Serverless v2 vs provisioned
  - Global Database
  - Backtrack
  - Aurora Replicas
  - Storage encryption

- [ ] **DynamoDB Patterns** (3 patterns)
  - On-demand vs provisioned
  - Global Tables
  - Point-in-time recovery
  - Encryption at rest
  - DynamoDB Streams

- [ ] **ElastiCache Patterns** (2 patterns)
  - Redis vs Memcached
  - Cluster mode
  - Encryption in transit
  - Backup strategy

**Deliverables:**
- 11 new database patterns
- Pattern count: 150 → 161+

**Estimated Effort:** 2 weeks

---

#### 2.3 Application Service Patterns (Week 13-14)
**Goal:** Add patterns for application services

**Tasks:**
- [ ] **API Gateway Patterns** (3 patterns)
  - REST vs HTTP vs WebSocket
  - Regional vs edge-optimized
  - Authorization (Lambda, IAM, Cognito)
  - Throttling and caching
  - Private API patterns

- [ ] **Load Balancer Patterns** (3 patterns)
  - ALB vs NLB detailed comparison
  - Target group strategies
  - Health check patterns
  - SSL/TLS termination
  - Cross-zone load balancing

- [ ] **Message Queue Patterns** (3 patterns)
  - SQS standard vs FIFO
  - SNS fan-out patterns
  - EventBridge event patterns
  - Dead letter queues
  - Message encryption

**Deliverables:**
- 9 new application patterns
- Pattern count: 161 → 170+

**Estimated Effort:** 2 weeks

---

#### 2.4 Storage Patterns (Week 15-16)
**Goal:** Add advanced S3 and storage patterns

**Tasks:**
- [ ] **S3 Advanced Patterns** (3 patterns)
  - Lifecycle policies (storage class transitions)
  - Replication (CRR, SRR, Batch Replication)
  - Intelligent tiering
  - Object Lock (compliance mode)
  - Inventory and analytics

- [ ] **EFS/FSx Patterns** (2 patterns)
  - EFS performance modes
  - FSx for Windows vs Lustre vs NetApp
  - Backup strategies
  - Encryption

**Deliverables:**
- 5 new storage patterns
- Pattern count: 170 → 175+

**Estimated Effort:** 2 weeks

---

## 🟢 Lower Priority (16+ weeks)

### Phase 3: Adaptive Monitoring & Intelligence

#### 3.1 Adaptive Monitoring Foundation (Week 17-20)
**Goal:** Add intelligence to CARL's monitoring

**Tasks:**
- [ ] Auto-discovery service
  - Detect new AWS services deployed
  - Detect new resources in accounts
  - Suggest monitoring enablement

- [ ] Auto-enablement service
  - Enable GuardDuty in new accounts automatically
  - Enable Security Hub in new accounts
  - Enable Inspector for new workloads
  - Deploy Config rules for new resource types

- [ ] Dynamic baseline learning
  - Learn normal patterns from CloudWatch metrics
  - Establish baselines for cost, traffic, usage
  - Detect anomalies based on learned baselines

- [ ] Self-healing triggers
  - Detect drift and trigger auto-remediation
  - Detect disabled services and re-enable
  - Detect non-compliant resources and fix

**Deliverables:**
- Auto-discovery engine
- Auto-enablement automation
- Baseline learning system
- Self-healing framework

**Estimated Effort:** 4 weeks

---

#### 3.2 Auto-Remediation Execution (Week 21-22)
**Goal:** Execute remediations automatically

**Tasks:**
- [ ] Remediation action library
  - S3 bucket encryption enablement
  - Security group rule fixes
  - IAM policy updates
  - Config rule remediations

- [ ] Approval workflow for high-risk remediations
  - Slack approval buttons
  - Multi-level approval
  - Rollback capability

- [ ] Remediation testing framework
  - Dry-run mode
  - Rollback automation
  - Impact analysis

**Deliverables:**
- Auto-remediation engine
- 20+ remediation actions
- Approval workflows
- Testing framework

**Estimated Effort:** 2 weeks

---

#### 3.3 Multi-Framework Support (Week 23-26)
**Goal:** Expand beyond SOC 2

**Tasks:**
- [ ] HIPAA control mappings
  - Map AWS services to HIPAA requirements
  - HIPAA-specific patterns
  - BAA evidence collection

- [ ] PCI-DSS control mappings
  - Payment card data requirements
  - PCI-DSS patterns
  - Cardholder data environment (CDE) isolation

- [ ] ISO 27001 control mappings
  - Information security controls
  - ISO 27001 patterns
  - ISMS documentation

- [ ] Framework selection in CARL
  - `/carl framework select hipaa|pci|iso27001`
  - Framework-specific recommendations
  - Framework-specific reports

**Deliverables:**
- HIPAA support
- PCI-DSS support
- ISO 27001 support
- Framework selector

**Estimated Effort:** 4 weeks

---

#### 3.4 Advanced Intelligence (Week 27-30)
**Goal:** ML-based insights

**Tasks:**
- [ ] Cost anomaly detection
  - Detect unusual cost spikes
  - Predict future costs
  - Recommend optimizations

- [ ] Security anomaly detection
  - Behavioral analysis
  - Unusual API calls
  - Lateral movement detection

- [ ] Predictive compliance scoring
  - Predict compliance gaps before audit
  - Recommend preemptive fixes
  - Compliance trend analysis

- [ ] Intelligent alerting
  - Reduce false positives
  - Alert prioritization
  - Context-aware notifications

**Deliverables:**
- ML-based anomaly detection
- Predictive models
- Intelligent alerting

**Estimated Effort:** 4 weeks

---

## 🔮 Future/Optional Features

These are features that have been discussed and designed but deferred for later consideration. They are not currently on the roadmap but may be added based on user feedback and business priorities.

### AI Framework Evaluation (LangChain, LlamaIndex, CrewAI, etc.)

**Status:** To be reviewed

**Question:** Should CARL use a common AI framework instead of custom orchestration?

**Current CARL Approach:**
- Direct Anthropic/Bedrock API calls
- Custom session/state management
- Custom prompt building
- Straightforward request → generate → upload flows

**Frameworks to Evaluate:**
- **LangChain** - Popular LLM orchestration, chains, agents, memory, tools
- **LlamaIndex** - Data framework, excellent for RAG
- **CrewAI** - Multi-agent collaboration
- **AutoGen** - Microsoft's multi-agent framework
- **Semantic Kernel** - Microsoft's orchestration SDK

**When a Framework Would Help:**
- Complex multi-step agent reasoning
- RAG (retrieval-augmented generation) from docs/policies/runbooks
- Memory/context across long conversations
- Multi-agent collaboration (Advisory → Architect handoff)
- Standardized tool/function calling patterns

**When It's Overkill:**
- Simple request → response flows
- Well-defined, deterministic workflows
- When full control over prompts and behavior is needed

**Potential Use Cases for CARL:**
- Add RAG over AWS docs, compliance policies, internal runbooks
- Build more autonomous planning (agent decides what to build)
- Add conversation memory across sessions
- Create specialized sub-agents (security reviewer, cost optimizer)

**Trade-offs:**
- **Pro:** Standardized patterns, built-in memory, community plugins
- **Con:** Added dependency, framework lock-in, abstraction overhead, version churn

**Decision Needed:**
- Evaluate if CARL's complexity warrants framework adoption
- Consider for Phase 4+ after core features are stable
- Test with a small POC (e.g., RAG over AWS Well-Architected docs)

**Estimated Effort:** 2-3 weeks for POC evaluation

**Priority:** Low - Current approach works well for CARL's guided workflows

---

### Historical Findings & Compliance Reporting

**Status:** Documented for future consideration

**Problem:**
Currently, findings are stored in DynamoDB indefinitely. There's no mechanism for:
- Historical analysis ("Show me all findings from Q1 2026")
- Compliance trend reporting ("We had 50 findings in January, 30 in February")
- Long-term audit evidence ("Prove we maintained <10 critical findings all year")

**Proposed Solution:**
1. **Add DynamoDB TTL** - Auto-expire findings after configurable period (default 90 days)
2. **Archive to S3** - Before deletion, archive findings to S3 in Parquet/JSON format
3. **Historical Reporting** - New commands to query archived data:
   - `/carl findings history --from 2026-01-01 --to 2026-03-31`
   - `/carl report trends --period quarterly`
   - `/carl evidence audit-trail --control CC6.1 --year 2026`

**Benefits:**
- SOC 2 auditors can see historical compliance posture
- Track remediation velocity over time
- Prove continuous compliance for certification
- Reduce DynamoDB storage costs (move cold data to S3)

**Implementation Considerations:**
- DynamoDB TTL is free
- S3 archival is cheap (~$0.023/GB/month in Standard-IA)
- Need to design query interface for archived data (Athena?)
- Re-scanning creates fresh findings anyway, so expiration is safe
- State fields (jira_ticket_id, ignored, exception_id) should be preserved even after TTL

**Estimated Effort:** 1-2 weeks

**Priority:** Low (current approach works fine, this is optimization + reporting enhancement)

**Related Design Decision:**
- We explicitly decided NOT to implement TTL in the initial release
- Current behavior: Findings persist indefinitely, re-scans update existing findings
- This is simpler and meets current needs (Jira deduplication, state tracking, audit trail)
- TTL + archival is only needed if users request historical trend analysis

---

### Interactive Requirements Gathering for Architecture Questions

**Status:** Documented for future implementation with Architect Agent

**Problem:**
Currently, when users ask architecture questions that need more details, CARL asks follow-up questions in text:
```
User: /carl ask I need an ETL solution
CARL: "Tell me your database type, data volume, table count..."
User: /carl ask SQL Server, 50GB daily, 100 tables (has to re-type context)
```

This works but is clunky for multi-parameter questions.

**Proposed Solution:**

**Phase 1: Advisory → Architect Handoff** (When Architect Agent is built)
```
User: /carl ask I need an ETL solution
Advisory Agent: Detects this is an architecture/build question
Advisory Agent: "This looks like an architecture project. Would you like me to hand off to the Architect Agent to design and build this?"
User: yes
Advisory Agent: Hands off to Architect Agent with context
```

**Phase 2: Architect Agent Interactive Forms**
```
Architect Agent: Opens Slack modal with structured form
┌─────────────────────────────────────────┐
│ ETL Solution Requirements               │
├─────────────────────────────────────────┤
│ Database Type: [SQL Server ▼]           │
│ Data Volume:   [50] GB daily            │
│ Table Count:   [100]                    │
│ Target:        [Redshift ▼]             │
│ Schedule:      [Hourly ▼]               │
│                                         │
│           [Cancel]  [Generate Code]     │
└─────────────────────────────────────────┘

Architect Agent:
1. Scans user's VPC, security groups
2. Selects appropriate patterns (Glue vs DMS vs EMR)
3. Generates Terraform code
4. Includes cost estimates
5. Creates GitHub PR
```

**Benefits:**
- Clean separation: Advisory = Q&A, Architect = Build
- Structured data collection (forms better than chat for multi-param)
- User doesn't lose context between questions
- Architect Agent can have complex multi-step workflows
- Handoff pattern works for other agents too (Remediation, Compliance)

**Implementation Considerations:**
- Advisory Agent needs `handoff_to_architect` tool (already defined in ADVISORY_AGENT.md)
- Architect Agent needs modal/form UI components
- Need session management to preserve context across handoff
- Slack modals support up to 10 form fields with validation

**Estimated Effort:**
- Phase 1 (Handoff): 1-2 days (when Architect Agent exists)
- Phase 2 (Interactive Forms): 1 week (modal UI, form processing, validation)

**Priority:** Medium - Implement with Architect Agent (Phase 2 of roadmap)

**Current Workaround:**
- User can re-ask with more details: `/carl ask SQL Server ETL, 50GB daily, 100 tables`
- Works fine, just requires typing context again
- Good enough until Architect Agent is built

**Related Pattern:**
This handoff pattern can be used for:
- Advisory → Architect (architecture questions)
- Advisory → Remediation (fix requests)
- Advisory → Compliance (compliance assessment requests)
- Creates clean agent specialization

---

## 🔮 Future Innovation: Unified Command Interface (Phase 4)

### Vision: Single `/carl ask` Command

**Current State:**
- 30+ slash commands (`/carl recommend`, `/carl build`, `/carl findings`, `/carl drift`, etc.)
- Each command has specific syntax and parameters
- Users need to remember which command does what
- Fragmented UX across different workflows

**Future Vision:**
- **Single command: `/carl ask`** interprets natural language and routes to correct handler
- Natural language understanding determines intent and parameters
- Unified interface with consistent UX
- Agent-based routing to specialized tools

**Examples:**

```
User: /carl ask recommend a three-tier web app
→ Routes to Architecture Agent → Shows options → Builds Terraform

User: /carl ask show me my security findings
→ Routes to Findings Service → Lists findings with filters

User: /carl ask check for infrastructure drift
→ Routes to Drift Detector → Scans Terraform state → Reports drift

User: /carl ask create a VPC with 3 AZs
→ Routes to Infrastructure Builder → Collects params → Generates code

User: /carl ask sync my findings to Jira
→ Routes to Jira Integration → Creates/updates tickets
```

**How It Works:**

1. **Intent Classification:** AI analyzes the question to determine:
   - Action type (recommend, build, check, list, sync, etc.)
   - Resource type (VPC, findings, drift, architecture, etc.)
   - Parameters (filters, configurations, options)

2. **Intelligent Routing:** Based on classification, route to:
   - Architecture Agent (design/recommend questions)
   - Compliance Scanner (security/findings questions)
   - Infrastructure Builder (build/create requests)
   - Drift Detector (drift check requests)
   - Jira Integration (sync requests)
   - Evidence Collector (compliance/audit requests)

3. **Parameter Extraction:** AI extracts parameters from natural language:
   - "three-tier web app" → requirement: "web application", tier: "three-tier"
   - "with 3 AZs" → availability_zones: 3
   - "in us-west-2" → region: "us-west-2"
   - "severity critical" → severity_filter: "critical"

4. **Context Preservation:** Maintains conversation context for follow-ups:
   ```
   User: /carl ask recommend a database
   CARL: Here are 3 options... [Aurora, RDS, DynamoDB]
   User: /carl ask build option 2
   CARL: [Knows user meant RDS from previous context]
   ```

**Benefits:**

- **Simplified UX:** One command to learn instead of 30+
- **Natural Language:** Ask questions naturally without memorizing syntax
- **Context-Aware:** Understands follow-up questions and references
- **Easier Onboarding:** New users only need to know `/carl ask`
- **Extensible:** Adding new features doesn't add new commands
- **Consistent:** Unified experience across all CARL capabilities

**Technical Implementation:**

1. **Classification Agent:**
   ```python
   class IntentClassifier:
       def classify(self, question: str) -> Intent:
           # Use LLM to classify intent
           return Intent(
               action="recommend",  # or build, check, list, sync, etc.
               resource="architecture",  # or findings, drift, vpc, etc.
               parameters={"requirement": "three-tier web app"},
               confidence=0.95
           )
   ```

2. **Unified Router:**
   ```python
   def handle_ask_command(question: str):
       intent = classifier.classify(question)

       router = {
           "recommend": architecture_agent,
           "build": infrastructure_builder,
           "check_findings": findings_service,
           "check_drift": drift_detector,
           "sync_jira": jira_integration,
           # ... etc
       }

       handler = router[intent.action]
       return handler.execute(intent.parameters)
   ```

3. **Context Manager:**
   ```python
   class ConversationContext:
       def remember(self, question: str, response: dict):
           # Store in session
           self.history.append((question, response))

       def recall(self, question: str) -> dict:
           # Resolve references like "option 2", "that VPC", etc.
           return self.resolve_references(question, self.history)
   ```

**Migration Strategy:**

- **Phase 1:** Keep existing commands, add unified routing (no breaking changes)
- **Phase 2:** Deprecation warnings on old commands, encourage `/carl ask`
- **Phase 3:** Remove old commands after 6-month transition period

**Estimated Effort:**
- Classification & routing logic: 1-2 weeks
- Parameter extraction: 1 week
- Context management: 1 week
- Testing & refinement: 1-2 weeks
- **Total: 4-6 weeks**

**Priority:** Medium-Low
- Current multi-command interface works fine
- More valuable after all core features are complete
- Nice-to-have UX improvement, not critical functionality
- Good candidate for Phase 4 (post-Phase 3)

**Status:** 📋 Planned for Future (Post-Phase 3)

---

## 📊 Summary Timeline

| Phase | Timeframe | Focus | Key Deliverables |
|-------|-----------|-------|------------------|
| **Phase 1** | Weeks 1-8 | AgentCore Migration & Security Patterns | AgentCore migration, patterns, Terraform generation |
| **Phase 2** | Weeks 9-16 | Architecture Patterns | 37+ patterns (compute, database, application, storage) |
| **Phase 3** | Weeks 17-30 | Intelligence & Multi-Framework | Adaptive monitoring, auto-remediation, HIPAA/PCI/ISO |

**Total Duration:** ~30 weeks (7 months)

---

## 🎯 Success Metrics

### Phase 1 Success Criteria
- ✅ Account Factory accessible via Slack
- ✅ All critical security service patterns added (WAF, CloudWatch, ACM, Secrets)
- ✅ Account baseline automation deployed
- ✅ Terraform generation for Account Factory modules
- ✅ Pattern count: 50+

### Phase 2 Success Criteria
- ✅ Complete architecture pattern coverage (compute, database, application, storage)
- ✅ Pattern count: 85+
- ✅ Can build any common AWS architecture with CARL

### Phase 3 Success Criteria
- ✅ Adaptive monitoring operational
- ✅ Auto-remediation executing for 20+ scenarios
- ✅ HIPAA + PCI-DSS + ISO 27001 support
- ✅ ML-based anomaly detection

---

## 💰 Estimated Costs (Development)

| Phase | Engineering Weeks | Estimated Cost* |
|-------|-------------------|-----------------|
| Phase 1 | 8 weeks | $40,000 - $80,000 |
| Phase 2 | 8 weeks | $40,000 - $80,000 |
| Phase 3 | 14 weeks | $70,000 - $140,000 |
| **Total** | **30 weeks** | **$150,000 - $300,000** |

*Assuming 1-2 senior engineers at $5,000-10,000/week fully loaded

---

## 🚀 Quick Wins (Can Start Immediately)

These can be done in parallel with Phase 1:

1. **CloudWatch Alerting Patterns** (3-5 days)
   - High value, frequently requested
   - Critical for production readiness

2. **AWS WAF Patterns** (3-5 days)
   - Common customer requirement
   - Security gap

3. **Certificate Manager Patterns** (2-3 days)
   - Simple, high impact
   - SSL/TLS best practices

4. **Account Factory Enhancements** (3-5 days)
   - Add Identity Center support to Account Factory
   - High visibility feature

---

## 📝 Notes

### Dependencies
- Phase 2 and 3 can start before Phase 1 completes
- Auto-remediation requires approval workflow (legal/security review)
- Multi-framework support requires compliance expertise

### Risks
- **Scope Creep**: Pattern creation can expand indefinitely
- **AWS Changes**: New services/features require pattern updates
- **Compliance Changes**: Framework updates require remapping

### Mitigation
- Define pattern quality bar (when to stop adding detail)
- Automated AWS service detection (flag when new services released)
- Quarterly compliance framework review

---

## 🔄 Continuous Improvements

Throughout all phases:
- Documentation updates as features ship
- Pattern refinement based on user feedback
- Cost optimization of CARL itself
- Performance optimization (especially AI inference)
- Security updates and patching

---

*Last Updated: 2026-01-31*
