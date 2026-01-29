# CARL Session Index

This index tracks all major development sessions for easy context retrieval.

## How to Use This Index

When starting a new Claude Code session, read `CLAUDE.md` first for current project state, then reference specific session summaries below for detailed context on past work.

## Session Summaries (Newest First)

### 2026-01-29: Phase 2 Continuous Learning Deployment
**File:** `SESSION_2026-01-29_PHASE2_DEPLOYMENT.md`

**Summary:** Implemented and deployed Phase 2 continuous learning system. Fixed multiple validation errors and syntax bugs. System learns from user interactions with feedback buttons and daily pattern analysis.

**Key Deliverables:**
- Learning service with interaction logging
- Feedback buttons (👍 👎) on every answer
- Pattern analyzer Lambda (daily at 2am UTC)
- DynamoDB tables: scan_history, resource_graph
- Architecture question handling

**Known Issues:**
- Hardcoded "ARCHITECTURE_QUESTION" detection (technical debt)

**Status:** Deployed to AWS (develop branch)

---

### 2026-01-28: Jira Integration & Evidence Collection
**File:** `SESSION_SUMMARY_JIRA_INTEGRATION.md`

**Summary:** Fixed end-to-end evidence collection and Jira sync pipeline. Evidence collection now creates findings for all detected issues, and Jira sync prevents duplicates.

**Key Deliverables:**
- Fixed security findings detection
- Stable finding IDs (content-based)
- Multiple findings per resource
- Jira duplicate prevention
- Fixed 6 syntax errors
- Fixed DynamoDB composite key operations

**Status:** Complete and working

---

## Quick Reference: What's Where

### User-Facing Documentation
- **`CLAUDE.md`** - Main context file (read this first!)
- **`FEATURES.md`** - Complete feature status overview
- **`SLACK_COMMANDS.md`** - User guide for all Slack commands
- **`INFRASTRUCTURE_BLUEPRINTS.md`** - Available infrastructure blueprints
- **`ROADMAP.md`** - Priority roadmap and next steps

### Technical Documentation
- **`CONTINUOUS_LEARNING.md`** - Phase 2 learning system architecture (700 lines)
- **`CARL_DESIGN_PRINCIPLES.md`** - Core design principles (4 principles)
- **`SMART_GENERATION.md`** - Smart infrastructure generation
- **`BOOTSTRAP_AUTOMATION.md`** - Complete AWS environment bootstrap
- **`EVIDENCE_AND_FINDINGS.md`** - Evidence collection & findings pipeline
- **`SLACK_IMPROVEMENTS.md`** - Async processing, modals, button handlers
- **`ARCHITECTURE.md`** - Full technical architecture

### Session Summaries (Detailed Context)
- **`SESSION_2026-01-29_PHASE2_DEPLOYMENT.md`** - Phase 2 implementation & deployment
- **`SESSION_SUMMARY_JIRA_INTEGRATION.md`** - Evidence collection & Jira fixes

### API & Service Documentation
- **`AI_OPPORTUNITIES.md`** - AI-powered features and opportunities
- **`COMPLIANCE_AGENT.md`** - Autonomous compliance assessment agent

## Common Tasks & Where to Find Info

| Task | Primary Document | Supporting Docs |
|------|------------------|-----------------|
| Understanding CARL's purpose | `CLAUDE.md` → Project Overview | `FEATURES.md` |
| Starting a new feature | `CLAUDE.md` → Architecture | `CARL_DESIGN_PRINCIPLES.md` |
| Understanding continuous learning | `CONTINUOUS_LEARNING.md` | `SESSION_2026-01-29_PHASE2_DEPLOYMENT.md` |
| Debugging evidence collection | `EVIDENCE_AND_FINDINGS.md` | `SESSION_SUMMARY_JIRA_INTEGRATION.md` |
| Adding new Slack commands | `SLACK_COMMANDS.md` | `SLACK_IMPROVEMENTS.md` |
| Infrastructure changes | `SMART_GENERATION.md` | `INFRASTRUCTURE_BLUEPRINTS.md` |
| Bootstrap automation | `BOOTSTRAP_AUTOMATION.md` | `CLAUDE.md` |
| Understanding AI agents | `COMPLIANCE_AGENT.md` | `AI_OPPORTUNITIES.md` |
| Prioritizing next work | `ROADMAP.md` | `CLAUDE.md` → Latest Updates |

## Session Summary Template

When creating a new session summary, use this structure:

```markdown
# Session Summary: [Title]

**Date:** YYYY-MM-DD
**Session Type:** [Implementation | Bug Fix | Deployment | Planning]
**Status:** [Complete | In Progress | Blocked]

## Executive Summary
[2-3 sentences: what was accomplished]

## Timeline of Events
[Chronological list of what happened]

## Key Deliverables
[What was created/changed]

## Known Issues & Technical Debt
[What needs follow-up]

## Files Changed Summary
[List of files created/modified]

## Next Session Priorities
[What to do next]
```

## Conversation Transcripts

Full conversation transcripts are stored in:
```
/Users/gnegelow/.claude/projects/-Users-gnegelow/[session-id].jsonl
```

Current session: `de2a05b1-59cf-4ee2-ba31-303e090a9f1b.jsonl`

---

**Last Updated:** 2026-01-29
**Total Sessions Documented:** 2
