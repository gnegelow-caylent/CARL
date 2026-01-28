"""
Cost Estimator Service for CARL.

Provides cost estimates for AWS infrastructure components.
"""

from dataclasses import dataclass
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CostEstimate:
    """Represents a cost estimate for a component."""
    component: str
    monthly_min: float
    monthly_max: float
    assumptions: list[str]
    optimization_tips: list[str]


@dataclass
class TotalCostEstimate:
    """Total cost estimate for an architecture."""
    components: list[CostEstimate]
    monthly_min: float
    monthly_max: float
    annual_min: float
    annual_max: float
    notes: list[str]


class CostEstimator:
    """Service for estimating AWS infrastructure costs."""

    # Pricing data (us-east-1, approximate)
    PRICING = {
        # Networking
        "nat_gateway": {
            "hourly": 0.045,
            "per_gb": 0.045,
            "monthly_base": 32.40,  # 720 hours
        },
        "network_firewall": {
            "endpoint_hourly": 0.395,
            "per_gb": 0.065,
            "monthly_base": 284.40,  # per endpoint
        },
        "waf": {
            "web_acl": 5.00,
            "per_rule": 1.00,
            "per_million_requests": 0.60,
        },
        "vpc_endpoint": {
            "hourly": 0.01,
            "per_gb": 0.01,
            "monthly_base": 7.20,
        },
        "transit_gateway": {
            "hourly": 0.05,
            "per_gb": 0.02,
            "monthly_base": 36.00,
        },

        # Compute
        "ec2": {
            "t3.micro": 7.59,
            "t3.small": 15.18,
            "t3.medium": 30.37,
            "t3.large": 60.74,
            "m5.large": 70.08,
            "m5.xlarge": 140.16,
        },
        "fargate": {
            "vcpu_hour": 0.04048,
            "gb_hour": 0.004445,
        },
        "eks": {
            "cluster_hourly": 0.10,
            "monthly_base": 72.00,  # control plane
        },
        "alb": {
            "hourly": 0.0225,
            "lcu_hour": 0.008,
            "monthly_base": 16.20,
        },

        # Database
        "rds": {
            "db.t3.micro": 12.41,
            "db.t3.small": 24.82,
            "db.t3.medium": 49.64,
            "db.r5.large": 146.00,
            "multi_az_multiplier": 2.0,
            "storage_per_gb": 0.115,
        },
        "aurora": {
            "acu_hour": 0.12,  # Serverless v2
            "storage_per_gb": 0.10,
            "io_per_million": 0.20,
        },
        "dynamodb": {
            "wcu": 0.00065,  # per hour
            "rcu": 0.00013,  # per hour
            "storage_per_gb": 0.25,
        },

        # Storage
        "s3": {
            "standard_per_gb": 0.023,
            "ia_per_gb": 0.0125,
            "glacier_per_gb": 0.004,
            "put_per_1k": 0.005,
            "get_per_1k": 0.0004,
        },
        "ebs": {
            "gp3_per_gb": 0.08,
            "io1_per_gb": 0.125,
            "snapshot_per_gb": 0.05,
        },

        # Security
        "config": {
            "rule_evaluation": 0.001,
            "config_item": 0.003,
        },
        "guardduty": {
            "per_million_events": 4.00,
            "s3_per_million": 0.80,
        },
        "security_hub": {
            "per_check": 0.0010,
        },
        "inspector": {
            "ec2_instance": 1.258,  # per month
            "lambda_function": 0.30,  # per month
        },
        "macie": {
            "per_bucket": 0.10,
            "per_gb_scanned": 1.00,
        },
        "cloudtrail": {
            "management_events": 0,  # free for first trail
            "data_events_per_100k": 0.10,
        },
        "kms": {
            "key_per_month": 1.00,
            "requests_per_10k": 0.03,
        },
    }

    def estimate_component(
        self,
        component_type: str,
        configuration: dict[str, Any],
    ) -> CostEstimate:
        """Estimate cost for a single component."""
        estimators = {
            "vpc": self._estimate_vpc,
            "nat_gateway": self._estimate_nat,
            "network_firewall": self._estimate_network_firewall,
            "waf": self._estimate_waf,
            "ec2": self._estimate_ec2,
            "fargate": self._estimate_fargate,
            "eks": self._estimate_eks,
            "alb": self._estimate_alb,
            "rds": self._estimate_rds,
            "aurora": self._estimate_aurora,
            "s3": self._estimate_s3,
            "security_stack": self._estimate_security_stack,
        }

        estimator = estimators.get(component_type)
        if estimator:
            return estimator(configuration)

        return CostEstimate(
            component=component_type,
            monthly_min=0,
            monthly_max=0,
            assumptions=["No pricing data available"],
            optimization_tips=[],
        )

    def estimate_architecture(
        self,
        components: list[dict[str, Any]],
    ) -> TotalCostEstimate:
        """Estimate total cost for an architecture."""
        estimates = []
        total_min = 0
        total_max = 0

        for comp in components:
            estimate = self.estimate_component(
                comp["type"],
                comp.get("config", {}),
            )
            estimates.append(estimate)
            total_min += estimate.monthly_min
            total_max += estimate.monthly_max

        return TotalCostEstimate(
            components=estimates,
            monthly_min=total_min,
            monthly_max=total_max,
            annual_min=total_min * 12,
            annual_max=total_max * 12,
            notes=[
                "Estimates based on us-east-1 pricing",
                "Data transfer costs not fully included",
                "Consider Reserved Instances for 30-60% savings",
            ],
        )

    def _estimate_vpc(self, config: dict) -> CostEstimate:
        """Estimate VPC costs (mostly free, but related components)."""
        return CostEstimate(
            component="VPC",
            monthly_min=0,
            monthly_max=0,
            assumptions=["VPC itself is free", "Cost is in NAT, endpoints, etc."],
            optimization_tips=["VPCs are free - cost is in associated resources"],
        )

    def _estimate_nat(self, config: dict) -> CostEstimate:
        """Estimate NAT Gateway costs."""
        count = config.get("count", 1)
        gb_per_month = config.get("data_gb", 100)

        base = self.PRICING["nat_gateway"]["monthly_base"] * count
        data = self.PRICING["nat_gateway"]["per_gb"] * gb_per_month * count

        monthly_min = base + (data * 0.5)  # Assume 50% of estimated traffic
        monthly_max = base + (data * 1.5)  # Assume 150% of estimated traffic

        return CostEstimate(
            component=f"NAT Gateway (x{count})",
            monthly_min=monthly_min,
            monthly_max=monthly_max,
            assumptions=[
                f"Assumes {gb_per_month}GB data/month per NAT",
                "Data processing at $0.045/GB",
            ],
            optimization_tips=[
                "Use VPC endpoints to reduce NAT traffic",
                "Consider NAT instances for very low traffic",
                "Review data transfer patterns",
            ],
        )

    def _estimate_network_firewall(self, config: dict) -> CostEstimate:
        """Estimate AWS Network Firewall costs."""
        endpoints = config.get("endpoints", 3)  # One per AZ
        gb_per_month = config.get("data_gb", 500)

        base = self.PRICING["network_firewall"]["monthly_base"] * endpoints
        data = self.PRICING["network_firewall"]["per_gb"] * gb_per_month

        return CostEstimate(
            component=f"Network Firewall ({endpoints} endpoints)",
            monthly_min=base + (data * 0.5),
            monthly_max=base + (data * 1.5),
            assumptions=[
                f"{endpoints} endpoints (one per AZ)",
                f"{gb_per_month}GB processed/month",
            ],
            optimization_tips=[
                "Consolidate inspection to reduce endpoints",
                "Use centralized inspection VPC pattern",
                "Review rule efficiency",
            ],
        )

    def _estimate_waf(self, config: dict) -> CostEstimate:
        """Estimate AWS WAF costs."""
        rules = config.get("rules", 10)
        requests_millions = config.get("requests_millions", 10)

        web_acl = self.PRICING["waf"]["web_acl"]
        rule_cost = self.PRICING["waf"]["per_rule"] * rules
        request_cost = self.PRICING["waf"]["per_million_requests"] * requests_millions

        monthly = web_acl + rule_cost + request_cost

        return CostEstimate(
            component="AWS WAF",
            monthly_min=monthly * 0.8,
            monthly_max=monthly * 1.5,
            assumptions=[
                f"{rules} rules",
                f"{requests_millions}M requests/month",
            ],
            optimization_tips=[
                "Use AWS Managed Rules (included in rule cost)",
                "Consolidate rules where possible",
                "Consider rate-based rules for DDoS",
            ],
        )

    def _estimate_ec2(self, config: dict) -> CostEstimate:
        """Estimate EC2 costs."""
        instance_type = config.get("instance_type", "t3.medium")
        count = config.get("count", 1)

        base_cost = self.PRICING["ec2"].get(instance_type, 30)
        monthly = base_cost * count

        return CostEstimate(
            component=f"EC2 {instance_type} (x{count})",
            monthly_min=monthly,
            monthly_max=monthly * 1.2,  # EBS, data transfer buffer
            assumptions=[
                "On-demand pricing",
                "Does not include EBS storage",
            ],
            optimization_tips=[
                "Use Reserved Instances for 30-60% savings",
                "Consider Spot for fault-tolerant workloads",
                "Use Compute Optimizer for right-sizing",
            ],
        )

    def _estimate_fargate(self, config: dict) -> CostEstimate:
        """Estimate Fargate costs."""
        vcpu = config.get("vcpu", 0.5)
        memory_gb = config.get("memory_gb", 1)
        tasks = config.get("tasks", 2)
        hours = config.get("hours_per_month", 720)

        vcpu_cost = self.PRICING["fargate"]["vcpu_hour"] * vcpu * hours * tasks
        memory_cost = self.PRICING["fargate"]["gb_hour"] * memory_gb * hours * tasks

        monthly = vcpu_cost + memory_cost

        return CostEstimate(
            component=f"Fargate ({tasks} tasks, {vcpu}vCPU, {memory_gb}GB)",
            monthly_min=monthly * 0.5,  # Scaling down
            monthly_max=monthly * 2,    # Scaling up
            assumptions=[
                f"{tasks} tasks running",
                f"{vcpu} vCPU, {memory_gb}GB memory each",
            ],
            optimization_tips=[
                "Use Fargate Spot for 50-70% savings",
                "Right-size CPU and memory",
                "Use ARM64 for 20% savings",
            ],
        )

    def _estimate_eks(self, config: dict) -> CostEstimate:
        """Estimate EKS costs."""
        nodes = config.get("nodes", 3)
        instance_type = config.get("instance_type", "m5.large")

        control_plane = self.PRICING["eks"]["monthly_base"]
        node_cost = self.PRICING["ec2"].get(instance_type, 70) * nodes

        monthly = control_plane + node_cost

        return CostEstimate(
            component=f"EKS Cluster ({nodes} x {instance_type})",
            monthly_min=monthly,
            monthly_max=monthly * 1.3,
            assumptions=[
                "EKS control plane: $72/month",
                f"{nodes} worker nodes",
                "Does not include load balancers, storage",
            ],
            optimization_tips=[
                "Use Spot instances for worker nodes",
                "Consider Karpenter for efficient scaling",
                "Use Graviton instances for savings",
            ],
        )

    def _estimate_alb(self, config: dict) -> CostEstimate:
        """Estimate ALB costs."""
        lcus = config.get("lcus", 5)

        base = self.PRICING["alb"]["monthly_base"]
        lcu_cost = self.PRICING["alb"]["lcu_hour"] * lcus * 720

        monthly = base + lcu_cost

        return CostEstimate(
            component="Application Load Balancer",
            monthly_min=monthly * 0.7,
            monthly_max=monthly * 1.5,
            assumptions=[
                f"Estimated {lcus} LCU average",
                "LCU based on connections, bandwidth, rules",
            ],
            optimization_tips=[
                "Minimize idle connections",
                "Use target groups efficiently",
                "Consider NLB for TCP workloads",
            ],
        )

    def _estimate_rds(self, config: dict) -> CostEstimate:
        """Estimate RDS costs."""
        instance_type = config.get("instance_type", "db.t3.medium")
        multi_az = config.get("multi_az", False)
        storage_gb = config.get("storage_gb", 100)

        instance_cost = self.PRICING["rds"].get(instance_type, 50)
        if multi_az:
            instance_cost *= self.PRICING["rds"]["multi_az_multiplier"]

        storage_cost = self.PRICING["rds"]["storage_per_gb"] * storage_gb

        monthly = instance_cost + storage_cost

        return CostEstimate(
            component=f"RDS {instance_type} ({'Multi-AZ' if multi_az else 'Single-AZ'})",
            monthly_min=monthly,
            monthly_max=monthly * 1.2,
            assumptions=[
                f"{storage_gb}GB storage",
                "gp2 storage type",
            ],
            optimization_tips=[
                "Use Reserved Instances for 30-60% savings",
                "gp3 is often cheaper than gp2",
                "Review provisioned IOPS needs",
            ],
        )

    def _estimate_aurora(self, config: dict) -> CostEstimate:
        """Estimate Aurora Serverless v2 costs."""
        min_acu = config.get("min_acu", 0.5)
        max_acu = config.get("max_acu", 8)
        storage_gb = config.get("storage_gb", 50)

        # Assume average ACU usage
        avg_acu = (min_acu + max_acu) / 2
        acu_cost = self.PRICING["aurora"]["acu_hour"] * avg_acu * 720
        storage_cost = self.PRICING["aurora"]["storage_per_gb"] * storage_gb

        monthly_min = (self.PRICING["aurora"]["acu_hour"] * min_acu * 720) + storage_cost
        monthly_max = (self.PRICING["aurora"]["acu_hour"] * max_acu * 720) + storage_cost

        return CostEstimate(
            component=f"Aurora Serverless v2 ({min_acu}-{max_acu} ACU)",
            monthly_min=monthly_min,
            monthly_max=monthly_max,
            assumptions=[
                f"ACU range: {min_acu} - {max_acu}",
                f"{storage_gb}GB storage",
                "I/O costs not included",
            ],
            optimization_tips=[
                "Set appropriate min ACU to avoid cold starts",
                "Monitor ACU usage to optimize range",
                "Consider Reserved for predictable workloads",
            ],
        )

    def _estimate_s3(self, config: dict) -> CostEstimate:
        """Estimate S3 costs."""
        storage_gb = config.get("storage_gb", 100)
        requests_k = config.get("requests_thousands", 1000)

        storage_cost = self.PRICING["s3"]["standard_per_gb"] * storage_gb
        request_cost = (self.PRICING["s3"]["put_per_1k"] * requests_k * 0.1 +
                       self.PRICING["s3"]["get_per_1k"] * requests_k * 0.9)

        monthly = storage_cost + request_cost

        return CostEstimate(
            component=f"S3 ({storage_gb}GB)",
            monthly_min=monthly * 0.8,
            monthly_max=monthly * 1.5,
            assumptions=[
                f"{storage_gb}GB storage",
                f"{requests_k}K requests/month",
            ],
            optimization_tips=[
                "Use S3 Intelligent-Tiering for variable access",
                "Lifecycle policies to move old data to IA/Glacier",
                "Enable S3 Storage Lens for insights",
            ],
        )

    def _estimate_security_stack(self, config: dict) -> CostEstimate:
        """Estimate security services stack costs."""
        resources = config.get("resources", 100)
        buckets = config.get("s3_buckets", 10)

        config_cost = resources * self.PRICING["config"]["config_item"] * 30  # Monthly
        guardduty_cost = 30  # Base estimate
        security_hub_cost = resources * self.PRICING["security_hub"]["per_check"] * 100  # checks/resource
        inspector_cost = resources * 0.5  # Rough estimate
        macie_cost = buckets * self.PRICING["macie"]["per_bucket"]

        monthly = config_cost + guardduty_cost + security_hub_cost + inspector_cost + macie_cost

        return CostEstimate(
            component="Security Stack (Config, GuardDuty, Security Hub, Inspector, Macie)",
            monthly_min=monthly * 0.7,
            monthly_max=monthly * 1.5,
            assumptions=[
                f"{resources} resources monitored",
                f"{buckets} S3 buckets",
            ],
            optimization_tips=[
                "Limit Config rules to essential ones",
                "Use Macie sampling for large buckets",
                "Disable unused GuardDuty protections",
            ],
        )


def format_cost_estimate(estimate: CostEstimate) -> str:
    """Format a cost estimate for display."""
    return f"""**{estimate.component}**
- Monthly: ${estimate.monthly_min:.2f} - ${estimate.monthly_max:.2f}
- Assumptions: {', '.join(estimate.assumptions)}
- Tips: {', '.join(estimate.optimization_tips[:2])}"""


def format_total_estimate(estimate: TotalCostEstimate) -> str:
    """Format a total cost estimate for display."""
    components_str = "\n".join([
        f"- {c.component}: ${c.monthly_min:.2f} - ${c.monthly_max:.2f}"
        for c in estimate.components
    ])

    return f"""**Total Cost Estimate**

{components_str}

**Summary:**
- Monthly: ${estimate.monthly_min:.2f} - ${estimate.monthly_max:.2f}
- Annual: ${estimate.annual_min:.2f} - ${estimate.annual_max:.2f}

**Notes:**
{chr(10).join('- ' + n for n in estimate.notes)}"""
