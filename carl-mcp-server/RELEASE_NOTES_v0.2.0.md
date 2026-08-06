# CARL MCP Server v0.2.0 Release Notes

**Release Date**: August 6, 2026
**Focus**: Quality & Reliability Hardening

This release fixes critical installation issues and significantly improves scan accuracy based on a comprehensive hands-on assessment of the MCP server against a live AWS account.

---

## 🚨 Critical Fixes (Install Now!)

### 1. Clean Installation Works Again ✅

**Problem**: Fresh installations failed with `AttributeError: 'Server' object has no attribute 'list_tools'`

**Fixed**:
- Pinned MCP SDK to `mcp>=0.9.0,<2.0.0` (MCP 2.0 broke compatibility)
- Added `botocore[crt]` dependency for SSO-based AWS credentials
- Server now starts successfully on clean install

**Action Required**: Upgrade dependencies
```bash
cd carl-mcp-server
pip install --upgrade -e .
```

### 2. SSO Credentials Now Work ✅

**Problem**: `MissingDependencyException: ... requires botocore[crt]` when using AWS SSO

**Fixed**: Added `botocore[crt]` extra to enable CRT-based credential providers

**Impact**: SSO login (`aws sso login`) now works with the MCP server

---

## 🎯 Major Improvements

### Scan Coverage: 10x More Resources Checked

**Before**: Only 10-20 resources checked per service
**After**: Up to 100 resources checked, with pagination for unlimited findings

| Resource Type | Old Limit | New Limit | Improvement |
|--------------|-----------|-----------|-------------|
| IAM Users | 10 | 100 | 10x |
| S3 Buckets | 20 | 100 | 5x |
| Security Groups | 20 | 100 | 5x |
| Security Hub Findings | 10 (CRITICAL only) | 100 (all severities) | 10x + all severities |
| GuardDuty Findings | 10 (severity ≥7) | 100 (all severities) | 10x + all severities |

**New**: Scans now show completeness
```
## IAM
*Checked 100 of 247 users ⚠️ **Truncated** - increase scan limit*
Found 12 issues:
...
```

You'll now know when you're seeing partial results and can adjust limits if needed.

### Accurate Severity Ratings

**Fixed False Alarms**: Port 80/443 open to internet no longer flagged as HIGH

**Before**:
```
🟠 HIGH: Security Group: sg-abc123
   Port 443 open to internet (0.0.0.0/0)
```

**After**:
```
ℹ️ INFO: Security Group: sg-abc123
   Port 443 open to internet (0.0.0.0/0)
```

**Why This Matters**: ALB and CloudFront security groups legitimately need ports 80/443 open. No more false HIGH severity alerts for normal web infrastructure.

**Still HIGH**: SSH (22) and RDP (3389) open to internet - correctly flagged as risky

### Smarter S3 Security Checks

**Added**: Account-level S3 Block Public Access detection

**How It Works**:
1. First checks if your AWS account has Block Public Access enabled (the 2019+ best practice)
2. If yes → individual buckets inherit protection, no CRITICAL alerts
3. If no → checks each bucket individually

**Before**: 50 buckets flagged CRITICAL even though account-level protection was enabled

**After**: One HIGH finding for missing account-level protection, no false bucket alerts

**Also Fixed**: Skips versioning check for AWS auto-created buckets (`cf-templates-*`, `elasticbeanstalk-*`) that don't need it

### Framework Support Actually Works

**Fixed**: `framework: "all"` now returns ALL frameworks

**Before**:
```bash
/carl evidence collect all
# Returns only SOC 2 controls: ["CC6.1", "CC6.7"]
```

**After**:
```bash
/carl evidence collect all
# Returns aggregated controls from all frameworks:
# ["CC6.1", "CC6.7", "164.312(a)(2)(iv)", "3.4", "3.5", "PR.DS-1"]
```

**Supported Frameworks**: SOC 2, HIPAA, PCI DSS, NIST CSF

### KMS Evidence Now Complete

**Added**: Key rotation status check (required for PCI DSS 3.5/3.6)

**Before**:
- Evidence claimed to support PCI 3.5/3.6
- Never actually checked `KeyRotationEnabled`
- Keys without rotation marked compliant ❌

**After**:
- Calls `get_key_rotation_status()` for each key
- Stores rotation status in evidence
- Keys without rotation marked non-compliant ✅

---

## 🛡️ Better Error Messages

### No More Silent Failures

**Before**:
```
⚠️ Evidence collected but not stored (storage disabled)
```

**After**:
```
❌ Evidence storage failed
- Error: DynamoDB table 'carl-prod-evidence' not found. Deploy CARL infrastructure first.

To enable storage, deploy CARL infrastructure:
- DynamoDB table: Set CARL_DYNAMODB_EVIDENCE_TABLE
- S3 bucket (optional): Set CARL_S3_EVIDENCE_BUCKET
```

**What Changed**:
- Actual error names shown (e.g., "ResourceNotFoundException")
- Table names displayed so you know what's missing
- Deployment instructions provided
- Clear distinction between "disabled by choice" vs "infrastructure error"

**Applies To**:
- Evidence collection (`evidence.py`)
- Report generation (`report.py`)

---

## 🧪 Testing & Quality

### New CI Smoke Tests

**Added**: 3 automated tests that catch common issues

```python
def test_server_starts()
    # Would have caught MCP 2.0 incompatibility

def test_server_requires_agentcore_arns()
    # Validates environment variable requirements

def test_all_tools_registered()
    # Confirms all 6 tools load correctly
```

**Run Tests**:
```bash
cd carl-mcp-server
pip install -r requirements-dev.txt
pytest tests/
```

**Impact**: Both critical bugs in this release would have been caught by CI

---

## 📊 What This Means For You

### If You're Using the MCP Server Today

**Immediate Benefits**:
1. **More Complete Scans** - See up to 100 resources per service instead of 10-20
2. **Better Severity Accuracy** - No more false HIGH alerts for web infrastructure
3. **Framework Flexibility** - "All" actually means all frameworks
4. **Honest Errors** - Know exactly what's missing when things fail
5. **KMS Compliance** - Rotation checks now work for PCI audits

**Action Required**:
```bash
cd carl-mcp-server
pip install --upgrade -e .
# Restart Claude Desktop
```

### If You're Deploying Fresh

**Good News**: Clean installation now works!

Follow the standard setup:
1. Deploy CARL infrastructure (terraform)
2. Install MCP server (pip)
3. Configure Claude Desktop
4. Restart

See [DEPLOYMENT.md](./DEPLOYMENT.md) for complete guide.

---

## 🔍 Technical Details

### Files Modified

**Core Logic** (3 files):
- `src/carl_mcp_server/tools/scan.py` - Scan coverage, stats, severity, S3 checks
- `src/carl_mcp_server/tools/evidence.py` - Framework aggregation, KMS rotation, limits
- `src/carl_mcp_server/tools/report.py` - Error message improvements

**Dependencies** (2 files):
- `requirements.txt` - MCP and botocore fixes
- `setup.py` - MCP and botocore fixes

**Testing** (3 new files):
- `tests/test_smoke.py` - CI smoke tests
- `requirements-dev.txt` - Test dependencies
- `pytest.ini` - Test configuration

### Backwards Compatibility

✅ **No Breaking Changes** - All improvements are backwards compatible

**Upgrade Path**:
```bash
pip install --upgrade -e .
```

**Infrastructure**: No changes required
- Same DynamoDB tables
- Same AgentCore runtimes
- Same IAM permissions

---

## 📚 Documentation

**New**:
- `CHANGELOG.md` - Detailed change log
- `RELEASE_NOTES_v0.2.0.md` - This document
- `PHASE_0_1_PROGRESS.md` - Complete implementation tracking

**Reference**:
- Original assessment: `Downloads/MCP_ASSESSMENT_AND_RECOMMENDATIONS.md` (380 lines)
- Addresses Sections 2, 3, 4 from assessment

---

## 🎯 What's Next?

### Phase 2: Config/Security Hub Integration (Planned)

The assessment recommended integrating with AWS Config and Security Hub for:
- AWS-maintained check coverage (hundreds vs dozens)
- Continuous evaluation (not just point-in-time)
- Proper query patterns (not DynamoDB Scan)
- Auditor-recognized compliance posture

See `Downloads/MCP_ASSESSMENT_AND_RECOMMENDATIONS.md` Section 8 for full design.

### Phase 3: Multi-Region & Scale (Planned)

- Multi-region scanning
- AWS Organizations support
- Container/serverless coverage (ECS, EKS, Lambda)

---

## 🙏 Credits

Based on comprehensive assessment and recommendations by Claude Opus 4.5 on August 3, 2026.

Assessment tested against live AWS account 331871780786 and identified:
- 2 critical installation bugs (both fixed)
- 9 quality/accuracy improvements (all addressed)
- Architecture recommendations for Phase 2

See full assessment in `Downloads/MCP_ASSESSMENT_AND_RECOMMENDATIONS.md`.

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/gnegelow-caylent/CARL/issues)
- **Documentation**: [README.md](./README.md)
- **Deployment Guide**: [DEPLOYMENT.md](./DEPLOYMENT.md)

---

## Version History

- **v0.2.0** (2026-08-06) - Quality & reliability hardening (this release)
- **v0.1.0** (2026-07-20) - Initial MCP server implementation
- **v1.0.0** (planned) - Production-ready release post-Phase 2
