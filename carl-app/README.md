# CARL Application

Python Lambda functions and application code for CARL (Cloud Automated Risk & Compliance Logic).

## Structure

```
carl-app/
├── src/
│   ├── handlers/           # Lambda function handlers
│   │   ├── slack_router.py
│   │   ├── findings_processor.py
│   │   ├── remediation_executor.py
│   │   └── report_generator.py
│   ├── services/           # Business logic
│   │   ├── bedrock_service.py
│   │   ├── slack_service.py
│   │   ├── findings_service.py
│   │   ├── remediation_service.py
│   │   └── compliance_service.py
│   ├── models/             # Data models
│   │   ├── finding.py
│   │   ├── remediation.py
│   │   └── preference.py
│   └── utils/              # Utilities
│       ├── aws_client.py
│       ├── logger.py
│       └── soc2_mappings.py
├── tests/
│   ├── unit/
│   └── integration/
├── layers/
│   └── common/             # Lambda layer with shared dependencies
├── scripts/
│   ├── build.sh            # Build Lambda packages
│   └── deploy.sh           # Deploy to AWS
└── .github/workflows/
    └── ci.yml              # CI/CD pipeline
```

## Prerequisites

- Python 3.12+
- pip
- AWS CLI configured
- Docker (for Lambda layer building)

## Setup

### 1. Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 3. Run Tests

```bash
pytest tests/
```

### 4. Build Lambda Packages

```bash
./scripts/build.sh
```

## Lambda Functions

### slack_router

Entry point for all Slack interactions:
- Events (app_mention, message)
- Slash commands (/carl)
- Interactive components (buttons, modals)

### findings_processor

Processes security findings from:
- AWS Config
- Security Hub
- GuardDuty
- Inspector
- Macie
- IAM Access Analyzer

### remediation_executor

Executes remediation actions with:
- Pre-action state capture
- Action execution
- Post-action verification
- Rollback capability

### report_generator

Generates compliance reports:
- Executive summaries (PDF)
- DevOps findings (CSV/JSON)
- Auditor evidence packages

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ENVIRONMENT` | Environment name (dev/prod) |
| `FINDINGS_TABLE` | DynamoDB findings table name |
| `PREFERENCES_TABLE` | DynamoDB preferences table name |
| `CONVERSATIONS_TABLE` | DynamoDB conversations table name |
| `EVIDENCE_BUCKET` | S3 bucket for evidence |
| `SLACK_TOKEN_SECRET_ARN` | Secrets Manager ARN for Slack token |
| `SLACK_SIGNING_SECRET_ARN` | Secrets Manager ARN for Slack signing secret |
| `BEDROCK_MODEL_ID` | Bedrock model ID for AI |
| `LOG_LEVEL` | Logging level (DEBUG/INFO/WARNING/ERROR) |

## Code Style

- Black for formatting
- isort for imports
- flake8 for linting
- mypy for type checking

Run all checks:

```bash
make lint
```
