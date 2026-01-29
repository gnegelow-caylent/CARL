# Advisory Agent - Intelligent Q&A with Environment Awareness

**Status:** ⚙️ Code Complete | ⚙️ Requires AWS Bedrock Agent Configuration

The Advisory Agent provides intelligent question-answering that factors in YOUR AWS environment and SOC 2 compliance requirements.

---

## What It Does

Answers complex questions by understanding your actual AWS environment:

```
/carl ask How do I stand up a web server?
```

The agent autonomously:
1. **Understands the question** - Analyzes intent and determines what info is needed
2. **Scans your environment** - Checks YOUR VPCs, subnets, security groups, load balancers
3. **Applies compliance knowledge** - Factors in SOC 2 requirements for web servers
4. **Provides tailored recommendations** - Based on what YOU have, not generic advice
5. **Asks clarifying questions** - If more information is needed
6. **Hands off to Architect** - If you want infrastructure code generated

**This is NOT generic ChatGPT** - it knows YOUR environment and YOUR compliance needs.

---

## Example Interactions

### Example 1: Infrastructure Question

**Question:** "How do I stand up a web server?"

**Without Advisory Agent (broken):**
```
Generic answer about EC2 instances and security groups.
Could get this from ChatGPT.
```

**With Advisory Agent:**
```
💬 CARL Advisory Agent

I scanned your AWS environment and found:
• You have VPC vpc-abc123 in us-east-1
• 3 public subnets across availability zones
• No Application Load Balancers currently deployed
• 2 security groups with HTTP/HTTPS rules

For a SOC 2-compliant web server deployment:

*Recommended Approach:*
1. Deploy EC2 instances in your existing VPC (vpc-abc123)
2. Use Auto Scaling Group across your 3 public subnets for HA
3. Add Application Load Balancer for traffic distribution
4. Configure security group sg-existing123 with:
   - Inbound: Port 443 (HTTPS) from 0.0.0.0/0
   - Inbound: Port 80 (HTTP) redirect to 443
   - Outbound: All traffic

*SOC 2 Requirements Met:*
• CC6.7 (Encryption in Transit) - Force HTTPS, ACM certificate on ALB
• CC7.2 (Monitoring) - Enable ALB access logs, CloudWatch alarms
• CC6.1 (Access Controls) - Security groups, no SSH from internet
• A1.2 (Availability) - Multi-AZ with Auto Scaling

*Want me to generate the Terraform code?*
Reply "yes" and I'll hand off to the Architect Agent to build this.

🔍 Agent actions: 3 steps
• Scanned VPC and subnet configuration
• Analyzed existing security groups
• Checked load balancer setup
```

### Example 2: Compliance Question

**Question:** "Do we have MFA enabled?"

**With Advisory Agent:**
```
💬 CARL Advisory Agent

I just scanned your IAM users:

*MFA Status: 2 of 4 users have MFA enabled*

✅ Users with MFA:
• admin@company.com (Virtual MFA device)
• security@company.com (Hardware token)

❌ Users without MFA:
• john@company.com
• jane@company.com

*SOC 2 Impact:*
This violates CC6.1 (Logical Access Controls).
Your auditor will flag this as HIGH priority.

*Next Steps:*
1. Enable MFA for john@company.com and jane@company.com
2. AWS Console → IAM → Users → Select user → Security credentials → Assign MFA
3. Or run: `aws iam enable-mfa-device --user-name john@company.com ...`

Want me to create Jira tickets for these 2 users?
```

### Example 3: Architecture Question

**Question:** "What's the best way to deploy a database?"

**With Advisory Agent (asks clarifying questions):**
```
💬 CARL Advisory Agent

I need more information to give you a tailored recommendation:

1. What type of data? (Relational, NoSQL, Time-series)
2. Expected load? (Read-heavy, Write-heavy, Balanced)
3. Availability needs? (Single-AZ OK, Multi-AZ required)
4. Size estimate? (< 100GB, 100GB-1TB, > 1TB)

Based on your answer, I'll scan your current setup and recommend the best approach for YOUR environment.

*Your current environment:*
• VPC: vpc-abc123 with private subnets
• No databases currently deployed
• Backup plan configured in us-east-1
```

---

## Configuration (Required Before Use)

The Advisory Agent uses **AWS Bedrock Agents** for autonomous multi-step reasoning.

### Step 1: Create Bedrock Agent

**Via AWS Console:**

1. Go to **AWS Bedrock** → **Agents**
2. Click **Create Agent**
3. Configure:
   - **Name:** `carl-advisory-agent`
   - **Description:** `Intelligent Q&A with environment awareness and compliance knowledge`
   - **Model:** Claude 3.5 Sonnet
   - **IAM Role:** Create new or use existing (needs Lambda invoke permissions)

4. Add **Agent Instructions:**
   ```
   You are an advisory agent for AWS infrastructure and SOC 2 compliance.

   Your goal is to answer user questions by:
   1. Understanding the question and determining intent
   2. Scanning the user's ACTUAL AWS environment (VPCs, S3, EC2, IAM, etc.)
   3. Providing recommendations based on what THEY HAVE, not generic advice
   4. Factoring in SOC 2 compliance requirements
   5. Asking clarifying questions when needed
   6. Handing off to Architect Agent for code generation if requested

   IMPORTANT PRINCIPLES:
   - Always scan the environment first before answering
   - Provide specific recommendations with resource IDs, names, ARNs
   - Map all recommendations to SOC 2 controls
   - Ask clarifying questions if the user's intent is unclear
   - Be concise but complete - no generic advice

   NEVER make changes to AWS - only READ and RECOMMEND.
   ```

5. Click **Create**

### Step 2: Add Action Groups (Tools)

Add action group for agent tools:

1. Click **Add Action Group**
2. Configure:
   - **Name:** `advisory-tools`
   - **Description:** `Tools for scanning environment and providing recommendations`
   - **Action group type:** Define with function details
   - **Lambda function:** Select or create Lambda for tool execution

3. Add Functions:

**scan_environment:**
```json
{
  "name": "scan_environment",
  "description": "Scan specific AWS resources (VPC, EC2, S3, IAM, etc.) based on question context",
  "parameters": {
    "resource_types": {
      "type": "array",
      "description": "List of AWS resource types to scan",
      "required": true
    }
  }
}
```

**get_compliance_requirements:**
```json
{
  "name": "get_compliance_requirements",
  "description": "Get SOC 2 compliance requirements for a resource type or scenario",
  "parameters": {
    "resource_type": {
      "type": "string",
      "description": "AWS resource type or scenario"
    }
  }
}
```

**analyze_architecture:**
```json
{
  "name": "analyze_architecture",
  "description": "Analyze current architecture and identify gaps or opportunities",
  "parameters": {
    "resources": {
      "type": "object",
      "description": "Resources from scan_environment"
    },
    "intent": {
      "type": "string",
      "description": "What the user wants to achieve"
    }
  }
}
```

**get_best_practices:**
```json
{
  "name": "get_best_practices",
  "description": "Get AWS best practices for a scenario with compliance context",
  "parameters": {
    "scenario": {
      "type": "string",
      "description": "What the user is trying to do"
    }
  }
}
```

**check_existing_resources:**
```json
{
  "name": "check_existing_resources",
  "description": "Check if specific resources exist in the environment",
  "parameters": {
    "resource_type": {
      "type": "string",
      "description": "Type of resource to check"
    }
  }
}
```

**ask_clarification:**
```json
{
  "name": "ask_clarification",
  "description": "Ask the user a clarifying question when more information is needed",
  "parameters": {
    "question": {
      "type": "string",
      "description": "Question to ask"
    },
    "options": {
      "type": "array",
      "description": "Optional multiple choice options"
    }
  }
}
```

**handoff_to_architect:**
```json
{
  "name": "handoff_to_architect",
  "description": "Hand off to Architect Agent for infrastructure code generation",
  "parameters": {
    "requirements": {
      "type": "object",
      "description": "Gathered requirements and context"
    }
  }
}
```

### Step 3: Create Lambda Function for Tools

Create Lambda function `carl-advisory-tools` with handler from `advisory_agent.py`:

```python
from services.advisory_agent import advisory_agent_tool_handler

def lambda_handler(event, context):
    return advisory_agent_tool_handler(event, context)
```

### Step 4: Configure Environment Variable

Set environment variable in CARL Lambda:

```bash
ADVISORY_AGENT_ID=<your-bedrock-agent-id>
```

### Step 5: Prepare and Test

1. Click **Prepare** to create agent version
2. Click **Test** in console to verify agent works
3. Deploy CARL Lambda with new environment variable

---

## How It Works

### Agent Flow

```
User: "How do I stand up a web server?"
  ↓
Advisory Agent analyzes question
  ↓
Agent decides: "Need to scan VPCs, subnets, security groups, load balancers"
  ↓
Agent calls scan_environment(resource_types=['vpc', 'ec2', 'elb'])
  ↓
Agent calls get_compliance_requirements(scenario='web_server')
  ↓
Agent analyzes with SOC 2 knowledge
  ↓
Agent synthesizes recommendation based on YOUR environment
  ↓
Response: "I see you have VPC vpc-123 with 3 public subnets..."
```

### Agent vs. Simple AI

**Simple AI (old /carl ask):**
- One AI call with all data
- No reasoning or planning
- Can't use tools
- Returns generic advice

**Advisory Agent (new /carl ask):**
- Multi-step reasoning
- Calls tools as needed
- Scans only what's relevant
- Tailored to YOUR environment
- Asks follow-up questions
- Hands off to other agents

---

## Architecture

```
┌─────────────────────────────────────────┐
│         CARL Advisory Agent             │
├─────────────────────────────────────────┤
│  Autonomous Q&A with:                   │
│  - Environment awareness                │
│  - Compliance knowledge                 │
│  - Multi-step reasoning                 │
└─────────────────────────────────────────┘
              │
              │ invokes
              ▼
┌─────────────────────────────────────────┐
│      AWS Bedrock Agent Runtime          │
│  - Plans steps autonomously             │
│  - Calls tools as needed                │
│  - Reasons about results                │
└─────────────────────────────────────────┘
              │
              │ calls tools via Lambda
              ▼
┌─────────────────────────────────────────┐
│       Advisory Agent Tools              │
│  (Lambda: carl-advisory-tools)          │
├─────────────────────────────────────────┤
│  • scan_environment                     │
│  • get_compliance_requirements          │
│  • analyze_architecture                 │
│  • get_best_practices                   │
│  • check_existing_resources             │
│  • ask_clarification                    │
│  • handoff_to_architect                 │
└─────────────────────────────────────────┘
              │
              │ reads AWS APIs
              ▼
┌─────────────────────────────────────────┐
│         Your AWS Environment            │
│  • VPCs, Subnets, Security Groups       │
│  • EC2, RDS, S3, IAM                    │
│  • CloudTrail, CloudWatch, Config       │
│  (READ-ONLY - Never writes)             │
└─────────────────────────────────────────┘
```

---

## Cost

**Per Question:**
- Agent invocation: ~$0.002
- Tool calls (2-4 avg): ~$0.001
- **Total: ~$0.003 per question**

**Monthly (500 questions):**
- ~$1.50/month

**Much cheaper than:**
- Engineer time: 5 min @ $100/hr = $8.33 per question
- **ROI: 2,777x**

---

## Design Principles

The Advisory Agent follows CARL's core design principles:

**1. Environment-First ✅**
- Scans YOUR AWS environment before answering
- Uses actual resource names, IDs, and configurations
- Could NOT get this from ChatGPT

**2. Compliance-Native ✅**
- Maps recommendations to SOC 2 controls
- Explains audit impact
- Provides compliance-ready guidance
- Could NOT get this from AWS Config

**Both principles = CARL's unique value**

---

## Troubleshooting

**Error: "Advisory Agent ID not configured"**
- Set `ADVISORY_AGENT_ID` environment variable in Lambda
- Get agent ID from AWS Bedrock console

**Error: "Invalid agent alias"**
- Ensure agent is prepared (version created)
- Use alias name "PROD" or get alias ID from console

**Agent returns generic advice:**
- Agent instructions may not emphasize environment scanning
- Update instructions to scan first, answer second

**Agent is slow (> 30 seconds):**
- Agent is doing multi-step reasoning (normal)
- Ensure async processing is enabled in /carl ask

---

## Next Steps

1. **Configure the Agent** - Follow setup steps above
2. **Test in Console** - Use Bedrock Agent test interface
3. **Deploy to CARL** - Set environment variable and deploy
4. **Try it out** - `/carl ask How do I stand up a web server?`

The Advisory Agent makes CARL truly intelligent - not just a scanner, but a knowledgeable advisor that understands YOUR environment and YOUR compliance needs.
