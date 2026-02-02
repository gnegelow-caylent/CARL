# AWS Bedrock AgentCore Migration Plan

**Status:** Planning
**Last Updated:** February 1, 2026

---

## Overview

Migrate CARL's custom `AgentCore` implementation to **[AWS Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)** - an agentic platform for building, deploying, and operating effective agents securely at scale.

### What is AgentCore?

AgentCore is AWS's managed agentic platform that provides:

**Build:**
- Persistent memory systems
- Gateway for connecting tools with minimal code
- Secure browser runtime for web-based workflows
- Code execution for data visualization

**Deploy:**
- Complete session isolation
- Support for workloads up to 8 hours (vs Lambda's 15 min limit)
- Native identity provider integration
- Fine-grained access policies

**Monitor:**
- Real-time performance dashboards via CloudWatch
- Quality evaluation (correctness, helpfulness, safety)
- OpenTelemetry integration for observability

**Note:** AgentCore is different from standard Bedrock Agents (`aws_bedrockagent_agent`). AgentCore is a comprehensive platform with memory, long-running tasks, and monitoring - not just agent orchestration.

### Why Migrate?

| Benefit | Description |
|---------|-------------|
| **Reduced code** | Remove ~2,000 lines of custom agent orchestration |
| **Enterprise features** | Persistent memory, 8-hour tasks, code interpreter |
| **No timeout limits** | Current Lambda limited to 15 minutes |
| **AWS-managed** | Scaling, monitoring, security handled by AWS |
| **Cost** | ~$0.40/month platform fee (acceptable trade-off) |

---

## Current State

### Custom Implementation

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| AgentCore class | `agent_core.py` | ~500 | Agent orchestration, tool calling |
| Learning service | `learning_service.py` | ~580 | Interaction logging, pattern analysis |
| Scanning tools | `scanning_tools.py` | ~340 | AWS resource scanning tools |
| Architecture tools | `architecture_tools.py` | ~940 | Pattern retrieval, pricing, Terraform |

### Custom DynamoDB Tables

| Table | Purpose | Can AgentCore Replace? |
|-------|---------|------------------------|
| `scan_history` | Interaction logging | Yes - AgentCore Memory |
| `resource_graph` | Resource relationships | Yes - AgentCore Memory |
| `foundation` | Session state | Yes - AgentCore Sessions |

### Current Agents

| Agent | Command | Status |
|-------|---------|--------|
| Advisory Agent | `/carl ask` | Uses custom AgentCore |
| Architecture Agent | `/carl architect` | Uses custom AgentCore |
| Terraform Generation | `/carl foundation`, `/carl account-factory`, `/carl build` | Uses custom AgentCore |
| Drift Scan | `/carl drift` | Uses custom AgentCore |

---

## Target State

### AWS Bedrock AgentCore Components

| Component | Replaces | Benefit |
|-----------|----------|---------|
| AgentCore Runtime | `agent_core.py` | Managed orchestration |
| AgentCore Memory | `learning_service.py`, DynamoDB tables | Persistent learning |
| AgentCore Gateway | Manual tool registration | Standardized tool management |
| AgentCore Observability | Custom CloudWatch logging | Built-in monitoring |
| AgentCore Policy | Custom IAM | Enterprise access control |

---

## Migration Phases

### Phase 1: Migrate `/carl ask` Only

**Goal:** Move just `/carl ask` to AgentCore as proof of concept

**Scope:** ONLY `/carl ask` - nothing else changes

- [ ] **1.1 Create AgentCore Agent in AWS**
  - [ ] Enable Bedrock AgentCore in account
  - [ ] Create agent with scanning instructions
  - [ ] Configure IAM permissions

- [ ] **1.2 Register Scanning Tools**
  - [ ] `scan_iam` → AgentCore action group
  - [ ] `scan_vpc` → AgentCore action group
  - [ ] `scan_s3` → AgentCore action group
  - [ ] `scan_cloudtrail` → AgentCore action group
  - [ ] `scan_security_hub` → AgentCore action group

- [ ] **1.3 Update Slack Router**
  - [ ] Add feature flag `USE_AGENTCORE_ASK=true/false`
  - [ ] Call AgentCore instead of custom Agent for `/carl ask`
  - [ ] Keep custom Agent as fallback

- [ ] **1.4 Test & Deploy**
  - [ ] Test in dev environment
  - [ ] Compare responses to custom implementation
  - [ ] Deploy with feature flag OFF
  - [ ] Enable for testing

**Deliverable:** `/carl ask` working on AgentCore (feature-flagged)

---

### Phase 2: Evaluation (Week 2)

**Goal:** Decide whether to proceed with full migration

- [ ] **2.1 Performance Comparison**
  - [ ] Response time: Custom vs AgentCore (target: <5s)
  - [ ] Accuracy: Same questions, compare answers
  - [ ] Tool calling: Verify correct tools selected
  - [ ] Memory: Verify learning persists across sessions

- [ ] **2.2 Cost Analysis**
  - [ ] Track AgentCore costs for 1 week
  - [ ] Compare to current Bedrock API costs
  - [ ] Calculate monthly projection
  - [ ] Document cost breakdown

- [ ] **2.3 Feature Evaluation**
  - [ ] Test persistent memory across sessions
  - [ ] Test long-running tasks (>15 min)
  - [ ] Evaluate code interpreter capability
  - [ ] Test session isolation

- [ ] **2.4 Decision Point**
  - [ ] Document pros/cons
  - [ ] Get stakeholder input
  - [ ] **GO / NO-GO decision**

**Deliverable:** Decision document with recommendation

---

### Phase 3: Migrate Other Commands (Future)

**Goal:** Migrate remaining commands IF Phase 1 & 2 succeed

*Only proceed after `/carl ask` is stable on AgentCore*

- [ ] **3.1 `/carl architect`**
  - [ ] Register architecture tools with AgentCore
  - [ ] Test pattern recommendations
  - [ ] Deploy with feature flag

- [ ] **3.2 `/carl build`, `/carl foundation`, `/carl account-factory`**
  - [ ] Register Terraform generation tools
  - [ ] Test interactive workflows
  - [ ] Deploy with feature flag

- [ ] **3.3 Cleanup (After All Migrated)**
  - [ ] Remove custom `agent_core.py`
  - [ ] Remove `learning_service.py` (if AgentCore Memory works)
  - [ ] Update documentation

**Deliverable:** All commands on AgentCore, custom code removed

---

## Success Criteria

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Response time | <5 seconds | CloudWatch latency metrics |
| Accuracy | Same as current | Side-by-side comparison |
| Cost | <$5/month increase | AWS Cost Explorer |
| Code reduction | >1,500 lines removed | Git diff |
| Uptime | 99.9% | CloudWatch availability |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| AgentCore doesn't support our tools | Keep custom AgentCore as fallback |
| Performance regression | A/B test before full switch |
| Cost higher than expected | Set billing alerts, abort if >$20/month |
| Memory doesn't work as expected | Keep DynamoDB tables, use hybrid approach |
| Breaking changes during migration | Feature flag allows instant rollback |

---

## Rollback Plan

If migration fails at any phase:

1. Set `USE_AGENTCORE=false` in environment
2. Redeploy with custom AgentCore
3. Document issues encountered
4. Reassess in 3 months

---

## Progress Log

| Date | Phase | Status | Notes |
|------|-------|--------|-------|
| 2026-02-01 | Planning | Complete | Migration plan created |
| | Phase 1 | Not Started | |
| | Phase 2 | Not Started | |
| | Phase 3 | Not Started | |

---

## References

- [AWS Bedrock AgentCore Product Page](https://aws.amazon.com/bedrock/agentcore/)
- [AWS Bedrock Agents Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html)
- [CARL Design Principles](./CARL_DESIGN_PRINCIPLES.md) - Principle #7
- [CARL Architecture](./ARCHITECTURE.md) - Agent section
- [Current AgentCore Implementation](./carl-app/src/services/agent_core.py)
