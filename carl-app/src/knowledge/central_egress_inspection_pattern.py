"""
Central Egress and Inspection VPC Pattern for CARL.

This pattern provides a comprehensive architecture for centralized egress
with traffic inspection using AWS Network Firewall or third-party appliances.

Common use cases:
- SOC 2 / PCI-DSS / HIPAA compliance requiring traffic inspection
- Defense-in-depth security architecture
- Centralized egress policy enforcement
- IDS/IPS capabilities
- URL/domain filtering
- Centralized logging and monitoring
"""

CENTRAL_EGRESS_INSPECTION_PATTERN = {
    "name": "Central Egress and Inspection VPC",
    "category": "networking",
    "description": """
    A dedicated inspection VPC that centralizes all outbound internet traffic
    from workload VPCs, performs deep packet inspection, applies security
    policies, and provides centralized egress with consistent IP addresses.
    """,

    "architecture_overview": """
    Architecture: Central Egress with Inspection

    ┌─────────────────────────────────────────────────────────────────┐
    │                      Workload VPCs                               │
    │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
    │  │  Workload 1  │  │  Workload 2  │  │  Workload N  │          │
    │  │   (VPC-1)    │  │   (VPC-2)    │  │   (VPC-N)    │          │
    │  │              │  │              │  │              │          │
    │  │ App Subnets  │  │ App Subnets  │  │ App Subnets  │          │
    │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
    │         │                 │                 │                   │
    │         └─────────────────┴─────────────────┘                   │
    │                           │                                      │
    └───────────────────────────┼──────────────────────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │   Transit Gateway      │
                    │  (Central Hub)         │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────────────────────────────┐
                    │         Inspection VPC                        │
                    │                                                │
                    │  ┌────────────┐      ┌────────────┐          │
                    │  │  TGW Subnet│      │  TGW Subnet│          │
                    │  │   (AZ-A)   │      │   (AZ-B)   │          │
                    │  └─────┬──────┘      └─────┬──────┘          │
                    │        │                   │                  │
                    │        ▼                   ▼                  │
                    │  ┌────────────┐      ┌────────────┐          │
                    │  │  Firewall  │      │  Firewall  │          │
                    │  │  Endpoint  │      │  Endpoint  │          │
                    │  │  (AWS NFW) │      │  (AWS NFW) │          │
                    │  │   (AZ-A)   │      │   (AZ-B)   │          │
                    │  └─────┬──────┘      └─────┬──────┘          │
                    │        │                   │                  │
                    │        ▼                   ▼                  │
                    │  ┌────────────┐      ┌────────────┐          │
                    │  │    NAT     │      │    NAT     │          │
                    │  │  Gateway   │      │  Gateway   │          │
                    │  │   (AZ-A)   │      │   (AZ-B)   │          │
                    │  │   Public   │      │   Public   │          │
                    │  │   Subnet   │      │   Subnet   │          │
                    │  └─────┬──────┘      └─────┬──────┘          │
                    │        │                   │                  │
                    └────────┼───────────────────┼──────────────────┘
                             │                   │
                             └────────┬──────────┘
                                      │
                                 ┌────▼────┐
                                 │ Internet │
                                 │ Gateway  │
                                 └─────────┘

    Traffic Flow:
    1. App in Workload VPC initiates outbound connection
    2. Traffic routes to Transit Gateway
    3. TGW routes to Inspection VPC (based on 0.0.0.0/0)
    4. Traffic enters firewall subnet (stateful inspection)
    5. Network Firewall inspects traffic (IDS/IPS, domain filtering)
    6. Traffic passes to NAT Gateway subnet
    7. NAT Gateway translates source IP (provides consistent egress IP)
    8. Traffic egresses to internet via Internet Gateway

    Return traffic follows reverse path (stateful)
    """,

    "when_to_use": [
        "SOC 2, PCI-DSS, HIPAA, or other compliance requiring traffic inspection",
        "5+ VPCs with outbound internet traffic",
        "Need to detect/prevent malicious outbound connections",
        "Require centralized logging of all internet traffic",
        "Defense-in-depth security posture",
        "Need consistent egress IP addresses for partner whitelisting",
        "URL/domain filtering requirements",
        "DLP (Data Loss Prevention) inspection needs",
        "Regulated industries (financial services, healthcare)",
        "Multi-account AWS Organizations environment",
    ],

    "when_not_to_use": [
        "Single VPC with minimal egress traffic",
        "Startup/early-stage without compliance requirements",
        "Cost is primary constraint (< 500GB/mo egress)",
        "No security requirements beyond basic security groups",
        "Development/test environments only",
    ],

    "pros": [
        "Deep packet inspection (Layer 7) for all outbound traffic",
        "Centralized security policy enforcement",
        "IDS/IPS capabilities (detect malware, C2 traffic, data exfiltration)",
        "Domain and IP filtering (block known malicious sites)",
        "TLS/SSL inspection capability (with proper setup)",
        "Centralized logging (single CloudWatch Logs destination)",
        "Consistent egress IP addresses",
        "Simplified partner IP whitelisting",
        "SOC 2 / compliance-ready architecture",
        "Single place to update security rules",
        "Reduced NAT Gateway costs at scale",
        "Protection against data exfiltration",
    ],

    "cons": [
        "Higher cost than distributed egress ($600-2000/mo base)",
        "Increased complexity (routing, TGW, firewall rules)",
        "Single egress path (though HA within inspection VPC)",
        "Added latency (typically 1-3ms, minimal impact)",
        "Operational overhead for firewall rule management",
        "Requires skilled networking team",
        "All traffic traverses inspection VPC (capacity planning needed)",
        "False positives require tuning (IDS/IPS signatures)",
    ],

    "components": {
        "inspection_vpc": {
            "description": "Dedicated VPC for traffic inspection",
            "cidr": "Recommended: /24 or /23 (e.g., 10.100.0.0/24)",
            "subnets": {
                "tgw_attachment": {
                    "purpose": "Transit Gateway ENIs",
                    "size": "/28 per AZ (16 IPs, 11 usable)",
                    "route_table": "Routes 0.0.0.0/0 to Firewall Endpoint"
                },
                "firewall": {
                    "purpose": "AWS Network Firewall endpoints",
                    "size": "/28 per AZ (supports scaling)",
                    "route_table": "Routes 0.0.0.0/0 to NAT Gateway"
                },
                "nat_gateway": {
                    "purpose": "NAT Gateways for internet egress",
                    "size": "/28 per AZ",
                    "route_table": "Routes 0.0.0.0/0 to Internet Gateway",
                    "public": True
                },
                "igw": {
                    "purpose": "Internet Gateway attachment",
                    "edge": "Attached to VPC edge"
                }
            }
        },

        "transit_gateway": {
            "description": "Hub connecting workload VPCs to inspection VPC",
            "attachments": [
                "Inspection VPC attachment",
                "Workload VPC attachments (1 per VPC)",
                "Optional: On-premises via VPN/Direct Connect"
            ],
            "route_tables": {
                "workload_rt": {
                    "routes": [
                        "0.0.0.0/0 → Inspection VPC",
                        "10.0.0.0/8 → Blackhole (force internet via inspection)"
                    ]
                },
                "inspection_rt": {
                    "routes": [
                        "10.0.0.0/8 → Workload VPCs (return traffic)",
                        "VPC-1 CIDR → VPC-1 attachment",
                        "VPC-2 CIDR → VPC-2 attachment"
                    ]
                }
            }
        },

        "network_firewall": {
            "description": "AWS Network Firewall for inspection",
            "endpoints_per_az": 1,
            "rule_groups": {
                "stateful": [
                    "Domain filtering (allow/deny lists)",
                    "Suricata IDS rules",
                    "TLS/SNI inspection"
                ],
                "stateless": [
                    "Basic packet filtering",
                    "Port/protocol rules",
                    "Capacity: 30,000 rules"
                ]
            },
            "logging": [
                "Alert logs (IDS events)",
                "Flow logs (all connections)",
                "Destination: CloudWatch Logs or S3"
            ]
        },

        "nat_gateways": {
            "description": "NAT Gateways for egress translation",
            "per_az": 1,
            "purpose": "Consistent egress IPs, source NAT",
            "redundancy": "Deploy in multiple AZs for HA"
        }
    },

    "routing_configuration": {
        "workload_vpc_route_table": {
            "description": "Route table for workload app subnets",
            "routes": [
                {
                    "destination": "0.0.0.0/0",
                    "target": "Transit Gateway attachment",
                    "purpose": "All internet traffic to TGW"
                }
            ]
        },

        "tgw_workload_route_table": {
            "description": "TGW route table for workload VPCs",
            "routes": [
                {
                    "destination": "0.0.0.0/0",
                    "target": "Inspection VPC attachment",
                    "purpose": "Force internet traffic through inspection"
                }
            ]
        },

        "inspection_tgw_subnet_rt": {
            "description": "Route table for TGW subnet in inspection VPC",
            "routes": [
                {
                    "destination": "0.0.0.0/0",
                    "target": "Firewall endpoint",
                    "purpose": "Traffic from workloads to firewall"
                },
                {
                    "destination": "VPC-1 CIDR",
                    "target": "Transit Gateway",
                    "purpose": "Return traffic to workloads"
                }
            ]
        },

        "inspection_firewall_subnet_rt": {
            "description": "Route table for firewall subnet",
            "routes": [
                {
                    "destination": "0.0.0.0/0",
                    "target": "NAT Gateway",
                    "purpose": "Inspected traffic to NAT"
                },
                {
                    "destination": "10.0.0.0/8",
                    "target": "Transit Gateway",
                    "purpose": "Return traffic to workloads"
                }
            ]
        },

        "inspection_nat_subnet_rt": {
            "description": "Route table for NAT Gateway subnet (public)",
            "routes": [
                {
                    "destination": "0.0.0.0/0",
                    "target": "Internet Gateway",
                    "purpose": "Egress to internet"
                },
                {
                    "destination": "10.0.0.0/8",
                    "target": "Firewall endpoint",
                    "purpose": "Return traffic through firewall"
                }
            ]
        }
    },

    "firewall_rules_examples": {
        "allow_https": {
            "type": "Stateful domain allow list",
            "rules": [
                ".amazonaws.com",
                ".amazon.com",
                "github.com",
                ".npmjs.org",
                ".pypi.org"
            ]
        },

        "block_malicious": {
            "type": "Stateful domain deny list",
            "rules": [
                "Managed threat intelligence feeds",
                "Custom blocklist IPs/domains"
            ]
        },

        "ids_rules": {
            "type": "Suricata IPS rules",
            "examples": [
                "Detect SQL injection attempts",
                "Detect malware C2 traffic",
                "Detect cryptocurrency mining",
                "Detect data exfiltration patterns"
            ]
        },

        "stateless_rules": {
            "type": "Fast-path filtering",
            "examples": [
                "Allow outbound TCP 443 (HTTPS)",
                "Allow outbound TCP 80 (HTTP)",
                "Allow outbound UDP 53 (DNS)",
                "Drop all other protocols"
            ]
        }
    },

    "cost_breakdown": {
        "base_monthly_cost": {
            "transit_gateway": {
                "attachment_costs": "$36/mo per VPC attachment",
                "example_5_vpcs": "$180/mo (5 VPCs x $36)",
                "note": "One attachment for inspection VPC included"
            },

            "network_firewall": {
                "endpoints": "$284.40/mo per endpoint",
                "recommended_ha": "$568.80/mo (2 AZs)",
                "enterprise_ha": "$853.20/mo (3 AZs)",
                "note": "Includes 1TB data processing"
            },

            "nat_gateways": {
                "gateway_cost": "$32.40/mo per gateway",
                "recommended_ha": "$64.80/mo (2 AZs)",
                "enterprise_ha": "$97.20/mo (3 AZs)"
            },

            "total_base": "$813-1130/mo (2-3 AZs, 5 VPCs)"
        },

        "variable_costs": {
            "tgw_data_processing": {
                "rate": "$0.02/GB",
                "estimate_500gb": "$10/mo",
                "estimate_5tb": "$100/mo"
            },

            "nfw_data_processing": {
                "rate": "$0.065/GB (beyond 1TB/mo included)",
                "estimate_2tb": "$65/mo extra",
                "estimate_10tb": "$585/mo extra"
            },

            "nat_data_processing": {
                "rate": "$0.045/GB",
                "estimate_500gb": "$22.50/mo",
                "estimate_5tb": "$225/mo"
            },

            "cross_az_data_transfer": {
                "rate": "$0.01/GB",
                "impact": "Typically 10-20% of processed data",
                "estimate": "$10-50/mo"
            }
        },

        "example_scenarios": {
            "small_deployment": {
                "vpcs": 5,
                "monthly_egress": "500GB",
                "azs": 2,
                "estimated_cost": "$900-1000/mo",
                "breakdown": "Base: $813 + Variable: $100"
            },

            "medium_deployment": {
                "vpcs": 10,
                "monthly_egress": "2TB",
                "azs": 2,
                "estimated_cost": "$1300-1500/mo",
                "breakdown": "Base: $993 + Variable: $400"
            },

            "enterprise_deployment": {
                "vpcs": 25,
                "monthly_egress": "10TB",
                "azs": 3,
                "estimated_cost": "$3000-3500/mo",
                "breakdown": "Base: $1850 + Variable: $1500"
            }
        }
    },

    "implementation_steps": [
        {
            "phase": "1. Design",
            "steps": [
                "Document existing VPC CIDRs and egress patterns",
                "Design inspection VPC CIDR (avoid conflicts)",
                "Plan firewall rule groups (allow lists, deny lists)",
                "Size Network Firewall capacity (based on traffic)",
                "Determine HA requirements (2 vs 3 AZs)"
            ]
        },
        {
            "phase": "2. Build Inspection VPC",
            "steps": [
                "Create inspection VPC with planned CIDR",
                "Create subnets (TGW, Firewall, NAT, IGW per AZ)",
                "Deploy Internet Gateway",
                "Deploy NAT Gateways (one per AZ)",
                "Create Network Firewall",
                "Configure firewall rule groups",
                "Configure route tables"
            ]
        },
        {
            "phase": "3. Connect Transit Gateway",
            "steps": [
                "Create Transit Gateway (if not exists)",
                "Attach inspection VPC to TGW",
                "Attach workload VPCs to TGW",
                "Create TGW route tables (workload, inspection)",
                "Configure TGW routes (0.0.0.0/0 to inspection)",
                "Test TGW connectivity"
            ]
        },
        {
            "phase": "4. Test & Validate",
            "steps": [
                "Test outbound connectivity from one workload VPC",
                "Verify traffic flows through firewall (check logs)",
                "Test domain filtering rules",
                "Test IDS alert generation",
                "Verify NAT Gateway translation (check egress IP)",
                "Performance test (latency, throughput)"
            ]
        },
        {
            "phase": "5. Migrate Workload VPCs",
            "steps": [
                "Update workload VPC route tables (staged rollout)",
                "Remove old NAT Gateways (after validation)",
                "Update security group rules if needed",
                "Monitor logs for issues",
                "Decommission per-VPC NAT Gateways"
            ]
        },
        {
            "phase": "6. Operationalize",
            "steps": [
                "Set up CloudWatch alarms (NFW metrics, TGW bandwidth)",
                "Configure log retention policies",
                "Create runbooks for common issues",
                "Train team on firewall rule management",
                "Document architecture and routing",
                "Set up regular rule review process"
            ]
        }
    ],

    "soc2_controls_addressed": {
        "CC6.6": {
            "control": "Logical access security measures",
            "how_addressed": "Centralized egress control with inspection"
        },
        "CC6.7": {
            "control": "Transmission security",
            "how_addressed": "Encrypted traffic inspection, TLS/SNI validation"
        },
        "CC6.8": {
            "control": "Prevent/detect malicious software",
            "how_addressed": "IDS/IPS signatures, threat intelligence feeds"
        },
        "CC7.2": {
            "control": "System monitoring",
            "how_addressed": "Centralized logging of all internet traffic"
        },
        "CC7.3": {
            "control": "Infrastructure evaluation",
            "how_addressed": "Network Firewall metrics, flow logs for analysis"
        }
    },

    "alternatives": {
        "third_party_firewalls": {
            "description": "Palo Alto, Fortinet, Check Point via Gateway Load Balancer",
            "when_to_use": [
                "Advanced features needed (App-ID, User-ID)",
                "Existing enterprise licensing",
                "Need unified management with on-prem firewalls"
            ],
            "cost": "Typically higher ($2000-5000/mo)",
            "complexity": "Higher (appliance management)"
        },

        "distributed_inspection": {
            "description": "NFW in each VPC (no Transit Gateway)",
            "when_to_use": [
                "VPCs don't communicate",
                "Isolated workloads",
                "No centralized management needed"
            ],
            "cost": "Similar per-VPC but multiplied",
            "complexity": "Lower per-VPC, higher overall management"
        },

        "proxy_based": {
            "description": "Squid, NGINX proxy in inspection VPC",
            "when_to_use": [
                "HTTP/HTTPS only",
                "URL filtering primary requirement",
                "Cost optimization critical"
            ],
            "cost": "Lower ($200-400/mo)",
            "complexity": "High (self-managed instances)"
        }
    },

    "best_practices": [
        "Deploy NAT Gateways in multiple AZs for high availability",
        "Use separate firewall rule groups per environment (prod, dev, test)",
        "Enable stateful session tracking for better inspection",
        "Implement deny-by-default with explicit allow lists",
        "Use AWS Firewall Manager for multi-account rule deployment",
        "Configure CloudWatch alarms for firewall rejected packets",
        "Archive firewall logs to S3 for long-term retention (7+ years SOC 2)",
        "Regularly review and update IDS signatures",
        "Test failover scenarios (AZ failure, firewall endpoint failure)",
        "Document IP address planning and CIDR allocation",
        "Use VPC Flow Logs in addition to firewall logs",
        "Implement change management process for firewall rules",
        "Monitor data processing costs (can spike unexpectedly)",
        "Consider separate inspection VPCs per region",
        "Use AWS Resource Access Manager for TGW sharing across accounts"
    ],

    "common_mistakes": [
        "Forgetting return traffic routing (asymmetric routing issues)",
        "Not accounting for cross-AZ data transfer costs",
        "Single NAT Gateway without HA (AZ failure = outage)",
        "Undersizing firewall capacity (throughput limits)",
        "Not testing failover before production deployment",
        "Overly permissive firewall rules (defeats purpose)",
        "Not monitoring firewall capacity metrics",
        "Forgetting to update TGW route tables for new VPCs",
        "Not planning for IP address exhaustion in firewall subnet",
        "Missing documentation for future troubleshooting"
    ],

    "monitoring_metrics": {
        "network_firewall": [
            "Dropped packets per second",
            "Passed packets per second",
            "Rule evaluation time",
            "Connection tracking table usage",
            "Stateful rule rejections"
        ],
        "transit_gateway": [
            "Bytes in/out",
            "Packets in/out",
            "Packet drop count (blackhole routes)",
            "Attachment bandwidth usage"
        ],
        "nat_gateways": [
            "Active connections",
            "Bytes processed",
            "Packets dropped",
            "Error port allocation"
        ]
    },

    "references": [
        "AWS Network Firewall Documentation: https://docs.aws.amazon.com/network-firewall/",
        "AWS Transit Gateway Centralized Egress: https://aws.amazon.com/blogs/networking-and-content-delivery/",
        "SOC 2 Network Security Controls: AICPA Trust Services Criteria",
        "AWS Best Practices for VPC Design: https://docs.aws.amazon.com/vpc/latest/userguide/",
        "Suricata IDS Rules: https://suricata.io/",
    ]
}


# Export for inclusion in architecture patterns
def get_central_egress_inspection_pattern():
    """Get the central egress and inspection pattern."""
    return CENTRAL_EGRESS_INSPECTION_PATTERN
