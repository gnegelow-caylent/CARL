"""
Finding data model for CARL.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class FindingSeverity(Enum):
    """Finding severity levels."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFORMATIONAL = "INFORMATIONAL"


class FindingSource(Enum):
    """Finding source services."""
    CONFIG = "CONFIG"
    SECURITY_HUB = "SECURITY_HUB"
    GUARDDUTY = "GUARDDUTY"
    INSPECTOR = "INSPECTOR"
    MACIE = "MACIE"
    ACCESS_ANALYZER = "ACCESS_ANALYZER"
    CARL_SCANNER = "CARL_SCANNER"


class FindingStatus(Enum):
    """Finding status."""
    NEW = "NEW"
    IN_PROGRESS = "IN_PROGRESS"
    REMEDIATED = "REMEDIATED"
    SUPPRESSED = "SUPPRESSED"
    ACCEPTED_RISK = "ACCEPTED_RISK"  # Risk accepted with justification
    IGNORED = "IGNORED"  # Acknowledged but no action needed


@dataclass
class Finding:
    """Normalized finding model."""

    id: str
    source: FindingSource
    severity: FindingSeverity
    title: str
    description: str
    resource_type: str
    resource_id: str
    account_id: str
    region: str
    control_ids: list[str] = field(default_factory=list)
    status: FindingStatus = FindingStatus.NEW
    remediation_steps: str = ""
    remediation_id: str | None = None
    raw_finding: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime | None = None

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Convert to DynamoDB item format."""
        return {
            "pk": f"ACCOUNT#{self.account_id}#FINDING#{self.id}",
            "sk": f"SOURCE#{self.source.value}#TIMESTAMP#{int(self.created_at.timestamp())}",
            "finding_id": self.id,
            "source": self.source.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "account_id": self.account_id,
            "region": self.region,
            "control_ids": self.control_ids,
            "status": self.status.value,
            "remediation_steps": self.remediation_steps,
            "remediation_id": self.remediation_id,
            "timestamp": int(self.created_at.timestamp()),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dynamodb_item(cls, item: dict[str, Any]) -> "Finding":
        """Create Finding from DynamoDB item."""
        return cls(
            id=item.get("finding_id", ""),
            source=FindingSource(item.get("source", "CONFIG")),
            severity=FindingSeverity(item.get("severity", "MEDIUM")),
            title=item.get("title", ""),
            description=item.get("description", ""),
            resource_type=item.get("resource_type", ""),
            resource_id=item.get("resource_id", ""),
            account_id=item.get("account_id", ""),
            region=item.get("region", ""),
            control_ids=item.get("control_ids", []),
            status=FindingStatus(item.get("status", "NEW")),
            remediation_steps=item.get("remediation_steps", ""),
            remediation_id=item.get("remediation_id"),
            created_at=datetime.fromisoformat(item["created_at"]) if item.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(item["updated_at"]) if item.get("updated_at") else None,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "source": self.source.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "account_id": self.account_id,
            "region": self.region,
            "control_ids": self.control_ids,
            "status": self.status.value,
            "remediation_steps": self.remediation_steps,
            "remediation_id": self.remediation_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
