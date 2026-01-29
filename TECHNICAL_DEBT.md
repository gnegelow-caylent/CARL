# CARL Technical Debt

This document tracks known technical debt items that need addressing.

## Active Technical Debt

### 🔴 HIGH PRIORITY: Hardcoded Architecture Question Detection

**Created:** 2026-01-29
**Location:** `carl-app/src/handlers/slack_router.py:1474`
**Estimated Effort:** 2-3 hours
**Impact:** High - affects system intelligence and brittleness

#### Problem Description

The current implementation uses a magic string to detect architecture questions:

```python
# Current brittle implementation
if "ARCHITECTURE_QUESTION" in scan_results_raw:
    logger.info("Detected architecture/design question - providing guidance")
    from services.architecture_advisor import ArchitectureAdvisor
    advisor = ArchitectureAdvisor()
    response = advisor.get_recommendation(question)
    # ...
```

**Why This Is Bad:**
1. Relies on agent outputting exact string "ARCHITECTURE_QUESTION"
2. Agent instructions prescribe output: "Respond: 'ARCHITECTURE_QUESTION: Provide design guidance'"
3. Still brittle pattern matching, just moved to AI output layer
4. Not truly intelligent - it's a workaround
5. User correctly identified: "is this hard coded though? It shouldn't be anymore, right?"

#### Context: How We Got Here

**Original Problem:**
- User asked: "i need to design an app with iot what are my options?"
- CARL refused: "Architecture design questions fall outside my core compliance/security assessment role"
- User feedback: "not great.. i shouldn't be able to easily break this"

**Quick Fix (Current State):**
- Updated agent instructions to recognize two question types
- Added magic string "ARCHITECTURE_QUESTION" as signal
- Routes to ArchitectureAdvisor when string detected

**User Follow-up:**
- "is this hard coded though? It shouldn't be anymore, right?"
- User immediately spotted it's still hardcoded logic

#### Proposed Solutions

##### Option 1: Two-Agent System (Recommended)
**Pros:** Clean separation, clear responsibility
**Cons:** Need to classify questions first

```python
# Pre-classify the question
classification = classify_question_type(question)

if classification == "compliance":
    # Use scanning agent with scanning tools
    scanning_agent = Agent(
        tools=[scan_iam, scan_s3, scan_vpc, ...],
        instructions="Scan AWS resources and report findings"
    )
    result = scanning_agent.execute(question)

elif classification == "architecture":
    # Use architecture agent with architecture tools
    architecture_agent = Agent(
        tools=[get_architecture_patterns, get_pricing, ...],
        instructions="Provide architecture guidance and design recommendations"
    )
    result = architecture_agent.execute(question)
```

##### Option 2: Single Agent with Mixed Tools
**Pros:** Agent autonomously chooses behavior
**Cons:** More complex tool set, might confuse agent

```python
# Single agent with both scanning and architecture tools
hybrid_agent = Agent(
    tools=[
        # Scanning tools
        scan_iam, scan_s3, scan_vpc, ...,
        # Architecture tools
        get_architecture_patterns,
        get_architecture_recommendation,
        get_pricing_info
    ],
    instructions="""
    You are CARL, an AWS assistant.

    For compliance questions: Use scanning tools to check existing resources
    For architecture questions: Use architecture tools to provide design guidance

    Choose the appropriate tools based on the question type.
    """
)

result = hybrid_agent.execute(question)
```

##### Option 3: Classification Tool
**Pros:** Explicit classification step, agent decides
**Cons:** Extra API call

```python
# Let Claude classify without prescribing output
def classify_question(question: str) -> str:
    """
    Use Claude to classify question type.
    Returns: "compliance" or "architecture"
    """
    prompt = f"""
    Classify this AWS question as either "compliance" or "architecture":

    Question: {question}

    - Compliance: Questions about existing deployed AWS resources
    - Architecture: Questions about what to build or how to design

    Return only one word: compliance or architecture
    """

    response = bedrock.invoke_claude(prompt)
    return response.strip().lower()

# Route based on classification
question_type = classify_question(question)

if question_type == "compliance":
    # Scanning agent...
else:
    # Architecture agent...
```

#### Recommended Approach

**Use Option 1: Two-Agent System with Classification**

**Why:**
- Clean separation of concerns
- Each agent has focused tools and instructions
- Classification step is explicit and auditable
- Easy to test and debug
- Can enhance classification over time (add logging, learning)

**Implementation Steps:**

1. **Create classification function** (30 min)
   ```python
   def classify_aws_question(question: str) -> str:
       """Classify question as compliance or architecture."""
       # Use Claude to classify (Option 3 approach)
       # Add logging for learning over time
   ```

2. **Refactor handle_ask_command_fallback** (1 hour)
   ```python
   # Add at top of function
   question_type = classify_aws_question(question)

   if question_type == "compliance":
       # Existing scanning agent code...
       scanning_agent = Agent(tools=scanning_tools, ...)
       result = scanning_agent.execute(question)
       # Log interaction with learning service

   elif question_type == "architecture":
       # Architecture agent code...
       architecture_agent = Agent(tools=architecture_tools, ...)
       result = architecture_agent.execute(question)
       # No learning yet for architecture questions
   ```

3. **Create architecture tools** (1 hour)
   ```python
   # carl-app/src/services/architecture_tools.py

   def create_architecture_tools() -> list[Tool]:
       """Create architecture recommendation tools."""
       return [
           Tool(
               name="get_architecture_patterns",
               description="Get AWS architecture patterns for a use case",
               function=lambda use_case: patterns.get_patterns(use_case),
               ...
           ),
           Tool(
               name="get_aws_pricing",
               description="Get real-time AWS pricing",
               function=lambda service, config: pricing.get_pricing(...),
               ...
           ),
           # Add more architecture tools...
       ]
   ```

4. **Test both paths** (30 min)
   - Test compliance: "Is my VPC secure?"
   - Test architecture: "What IoT services should I use?"
   - Verify no "ARCHITECTURE_QUESTION" string in code
   - Verify logs show classification decision

5. **Remove magic string** (15 min)
   - Delete `if "ARCHITECTURE_QUESTION" in scan_results_raw:` check
   - Remove "ARCHITECTURE_QUESTION" from agent instructions
   - Verify no hardcoded strings remain

#### Testing Checklist

- [ ] Compliance question routes to scanning agent
- [ ] Architecture question routes to architecture agent
- [ ] Classification is logged for learning
- [ ] No magic strings in code
- [ ] No prescriptive output instructions
- [ ] Both paths work end-to-end
- [ ] User feedback buttons work for compliance questions
- [ ] Edge cases handled (ambiguous questions)

#### Success Criteria

1. **No hardcoded strings** - No "ARCHITECTURE_QUESTION" or similar magic strings
2. **AI decides behavior** - Classification and routing are AI-driven
3. **Clean architecture** - Clear separation between compliance and architecture flows
4. **Observable** - Classification decisions are logged
5. **User satisfaction** - System handles both question types intelligently

---

## Resolved Technical Debt

### ✅ Syntax Error in slack_router.py (RESOLVED 2026-01-29)

**Problem:** Unterminated string literal at line 1418
**Fix:** Added closing `"""` after line 1454
**Commit:** `cb8e005`

---

## Technical Debt Prevention

### Best Practices to Avoid Future Debt

1. **No Magic Strings** - If you find yourself checking for exact string matches, it's probably brittle
2. **Let AI Decide** - Use tools and instructions, not prescriptive output requirements
3. **Test Edge Cases** - Always test with unusual inputs
4. **User Feedback** - Listen when users say "shouldn't this be smarter?"
5. **Document Workarounds** - If you add a workaround, document it here immediately

### Code Review Checklist

When reviewing code, check for:
- [ ] Magic strings or hardcoded patterns
- [ ] Prescriptive output requirements ("respond with X")
- [ ] Brittle keyword matching
- [ ] Missing error handling
- [ ] Untested edge cases
- [ ] Missing documentation

---

**Last Updated:** 2026-01-29
**Active Debt Items:** 1
**Resolved Debt Items:** 1
