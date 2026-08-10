# Changelog

All notable changes to the CARL MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added (2026-08-10)
- PCI DSS, HIPAA, and NIST CSF control definitions for report generation (9 + 6 + 9 controls)
- CloudTrail multi-region checks (CIS AWS Foundations compliance)
- VPC Flow Logs traffic type validation (ALL vs ACCEPT/REJECT)
- IAM root account MFA check (CRITICAL severity)
- IAM access key rotation checks (90-day threshold)
- Comprehensive scan disclosure showing "X of Y resources scanned"
- CloudTrail trail count stats
- Assessment status tracking document (ASSESSMENT_STATUS.md)

### Changed (2026-08-10)
- Standardized S3 public access block compliance logic between scan.py and evidence.py
- Improved error reporting in evidence collection (shows actual errors vs "storage disabled")
- Enhanced Security Hub/GuardDuty output with limit warnings
- Updated GitHub Actions to latest versions (v4.2.2, v5.3.0, v3.1.2)

### Fixed (2026-08-10)
- S3 compliance logic contradiction (evidence.py now matches scan.py requirements)

### Verified (2026-08-10)
- KMS key rotation checks already implemented and working correctly

---

## [0.2.0] - 2026-08-06

### Fixed - Critical Blockers

#### Dependency Issues
- **Fixed MCP SDK version incompatibility** - Pinned `mcp>=0.9.0,<2.0.0` to prevent breakage with MCP 2.0
  - MCP 2.0 removed decorator-based API that server.py depends on
  - Clean installs now resolve to mcp==1.29.0 (last 1.x release)
  - Server starts successfully on fresh installations
- **Fixed missing botocore CRT dependency** - Changed `botocore>=1.34.0` to `botocore[crt]>=1.34.0`
  - Enables SSO-based AWS credential providers
  - Fixes `MissingDependencyException` errors on AWS CLI SSO login

#### Error Handling
- **Fixed silent error swallowing in evidence collection** (`evidence.py`)
  - Storage failures now show actual errors: "DynamoDB table 'carl-prod-evidence' not found"
  - Previously showed misleading: "Evidence collected but not stored (storage disabled)"
  - Added deployment instructions when infrastructure is missing
- **Fixed silent error swallowing in report generation** (`report.py`)
  - Database query failures now display actual table names and errors
  - Distinguishes between "no evidence collected" vs "infrastructure missing"
  - Added helpful deployment guidance in error messages

### Improved - Assessment Quality

#### Scan Coverage & Transparency
- **Increased resource scan limits** - 10x improvement in coverage
  - IAM users: 10 → 100
  - S3 buckets: 20 → 100
  - Security groups: 20 → 100
  - Security Hub findings: 10 (CRITICAL only) → 100 (all severities, paginated)
  - GuardDuty findings: 10 (severity ≥7) → 100 (all severities, paginated)
- **Added scan statistics and transparency**
  - Shows "Checked X of Y resources" in all scan outputs
  - Displays truncation warnings when limits are reached
  - Example: `*Checked 100 of 247 users ⚠️ **Truncated** - increase scan limit*`
  - Users can now make informed decisions about scan completeness

#### Severity Calibration
- **Fixed security group severity ratings** for internet-facing rules
  - Port 22 (SSH) on 0.0.0.0/0: HIGH (unchanged - correct)
  - Port 3389 (RDP) on 0.0.0.0/0: HIGH (unchanged - correct)
  - Port 80 (HTTP) on 0.0.0.0/0: INFO (was HIGH - **fixed**, normal for web servers)
  - Port 443 (HTTPS) on 0.0.0.0/0: INFO (was HIGH - **fixed**, normal for web servers)
  - Other ports on 0.0.0.0/0: MEDIUM
  - Eliminates false HIGH severity alerts for ALB/CloudFront security groups

#### S3 Security Assessment
- **Added account-level S3 Block Public Access detection**
  - Checks account-level protection before flagging individual buckets
  - Only flags bucket-level issues when account-level protection is missing
  - Prevents false CRITICAL findings when account is protected at higher level
  - Added HIGH severity finding when account-level protection not configured
- **Improved S3 versioning checks**
  - Skips AWS auto-created buckets: `cf-templates-*`, `elasticbeanstalk-*`, `aws-*`
  - Reduces alert fatigue from buckets where versioning is irrelevant

### Improved - Evidence Collection

#### Framework Support
- **Fixed framework 'all' aggregation** (`evidence.py`)
  - Previously: `framework: "all"` silently returned only SOC 2 controls
  - Now: `framework: "all"` aggregates all frameworks (SOC 2 + HIPAA + PCI + NIST)
  - Returns deduplicated list of controls across all frameworks
  - Example: `["CC6.1", "164.312(a)(2)(iv)", "3.4", "PR.DS-1"]`

#### Resource Limits Alignment
- **Aligned evidence collection limits with scan limits** (`evidence.py`)
  - S3 buckets: 10 → 100 (matches scan.py)
  - Security Hub: 20 (MaxResults) → 100 (paginated, matches scan.py)
  - KMS keys: 10 → 100 (matches scan.py)
  - Added pagination for Security Hub findings (same approach as scan.py)
  - Eliminates inconsistency between scan and evidence collection

#### Compliance Controls
- **Added KMS key rotation check** (`evidence.py`)
  - Now calls `get_key_rotation_status()` for each customer-managed key
  - Stores `rotation_enabled` boolean in evidence data
  - Updated compliance logic to require rotation for compliance
  - Properly supports PCI DSS 3.5/3.6 requirements (previously claimed but not checked)
  - Example evidence:
    ```json
    {
      "rotation_enabled": true,
      "compliant": true,
      "controls": ["PCI-3.5", "PCI-3.6", "CC6.7", "PR.DS-1"]
    }
    ```

### Added - Testing & CI

- **Added CI smoke tests** (`tests/test_smoke.py`)
  - `test_server_starts()` - Verifies server creation
  - `test_server_requires_agentcore_arns()` - Validates environment variable requirements
  - `test_all_tools_registered()` - Confirms tool registration mechanism
  - Both Phase 0 bugs would have been caught by these tests
- **Added pytest configuration**
  - Created `requirements-dev.txt` with pytest dependencies
  - Created `pytest.ini` with test discovery settings
  - Run tests: `pytest tests/`

### Technical Details

#### Files Modified (6 files)
- `requirements.txt` - MCP and botocore dependency fixes
- `setup.py` - MCP and botocore dependency fixes
- `src/carl_mcp_server/tools/scan.py` - Truncation fixes, stats tracking, severity calibration, S3 account-level checks, formatting
- `src/carl_mcp_server/tools/evidence.py` - Error messages, limit alignment, framework aggregation, KMS rotation check
- `src/carl_mcp_server/tools/report.py` - Error messages, infrastructure error detection

#### Files Created (3 files)
- `tests/test_smoke.py` - CI smoke tests (3 tests)
- `requirements-dev.txt` - Development dependencies
- `pytest.ini` - Pytest configuration

### Upgrade Notes

**No Breaking Changes** - All changes are backwards compatible improvements.

**Dependency Updates Required**:
```bash
pip install --upgrade -e .
```

**What Users Will Notice**:
1. More resources scanned (up to 100 vs 10-20)
2. Scan completeness visibility ("Checked X of Y")
3. More accurate severity ratings (HTTP/HTTPS on ALB no longer HIGH)
4. Honest error messages (table names, deployment instructions)
5. Framework "all" actually returns all frameworks
6. KMS evidence includes rotation status

**Infrastructure Requirements** - Unchanged:
- Same DynamoDB tables
- Same AgentCore runtimes
- Same IAM permissions

### Documentation

- **Created**: `PHASE_0_1_PROGRESS.md` - Complete implementation tracking (700+ lines)
- **Reference**: Original assessment in `Downloads/MCP_ASSESSMENT_AND_RECOMMENDATIONS.md`
- **Updated**: This CHANGELOG.md

### Metrics

- **Lines of Code Changed**: ~500 lines across 6 files
- **Test Coverage Added**: 3 smoke tests covering critical paths
- **Bugs Fixed**: 11 issues (2 critical, 9 quality/accuracy improvements)
- **Implementation Time**: ~2 hours
- **Assessment Coverage**: Addresses Sections 2 (bugs), 3 (errors), 4 (assessment quality) from original review

---

## [0.1.0] - 2026-07-20

### Added
- Initial MCP server implementation
- 6 tools: scan_environment, collect_evidence, generate_report, ask, architect, remediate_finding
- Integration with AWS Bedrock AgentCore
- Support for SOC 2, HIPAA, PCI DSS, NIST CSF frameworks
- Multi-region scanning capability (code exists, single-region in practice per assessment)

### Known Issues (Addressed in 0.2.0)
- Dependency pinning issues with MCP 2.0
- Missing botocore[crt] dependency
- Silent error swallowing
- Silent resource truncation
- Severity miscalibration for web traffic
- Framework 'all' only returning SOC 2
- No KMS rotation check

---

## Version Number Notes

- **0.1.0** - Initial feature branch implementation
- **0.2.0** - Assessment-driven hardening (this release)
- **0.3.0** - Planned: Config/Security Hub integration
- **1.0.0** - Target: Production-ready release after Phase 2 completion
