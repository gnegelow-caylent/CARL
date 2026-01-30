"""
AWS Pricing Database for CARL.

Accurate pricing data for us-east-1 as of 2024.
All prices in USD per month unless otherwise noted.

Sources:
- https://aws.amazon.com/pricing/
- AWS Price List API
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Region(Enum):
    """AWS Regions with pricing multipliers relative to us-east-1."""
    US_EAST_1 = ("us-east-1", 1.0)
    US_EAST_2 = ("us-east-2", 1.0)
    US_WEST_1 = ("us-west-1", 1.08)
    US_WEST_2 = ("us-west-2", 1.0)
    EU_WEST_1 = ("eu-west-1", 1.10)
    EU_CENTRAL_1 = ("eu-central-1", 1.12)
    AP_SOUTHEAST_1 = ("ap-southeast-1", 1.12)
    AP_NORTHEAST_1 = ("ap-northeast-1", 1.15)

    def __init__(self, region_code: str, multiplier: float):
        self.region_code = region_code
        self.multiplier = multiplier


@dataclass
class PricingItem:
    """Represents a pricing item with breakdown."""
    component: str
    unit: str
    unit_price: float
    quantity: float
    monthly_cost: float
    notes: str = ""


# =============================================================================
# NETWORKING PRICING (us-east-1 base)
# =============================================================================

NETWORKING_PRICING = {
    # NAT Gateway
    "nat_gateway": {
        "hourly_rate": 0.045,  # Per NAT Gateway hour
        "data_processing_per_gb": 0.045,  # Per GB processed
        "monthly_base": 32.40,  # 720 hours * $0.045
        "notes": "Charged per hour + per GB processed. Cross-AZ data transfer adds $0.01/GB.",
    },

    # Transit Gateway
    "transit_gateway": {
        "hourly_per_attachment": 0.05,  # Per VPC/VPN attachment hour
        "data_processing_per_gb": 0.02,  # Per GB processed
        "monthly_per_attachment": 36.00,  # 720 hours * $0.05
        "notes": "Each VPC attachment costs approx. $36/mo. Data processing is $0.02/GB.",
    },

    # Transit Gateway Connect (SD-WAN)
    "tgw_connect": {
        "hourly_per_attachment": 0.05,
        "data_processing_per_gb": 0.02,
        "monthly_per_attachment": 36.00,
    },

    # VPC Peering
    "vpc_peering": {
        "hourly_rate": 0,  # Free
        "data_transfer_same_az": 0,  # Free
        "data_transfer_cross_az": 0.01,  # Per GB
        "data_transfer_cross_region": 0.02,  # Per GB (varies by region pair)
        "notes": "Free to create. Pay only for cross-AZ/cross-region data transfer.",
    },

    # AWS Network Firewall
    "network_firewall": {
        "endpoint_hourly": 0.395,  # Per firewall endpoint hour
        "data_processing_per_gb": 0.065,  # Per GB processed
        "monthly_per_endpoint": 284.40,  # 720 * $0.395
        "notes": "Need one endpoint per AZ. Typically 2-3 endpoints = $570-850/mo base.",
    },

    # AWS Cloud WAN
    "cloud_wan": {
        "core_network_edge_hourly": 0.05,  # Per CNE per hour
        "core_network_edge_monthly": 36.00,
        "data_processing_per_gb": 0.02,
        "peering_attachment_hourly": 0.05,
        "notes": "Similar to TGW pricing but with global policy management.",
    },

    # VPC Endpoints
    "vpc_endpoint_interface": {
        "hourly_rate": 0.01,  # Per endpoint hour per AZ
        "data_processing_per_gb": 0.01,  # Per GB processed
        "monthly_per_az": 7.20,  # 720 * $0.01
        "notes": "Interface endpoints charged per AZ. Gateway endpoints (S3, DynamoDB) are free.",
    },

    "vpc_endpoint_gateway": {
        "hourly_rate": 0,
        "data_processing_per_gb": 0,
        "notes": "S3 and DynamoDB Gateway endpoints are free. Highly recommended.",
    },

    # Elastic IP
    "elastic_ip": {
        "in_use": 0,  # Free when attached
        "idle_hourly": 0.005,  # Per hour when not attached
        "idle_monthly": 3.60,
        "notes": "Free when attached to running instance. $3.60/mo if idle.",
    },

    # VPC Flow Logs
    "vpc_flow_logs": {
        "to_cloudwatch_per_gb": 0.50,  # Per GB ingested to CloudWatch
        "to_s3_per_gb": 0.25,  # Per GB delivered to S3
        "notes": "S3 destination is 50% cheaper than CloudWatch.",
    },

    # Data Transfer
    "data_transfer": {
        "inbound": 0,  # Free
        "outbound_first_10tb": 0.09,  # Per GB
        "outbound_next_40tb": 0.085,
        "outbound_over_150tb": 0.07,
        "cross_az": 0.01,  # Per GB each direction
        "cross_region": 0.02,  # Per GB (varies)
        "notes": "Inbound is free. Outbound charged in tiers. Cross-AZ often forgotten.",
    },
}

# =============================================================================
# VPN PRICING
# =============================================================================

VPN_PRICING = {
    # Site-to-Site VPN
    "site_to_site_vpn": {
        "connection_hourly": 0.05,  # Per VPN connection hour
        "monthly_per_connection": 36.00,
        "data_transfer_out_per_gb": 0.09,  # Standard data transfer rates
        "notes": "Each VPN connection supports 2 tunnels. Need redundancy = 2 connections = $72/mo.",
    },

    # Accelerated Site-to-Site VPN
    "accelerated_vpn": {
        "connection_hourly": 0.05,
        "accelerator_hourly": 0.025,  # Per accelerator endpoint
        "monthly_per_connection": 36.00,
        "monthly_accelerator": 18.00,  # Per direction
        "data_transfer_premium_per_gb": 0.015,  # Additional to standard
        "notes": "Uses Global Accelerator for better performance. Adds approx. $36/mo per connection.",
    },

    # AWS Client VPN
    "client_vpn": {
        "endpoint_hourly": 0.10,  # Per endpoint association hour
        "connection_hourly": 0.05,  # Per active connection hour
        "monthly_per_subnet": 72.00,  # 720 * $0.10
        "estimated_per_user_monthly": 5.00,  # Assuming 3hr/day usage
        "notes": "Endpoint fee per associated subnet + per active connection. Can add up quickly.",
    },
}

# =============================================================================
# DIRECT CONNECT PRICING
# =============================================================================

DIRECT_CONNECT_PRICING = {
    "dedicated_1gbps": {
        "port_hourly": 0.30,
        "monthly_port": 216.00,
        "notes": "Port fee only. Circuit cost from telecom provider is additional.",
    },
    "dedicated_10gbps": {
        "port_hourly": 2.25,
        "monthly_port": 1620.00,
    },
    "hosted_50mbps": {"monthly": 30.00},
    "hosted_100mbps": {"monthly": 60.00},
    "hosted_200mbps": {"monthly": 90.00},
    "hosted_300mbps": {"monthly": 120.00},
    "hosted_400mbps": {"monthly": 150.00},
    "hosted_500mbps": {"monthly": 180.00},
    "hosted_1gbps": {"monthly": 220.00},
    "hosted_2gbps": {"monthly": 440.00},
    "hosted_5gbps": {"monthly": 900.00},
    "hosted_10gbps": {"monthly": 1575.00},
    "data_transfer_out_per_gb": 0.02,  # Varies by region
    "notes": "Significantly cheaper data transfer than internet. ROI typically at 500GB+/mo.",
}

# =============================================================================
# COMPUTE PRICING
# =============================================================================

COMPUTE_PRICING = {
    # EC2 On-Demand (common types, us-east-1)
    "ec2": {
        # T3 (burstable)
        "t3.nano": 3.80,
        "t3.micro": 7.59,
        "t3.small": 15.18,
        "t3.medium": 30.37,
        "t3.large": 60.74,
        "t3.xlarge": 121.47,

        # M5 (general purpose)
        "m5.large": 70.08,
        "m5.xlarge": 140.16,
        "m5.2xlarge": 280.32,
        "m5.4xlarge": 560.64,

        # M6i (current gen)
        "m6i.large": 70.08,
        "m6i.xlarge": 140.16,
        "m6i.2xlarge": 280.32,

        # C5 (compute optimized)
        "c5.large": 62.05,
        "c5.xlarge": 124.10,
        "c5.2xlarge": 248.20,

        # R5 (memory optimized)
        "r5.large": 91.98,
        "r5.xlarge": 183.96,
        "r5.2xlarge": 367.92,

        # Graviton (ARM - 20% cheaper)
        "t4g.micro": 6.05,
        "t4g.small": 12.10,
        "t4g.medium": 24.19,
        "m6g.large": 56.06,
        "m6g.xlarge": 112.13,

        "notes": "On-demand pricing. Reserved Instances save 30-60%. Spot saves 60-90%.",
    },

    # EKS
    "eks": {
        "cluster_hourly": 0.10,
        "monthly_cluster": 72.00,  # Control plane only
        "notes": "EKS cluster fee is fixed. Worker nodes are EC2/Fargate costs.",
    },

    # Fargate
    "fargate": {
        "vcpu_per_hour": 0.04048,
        "memory_gb_per_hour": 0.004445,
        "vcpu_monthly": 29.15,  # 720 hours
        "memory_gb_monthly": 3.20,
        "spot_discount": 0.70,  # 70% off
        "notes": "Per-second billing. Spot available for 70% savings.",
    },

    # Lambda
    "lambda": {
        "requests_per_million": 0.20,
        "duration_per_gb_second": 0.0000166667,
        "free_tier_requests": 1000000,
        "free_tier_gb_seconds": 400000,
        "notes": "Very cost effective for sporadic workloads. Free tier is generous.",
    },

    # Application Load Balancer
    "alb": {
        "hourly": 0.0225,
        "monthly_base": 16.20,
        "lcu_hourly": 0.008,
        "notes": "LCU based on connections, bandwidth, rules. Typically $25-50/mo for moderate load.",
    },

    # Network Load Balancer
    "nlb": {
        "hourly": 0.0225,
        "monthly_base": 16.20,
        "nlcu_hourly": 0.006,
        "notes": "Better for TCP/UDP, static IPs. Slightly cheaper LCU than ALB.",
    },
}

# =============================================================================
# DATABASE PRICING
# =============================================================================

DATABASE_PRICING = {
    # RDS (common instance types)
    "rds": {
        # db.t3 (burstable)
        "db.t3.micro": 12.41,
        "db.t3.small": 24.82,
        "db.t3.medium": 49.64,
        "db.t3.large": 99.28,

        # db.r5 (memory optimized)
        "db.r5.large": 146.00,
        "db.r5.xlarge": 292.00,
        "db.r5.2xlarge": 584.00,

        # db.m5 (general purpose)
        "db.m5.large": 124.10,
        "db.m5.xlarge": 248.20,

        "multi_az_multiplier": 2.0,
        "storage_gp2_per_gb": 0.115,
        "storage_gp3_per_gb": 0.08,
        "storage_io1_per_gb": 0.125,
        "storage_io1_per_iops": 0.10,
        "backup_per_gb": 0.095,  # Beyond retention

        "notes": "Multi-AZ doubles instance cost. Storage costs are additional. gp3 is usually better value than gp2.",
    },

    # Aurora
    "aurora": {
        # Aurora Serverless v2
        "serverless_v2_acu_hourly": 0.12,
        "serverless_v2_acu_monthly": 86.40,  # Per ACU at 100%
        "min_acu": 0.5,
        "max_acu": 128,

        # Aurora Provisioned
        "db.r5.large": 175.20,
        "db.r5.xlarge": 350.40,
        "db.r6g.large": 140.16,  # Graviton

        "storage_per_gb": 0.10,
        "io_per_million": 0.20,
        "backup_per_gb": 0.021,

        "notes": "Aurora is ~20% more expensive than RDS but more performant. I/O costs can add up.",
    },

    # DynamoDB
    "dynamodb": {
        "on_demand_wru_per_million": 1.25,
        "on_demand_rru_per_million": 0.25,
        "provisioned_wcu_monthly": 0.47,  # Per WCU
        "provisioned_rcu_monthly": 0.09,  # Per RCU
        "storage_per_gb": 0.25,
        "global_tables_per_rwu": 1.875,

        "notes": "On-demand is simpler. Provisioned is cheaper for predictable workloads. First 25GB storage free.",
    },

    # ElastiCache
    "elasticache": {
        "cache.t3.micro": 12.41,
        "cache.t3.small": 24.82,
        "cache.t3.medium": 49.64,
        "cache.r5.large": 131.40,
        "cache.r6g.large": 105.12,  # Graviton

        "notes": "Redis is slightly more expensive than Memcached. Graviton offers good savings.",
    },
}

# =============================================================================
# STORAGE PRICING
# =============================================================================

STORAGE_PRICING = {
    "s3": {
        "standard_per_gb": 0.023,
        "standard_ia_per_gb": 0.0125,
        "one_zone_ia_per_gb": 0.01,
        "glacier_instant_per_gb": 0.004,
        "glacier_flexible_per_gb": 0.0036,
        "glacier_deep_archive_per_gb": 0.00099,
        "intelligent_tiering_per_gb": 0.023,  # Same as standard, auto-tiers
        "intelligent_tiering_monitoring_per_1k": 0.0025,

        "put_per_1k": 0.005,
        "get_per_1k": 0.0004,
        "lifecycle_transitions_per_1k": 0.01,

        "notes": "Intelligent-Tiering is great for unknown access patterns. Lifecycle policies can save 40-70%.",
    },

    "ebs": {
        "gp3_per_gb": 0.08,
        "gp3_iops_free": 3000,
        "gp3_throughput_free_mbps": 125,
        "gp3_additional_iops": 0.005,
        "gp3_additional_throughput_per_mbps": 0.04,

        "gp2_per_gb": 0.10,  # Legacy, avoid

        "io1_per_gb": 0.125,
        "io1_per_iops": 0.065,

        "io2_per_gb": 0.125,
        "io2_per_iops": 0.065,

        "snapshot_per_gb": 0.05,

        "notes": "gp3 is almost always better than gp2. io2 offers better durability than io1.",
    },

    "efs": {
        "standard_per_gb": 0.30,
        "ia_per_gb": 0.025,
        "one_zone_per_gb": 0.16,
        "one_zone_ia_per_gb": 0.0133,

        "notes": "EFS is expensive for large storage. Use lifecycle policies to move to IA.",
    },
}

# =============================================================================
# SECURITY SERVICES PRICING
# =============================================================================

SECURITY_PRICING = {
    "waf": {
        "web_acl_monthly": 5.00,
        "rule_monthly": 1.00,
        "managed_rule_group": 0,  # Depends on publisher
        "requests_per_million": 0.60,
        "bot_control_per_million": 1.00,

        "notes": "WAF is very cost-effective. Bot Control adds significant cost for high traffic.",
    },

    "shield": {
        "standard": 0,  # Free
        "advanced_monthly": 3000.00,
        "advanced_data_transfer_per_gb": 0.025,  # Above baseline

        "notes": "Shield Standard is free and sufficient for most. Advanced is for DDoS SLA/support.",
    },

    "cloudfront": {
        "requests_per_10k_http": 0.0075,
        "requests_per_10k_https": 0.01,
        "data_transfer_first_10tb": 0.085,
        "data_transfer_next_40tb": 0.080,
        "data_transfer_next_100tb": 0.060,
        "origin_shield_per_10k": 0.0075,
        "field_level_encryption_per_10k": 0.02,

        "notes": "Often cheaper than serving directly from origin. Origin Shield reduces origin load.",
    },

    "config": {
        "config_item_recorded": 0.003,
        "rule_evaluation": 0.001,
        "conformance_pack_evaluation": 0.001,

        "notes": "Costs scale with number of resources. 100 resources ≈ $10-30/mo.",
    },

    "guardduty": {
        "cloudtrail_mgmt_events_per_million": 4.00,
        "cloudtrail_s3_events_per_million": 0.80,
        "vpc_flow_logs_first_500gb": 1.00,  # Per GB
        "vpc_flow_logs_next_2tb": 0.50,
        "vpc_flow_logs_over_5tb": 0.25,
        "eks_audit_logs_per_million": 1.60,
        "s3_protection_per_million": 1.00,
        "malware_per_gb_scanned": 0.05,

        "notes": "Costs vary significantly by volume. S3 protection is optional but recommended.",
    },

    "security_hub": {
        "finding_ingestion_first_10k": 0,  # Free
        "finding_ingestion_per_finding": 0.00003,
        "security_checks_per_check": 0.0010,

        "notes": "Very affordable. Costs scale with number of checks/findings.",
    },

    "inspector": {
        "ec2_instance_monthly": 1.258,
        "ecr_initial_scan": 0.09,  # Per image
        "ecr_rescan": 0.01,
        "lambda_function_monthly": 0.30,

        "notes": "Per-resource pricing. Costs predictable based on resource count.",
    },

    "macie": {
        "bucket_evaluation_monthly": 0.10,  # Per bucket
        "sensitive_data_discovery_first_gb": 1.00,
        "sensitive_data_discovery_next_gb": 0.30,  # 1-50TB tier

        "notes": "Bucket evaluation is cheap. Discovery scanning can be expensive for large buckets.",
    },

    "kms": {
        "customer_managed_key_monthly": 1.00,
        "aws_managed_key": 0,  # Free
        "requests_per_10k": 0.03,

        "notes": "CMKs cost $1/mo each. Use AWS-managed keys where compliance allows.",
    },

    "secrets_manager": {
        "secret_monthly": 0.40,
        "api_calls_per_10k": 0.05,

        "notes": "More expensive than Parameter Store but offers rotation. Use SSM for non-rotating secrets.",
    },

    "cloudtrail": {
        "management_events_first_trail": 0,  # Free
        "management_events_additional_trails": 2.00,  # Per 100k events
        "data_events_per_100k": 0.10,
        "insights_events_per_100k": 0.35,

        "notes": "First trail is free for management events. Data events add up quickly.",
    },
}

# =============================================================================
# CONTROL TOWER / LANDING ZONE PRICING
# =============================================================================

LANDING_ZONE_PRICING = {
    "control_tower": {
        "base_cost": 0,  # Control Tower itself is free
        "notes": "Control Tower is free. Costs come from underlying services (Config, CloudTrail, etc.)",
    },

    "organizations": {
        "base_cost": 0,  # Free
        "notes": "AWS Organizations is free. SCPs have no cost.",
    },

    "sso": {
        "base_cost": 0,  # Free for workforce identities
        "notes": "IAM Identity Center (SSO) is free for internal users.",
    },

    "typical_landing_zone_per_account": {
        "cloudtrail": 5.00,  # Org trail share
        "config": 15.00,  # ~50 rules
        "security_hub": 10.00,
        "guardduty": 20.00,
        "estimated_total": 50.00,

        "notes": "Baseline security services cost approx. $50/account/month. Varies by activity.",
    },
}

# =============================================================================
# BACKUP AND DR PRICING
# =============================================================================

BACKUP_PRICING = {
    "aws_backup": {
        "warm_storage_per_gb": 0.05,
        "cold_storage_per_gb": 0.01,
        "restore_warm_per_gb": 0.02,
        "restore_cold_per_gb": 0.02,
        "notes": "Warm storage for quick restore. Cold storage for compliance/archival.",
    },

    "ebs_snapshots": {
        "per_gb_month": 0.05,
        "notes": "Incremental after first snapshot. Cross-region copy adds transfer.",
    },

    "rds_backup": {
        "included_backup": "100%",  # Free up to DB size
        "additional_per_gb": 0.095,
        "notes": "Backup storage up to DB size is free. Beyond that, $0.095/GB.",
    },

    "s3_cross_region_replication": {
        "data_transfer_per_gb": 0.02,
        "notes": "Plus storage in destination region.",
    },

    "aurora_backtrack": {
        "per_million_changes": 0.012,
        "notes": "Point-in-time recovery up to 72 hours.",
    },
}

# =============================================================================
# LOGGING PRICING
# =============================================================================

LOGGING_PRICING = {
    "cloudwatch_logs": {
        "ingestion_per_gb": 0.50,
        "storage_per_gb_month": 0.03,
        "insights_query_per_gb_scanned": 0.005,
        "notes": "Expensive for high volume. Consider S3 for long-term.",
    },

    "s3_log_delivery": {
        "vpc_flow_logs_per_gb": 0.25,
        "cloudtrail_per_gb": 0.00,  # Included
        "elb_access_logs": 0.00,  # Free to S3
        "cloudfront_logs": 0.00,  # Free to S3
        "notes": "S3 delivery is cheaper than CloudWatch for most log types.",
    },

    "kinesis_firehose": {
        "per_gb_ingested": 0.029,
        "format_conversion_per_gb": 0.018,  # To Parquet
        "notes": "Good for streaming to S3 with transformation.",
    },

    "opensearch": {
        "t3_small_hourly": 0.036,  # approx. $26/mo
        "m5_large_hourly": 0.142,  # approx. $102/mo
        "r5_large_hourly": 0.167,  # approx. $120/mo
        "storage_per_gb": 0.10,  # GP2
        "notes": "Cluster costs add up. Minimum 2 nodes recommended.",
    },

    "athena": {
        "per_tb_scanned": 5.00,
        "notes": "Use partitions and Parquet to reduce scan size.",
    },
}

# =============================================================================
# SYSTEMS MANAGER PRICING
# =============================================================================

SYSTEMS_MANAGER_PRICING = {
    "session_manager": {
        "base_cost": 0,
        "notes": "Free. Logging to CloudWatch/S3 has storage costs.",
    },

    "patch_manager": {
        "base_cost": 0,
        "notes": "Free. Uses maintenance windows.",
    },

    "parameter_store": {
        "standard_parameters": 0,  # Free up to 10K
        "advanced_per_parameter": 0.05,  # Per month
        "api_throughput_per_10k": 0.05,  # Higher throughput tier
        "notes": "Standard is free and sufficient for most. Advanced for large values.",
    },

    "automation": {
        "per_step_per_resource": 0.00003,
        "notes": "Very cheap. First 100K steps/mo free.",
    },

    "state_manager": {
        "per_association": 0.0033,  # Per hour
        "notes": "approx. $2.40/mo per association.",
    },

    "opsitems": {
        "per_opsitem": 0.00042,  # Creation
        "notes": "Minimal cost.",
    },
}

# =============================================================================
# IDENTITY PRICING
# =============================================================================

IDENTITY_PRICING = {
    "iam_identity_center": {
        "base_cost": 0,
        "notes": "Free for workforce identities. No per-user cost.",
    },

    "managed_ad": {
        "standard_hourly": 0.11,  # approx. $80/mo
        "enterprise_hourly": 0.42,  # approx. $302/mo
        "notes": "Two domain controllers minimum.",
    },

    "ad_connector": {
        "small_hourly": 0.05,  # approx. $36/mo
        "large_hourly": 0.13,  # approx. $94/mo
        "notes": "Connects to existing AD.",
    },

    "cognito": {
        "mau_first_50k": 0,  # Free tier
        "mau_next_50k": 0.0055,  # Per user
        "notes": "For customer identities, not internal users.",
    },
}

# =============================================================================
# FIREWALL MANAGER PRICING
# =============================================================================

FIREWALL_MANAGER_PRICING = {
    "policy": {
        "per_policy_per_region_month": 100.00,
        "notes": "Flat fee per policy per region. Plus underlying service costs.",
    },

    "waf_policy": {
        "policy_cost": 100.00,
        "plus_waf_costs": True,
        "notes": "FMS policy + WAF Web ACL + rules + requests.",
    },

    "security_group_policy": {
        "policy_cost": 100.00,
        "notes": "FMS policy cost only. SGs are free.",
    },

    "network_firewall_policy": {
        "policy_cost": 100.00,
        "plus_nfw_costs": True,
        "notes": "FMS policy + Network Firewall endpoints + data processing.",
    },
}


def calculate_monthly_cost(
    component: str,
    configuration: dict[str, Any],
    region: Region = Region.US_EAST_1,
) -> list[PricingItem]:
    """
    Calculate monthly cost for a component with detailed breakdown.

    Returns list of pricing items that sum to total cost.
    """
    items = []
    multiplier = region.multiplier

    if component == "nat_gateway":
        count = configuration.get("count", 1)
        data_gb = configuration.get("data_gb_per_month", 100)

        base = NETWORKING_PRICING["nat_gateway"]["monthly_base"] * count * multiplier
        data_cost = NETWORKING_PRICING["nat_gateway"]["data_processing_per_gb"] * data_gb * count * multiplier

        items.append(PricingItem(
            component=f"NAT Gateway ({count}x)",
            unit="gateway-month",
            unit_price=NETWORKING_PRICING["nat_gateway"]["monthly_base"] * multiplier,
            quantity=count,
            monthly_cost=base,
            notes="$0.045/hour per gateway"
        ))
        items.append(PricingItem(
            component="NAT Gateway Data Processing",
            unit="GB",
            unit_price=NETWORKING_PRICING["nat_gateway"]["data_processing_per_gb"] * multiplier,
            quantity=data_gb * count,
            monthly_cost=data_cost,
            notes="$0.045/GB processed"
        ))

    elif component == "transit_gateway":
        attachments = configuration.get("vpc_attachments", 1)
        data_gb = configuration.get("data_gb_per_month", 100)

        attach_cost = NETWORKING_PRICING["transit_gateway"]["monthly_per_attachment"] * attachments * multiplier
        data_cost = NETWORKING_PRICING["transit_gateway"]["data_processing_per_gb"] * data_gb * multiplier

        items.append(PricingItem(
            component=f"TGW Attachments ({attachments}x)",
            unit="attachment-month",
            unit_price=NETWORKING_PRICING["transit_gateway"]["monthly_per_attachment"] * multiplier,
            quantity=attachments,
            monthly_cost=attach_cost,
            notes="$0.05/hour per VPC attachment"
        ))
        items.append(PricingItem(
            component="TGW Data Processing",
            unit="GB",
            unit_price=NETWORKING_PRICING["transit_gateway"]["data_processing_per_gb"] * multiplier,
            quantity=data_gb,
            monthly_cost=data_cost,
            notes="$0.02/GB processed"
        ))

    elif component == "network_firewall":
        endpoints = configuration.get("endpoints", 2)
        data_gb = configuration.get("data_gb_per_month", 500)

        endpoint_cost = NETWORKING_PRICING["network_firewall"]["monthly_per_endpoint"] * endpoints * multiplier
        data_cost = NETWORKING_PRICING["network_firewall"]["data_processing_per_gb"] * data_gb * multiplier

        items.append(PricingItem(
            component=f"Firewall Endpoints ({endpoints}x)",
            unit="endpoint-month",
            unit_price=NETWORKING_PRICING["network_firewall"]["monthly_per_endpoint"] * multiplier,
            quantity=endpoints,
            monthly_cost=endpoint_cost,
            notes="$0.395/hour per endpoint (need 1 per AZ)"
        ))
        items.append(PricingItem(
            component="Firewall Data Processing",
            unit="GB",
            unit_price=NETWORKING_PRICING["network_firewall"]["data_processing_per_gb"] * multiplier,
            quantity=data_gb,
            monthly_cost=data_cost,
            notes="$0.065/GB inspected"
        ))

    elif component == "client_vpn":
        subnets = configuration.get("associated_subnets", 2)
        users = configuration.get("concurrent_users", 10)
        hours_per_user = configuration.get("hours_per_day", 8) * 22  # Business days

        subnet_cost = VPN_PRICING["client_vpn"]["monthly_per_subnet"] * subnets * multiplier
        connection_cost = VPN_PRICING["client_vpn"]["connection_hourly"] * users * hours_per_user * multiplier

        items.append(PricingItem(
            component=f"Client VPN Endpoints ({subnets} subnets)",
            unit="subnet-month",
            unit_price=VPN_PRICING["client_vpn"]["monthly_per_subnet"] * multiplier,
            quantity=subnets,
            monthly_cost=subnet_cost,
            notes="$0.10/hour per associated subnet"
        ))
        items.append(PricingItem(
            component=f"Client VPN Connections ({users} users)",
            unit="connection-hours",
            unit_price=VPN_PRICING["client_vpn"]["connection_hourly"] * multiplier,
            quantity=users * hours_per_user,
            monthly_cost=connection_cost,
            notes=f"$0.05/hour per active connection ({hours_per_user} hrs/mo assumed)"
        ))

    elif component == "site_to_site_vpn":
        connections = configuration.get("connections", 1)
        data_gb = configuration.get("data_gb_per_month", 100)

        conn_cost = VPN_PRICING["site_to_site_vpn"]["monthly_per_connection"] * connections * multiplier
        data_cost = VPN_PRICING["site_to_site_vpn"]["data_transfer_out_per_gb"] * data_gb * multiplier

        items.append(PricingItem(
            component=f"VPN Connections ({connections}x)",
            unit="connection-month",
            unit_price=VPN_PRICING["site_to_site_vpn"]["monthly_per_connection"] * multiplier,
            quantity=connections,
            monthly_cost=conn_cost,
            notes="$0.05/hour per connection (2 tunnels each)"
        ))
        items.append(PricingItem(
            component="VPN Data Transfer Out",
            unit="GB",
            unit_price=VPN_PRICING["site_to_site_vpn"]["data_transfer_out_per_gb"] * multiplier,
            quantity=data_gb,
            monthly_cost=data_cost,
            notes="Standard data transfer rates"
        ))

    # Add more component calculations as needed...

    return items


def get_component_pricing_summary(component: str) -> dict[str, Any]:
    """Get pricing summary and notes for a component."""
    pricing_maps = {
        "nat_gateway": NETWORKING_PRICING["nat_gateway"],
        "transit_gateway": NETWORKING_PRICING["transit_gateway"],
        "network_firewall": NETWORKING_PRICING["network_firewall"],
        "vpc_endpoint": NETWORKING_PRICING["vpc_endpoint_interface"],
        "client_vpn": VPN_PRICING["client_vpn"],
        "site_to_site_vpn": VPN_PRICING["site_to_site_vpn"],
        "direct_connect": DIRECT_CONNECT_PRICING,
        "waf": SECURITY_PRICING["waf"],
        "shield": SECURITY_PRICING["shield"],
        "cloudfront": SECURITY_PRICING["cloudfront"],
    }

    return pricing_maps.get(component, {"notes": "Pricing data not available"})
