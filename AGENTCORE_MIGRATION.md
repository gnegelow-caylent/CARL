# AWS Bedrock AgentCore Migration Plan

**Status:** Planning
**Last Updated:** February 1, 2026
**Goal:** Migrate entire CARL application to AgentCore

---

## Overview

Migrate CARL from Lambda + custom agent orchestration to **[AWS Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)** - a managed agentic platform for building, deploying, and operating AI agents at scale.

### What is AgentCore?

AgentCore is AWS's managed agentic platform (currently in preview) that provides:

| Service | Description |
|---------|-------------|
| **Runtime** | Serverless compute with 8-hour support, session isolation, fast cold starts |
| **Memory** | Persistent short-term (STM) and long-term memory (LTM) across sessions |
| **Gateway** | Converts APIs/Lambda functions into MCP tools with OAuth support |
| **Code Interpreter** | Sandboxed code execution for data analysis |
| **Browser** | Cloud-based web automation |
| **Observability** | OpenTelemetry tracing, CloudWatch dashboards |
| **Identity** | AWS and third-party authentication integration |

**Key Difference:** AgentCore is NOT standard Bedrock Agents (`aws_bedrockagent_agent`). It's a comprehensive deployment platform with memory, long-running tasks, and monitoring.

### Why Migrate the Entire App?

| Current Pain Point | AgentCore Solution |
|-------------------|-------------------|
| Lambda 15-min timeout | 8-hour runtime support |
| Custom session state (DynamoDB) | Built-in persistent memory |
| Manual tool registration | Gateway auto-converts to MCP tools |
| Custom orchestration (~2,000 lines) | Managed Runtime |
| DIY observability | Built-in OpenTelemetry + dashboards |
| Complex multi-step wizards lose state | Memory persists across sessions |

---

## Current Architecture

### What We Have Today

```
┌─────────────────────────────────────────────────────────────┐
│                    Current CARL Architecture                 │
├─────────────────────────────────────────────────────────────┤
│  Slack → API Gateway → Lambda (15 min limit)                │
│                           │                                  │
│                           ├── agent_core.py (orchestration)  │
│                           ├── scanning_tools.py              │
│                           ├── architecture_tools.py          │
│                           ├── learning_service.py            │
│                           └── bedrock_service.py             │
│                                                              │
│  State: DynamoDB (foundation, scan_history, resource_graph)  │
└─────────────────────────────────────────────────────────────┘
```

### Code to Remove After Migration

| File | Lines | Purpose |
|------|-------|---------|
| `agent_core.py` | ~500 | Custom agent orchestration |
| `learning_service.py` | ~580 | Interaction logging, pattern analysis |
| `scanning_tools.py` | ~340 | Tool definitions (move to Gateway) |
| `architecture_tools.py` | ~940 | Tool definitions (move to Gateway) |
| **Total** | **~2,360** | Replaced by AgentCore Runtime + Memory |

### DynamoDB Tables to Retire

| Table | Purpose | Replaced By |
|-------|---------|-------------|
| `scan_history` | Interaction logging | AgentCore Memory (STM) |
| `resource_graph` | Resource relationships | AgentCore Memory (LTM) |
| `foundation` | Session state | AgentCore Sessions |

---

## Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Target CARL Architecture                  │
├─────────────────────────────────────────────────────────────┤
│  Slack → API Gateway → AgentCore Runtime (8 hr support)     │
│                           │                                  │
│                           ├── AgentCore Memory (STM + LTM)   │
│                           ├── AgentCore Gateway (MCP Tools)  │
│                           │      ├── scan_iam                │
│                           │      ├── scan_vpc                │
│                           │      ├── scan_s3                 │
│                           │      ├── get_pricing             │
│                           │      ├── generate_terraform      │
│                           │      └── ... (all tools)         │
│                           └── AgentCore Observability        │
│                                                              │
│  State: AgentCore Memory (replaces custom DynamoDB)          │
└─────────────────────────────────────────────────────────────┘
```

---

## AgentCore SDK & Deployment

### Installation

```bash
pip install bedrock-agentcore
```

### Basic Agent Structure

```python
from bedrock_agentcore import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

@app.entrypoint
def carl_agent(request):
    """Main CARL agent entrypoint."""
    prompt = request.get("prompt")
    session_id = request.get("session_id")

    # AgentCore handles orchestration, memory, tool calling
    return process_carl_request(prompt, session_id)

app.run()
```

### Deployment Commands

```bash
# 1. Configure agent
agentcore configure \
  --entrypoint carl_agent.py \
  --name carl-agent \
  --runtime PYTHON_3_12

# 2. Deploy to AWS
agentcore launch

# 3. Test invocation
agentcore invoke '{"prompt": "What is my S3 compliance status?"}'

# 4. Cleanup (if needed)
agentcore destroy
```

### Memory Configuration

```bash
# With short-term + long-term memory (recommended for CARL)
agentcore configure -e carl_agent.py --name carl-agent

# Without memory (for stateless commands)
agentcore configure -e carl_agent.py --name carl-agent --disable-memory
```

---

## Migration Phases

### Phase 1: `/carl ask` (Proof of Concept)

**Goal:** Migrate simplest command to learn the platform

**Why Start Here:**
- Single request/response (no complex state)
- Uses scanning tools (tests Gateway integration)
- Low risk - can easily compare to existing implementation

**Tasks:**

- [ ] **1.1 Setup AgentCore Environment**
  - [ ] Install `bedrock-agentcore` SDK
  - [ ] Configure AWS credentials with AgentCore permissions
  - [ ] Verify AgentCore available in us-east-1

- [ ] **1.2 Create Ask Agent**
  - [ ] Create `carl_ask_agent.py` with entrypoint
  - [ ] Port scanning tools to AgentCore Gateway
  - [ ] Configure agent with `agentcore configure`
  - [ ] Deploy with `agentcore launch`

- [ ] **1.3 Integrate with Slack**
  - [ ] Add `USE_AGENTCORE_ASK` feature flag
  - [ ] Update slack_router.py to call AgentCore endpoint
  - [ ] Keep Lambda fallback for rollback

- [ ] **1.4 Test & Validate**
  - [ ] Compare response quality
  - [ ] Measure latency
  - [ ] Verify tool calling works
  - [ ] Test error handling

**Deliverable:** `/carl ask` running on AgentCore with feature flag

---

### Phase 2: Evaluation & Decision

**Goal:** Determine if AgentCore is right for full migration

**Metrics to Track:**

| Metric | Target | Measurement |
|--------|--------|-------------|
| Response time | <5s | CloudWatch |
| Tool accuracy | Same as Lambda | Side-by-side test |
| Cost | <$10/month increase | Cost Explorer |
| Memory persistence | Works across sessions | Manual test |
| Reliability | 99.9% uptime | CloudWatch |

**Tasks:**

- [ ] **2.1 Run for 2 weeks in production**
- [ ] **2.2 Collect performance data**
- [ ] **2.3 Analyze costs**
- [ ] **2.4 Document issues encountered**
- [ ] **2.5 GO / NO-GO decision**

**Deliverable:** Decision document with data

---

### Phase 3: Migrate `/carl recommend` & `/carl architect`

**Goal:** Migrate architecture advisory commands

**Why Next:**
- Uses pricing tools and pattern retrieval
- Tests Gateway with more complex tools
- Benefits from memory (user preferences)

**Tasks:**

- [ ] **3.1 Port architecture tools to Gateway**
- [ ] **3.2 Create architecture agent**
- [ ] **3.3 Test pattern recommendations**
- [ ] **3.4 Deploy with feature flag**

---

### Phase 4: Migrate `/carl foundation` & `/carl account-factory`

**Goal:** Migrate complex multi-step wizards

**Why This Phase:**
- **Biggest benefit** - persistent memory for wizard state
- Currently uses DynamoDB for session state
- Multi-step flows can span multiple interactions

**Tasks:**

- [ ] **4.1 Port Terraform generation tools**
- [ ] **4.2 Configure LTM for session persistence**
- [ ] **4.3 Test multi-step wizard flows**
- [ ] **4.4 Retire `foundation` DynamoDB table**

---

### Phase 5: Migrate Remaining Commands

**Commands:**
- `/carl compliance assess`
- `/carl evidence collect`
- `/carl drift scan`
- `/carl report`

**Tasks:**

- [ ] **5.1 Port all remaining tools to Gateway**
- [ ] **5.2 Create unified CARL agent**
- [ ] **5.3 Test all commands end-to-end**
- [ ] **5.4 Remove feature flags, make AgentCore default**

---

### Phase 6: Cleanup

**Goal:** Remove legacy code and infrastructure

**Tasks:**

- [ ] **6.1 Delete custom agent code**
  - [ ] Remove `agent_core.py`
  - [ ] Remove `learning_service.py`
  - [ ] Remove tool definition files (now in Gateway)

- [ ] **6.2 Retire DynamoDB tables**
  - [ ] Remove `scan_history` table
  - [ ] Remove `resource_graph` table
  - [ ] Remove `foundation` table

- [ ] **6.3 Update documentation**
- [ ] **6.4 Archive Lambda-based implementation**

**Deliverable:** Clean codebase, ~2,000+ lines removed

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Code reduction | >2,000 lines removed |
| Response time | <5 seconds (same or better) |
| Cost increase | <$20/month |
| Memory working | Session state persists |
| All commands migrated | 100% |
| Zero Lambda dependency | Complete |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| AgentCore preview instability | Feature flags for instant rollback |
| Higher costs than expected | Set billing alerts, abort threshold $50/month |
| Memory doesn't fit our use case | Hybrid approach (AgentCore + DynamoDB) |
| Tool compatibility issues | Keep Lambda tools as fallback |
| Performance regression | A/B testing before full switch |

---

## Rollback Plan

At any phase, if issues occur:

1. Set `USE_AGENTCORE=false` environment variable
2. Lambda implementation takes over immediately
3. Document issues for future resolution
4. AgentCore resources remain for debugging

---

## Timeline (Estimated)

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1 | 1 week | None |
| Phase 2 | 2 weeks | Phase 1 complete |
| Phase 3 | 1 week | Phase 2 GO decision |
| Phase 4 | 2 weeks | Phase 3 complete |
| Phase 5 | 1 week | Phase 4 complete |
| Phase 6 | 1 week | Phase 5 complete |
| **Total** | **~8 weeks** | |

---

## Progress Log

| Date | Phase | Status | Notes |
|------|-------|--------|-------|
| 2026-02-01 | Planning | Complete | Full migration plan created |
| | Phase 1 | Not Started | `/carl ask` POC |
| | Phase 2 | Not Started | Evaluation |
| | Phase 3 | Not Started | Architecture commands |
| | Phase 4 | Not Started | Foundation/Account Factory |
| | Phase 5 | Not Started | Remaining commands |
| | Phase 6 | Not Started | Cleanup |

---

## References

- [AWS Bedrock AgentCore Product Page](https://aws.amazon.com/bedrock/agentcore/)
- [AgentCore Python SDK](https://github.com/aws/bedrock-agentcore-sdk-python)
- [AgentCore Starter Toolkit](https://github.com/aws/bedrock-agentcore-starter-toolkit)
- [AgentCore Samples](https://github.com/awslabs/amazon-bedrock-agentcore-samples)
- [AgentCore CLI Reference](https://aws.github.io/bedrock-agentcore-starter-toolkit/api-reference/cli.html)
- [CARL Design Principles](./CARL_DESIGN_PRINCIPLES.md) - Principle #7
- [CARL Architecture](./ARCHITECTURE.md)
