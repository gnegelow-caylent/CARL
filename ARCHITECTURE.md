# CARL - Cloud Automated Risk & Compliance Logic

## Executive Summary

CARL is an AI-powered AWS compliance platform that helps organizations achieve and maintain compliance with SOC 2 and other regulatory frameworks. Built on AWS-native services and powered by Amazon Bedrock (Claude), CARL provides **end-to-end compliance automation** including architecture recommendations, real-time monitoring, evidence collection, and audit reporting.

### Key Differentiators

- **AI-Driven with Continuous Learning**: Claude Sonnet generates personalized recommendations that improve over time with user feedback
- **Hybrid Intelligence**: AI reasoning combined with curated static patterns for accurate pricing and best practices
- **AWS-Native**: No vendor lock-in, leverages services customers already use
- **Cost-Effective**: $75-200/month vs $500+/month for enterprise tools
- **Audit-Ready**: Automated evidence collection and compliance report generation

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CARL ARCHITECTURE                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────┐     ┌──────────────────────────────────────────────────────┐  │
│  │              │     │                 MANAGEMENT ACCOUNT                    │  │
│  │    SLACK     │◄───►│  ┌────────────┐  ┌────────────┐  ┌────────────────┐  │  │
│  │   WORKSPACE  │     │  │  API GW    │  │  BEDROCK   │  │  STEP          │  │  │
│  │              │     │  │  + Lambda  │  │  (Claude)  │  │  FUNCTIONS     │  │  │
│  └──────────────┘     │  └─────┬──────┘  └──────┬─────┘  └───────┬────────┘  │  │
│                       │        │                │                 │           │  │
│                       │        ▼                ▼                 ▼           │  │
│                       │  ┌─────────────────────────────────────────────────┐  │  │
│                       │  │                SERVICES LAYER                   │  │  │
│                       │  │  ┌─────────────┐  ┌─────────────┐              │  │  │
│                       │  │  │ AI Architect│  │  Evidence   │              │  │  │
│                       │  │  │  + Learning │  │  Collector  │              │  │  │
│                       │  │  └─────────────┘  └─────────────┘              │  │  │
│                       │  │  ┌─────────────┐  ┌─────────────┐              │  │  │
│                       │  │  │  Report     │  │  Exception  │              │  │  │
│                       │  │  │  Generator  │  │  Manager    │              │  │  │
│                       │  │  └─────────────┘  └─────────────┘              │  │  │
│                       │  │  ┌─────────────┐  ┌─────────────┐              │  │  │
│                       │  │  │   Drift     │  │  Foundation │              │  │  │
│                       │  │  │  Detector   │  │  Builder    │              │  │  │
│                       │  │  └─────────────┘  └─────────────┘              │  │  │
│                       │  │  ┌─────────────────────────────────────────┐  │  │  │
│                       │  │  │  Bootstrap Automation (NEW)             │  │  │  │
│                       │  │  │  - Organizations + OU + SCPs            │  │  │  │
│                       │  │  │  - Identity Center + Permission Sets   │  │  │  │
│                       │  │  │  - Security Services Delegated Admin   │  │  │  │
│                       │  │  └─────────────────────────────────────────┘  │  │  │
│                       │  └─────────────────────────────────────────────────┘  │  │
│                       │        │                                              │  │
│                       │        ▼                                              │  │
│                       │  ┌─────────────────────────────────────────────────┐  │  │
│                       │  │               KNOWLEDGE LAYER                   │  │  │
│                       │  │  ┌─────────────────────────────────────────┐   │  │  │
│                       │  │  │  43+ Architecture Patterns (NEW)         │   │  │  │
│                       │  │  │  (VPC, VPC Endpoints, KMS, IAM,         │   │  │  │
│                       │  │  │   Security, Logging, Operational)       │   │  │  │
│                       │  │  └─────────────────────────────────────────┘   │  │  │
│                       │  │  ┌─────────────────────────────────────────┐   │  │  │
│                       │  │  │  AWS Pricing Data (Accurate, not est.)  │   │  │  │
│                       │  │  └─────────────────────────────────────────┘   │  │  │
│                       │  │  ┌─────────────────────────────────────────┐   │  │  │
│                       │  │  │  SOC 2 Control Mappings                 │   │  │  │
│                       │  │  └─────────────────────────────────────────┘   │  │  │
│                       │  │  ┌─────────────────────────────────────────┐   │  │  │
│                       │  │  │  RAG + Continuous Learning (Feedback)   │   │  │  │
│                       │  │  └─────────────────────────────────────────┘   │  │  │
│                       │  └─────────────────────────────────────────────────┘  │  │
│                       │        │                                              │  │
│                       │        ▼                                              │  │
│                       │  ┌─────────────────────────────────────────────────┐  │  │
│                       │  │                DATA LAYER                       │  │  │
│                       │  │  ┌────────────────────────────────────────────┐ │  │  │
│                       │  │  │  KMS Customer-Managed Key (NEW)            │ │  │  │
│                       │  │  │  - Encrypts DynamoDB, Secrets, S3, Logs    │ │  │  │
│                       │  │  │  - Auto-rotation enabled                   │ │  │  │
│                       │  │  └────────────────────────────────────────────┘ │  │  │
│                       │  │                                                 │  │  │
│                       │  │  DynamoDB Tables (10):                          │  │  │
│                       │  │  - findings, evidence, exceptions, drift        │  │  │
│                       │  │  - preferences, approvals, conversations        │  │  │
│                       │  │  - remediations, ai_feedback, foundation        │  │  │
│                       │  │  - scan_history, resource_graph (NEW)           │  │  │
│                       │  │  - pricing_cache (366 items, 3 regions) (NEW)   │  │  │
│                       │  │                                                 │  │  │
│                       │  │  S3 Buckets (KMS encrypted):                    │  │  │
│                       │  │  - Evidence (audit artifacts)                   │  │  │
│                       │  │  - Reports (compliance reports)                 │  │  │
│                       │  │  - Terraform State (versioned)                  │  │  │
│                       │  │                                                 │  │  │
│                       │  │  Secrets Manager (KMS encrypted):               │  │  │
│                       │  │  - Slack bot token, signing secret              │  │  │
│                       │  │  - 7-day recovery window                        │  │  │
│                       │  │                                                 │  │  │
│                       │  │  Lambda Functions (3):                          │  │  │
│                       │  │  - pricing-prefetch (monthly refresh) (NEW)     │  │  │
│                       │  │  - pattern-analyzer (daily 2am UTC) (NEW)       │  │  │
│                       │  │  - api (main CARL interface)                    │  │  │
│                       │  │                                                 │  │  │
│                       │  │  EventBridge Schedules:                         │  │  │
│                       │  │  - Pricing refresh (1st of month) (NEW)         │  │  │
│                       │  │  - Pattern analysis (daily 2am) (NEW)           │  │  │
│                       │  └─────────────────────────────────────────────────┘  │  │
│                       │        │                                              │  │
│                       │        ▼                                              │  │
│                       │  ┌─────────────────────────────────────────────────┐  │  │
│                       │  │           AGGREGATION LAYER                      │  │  │
│                       │  │  ┌─────────────┐    ┌─────────────────────────┐ │  │  │
│                       │  │  │SECURITY HUB │    │    AUDIT MANAGER        │ │  │  │
│                       │  │  │(Findings)   │    │    (SOC2 Evidence)      │ │  │  │
│                       │  │  └─────────────┘    └─────────────────────────┘ │  │  │
│                       │  └─────────────────────────────────────────────────┘  │  │
│                       └──────────────────────────────────────────────────────┘  │
│                                        │                                         │
│                                        ▼                                         │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                         MEMBER ACCOUNTS (1..N)                             │  │
│  │  ┌─────────────────────────────────────────────────────────────────────┐  │  │
│  │  │                    SECURITY SERVICES                                 │  │  │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │  │  │
│  │  │  │  CONFIG  │ │GUARDDUTY │ │INSPECTOR │ │  MACIE   │ │   IAM    │  │  │  │
│  │  │  │  Rules   │ │  Threats │ │  Vulns   │ │  Data    │ │ Access   │  │  │  │
│  │  │  │          │ │          │ │          │ │          │ │ Analyzer │  │  │  │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │  │  │
│  │  └─────────────────────────────────────────────────────────────────────┘  │  │
│  │                                    │                                       │  │
│  │                                    ▼                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────────┐  │  │
│  │  │                    MONITORING & LOGGING                              │  │  │
│  │  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────────┐ │  │  │
│  │  │  │  CLOUDTRAIL  │ │ EVENTBRIDGE  │ │      CLOUDWATCH              │ │  │  │
│  │  │  │  (Audit)     │ │ (Events)     │ │      (Metrics/Logs)          │ │  │  │
│  │  │  └──────────────┘ └──────────────┘ └──────────────────────────────┘ │  │  │
│  │  └─────────────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Services Layer - Core Components

### 1. AI Architect (`ai_architect.py`)

The AI-driven architecture recommendation engine that provides personalized AWS recommendations.

```
┌─────────────────────────────────────────────────────────────────┐
│                      AI ARCHITECT                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User Request                    Knowledge Layer                 │
│  ┌─────────────┐                ┌─────────────────────────────┐ │
│  │ "What VPC   │                │  43+ Static Patterns (NEW)  │ │
│  │  pattern    │───────────────►│  - Accurate pricing         │ │
│  │  should I   │                │  - Pros/cons                │ │
│  │  use?"      │                │  - SOC 2 mappings           │ │
│  └─────────────┘                └──────────────┬──────────────┘ │
│                                                │                 │
│                       ┌────────────────────────▼────────────────┐│
│                       │         Bedrock (Claude Sonnet)         ││
│                       │                                         ││
│                       │  - Analyzes requirements                ││
│                       │  - Considers user feedback history      ││
│                       │  - Generates personalized advice        ││
│                       │  - Uses patterns as context, not answer ││
│                       └─────────────────────────────────────────┘│
│                                       │                          │
│                                       ▼                          │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    Learning Loop                            │ │
│  │                                                             │ │
│  │  👍/👎 Feedback → DynamoDB → Knowledge Retrieval → Future  │ │
│  │                                                Queries      │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Methods:**
- `recommend_foundation()` - AI-driven foundation recommendations based on requirements
- `recommend_pattern()` - Pattern-specific recommendations with context awareness
- `explain_tradeoffs()` - Compare options with AI reasoning
- `record_feedback()` - Store user feedback for continuous learning

**SOC 2 Mapping:** CC1.1 (Control Environment), CC5.1 (Control Activities)

### 2. Evidence Collector (`evidence_collector.py`)

Automated collection of audit evidence from AWS services.

```
┌─────────────────────────────────────────────────────────────────┐
│                   EVIDENCE COLLECTOR                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  AWS Services                    Evidence Types                  │
│  ┌──────────────┐               ┌───────────────────────────┐   │
│  │     IAM      │──────────────►│ Users, Roles, Policies,   │   │
│  │              │               │ Password Policy, MFA      │   │
│  └──────────────┘               └───────────────────────────┘   │
│  ┌──────────────┐               ┌───────────────────────────┐   │
│  │      S3      │──────────────►│ Bucket configs, Encryption│   │
│  │              │               │ Public access, Versioning │   │
│  └──────────────┘               └───────────────────────────┘   │
│  ┌──────────────┐               ┌───────────────────────────┐   │
│  │  CloudTrail  │──────────────►│ Trail configs, Log status │   │
│  │              │               │ Encryption, Validation    │   │
│  └──────────────┘               └───────────────────────────┘   │
│  ┌──────────────┐               ┌───────────────────────────┐   │
│  │ Security Hub │──────────────►│ Compliance summaries,     │   │
│  │              │               │ Finding counts by control │   │
│  └──────────────┘               └───────────────────────────┘   │
│  ┌──────────────┐               ┌───────────────────────────┐   │
│  │     VPC      │──────────────►│ Flow logs, Security groups│   │
│  │              │               │ NACLs, VPC configurations │   │
│  └──────────────┘               └───────────────────────────┘   │
│                                                                  │
│                           │                                      │
│                           ▼                                      │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    Evidence Processing                      │ │
│  │                                                             │ │
│  │  - Integrity hash (SHA-256)                                 │ │
│  │  - SOC 2 control mapping                                    │ │
│  │  - Timestamp and chain of custody                           │ │
│  │  - Store in S3 with metadata in DynamoDB                    │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Methods:**
- `collect_all_evidence()` - Collect from all supported services
- `collect_iam_evidence()` - IAM users, roles, policies, MFA status
- `collect_s3_evidence()` - Bucket configurations, encryption, public access
- `collect_cloudtrail_evidence()` - Trail configurations and status
- `collect_security_hub_evidence()` - Compliance summaries by control
- `collect_vpc_evidence()` - VPC configs, security groups, flow logs
- `get_control_coverage()` - Map collected evidence to SOC 2 controls

**SOC 2 Mapping:** All controls (CC6.1 through CC9.2, A1, C1)

### 2.5. Intelligent Scanning System (`scanning_tools.py` + `agent_core.py`)

**NEW (January 29, 2026):** AI-driven intelligent scanning that replaces static keyword matching.

```
┌─────────────────────────────────────────────────────────────────┐
│              INTELLIGENT SCANNING SYSTEM                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User Question                AI-Driven Decision                 │
│  ┌──────────────────┐        ┌────────────────────────────────┐ │
│  │ "How's my        │        │  Agent (Claude Sonnet 4.5)     │ │
│  │  database        │───────►│                                │ │
│  │  connectivity?"  │        │  Analyzes question semantics   │ │
│  └──────────────────┘        │  Understands intent            │ │
│                              │  Decides what to scan          │ │
│                              └────────────┬───────────────────┘ │
│                                           │                      │
│                                           ▼                      │
│                              ┌────────────────────────────────┐ │
│                              │    Available Scanning Tools    │ │
│                              │                                │ │
│                              │  • scan_iam                    │ │
│                              │  • scan_s3                     │ │
│                              │  • scan_vpc                    │ │
│                              │  • scan_cloudtrail             │ │
│                              │  • scan_security_hub           │ │
│                              │  • scan_all                    │ │
│                              └────────────┬───────────────────┘ │
│                                           │                      │
│           Agent selects: scan_vpc         │                      │
│                                           ▼                      │
│                              ┌────────────────────────────────┐ │
│                              │    Evidence Collector          │ │
│                              │                                │ │
│                              │  Executes AWS API calls:       │ │
│                              │  • describe_vpcs()             │ │
│                              │  • describe_security_groups()  │ │
│                              │  • describe_flow_logs()        │ │
│                              │  • Returns scan results        │ │
│                              └────────────┬───────────────────┘ │
│                                           │                      │
│                                           ▼                      │
│                              ┌────────────────────────────────┐ │
│                              │    Scan Results (JSON)         │ │
│                              │                                │ │
│                              │  {                             │ │
│                              │    "success": true,            │ │
│                              │    "resource_type": "VPC",     │ │
│                              │    "details": {                │ │
│                              │      "vpc_count": 2,           │ │
│                              │      "risky_sgs": [...]        │ │
│                              │    }                           │ │
│                              │  }                             │ │
│                              └────────────┬───────────────────┘ │
│                                           │                      │
│                                           ▼                      │
│                              ┌────────────────────────────────┐ │
│                              │  AI Response Generation        │ │
│                              │                                │ │
│                              │  "Your VPC vpc-abc123 has..."  │ │
│                              │  (Specific, environment-aware) │ │
│                              └────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Innovation:** Replaces 114 lines of brittle keyword matching with AI-driven reasoning.

**Before (Static Keywords):**
```python
# Hardcoded if/else statements - brittle and unmaintainable
if any(kw in question for kw in ['mfa', 'multi-factor', 'iam user', ...]):
    scan_iam()
if any(kw in question for kw in ['vpc', 'network', 'security group', ...]):
    scan_vpc()
# ...100+ more lines
```

**After (AI-Driven):**
```python
# Agent decides intelligently based on question semantics
agent = Agent(tools=create_scanning_tools(evidence_collector))
scan_results = agent.execute("Analyze question and scan relevant resources")
# AI understands "database connectivity" = VPC + security groups
# No hardcoded keywords needed
```

**Scanning Tools (6 Tools):**
- `scan_iam` - IAM users, roles, policies, MFA, password policies
- `scan_s3` - S3 buckets, encryption, public access, versioning
- `scan_vpc` - VPCs, security groups, flow logs, network configuration
- `scan_cloudtrail` - CloudTrail audit logging configuration
- `scan_security_hub` - Security Hub findings and enabled standards
- `scan_all` - Comprehensive scan of all resources (for broad questions)

**Agent Decision Process:**
1. **Natural Language Understanding**: Analyzes question semantics, not keywords
2. **Context Reasoning**: Understands "database connectivity" needs network + database info
3. **Tool Selection**: Chooses appropriate scanning tool(s) - can call multiple tools
4. **Result Aggregation**: Combines scan results into coherent context
5. **Response Generation**: Answers with specific resource names and configurations

**Benefits:**
- **Scalable**: Works with 200+ AWS services without code changes
- **Intelligent**: Understands synonyms, context, and intent
- **Adaptive**: Learns patterns and improves over time
- **Maintainable**: 6 tool definitions vs 114 lines of if/else
- **Future-proof**: New AWS services work automatically

**SOC 2 Mapping:** CC4.1 (Monitoring) - Continuous environment monitoring

**Related Design Principle:** #4 - Continuous Learning & Environment Adaptation

### 2.6. Continuous Learning System (`learning_service.py` + `pattern_analyzer.py`)

**NEW (January 29, 2026) - Phase 2:** System that learns from every interaction to improve over time.

```
┌─────────────────────────────────────────────────────────────────┐
│             CONTINUOUS LEARNING SYSTEM                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User Interaction              Learning Loop                     │
│  ┌──────────────────┐         ┌────────────────────────────────┐│
│  │ User: "How's my  │         │  1. Log Interaction            ││
│  │ database         │────────►│     - Question asked           ││
│  │ connectivity?"   │         │     - Scans performed          ││
│  └──────────────────┘         │     - Resources found          ││
│         │                     │     - Duration                 ││
│         ▼                     └───────────┬────────────────────┘│
│  ┌──────────────────┐                    │                      │
│  │ CARL scans VPC + │                    ▼                      │
│  │ Security Groups  │         ┌────────────────────────────────┐│
│  │ and answers      │         │  2. User Feedback              ││
│  └──────────────────┘         │                                ││
│         │                     │  Was this answer helpful?      ││
│         ▼                     │  [👍 Yes]  [👎 No]            ││
│  ┌──────────────────┐         │                                ││
│  │ Feedback buttons │────────►│  Feedback → DynamoDB           ││
│  │ [👍 Yes] [👎 No]│         └───────────┬────────────────────┘│
│  └──────────────────┘                    │                      │
│                                          ▼                      │
│                           ┌──────────────────────────────────┐ │
│                           │  3. Storage                       │ │
│                           │                                   │ │
│                           │  Scan History Table:              │ │
│                           │  ┌────────────────────────────┐  │ │
│                           │  │ Question + Scans           │  │ │
│                           │  │ Resources + Feedback       │  │ │
│                           │  │ Timestamp + Duration       │  │ │
│                           │  └────────────────────────────┘  │ │
│                           │                                   │ │
│                           │  Resource Graph Table:            │ │
│                           │  ┌────────────────────────────┐  │ │
│                           │  │ vpc-abc123 (VPC)           │  │ │
│                           │  │ - Contains: [sg-xyz, ...]  │  │ │
│                           │  │ - Scan count: 23           │  │ │
│                           │  │ - Issues: 2                │  │ │
│                           │  └────────────────────────────┘  │ │
│                           └──────────────┬───────────────────┘ │
│                                          │                      │
│                                          ▼                      │
│                           ┌──────────────────────────────────┐ │
│                           │  4. Pattern Analysis (Daily 2am) │ │
│                           │                                   │ │
│                           │  Analyzes last 30 days:           │ │
│                           │  • Question → Scans mapping       │ │
│                           │  • Resource frequency             │ │
│                           │  • Common topics                  │ │
│                           │                                   │ │
│                           │  Generates learned patterns:      │ │
│                           │  "database" → VPC + SG (85%)      │ │
│                           │  "mfa" → IAM (95%)                │ │
│                           │                                   │ │
│                           │  Publishes CloudWatch metrics     │ │
│                           └──────────────┬───────────────────┘ │
│                                          │                      │
│                                          ▼                      │
│                           ┌──────────────────────────────────┐ │
│                           │  5. Learned Context Injection    │ │
│                           │                                   │ │
│                           │  Next time user asks question:    │ │
│                           │                                   │ │
│                           │  Agent Instructions += Learned:   │ │
│                           │  • Common topics: vpc, security   │ │
│                           │  • Top resources: vpc-abc123      │ │
│                           │  • For "database" → scan VPC+SG   │ │
│                           │                                   │ │
│                           │  AI makes smarter decisions! 🧠   │ │
│                           └───────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Components:**

**1. LearningService (580 lines)**
- `log_interaction()` - Store every scan interaction
- `record_feedback()` - Process 👍 👎 clicks
- `update_resource_graph()` - Track AWS resources
- `analyze_patterns()` - Generate learned insights
- `get_learned_context()` - Context for agent instructions

**2. Pattern Analyzer Lambda (200 lines)**
- Runs daily at 2am UTC via EventBridge
- Analyzes last 30 days of interactions
- Identifies useful scan patterns
- Publishes CloudWatch metrics

**3. DynamoDB Tables**
- **Scan History**: Questions, scans, feedback, timestamps
- **Resource Graph**: AWS resources, relationships, scan metadata

**The Learning Cycle:**
```
Day 1: User asks "database connectivity" → AI guesses VPC scan → 👍
Day 7: AI learns "database" → VPC scan (60% confidence, n=5)
Day 30: AI confident "database" → VPC + SG scans (85% confidence, n=15)
Day 90: AI anticipates needs, knows your environment deeply
```

**CloudWatch Metrics:**
- `CARL/Learning/PatternsLearned` - Count of learned patterns
- `CARL/Learning/PatternConfidence` - Average confidence %
- `CARL/Learning/InteractionsAnalyzed` - Total interactions

**Cost:** ~$0.67/month (DynamoDB + Lambda)

**Benefits:**
- Smarter scan decisions over time
- Environment-specific recommendations
- Reduced redundant AWS API calls
- Measurable improvement via metrics

**SOC 2 Mapping:** CC4.1 (Monitoring), CC8.1 (Change Management) - Adaptive system improvement

**Related Design Principle:** #4 - Continuous Learning & Environment Adaptation

**Documentation:** See `CONTINUOUS_LEARNING.md` for complete details

### 3. Report Generator (`report_generator.py`)

Generates SOC 2 compliance reports in multiple formats.

```
┌─────────────────────────────────────────────────────────────────┐
│                    REPORT GENERATOR                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Report Types:                                                   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ EXECUTIVE SUMMARY                                            ││
│  │                                                              ││
│  │ - Overall compliance score                                   ││
│  │ - Finding counts by severity                                 ││
│  │ - Key risks and recommendations                              ││
│  │ - Evidence collection coverage                               ││
│  │ - Trend data (if available)                                  ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ FULL AUDIT REPORT                                            ││
│  │                                                              ││
│  │ - All executive summary content PLUS:                        ││
│  │ - Control-by-control assessment                              ││
│  │ - Evidence inventory per control                             ││
│  │ - Detailed findings with remediation steps                   ││
│  │ - Risk exception summary                                     ││
│  │ - Appendices (configurations, logs)                          ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ CONTROL REPORT                                               ││
│  │                                                              ││
│  │ - Single control deep-dive (e.g., CC6.1)                     ││
│  │ - All evidence for that control                              ││
│  │ - All findings affecting that control                        ││
│  │ - Remediation status                                         ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│                           │                                      │
│                           ▼                                      │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    Output                                   │ │
│  │                                                             │ │
│  │  - Markdown format (readable, portable)                     │ │
│  │  - Stored in S3 reports bucket                              │ │
│  │  - Presigned URL returned for download                      │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Methods:**
- `generate_executive_summary()` - High-level compliance overview
- `generate_full_audit_report()` - Comprehensive audit documentation
- `generate_control_report()` - Single control deep-dive
- `save_report()` - Store in S3 and return presigned URL

**SOC 2 Mapping:** CC4.1 (Monitoring), CC4.2 (Evaluation)

### 4. Exception Manager (`exception_manager.py`)

Risk acceptance and exception workflow management.

```
┌─────────────────────────────────────────────────────────────────┐
│                   EXCEPTION MANAGER                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Exception Types:                                                │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ - RISK_ACCEPTANCE: Accept the risk, document rationale       ││
│  │ - COMPENSATING_CONTROL: Alternative control in place         ││
│  │ - PLANNED_REMEDIATION: Fix scheduled, temporary exception    ││
│  │ - FALSE_POSITIVE: Finding is incorrect                       ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  Workflow:                                                       │
│                                                                  │
│  ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌───────────┐  │
│  │ REQUEST │───►│ PENDING  │───►│ APPROVED │───►│  ACTIVE   │  │
│  └─────────┘    └────┬─────┘    └──────────┘    └─────┬─────┘  │
│                      │                                 │        │
│                      │                                 ▼        │
│                      ▼                          ┌───────────┐   │
│                ┌──────────┐                     │  EXPIRED  │   │
│                │  DENIED  │                     └───────────┘   │
│                └──────────┘                                     │
│                                                                  │
│  Features:                                                       │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ - Expiration tracking with auto-expire processing            ││
│  │ - Renewal workflow for extending exceptions                  ││
│  │ - Audit trail of all approvals/denials                       ││
│  │ - Statistics and reporting                                   ││
│  │ - Control-level exception linking                            ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Methods:**
- `request_exception()` - Submit new exception request
- `approve_exception()` - Approve with optional modified expiration
- `deny_exception()` - Deny with reason
- `revoke_exception()` - Revoke active exception early
- `renew_exception()` - Extend expiration of active exception
- `get_expiring_exceptions()` - Find exceptions expiring within N days
- `process_expirations()` - Auto-expire past-due exceptions
- `get_exception_statistics()` - Aggregate stats for reporting

**SOC 2 Mapping:** CC3.1 (Risk Assessment), CC9.1 (Risk Mitigation)

### 5. Drift Detector (`drift_detector.py`)

Infrastructure configuration drift detection and monitoring.

```
┌─────────────────────────────────────────────────────────────────┐
│                    DRIFT DETECTOR                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Scan Types:                                                     │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ S3 DRIFT                                                     ││
│  │ - Public access changes (security-sensitive)                 ││
│  │ - Encryption configuration changes                           ││
│  │ - Versioning status changes                                  ││
│  │ - Logging configuration changes                              ││
│  └─────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ IAM DRIFT                                                    ││
│  │ - New users/roles without MFA (security-sensitive)           ││
│  │ - Policy attachment changes                                  ││
│  │ - Access key age and rotation                                ││
│  │ - Password policy changes                                    ││
│  └─────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ VPC DRIFT                                                    ││
│  │ - Security group rule changes                                ││
│  │ - Open ports to 0.0.0.0/0 (security-sensitive)               ││
│  │ - Flow log configuration                                     ││
│  │ - NACL changes                                               ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  Baseline Management:                                            │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ - Baselines stored in DynamoDB                               ││
│  │ - First scan establishes baseline                            ││
│  │ - Subsequent scans compare against baseline                  ││
│  │ - Acknowledged drift updates baseline                        ││
│  │ - Terraform state comparison for IaC drift                   ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  Output:                                                         │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ DriftReport:                                                 ││
│  │ - drift_items: List of detected changes                      ││
│  │ - total_resources_scanned: Coverage metric                   ││
│  │ - security_sensitive_count: High-priority items              ││
│  │ - scan_timestamp: When scan was performed                    ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Methods:**
- `detect_all_drift()` - Full drift scan across all resource types
- `compare_with_terraform_state()` - Compare with Terraform state file
- `acknowledge_drift()` - Mark drift as reviewed, update baseline
- `get_drift_summary()` - Aggregate drift statistics

**SOC 2 Mapping:** CC6.6 (Configuration Management), CC8.1 (Change Management)

### 6. Knowledge Retrieval (`knowledge_retrieval.py`)

RAG (Retrieval Augmented Generation) system for continuous learning.

```
┌─────────────────────────────────────────────────────────────────┐
│                  KNOWLEDGE RETRIEVAL                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ STATIC KNOWLEDGE (Knowledge Base)                            ││
│  │                                                              ││
│  │ - 36+ Architecture patterns                                  ││
│  │ - AWS pricing data                                           ││
│  │ - SOC 2 control definitions                                  ││
│  │ - Best practices documentation                               ││
│  └─────────────────────────────────────────────────────────────┘│
│                         +                                        │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ LEARNED KNOWLEDGE (DynamoDB)                                 ││
│  │                                                              ││
│  │ - User feedback on recommendations                           ││
│  │ - Environment-specific learnings                             ││
│  │ - Custom patterns from positive feedback                     ││
│  │ - Anti-patterns from negative feedback                       ││
│  └─────────────────────────────────────────────────────────────┘│
│                         =                                        │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ CONTEXTUAL KNOWLEDGE                                         ││
│  │                                                              ││
│  │ - Query-relevant static patterns                             ││
│  │ - Past feedback for similar queries                          ││
│  │ - Combined context for AI recommendations                    ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  Learning Flow:                                                  │
│                                                                  │
│  User Feedback                                                   │
│       │                                                          │
│       ▼                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ Extract      │───►│ Store in     │───►│ Include in   │       │
│  │ Learnings    │    │ DynamoDB     │    │ Future       │       │
│  │ (via Claude) │    │ (ai_feedback)│    │ Queries      │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Methods:**
- `retrieve_from_knowledge_base()` - Query Bedrock Knowledge Base
- `retrieve_and_generate()` - RAG query with generation
- `learn_from_feedback()` - Extract and store learnings from feedback
- `get_contextual_knowledge()` - Get combined static + learned knowledge

**SOC 2 Mapping:** CC1.4 (Continuous Improvement)

### 7. Real-Time Pricing Tool (`pricing_tool.py`) **NEW**

Real-time AWS pricing using AWS Price List API for cost-aware recommendations.

```
┌─────────────────────────────────────────────────────────────────┐
│                     PRICING TOOL                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              AWS Price List API                              ││
│  │                                                              ││
│  │  Query real-time pricing for:                                ││
│  │  - EC2 (all instance types, all regions)                     ││
│  │  - RDS (all database engines, instance types)                ││
│  │  - S3, Lambda, DynamoDB, Redshift                            ││
│  │  - Glue, DMS, EMR, Kinesis                                   ││
│  │  - VPC, NAT Gateway, ELB                                     ││
│  │  - 200+ AWS services                                         ││
│  └─────────────────────────────────────────────────────────────┘│
│                           │                                      │
│                           ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │               Pricing Tool Functions                         ││
│  │                                                              ││
│  │  get_aws_pricing(service_code, region, filters)              ││
│  │    → Full control, custom filters                            ││
│  │                                                              ││
│  │  get_common_service_pricing(service_name, region, ...)       ││
│  │    → Simplified for common use cases                         ││
│  └─────────────────────────────────────────────────────────────┘│
│                           │                                      │
│                           ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                 AgentCore Tool                               ││
│  │                                                              ││
│  │  pricing_tool = Tool(                                        ││
│  │    name="get_aws_pricing",                                   ││
│  │    function=get_common_service_pricing,                      ││
│  │    description="Get real-time pricing..."                    ││
│  │  )                                                           ││
│  │                                                              ││
│  │  Any agent can register and use:                             ││
│  │  - Advisory Agent                                            ││
│  │  - Architect Agent                                           ││
│  │  - Remediation Agent                                         ││
│  └─────────────────────────────────────────────────────────────┘│
│                           │                                      │
│                           ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │               Cost-Aware Recommendations                     ││
│  │                                                              ││
│  │  Example: "Should I use AWS Glue or EC2 for ETL?"            ││
│  │                                                              ││
│  │  Agent autonomously:                                         ││
│  │  1. Calls get_aws_pricing(service_name="glue")               ││
│  │  2. Calls get_aws_pricing(service_name="ec2", ...)           ││
│  │  3. Compares: Glue $220/mo vs EC2 $50/mo + ops time          ││
│  │  4. Recommends: Glue (better value, saves $110/mo ops time)  ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Features:**
- Real-time pricing from AWS Price List API (always current)
- Region-aware pricing with automatic multipliers
- Instance-specific pricing (t3.medium, db.t3.large, etc.)
- Supports 200+ AWS services
- AgentCore Tool interface for autonomous agent use

**Key Functions:**
- `get_aws_pricing()` - Low-level API access with custom filters
- `get_common_service_pricing()` - High-level simplified interface
- `pricing_tool` - Tool definition for AgentCore registration

**Design Principle Integration:**
This tool implements **Design Principle #3: Cost-Aware Recommendations**
- Always factor cost into architecture decisions
- Compare options with cost tradeoffs
- Recommend best VALUE (not just cheapest)
- Show break-even analysis when relevant

**Usage Example:**
```python
from services.pricing_tool import pricing_tool

# Register with any agent
agent = Agent(tools=[pricing_tool], instructions="...")

# Agent autonomously calls pricing when needed
# User: "What's the cost of running t3.medium 24/7?"
# Agent calls: get_aws_pricing(service_name="ec2", instance_type="t3.medium")
# Returns: $0.0416/hour = ~$30/month (real-time from API)
```

**Cost:** Free - AWS Price List API has no charges

### 8. Foundation Builder (`foundation/`)

Guided wizard for building compliant AWS infrastructure from scratch.

```
┌─────────────────────────────────────────────────────────────────┐
│                   FOUNDATION BUILDER                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Decision Engine (decision_engine.py):                           │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Session-based wizard with:                                   ││
│  │ - Account structure decisions                                ││
│  │ - Networking architecture (VPC, subnets, NAT)                ││
│  │ - Identity management (IAM Identity Center, permissions)     ││
│  │ - Security tooling (Security Hub, GuardDuty, Config)         ││
│  │ - Logging strategy (CloudTrail, centralized logging)         ││
│  │ - Cost management preferences                                ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  Foundation Builder (foundation_builder.py):                     │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Terraform code generation for:                               ││
│  │ - VPC with public/private subnets                            ││
│  │ - Security groups with SOC 2 compliant defaults              ││
│  │ - IAM roles and policies                                     ││
│  │ - S3 buckets with encryption                                 ││
│  │ - CloudTrail with log validation                             ││
│  │ - Security Hub and GuardDuty                                 ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  AI Integration:                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ - AI-recommended defaults based on requirements              ││
│  │ - Natural language explanations for each decision            ││
│  │ - Cost implications for each choice                          ││
│  │ - SOC 2 compliance impact analysis                           ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**SOC 2 Mapping:** CC5.1 (Control Activities), CC6.1 (Logical Access)

### 9. Bootstrap Automation (`bootstrap/`) **NEW**

Complete AWS environment bootstrap automation from scratch.

```
┌─────────────────────────────────────────────────────────────────┐
│              BOOTSTRAP AUTOMATION (3-PHASE)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Phase 1: Organizations Bootstrap (organizations_bootstrap.py)  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ - Create AWS Organizations                                   ││
│  │ - Build OU structure (Security, Infrastructure, Workloads)   ││
│  │ - Deploy SCPs (deny security disabling, region restrictions) ││
│  │ - AWS recommended or custom structure                        ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  Phase 2: Identity Center (identity_center_bootstrap.py)        │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ - Create permission sets (5 baseline: Admin, PowerUser, etc.)││
│  │ - Create groups (CloudPlatformAdmins, Developers, etc.)      ││
│  │ - Create account assignments (group → account → permission)  ││
│  │ - Configure session durations                                ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  Phase 3: Security Services (security_services_bootstrap.py)    │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ - Security Hub (delegated admin + auto-enable)               ││
│  │ - GuardDuty (all data sources + auto-enable)                 ││
│  │ - Inspector (EC2, ECR, Lambda scanning)                      ││
│  │ - Macie (S3 sensitive data discovery, optional)              ││
│  │ - Detective (security investigation, optional)               ││
│  │ - Config organization aggregator                             ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  Orchestrator (bootstrap_orchestrator.py):                      │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ - Coordinates all 3 phases                                   ││
│  │ - Quickstart configuration (AWS recommended)                 ││
│  │ - Minimal configuration (getting started)                    ││
│  │ - Custom configuration support                               ││
│  │ - Idempotent operations (safe to re-run)                     ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Methods:**
- `bootstrap_complete_environment()` - Run all 3 phases
- `get_quickstart_config()` - AWS recommended configuration
- `get_minimal_config()` - Basic setup for getting started
- Organizations: `bootstrap_organization()`, `get_aws_recommended_ou_structure()`, `get_recommended_scps()`
- Identity Center: `bootstrap_identity_center()`, `get_recommended_permission_sets()`, `get_recommended_groups()`
- Security Services: `bootstrap_all_services()`, `enable_service_in_member_accounts()`

**What Gets Automated:**
- OU structure: Security, Infrastructure, Workloads (Prod, Staging, Dev), Sandbox, PolicyStaging, Suspended
- SCPs: Deny security service disabling, deny leaving org, region restrictions, require IMDSv2, deny root user
- Permission sets: AdministratorAccess, PowerUserAccess, ReadOnlyAccess, SecurityAudit, BillingAccess
- Groups: CloudPlatformAdmins, Developers, SecurityTeam, ReadOnlyUsers, FinanceTeam
- Security services across all regions with delegated admin

**Cost Impact:**
- Organizations: Free
- Identity Center: Free
- Security services: Underlying service costs ($40-190/account/mo)

**SOC 2 Mapping:** CC6.1 (Access Control), CC6.6 (Network Segmentation), CC6.8 (Threat Detection), CC7.1 (Vulnerability Management), CC7.2 (Security Monitoring), CC8.1 (Change Management)

---

## AI Agent Architecture

### Overview

CARL uses **AgentCore** (`agent_core.py`) for autonomous multi-step workflows. Each agent is specialized for a specific domain and can reason, plan, use tools, and collaborate with other agents.

```
┌──────────────────────────────────────────────────────────────────────┐
│                         CARL Agent System                             │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  User Command (Slack)                                                 │
│       │                                                               │
│       ▼                                                               │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                    slack_router.py                              │  │
│  │  - Routes commands to appropriate agent                         │  │
│  │  - Manages sessions and state                                   │  │
│  │  - Handles responses and formatting                             │  │
│  └────────────────────────────────────────────────────────────────┘  │
│       │                                                               │
│       ├──────────────┬──────────────┬──────────────┬──────────────┐  │
│       ▼              ▼              ▼              ▼              ▼  │
│  ┌──────────┐  ┌────────────┐  ┌─────────┐  ┌──────────┐  ┌────────┐│
│  │ Advisory │  │ Architect  │  │Terraform│  │  Drift   │  │  (TBD) ││
│  │  Agent   │  │   Agent    │  │   Gen   │  │  Scan    │  │        ││
│  │    ✅    │  │     ✅     │  │    ✅   │  │    ✅    │  │        ││
│  └──────────┘  └────────────┘  └─────────┘  └──────────┘  └────────┘│
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

### Agent Capabilities

**1. Advisory Agent** ✅ **LIVE**

**Purpose:** Intelligent Q&A with environment awareness and compliance knowledge

**Command:** `/carl ask <question>`

**What It Does:**
- Analyzes complex questions to understand user intent
- Scans relevant AWS resources based on question context
- Provides tailored recommendations using actual environment data
- Factors in SOC 2 compliance requirements
- Asks clarifying questions when more information is needed

**Tools:** `scan_iam`, `scan_vpc`, `scan_s3`, `scan_cloudtrail`, `scan_security_hub`, `scan_all`

**Implementation:** `slack_router.py` (handle_ask_command) + `agent_core.py` + `scanning_tools.py`

---

**2. Architecture Agent** ✅ **LIVE**

**Purpose:** Pattern-based architecture recommendations with cost estimates

**Command:** `/carl architect <question>`

**What It Does:**
- Uses 148+ architecture patterns as context
- Provides recommendations with pros/cons
- Real-time AWS pricing via pricing tool
- SOC 2 compliance mapping

**Tools:** `get_architecture_patterns`, `get_aws_pricing`, `get_compliance_requirements`, `compare_architecture_options`

**Implementation:** `slack_router.py` (handle_architect_command) + `agent_core.py` + `architecture_tools.py`

---

**3. Terraform Generation Service** ✅ **LIVE**

**Purpose:** AI-driven Terraform code generation grounded by architecture patterns

**Commands:** `/carl foundation`, `/carl account-factory`, `/carl build`

**What It Does:**
- Uses Claude AI with 148+ architecture patterns as grounding context
- Generates compliant Terraform for VPCs, security services, SCPs, etc.
- Validates generated code
- Includes SOC 2 control mappings

**Used By:**
- **Foundation Builder** (`/carl foundation`) - Single account setup
- **Account Factory** (`/carl account-factory`) - Multi-account with AFT
- **Build Command** (`/carl build`) - Interactive blueprint builds

**Implementation:** `ai_terraform_generator.py` + `generate_terraform_code()` in `architecture_tools.py`

---

**4. Remediation** (via `/carl drift`)

**Purpose:** Fix drift and compliance issues

**Note:** Remediation functionality is accessed through `/carl drift scan` and `/carl drift terraform` commands, which detect configuration drift and generate Terraform to fix it.

---

### Agent Implementation: AWS Bedrock Agents

**Why Bedrock Agents?**

✅ No need to build orchestration logic (AWS handles it)
✅ Built-in reasoning and planning
✅ Error handling and retries
✅ Tool calling framework
✅ Session management
✅ Cost-effective ($0.002/invocation + model costs)

**How It Works:**

```python
# Initialize agent
from services.advisory_agent import AdvisoryAgent

agent = AdvisoryAgent(agent_id="advisory-agent-id")

# Invoke with question
result = agent.ask_question(
    question="How do I stand up a web server?",
    session_id="user-session-123"
)

# Agent autonomously:
# 1. Plans steps (what resources to scan)
# 2. Calls tools (scan_environment, get_compliance_requirements)
# 3. Reasons about results
# 4. Generates tailored response
# 5. Returns answer + actions taken
```

**Agent Configuration:**

Each agent is configured in AWS Bedrock with:
- **Agent Instructions:** System prompt defining agent's role and behavior
- **Action Groups:** Sets of tools the agent can use
- **Knowledge Bases:** Static patterns, pricing data, SOC 2 mappings (RAG)
- **Lambda Functions:** Tool implementations

**Cost Model:**

| Agent Type | Per Invocation | Monthly (100 uses) |
|------------|----------------|-------------------|
| Advisory | $0.003 | $0.30 |
| Architect | $0.01 | $1.00 |
| Terraform Gen | $0.01 | $1.00 |
| Drift Scan | $0.005 | $0.50 |
| **Total** | - | **$2.80/month** |

**ROI:** Saves 20+ hours/month of engineering time = **$2,000+/month value**

---

## AWS Services Stack

### Security & Compliance Services (Per Account)

| Service | Purpose | SOC 2 Mapping |
|---------|---------|---------------|
| **AWS Config** | Configuration compliance, conformance packs | CC6.1, CC6.6, CC6.7 |
| **Security Hub** | Finding aggregation, security standards | CC7.1, CC7.2 |
| **GuardDuty** | Runtime threat detection | CC6.8, CC7.2, CC7.3 |
| **Inspector** | Vulnerability scanning (EC2, Lambda, ECR) | CC6.1, CC7.1 |
| **Macie** | Sensitive data discovery | CC6.1, CC6.5 |
| **IAM Access Analyzer** | Least privilege, external access | CC6.1, CC6.2, CC6.3 |
| **CloudTrail** | API audit logging | CC4.1, CC4.2, CC7.2 |
| **Audit Manager** | Evidence collection, assessment reports | All CC controls |

### CARL Core Services (Management Account)

| Service | Purpose | Est. Cost |
|---------|---------|-----------|
| **API Gateway** | Slack webhook endpoint | $3-5/mo |
| **Lambda** | Bot logic, services | $5-15/mo |
| **Bedrock (Claude)** | AI processing (Haiku + Sonnet) | $30-100/mo |
| **DynamoDB** | State, evidence, exceptions, drift, feedback | $10-30/mo |
| **S3** | Evidence storage, reports | $5-15/mo |
| **Secrets Manager** | API keys, credentials | $2/mo |
| **EventBridge** | Cross-account event routing | $1-2/mo |
| **SNS** | Notifications | <$1/mo |
| **KMS** | Encryption keys | $1/mo |
| **CloudWatch Logs** | Application logging | $5-10/mo |

---

## Data Model

### DynamoDB Tables

**1. Findings Table**
```
PK: ACCOUNT#{account_id}#FINDING#{finding_id}
SK: SOURCE#{source}#TIMESTAMP#{timestamp}

Attributes:
- finding_id, account_id, source, severity, status
- resource_type, resource_id, control_ids
- title, description, remediation_steps
- created_at, updated_at, remediation_id

GSIs: severity-index, control-index, account-status-index
```

**2. Evidence Table**
```
PK: EVIDENCE#{evidence_id}
SK: TIMESTAMP#{timestamp}

Attributes:
- evidence_id, evidence_type, source
- collected_at, s3_key, integrity_hash
- control_ids, metadata

GSIs: type-index, control-index
```

**3. Exceptions Table**
```
PK: EXCEPTION#{exception_id}
SK: STATUS#{status}

Attributes:
- exception_id, finding_id, exception_type
- status, justification, compensating_control
- requested_by, approved_by, denied_by
- requested_at, approved_at, expires_at
- control_ids, risk_level

GSIs: status-index, control-index, expiration-index
```

**4. Drift Table**
```
PK: DRIFT#{drift_id}
SK: TIMESTAMP#{timestamp}

Attributes:
- drift_id, resource_type, resource_id
- drift_type, attribute_name
- expected_value, actual_value
- security_sensitive, acknowledged
- detected_at, acknowledged_at, acknowledged_by

GSIs: resource-index, acknowledged-index
```

**5. AI Feedback Table**
```
PK: FEEDBACK#{feedback_id}
SK: TIMESTAMP#{timestamp}

Attributes:
- feedback_id, recommendation_id
- category, feedback_type (positive/negative)
- feedback_text, user_id
- created_at

GSIs: category-index, recommendation-index
```

**6. Preferences Table**
```
PK: ACCOUNT#{account_id}
SK: PREFERENCE#{preference_type}

Types:
- AUTO_REMEDIATION: { enabled, approved_types }
- NOTIFICATIONS: { channel_id, severities }
- SUPPRESSIONS: { finding_types, resource_ids }
- THRESHOLDS: { auto_approve_count, confidence_required }
```

**7. Approvals Table**
```
PK: APPROVAL#{approval_id}
SK: TIMESTAMP#{timestamp}

Attributes:
- approval_id, account_id, finding_id
- finding_type, resource_type, remediation_action
- requested_by, approved_by, status
- created_at, resolved_at, slack_message_ts
```

**8. Remediations Table**
```
PK: REMEDIATION#{remediation_id}
SK: TIMESTAMP#{timestamp}

Attributes:
- remediation_id, account_id, finding_id
- action, status, pre_state, post_state
- execution_arn, error_message
- created_at, completed_at
```

**9. Conversations Table** (for AI context)
```
PK: CHANNEL#{channel_id}
SK: TIMESTAMP#{timestamp}

Attributes:
- message_id, user_id, content, role
- context: { account_id, finding_ids, etc. }
- ttl: 24 hours
```

---

## Security Model

### CARL's Own Security

```
┌─────────────────────────────────────────────────────────────┐
│                 CARL SECURITY MODEL                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Secrets Management:                                         │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Secrets Manager                                     │    │
│  │  - /carl/slack/bot-token                             │    │
│  │  - /carl/slack/signing-secret                        │    │
│  │  - /carl/github/app-private-key (future)             │    │
│  │  - /carl/github/webhook-secret (future)              │    │
│  │                                                      │    │
│  │  Rotation: Automatic 90-day rotation                 │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  IAM:                                                        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  - Least privilege for each Lambda                   │    │
│  │  - Separate roles for read vs. write operations      │    │
│  │  - No wildcard permissions                           │    │
│  │  - STS external ID for cross-account                 │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  Encryption:                                                 │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  - S3: SSE-KMS with customer-managed key             │    │
│  │  - DynamoDB: Encryption at rest (AWS managed)        │    │
│  │  - Secrets Manager: Automatic encryption             │    │
│  │  - All data in transit: TLS 1.2+                     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  Audit Trail:                                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  - All CARL actions logged to CloudTrail             │    │
│  │  - All remediations logged to DynamoDB               │    │
│  │  - Exception approvals/denials tracked               │    │
│  │  - S3 access logging enabled                         │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## SOC 2 Trust Services Criteria Coverage

| Control | Description | CARL Feature |
|---------|-------------|--------------|
| **CC1.1** | Control Environment | AI Architect, Foundation Builder |
| **CC3.1** | Risk Assessment | Exception Manager, Risk Analysis |
| **CC4.1** | Monitoring Activities | Report Generator, Findings Service |
| **CC4.2** | Evaluation | Evidence Collector, Compliance Reports |
| **CC5.1** | Control Activities | Foundation Builder, Remediation |
| **CC6.1** | Logical Access | IAM Evidence, Access Monitoring |
| **CC6.2** | Access Provisioning | IAM Drift Detection |
| **CC6.3** | Access Removal | Unused Credential Detection |
| **CC6.5** | Data Protection | S3 Encryption Evidence, Macie |
| **CC6.6** | Configuration Mgmt | Drift Detector, Config Rules |
| **CC6.7** | Transmission Security | VPC Evidence, TLS Detection |
| **CC6.8** | Change Management | Drift Detection, CloudTrail |
| **CC7.1** | Vulnerability Mgmt | Inspector Integration |
| **CC7.2** | Security Monitoring | GuardDuty, Security Hub |
| **CC7.3** | Incident Response | Alert Routing, Evidence Collection |
| **CC8.1** | Change Management | Drift Detector, Terraform Comparison |
| **CC9.1** | Risk Mitigation | Exception Manager |
| **A1.1** | Availability | Backup Evidence, DR Monitoring |
| **C1.1** | Confidentiality | Encryption Evidence, Data Classification |

---

## Cost Summary

### CARL Foundation Module (Core Infrastructure)

**Actual Measured Cost: $2.61/month**

| Component | Monthly Cost | Notes |
|-----------|--------------|-------|
| **DynamoDB Tables** (10 tables) | $0.51 | Pay-per-request, low usage |
| **Lambda Executions** (3 functions) | $0.15 | Pricing prefetch monthly, pattern analyzer daily, API as needed |
| **Secrets Manager** (2 secrets) | $0.80 | $0.40 per secret (Slack bot token, signing secret) |
| **CloudWatch Logs** | $0.10 | 7-day retention, KMS encrypted |
| **KMS Customer-Managed Key** | $1.00 | Single key for all encryption |
| **S3 Storage** (3 buckets) | $0.05 | Evidence, reports, Terraform state (minimal usage) |
| **SNS Topics** | $0.00 | Free tier |
| **EventBridge Schedules** | $0.00 | Free tier (2 schedules) |
| **Total Foundation** | **$2.61** | Core CARL infrastructure |

### Additional Costs with Security Scanning

| Deployment | Monthly Cost |
|------------|--------------|
| Single Account (with Security Hub) | $22-50 |
| 5 Accounts (with Security Hub) | $102-250 |
| 20 Accounts (with Security Hub) | $402-1,000 |

**Additional cost breakdown when enabling full compliance scanning:**
- Bedrock API (Claude Haiku + Sonnet): $15-30/mo (varies by usage)
- Security Hub: $20-50/mo per account (depends on findings volume)
- Additional S3/DynamoDB: $5-15/mo (scales with findings and evidence)

**Note:** The foundation module ($2.61/mo) is always required. Security Hub and compliance scanning are optional and can be enabled per account as needed.

---

## New Architecture Patterns (Latest Release)

### VPC Endpoints & PrivateLink (`vpc_endpoint_patterns.py`)

**3 New Decision Categories:**

1. **VPC Endpoint Strategy** - When and how to use VPC endpoints
   - Gateway Endpoints Only (S3 + DynamoDB, free)
   - Selective Interface Endpoints (critical services, $20-100/mo)
   - Comprehensive Interface Endpoints (no internet egress, $100-500/mo)
   - Centralized Endpoint VPC (shared via TGW, cost-effective at scale)

2. **Endpoint Policies** - How to secure endpoints
   - Full Access (default)
   - Least Privilege Policies (production recommended)

3. **PrivateLink** - Service provider and consumer patterns
   - PrivateLink for SaaS Delivery
   - PrivateLink for Partner Integration
   - PrivateLink for Internal Services

**Key Features:**
- Essential endpoint priorities (Tier 1: SSM, KMS, Secrets; Tier 2: ECR, S3, STS; Tier 3: Service-specific)
- Cost analysis ($7.20/mo per endpoint per AZ)
- Security best practices (endpoint policies, private DNS)
- Break-even analysis vs NAT Gateway

**SOC 2 Impact:** CC6.6 (Network segmentation), CC6.7 (Private connectivity), CC6.8 (Reduced attack surface)

---

### KMS Key Management (`kms_patterns.py`)

**4 New Decision Categories:**

1. **KMS Key Strategy** - How many keys, what architecture
   - AWS Managed Keys (free, limited control)
   - Single CMK per Service (recommended, $5-20/mo)
   - Multi-Key Strategy (per workload/environment, $20-100/mo)
   - Centralized Key Management (multi-account, shared keys)

2. **Key Rotation** - Automatic vs manual rotation
   - Automatic Yearly Rotation (recommended, transparent, no downtime)
   - Manual Rotation with Aliases (custom schedule, more control)

3. **Key Policies** - Least privilege key access control
   - Minimal Key Policy (root account, development only)
   - Standard Key Policy (separate admin/user, production)
   - Cross-Account Key Policy (shared keys across accounts)

4. **Encryption at Rest** - What to encrypt and how
   - Service Default Encryption (development)
   - Encryption Everywhere with CMK (production recommended)

**Key Features:**
- Recommended key architecture (8 keys per production account: S3, RDS, EBS, Secrets, Logs, Backup, SNS, SQS)
- Key policy templates with separation of duties
- What to always encrypt (RDS, S3 sensitive data, EBS, Secrets Manager, DynamoDB PII)
- Enable EBS encryption by default account-wide

**SOC 2 Impact:** CC6.5 (Encryption of confidential information), C1.1 (Confidentiality through encryption), CC8.1 (Automated key rotation)

---

## Future Roadmap

**See [ROADMAP.md](./ROADMAP.md) for detailed priority list.**

### Near-Term
- Auto-remediation execution
- Jira/ticketing integration
- Web dashboard

### Medium-Term
- Multi-framework support (HIPAA, PCI-DSS, ISO 27001)
- CI/CD integration (pre-deployment compliance checks)
- GitHub code scanning integration

### Long-Term
- ML-based anomaly detection
- Predictive compliance scoring
- Multi-cloud support
