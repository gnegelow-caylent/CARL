"""
Framework Loader for CARL.

Loads and parses compliance framework definitions from YAML files.
These frameworks drive both Foundation (single account) and Account Factory (multi-account).
"""

import os
import yaml
from dataclasses import dataclass, field
from typing import Any, Optional
from pathlib import Path

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ServiceConfig:
    """Configuration for a required AWS service."""
    service: str
    config: dict[str, Any]
    controls: list[str]
    why_required: str
    audit_evidence: list[str]
    validation_checks: list[dict[str, str]] = field(default_factory=list)


@dataclass
class FrameworkQuestion:
    """Question to ask user during framework setup."""
    id: str
    question: str
    description: str
    input_type: str
    options: list[dict[str, Any]] = field(default_factory=list)
    default: Any = None
    required: bool = True
    depends_on: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, str] = field(default_factory=dict)
    min: Optional[int] = None
    max: Optional[int] = None


@dataclass
class OrganizationalUnit:
    """Organizational Unit structure (for Account Factory)."""
    ou_name: str
    purpose: str
    accounts: list[dict[str, str]] = field(default_factory=list)


@dataclass
class ServiceControlPolicy:
    """Service Control Policy definition (for Account Factory)."""
    name: str
    description: str
    target_ous: list[str]
    statement: dict[str, Any] | list[dict[str, Any]]


@dataclass
class ComplianceFramework:
    """Complete compliance framework definition."""

    # Framework metadata
    id: str
    name: str
    version: str
    description: str

    # Use cases and context
    typical_use_cases: list[str] = field(default_factory=list)
    audit_frequency: str = ""
    audit_cost_estimate: str = ""

    # Required AWS services (organized by category)
    required_services: dict[str, list[ServiceConfig]] = field(default_factory=dict)

    # Questions to ask user
    questions: list[FrameworkQuestion] = field(default_factory=list)

    # Organizational structure (for Account Factory)
    organizational_structure: list[OrganizationalUnit] = field(default_factory=list)

    # Service Control Policies (for Account Factory)
    scps: list[ServiceControlPolicy] = field(default_factory=list)

    # Cost estimates
    estimated_monthly_costs: dict[str, Any] = field(default_factory=dict)

    # Evidence collection schedule
    evidence_collection: dict[str, list[str]] = field(default_factory=dict)

    def get_all_required_services(self) -> list[ServiceConfig]:
        """Get flat list of all required services across all categories."""
        services = []
        for category_services in self.required_services.values():
            services.extend(category_services)
        return services

    def get_service_by_name(self, service_name: str) -> Optional[ServiceConfig]:
        """Find a service config by service name."""
        for service in self.get_all_required_services():
            if service.service == service_name:
                return service
        return None

    def get_services_by_control(self, control_id: str) -> list[ServiceConfig]:
        """Get all services that satisfy a specific control."""
        return [
            service for service in self.get_all_required_services()
            if control_id in service.controls
        ]

    def get_question_by_id(self, question_id: str) -> Optional[FrameworkQuestion]:
        """Find a question by ID."""
        for question in self.questions:
            if question.id == question_id:
                return question
        return None


class FrameworkLoader:
    """
    Loads compliance framework definitions from YAML files.

    Frameworks are stored in: carl-app/compliance-frameworks/{framework_id}.yaml
    """

    def __init__(self, frameworks_dir: str = None):
        """Initialize the framework loader."""
        if frameworks_dir is None:
            # In Lambda: /var/task/services/framework_loader.py
            # Need: /var/task/compliance-frameworks/
            # So go up 2 levels (services → task), not 3
            project_root = Path(__file__).parent.parent
            frameworks_dir = project_root / "compliance-frameworks"

        self.frameworks_dir = Path(frameworks_dir)
        logger.info(f"Framework loader initialized with directory: {self.frameworks_dir}")

    def load(self, framework_id: str) -> ComplianceFramework:
        """
        Load a compliance framework by ID.

        Args:
            framework_id: Framework identifier (e.g., "soc2", "hipaa", "pci-dss")

        Returns:
            ComplianceFramework object

        Raises:
            FileNotFoundError: If framework YAML doesn't exist
            ValueError: If YAML is malformed
        """
        yaml_path = self.frameworks_dir / f"{framework_id}.yaml"

        if not yaml_path.exists():
            raise FileNotFoundError(
                f"Framework '{framework_id}' not found at {yaml_path}. "
                f"Available frameworks: {self.list_available_frameworks()}"
            )

        logger.info(f"Loading framework: {framework_id} from {yaml_path}")

        try:
            with open(yaml_path, 'r') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse framework YAML: {e}")

        if not data or 'framework' not in data:
            raise ValueError(f"Invalid framework YAML structure in {yaml_path}")

        framework_data = data['framework']

        # Parse required services (organized by category)
        required_services = {}
        for category, services_list in framework_data.get('required_services', {}).items():
            parsed_services = []
            for service_data in services_list:
                service_config = ServiceConfig(
                    service=service_data['service'],
                    config=service_data['config'],
                    controls=service_data['controls'],
                    why_required=service_data['why_required'],
                    audit_evidence=service_data['audit_evidence'],
                    validation_checks=service_data.get('validation_checks', [])
                )
                parsed_services.append(service_config)
            required_services[category] = parsed_services

        # Parse questions
        questions = []
        for q_data in framework_data.get('questions', []):
            question = FrameworkQuestion(
                id=q_data['id'],
                question=q_data['question'],
                description=q_data['description'],
                input_type=q_data['input_type'],
                options=q_data.get('options', []),
                default=q_data.get('default'),
                required=q_data.get('required', True),
                depends_on=q_data.get('depends_on', {}),
                validation=q_data.get('validation', {}),
                min=q_data.get('min'),
                max=q_data.get('max')
            )
            questions.append(question)

        # Parse organizational structure
        org_structure = []
        for ou_data in framework_data.get('organizational_structure', []):
            ou = OrganizationalUnit(
                ou_name=ou_data['ou_name'],
                purpose=ou_data['purpose'],
                accounts=ou_data.get('accounts', [])
            )
            org_structure.append(ou)

        # Parse SCPs
        scps = []
        for scp_data in framework_data.get('scps', []):
            scp = ServiceControlPolicy(
                name=scp_data['name'],
                description=scp_data['description'],
                target_ous=scp_data['target_ous'],
                statement=scp_data['statement']
            )
            scps.append(scp)

        # Create framework object
        framework = ComplianceFramework(
            id=framework_data['id'],
            name=framework_data['name'],
            version=framework_data['version'],
            description=framework_data['description'],
            typical_use_cases=framework_data.get('typical_use_cases', []),
            audit_frequency=framework_data.get('audit_frequency', ''),
            audit_cost_estimate=framework_data.get('audit_cost_estimate', ''),
            required_services=required_services,
            questions=questions,
            organizational_structure=org_structure,
            scps=scps,
            estimated_monthly_costs=framework_data.get('estimated_monthly_costs', {}),
            evidence_collection=framework_data.get('evidence_collection', {})
        )

        logger.info(
            f"Loaded framework '{framework.name}' with "
            f"{len(framework.get_all_required_services())} required services, "
            f"{len(framework.questions)} questions"
        )

        return framework

    def list_available_frameworks(self) -> list[str]:
        """List all available framework IDs."""
        if not self.frameworks_dir.exists():
            return []

        frameworks = []
        for yaml_file in self.frameworks_dir.glob("*.yaml"):
            framework_id = yaml_file.stem
            frameworks.append(framework_id)

        return sorted(frameworks)

    def get_framework_metadata(self, framework_id: str) -> dict[str, str]:
        """
        Get basic metadata about a framework without loading full definition.

        Useful for showing framework options to user before loading.
        """
        yaml_path = self.frameworks_dir / f"{framework_id}.yaml"

        if not yaml_path.exists():
            return {}

        try:
            with open(yaml_path, 'r') as f:
                data = yaml.safe_load(f)

            framework_data = data.get('framework', {})
            return {
                'id': framework_data.get('id', framework_id),
                'name': framework_data.get('name', ''),
                'version': framework_data.get('version', ''),
                'description': framework_data.get('description', ''),
                'typical_use_cases': framework_data.get('typical_use_cases', [])
            }
        except Exception as e:
            logger.warning(f"Failed to load metadata for {framework_id}: {e}")
            return {}


# Singleton instance
_framework_loader: Optional[FrameworkLoader] = None


def get_framework_loader() -> FrameworkLoader:
    """Get or create the global framework loader instance."""
    global _framework_loader
    if _framework_loader is None:
        _framework_loader = FrameworkLoader()
    return _framework_loader
