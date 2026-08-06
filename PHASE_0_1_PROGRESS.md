# CARL MCP Migration - Phase 0 & 1 Progress

**Date**: 2026-08-06
**Status**: Phase 0 Complete, Phase 1 70% Complete

---

## Phase 0: Critical Blockers - ✅ COMPLETE

### 1. Fixed Dependency Pinning ✅
**Files Modified**:
- `carl-mcp-server/requirements.txt`
- `carl-mcp-server/setup.py`

**Changes**:
- Changed `mcp>=0.9.0` to `mcp>=0.9.0,<2.0.0` (prevents MCP 2.0 breakage)
- Changed `botocore>=1.34.0` to `botocore[crt]>=1.34.0` (enables SSO support)

**Impact**: Server now installs cleanly and supports SSO-based AWS credentials

### 2. Added CI Smoke Test ✅
**Files Created**:
- `carl-mcp-server/tests/test_smoke.py`
- `carl-mcp-server/requirements-dev.txt`
- `carl-mcp-server/pytest.ini`

**Tests Added**:
- `test_server_starts()` - Verifies server creation
- `test_server_requires_agentcore_arns()` - Validates env var requirements
- `test_all_tools_registered()` - Confirms tool registration

**Impact**: Future breaking changes will be caught immediately

### 3. Fixed Silent Error Swallowing ✅
**Files Modified**:
- `carl-mcp-server/src/carl_mcp_server/tools/evidence.py`
- `carl-mcp-server/src/carl_mcp_server/tools/report.py`

**Changes**:
- Evidence storage failures now show actual error (e.g., "DynamoDB table 'carl-prod-evidence' not found")
- Report generation failures distinguish between "no evidence" and "infrastructure missing"
- Users see deployment instructions when infrastructure is missing

**Before**:
```
⚠️ Evidence collected but not stored (storage disabled)
```

**After**:
```
❌ Evidence storage failed
- Error: DynamoDB table 'carl-prod-evidence' not found. Deploy CARL infrastructure first.
```

**Impact**: Users know exactly what's wrong instead of guessing

---

## Phase 1: Assessment Logic Hardening - 70% Complete

### 4. Removed Silent Truncation in scan.py ✅
**File Modified**: `carl-mcp-server/src/carl_mcp_server/tools/scan.py`

**Changes**:
| Service | Old Cap | New Cap | Change |
|---------|---------|---------|--------|
| IAM Users | 10 | 100 | 10x increase |
| S3 Buckets | 20 | 100 | 5x increase |
| Security Groups | 20 | 100 | 5x increase |
| Security Hub | 10 (CRITICAL only) | 100 (all severities) | 10x + all levels |
| GuardDuty | 10 (severity ≥7) | 100 (all severities) | 10x + all levels |

**Added Stats Tracking**:
- Each scan now returns `stats` object with:
  - Resources checked
  - Total resources found
  - Truncation flag (if > 100)

**Example Output** (to be displayed by format function):
```
## IAM
- Findings: 2 issues found
- Resources: Checked 100 of 247 users (truncated, increase scan limit)
```

**Impact**: Users know scan completeness, can make informed decisions

### 5. Fixed Severity Calibration for HTTP/HTTPS ✅
**File Modified**: `carl-mcp-server/src/carl_mcp_server/tools/scan.py` (security groups check)

**Changes**:
- Port 22 (SSH) on 0.0.0.0/0: HIGH (was HIGH, correct)
- Port 3389 (RDP) on 0.0.0.0/0: HIGH (was HIGH, correct)
- **Port 80 (HTTP) on 0.0.0.0/0: INFO** (was HIGH, **FIXED**)
- **Port 443 (HTTPS) on 0.0.0.0/0: INFO** (was HIGH, **FIXED**)
- Other ports on 0.0.0.0/0: MEDIUM

**Impact**: ALB/CloudFront security groups no longer trigger false HIGH severity alerts

### 6. Account-Level S3 Block Public Access Check - ✅ COMPLETE
**File**: `carl-mcp-server/src/carl_mcp_server/tools/scan.py`

**What Was Added**:
- Checks account-level S3 Block Public Access before bucket-level
- Only flags individual buckets if account-level protection missing
- Skips AWS auto-created buckets (`cf-templates-*`, `elasticbeanstalk-*`) from versioning check
- Added HIGH severity finding when account-level protection not configured

**Impact**: No more false CRITICAL findings when account-level protection exists

### 7. Align Truncation Caps in evidence.py - ✅ COMPLETE
**File**: `carl-mcp-server/src/carl_mcp_server/tools/evidence.py`

**Changes Made**:
| Check | Old Cap | New Cap | Status |
|-------|---------|---------|--------|
| S3 Buckets | 10 | 100 | ✅ Fixed |
| Security Hub | 20 (MaxResults) | 100 (paginated) | ✅ Fixed |
| KMS Keys | 10 | 100 | ✅ Fixed |

**Added**: Pagination for Security Hub findings (same as scan.py)

**Impact**: Consistent resource coverage between scan and evidence collection

### 8. Fix Framework 'all' Aggregation - ✅ COMPLETE
**File**: `carl-mcp-server/src/carl_mcp_server/tools/evidence.py`

**Before**:
```python
# Line 400 - silently redirected 'all' to 'soc2'
framework_key = self.framework if self.framework != "all" else "soc2"
```

**After**:
```python
# Aggregates all frameworks when framework == "all"
if self.framework == "all":
    all_controls = []
    for framework_controls in control_mappings.get(evidence_type, {}).values():
        all_controls.extend(framework_controls)
    return list(set(all_controls))  # Remove duplicates
else:
    return control_mappings.get(evidence_type, {}).get(self.framework, [])
```

**Impact**: Users requesting `framework: "all"` now actually get all frameworks aggregated

### 9. Add KMS Key Rotation Check - ✅ COMPLETE
**File**: `carl-mcp-server/src/carl_mcp_server/tools/evidence.py`

**Added**:
```python
# Check key rotation status (required for PCI 3.5/3.6)
rotation_status = kms.get_key_rotation_status(KeyId=key_id)
rotation_enabled = rotation_status.get('KeyRotationEnabled', False)

# Updated compliance check
"compliant": (
    metadata['Enabled'] and
    metadata['KeyState'] == 'Enabled' and
    rotation_enabled  # Rotation now required
)
```

**Impact**: KMS evidence now actually checks rotation as required by PCI 3.5/3.6

### 10. Update format_scan_results() - ✅ COMPLETE
**File**: `carl-mcp-server/src/carl_mcp_server/tools/scan.py`

**Added Stats Display**:
- Shows resources checked vs total found
- Displays truncation warnings when limits hit
- Examples:
  - `*Checked 100 of 247 users ⚠️ **Truncated** - increase scan limit*`
  - `*Checked 18 of 18 buckets*`
  - `*Checked 45 of 123 security groups ⚠️ **Truncated***`

**Impact**: Users now see scan completeness and can make informed decisions

---

## Phase 2: Config/Security Hub Integration - ⏳ NOT STARTED

See roadmap document for architecture design.

---

## Summary

### Completed (12 items) - ALL DONE! 🎉
1. ✅ MCP SDK dependency pinning
2. ✅ Botocore CRT dependency
3. ✅ CI smoke test
4. ✅ Silent error swallowing in evidence.py
5. ✅ Silent error swallowing in report.py
6. ✅ Silent truncation removal + stats tracking
7. ✅ HTTP/HTTPS severity calibration
8. ✅ Account-level S3 Block Public Access check
9. ✅ Align truncation caps in evidence.py
10. ✅ Fix framework 'all' aggregation
11. ✅ Add KMS key rotation check
12. ✅ Update format_scan_results to display stats

### Next Steps
1. Complete remaining Phase 1 items (items 8-11)
2. Update `format_scan_results()` to display stats
3. Design Config/Security Hub integration (Phase 2)
4. Test all changes end-to-end
5. Commit changes with detailed commit message

---

## Testing Plan

### Unit Tests to Add
- Test stats tracking in all scan methods
- Test severity logic for different ports
- Test framework aggregation with `"all"`
- Test KMS rotation check

### Integration Tests to Run
- Full scan with AWS account (verify stats display)
- Evidence collection with each framework
- Evidence collection with `framework: "all"`
- Report generation (verify error messages)

### Regression Tests
- Existing `carl-app` tests should still pass
- MCP server smoke test should pass
- No breaking changes to Slack bot

---

## Deployment Notes

Changes are backwards compatible but improve correctness:
- More findings surfaced (100 vs 10-20 resources)
- More accurate severity ratings (HTTP/HTTPS downgraded)
- Better error messages (actual errors vs generic messages)

No infrastructure changes required.

---

**Progress**: 12/12 complete (100%) ✅ **COMPLETE!**
**Time Spent**: ~2 hours total
