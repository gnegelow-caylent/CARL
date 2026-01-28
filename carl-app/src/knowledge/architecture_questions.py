"""
Architecture Questions Framework

Contextual questions for intelligent architecture recommendations.
Supports multi-turn conversations with weighted scoring.
"""

from typing import Dict, Any

ARCHITECTURE_QUESTIONS: Dict[str, Any] = {
    "database": {
        "questions": [
            {
                "id": "use_case",
                "text": "What's your primary use case?",
                "options": ["user_profiles", "product_catalog", "analytics", "time_series", "documents", "caching"],
                "weight": 10
            },
            {
                "id": "data_volume",
                "text": "What's your expected data volume?",
                "options": ["<1gb", "1-100gb", "100gb-1tb", ">1tb"],
                "weight": 8
            },
            {
                "id": "query_pattern",
                "text": "What's your query pattern?",
                "options": ["simple_lookups", "complex_joins", "aggregations", "full_text_search", "mixed"],
                "weight": 9
            },
            {
                "id": "consistency",
                "text": "What consistency requirements do you have?",
                "options": ["eventual_ok", "strong_required", "depends_on_operation"],
                "weight": 7
            },
            {
                "id": "availability",
                "text": "What availability do you need?",
                "options": ["99.9%", "99.95%", "99.99%", "multi_region"],
                "weight": 8
            },
            {
                "id": "budget",
                "text": "What's your monthly database budget?",
                "options": ["<100", "100-500", "500-2000", ">2000"],
                "weight": 6
            },
            {
                "id": "team_experience",
                "text": "What's your team's database experience?",
                "options": ["beginner", "intermediate", "advanced", "expert"],
                "weight": 5
            }
        ],
        "recommendation_logic": {
            "DynamoDB": {
                "use_case": {"user_profiles": 10, "product_catalog": 8, "caching": 9, "time_series": 7},
                "data_volume": {"<1gb": 10, "1-100gb": 10, "100gb-1tb": 9, ">1tb": 8},
                "query_pattern": {"simple_lookups": 10, "aggregations": 5, "complex_joins": 2},
                "consistency": {"eventual_ok": 10, "strong_required": 8},
                "availability": {"99.9%": 9, "99.95%": 10, "99.99%": 10, "multi_region": 10},
                "budget": {"<100": 10, "100-500": 9, "500-2000": 7},
                "team_experience": {"beginner": 8, "intermediate": 9, "advanced": 10}
            },
            "RDS PostgreSQL": {
                "use_case": {"user_profiles": 8, "product_catalog": 9, "analytics": 8, "documents": 7},
                "data_volume": {"<1gb": 8, "1-100gb": 10, "100gb-1tb": 9, ">1tb": 7},
                "query_pattern": {"complex_joins": 10, "aggregations": 9, "simple_lookups": 7, "full_text_search": 6},
                "consistency": {"strong_required": 10, "eventual_ok": 8},
                "availability": {"99.9%": 8, "99.95%": 9, "99.99%": 7},
                "budget": {"<100": 6, "100-500": 9, "500-2000": 10, ">2000": 10},
                "team_experience": {"intermediate": 10, "advanced": 10, "expert": 10}
            },
            "Aurora PostgreSQL": {
                "use_case": {"user_profiles": 9, "product_catalog": 10, "analytics": 9, "documents": 8},
                "data_volume": {"100gb-1tb": 10, ">1tb": 10, "1-100gb": 8},
                "query_pattern": {"complex_joins": 10, "aggregations": 10, "simple_lookups": 8},
                "consistency": {"strong_required": 10, "depends_on_operation": 9},
                "availability": {"99.95%": 10, "99.99%": 10, "multi_region": 10},
                "budget": {"500-2000": 10, ">2000": 10, "100-500": 7},
                "team_experience": {"advanced": 10, "expert": 10, "intermediate": 8}
            },
            "DocumentDB": {
                "use_case": {"documents": 10, "product_catalog": 8, "user_profiles": 7},
                "data_volume": {"1-100gb": 10, "100gb-1tb": 10, ">1tb": 9},
                "query_pattern": {"simple_lookups": 9, "aggregations": 8, "full_text_search": 7},
                "consistency": {"eventual_ok": 9, "strong_required": 7},
                "availability": {"99.9%": 9, "99.95%": 10, "99.99%": 9},
                "budget": {"100-500": 9, "500-2000": 10, ">2000": 10},
                "team_experience": {"intermediate": 9, "advanced": 10, "beginner": 6}
            }
        },
        "options": {
            "DynamoDB": {
                "description": "Fully managed NoSQL database with single-digit millisecond latency",
                "monthly_cost_range": (25.00, 500.00),
                "pros": [
                    "Scales automatically without downtime",
                    "Pay only for what you use",
                    "Built-in backup and point-in-time recovery",
                    "Global tables for multi-region"
                ],
                "cons": [
                    "Query patterns must be planned upfront",
                    "Limited aggregation capabilities",
                    "Can't do complex joins"
                ]
            },
            "RDS PostgreSQL": {
                "description": "Managed relational database with full SQL support",
                "monthly_cost_range": (150.00, 2000.00),
                "pros": [
                    "Full SQL with complex queries and joins",
                    "ACID compliance built-in",
                    "Familiar for most developers",
                    "Extensive ecosystem and tools"
                ],
                "cons": [
                    "Requires capacity planning",
                    "Read replicas cost extra",
                    "More operational overhead than DynamoDB"
                ]
            },
            "Aurora PostgreSQL": {
                "description": "MySQL/PostgreSQL-compatible with 5x performance and high availability",
                "monthly_cost_range": (300.00, 5000.00),
                "pros": [
                    "Auto-scales storage up to 128 TB",
                    "Up to 15 read replicas",
                    "Fast failover (< 30 seconds)",
                    "Global database option"
                ],
                "cons": [
                    "Higher base cost than RDS",
                    "Requires more expertise to optimize",
                    "Not available in all regions"
                ]
            },
            "DocumentDB": {
                "description": "MongoDB-compatible document database",
                "monthly_cost_range": (200.00, 3000.00),
                "pros": [
                    "MongoDB API compatibility",
                    "Flexible schema for evolving data",
                    "Good for nested/hierarchical data",
                    "Auto-scaling storage"
                ],
                "cons": [
                    "Not 100% MongoDB compatible",
                    "Higher cost than DynamoDB",
                    "Limited to specific use cases"
                ]
            }
        }
    },

    "vpc": {
        "questions": [
            {
                "id": "workload_type",
                "text": "What type of workload are you running?",
                "options": ["web_app", "microservices", "data_processing", "hybrid_cloud", "machine_learning"],
                "weight": 10
            },
            {
                "id": "internet_access",
                "text": "Do your resources need internet access?",
                "options": ["public_facing", "outbound_only", "no_internet", "mixed"],
                "weight": 9
            },
            {
                "id": "compliance_requirements",
                "text": "What are your compliance requirements?",
                "options": ["none", "soc2", "hipaa", "pci_dss", "multiple"],
                "weight": 8
            },
            {
                "id": "scale",
                "text": "How many resources will you have?",
                "options": ["<50", "50-200", "200-1000", ">1000"],
                "weight": 7
            },
            {
                "id": "multi_region",
                "text": "Do you need multiple regions?",
                "options": ["single_region", "active_passive", "active_active"],
                "weight": 8
            },
            {
                "id": "on_premises",
                "text": "Do you have on-premises connectivity needs?",
                "options": ["no", "vpn_sufficient", "direct_connect_required"],
                "weight": 7
            }
        ],
        "recommendation_logic": {
            "Single VPC with Public/Private Subnets": {
                "workload_type": {"web_app": 10, "microservices": 7, "data_processing": 6},
                "internet_access": {"public_facing": 10, "mixed": 9, "outbound_only": 7},
                "compliance_requirements": {"none": 9, "soc2": 8},
                "scale": {"<50": 10, "50-200": 9, "200-1000": 6},
                "multi_region": {"single_region": 10},
                "on_premises": {"no": 10, "vpn_sufficient": 7}
            },
            "Multi-Tier VPC (Public/Private/Data)": {
                "workload_type": {"web_app": 9, "microservices": 10, "data_processing": 8},
                "internet_access": {"mixed": 10, "public_facing": 9, "outbound_only": 8},
                "compliance_requirements": {"soc2": 10, "hipaa": 9, "pci_dss": 10},
                "scale": {"50-200": 10, "200-1000": 10, ">1000": 9},
                "multi_region": {"single_region": 10, "active_passive": 8},
                "on_premises": {"no": 9, "vpn_sufficient": 10}
            },
            "Hub-and-Spoke with Transit Gateway": {
                "workload_type": {"microservices": 10, "hybrid_cloud": 10, "data_processing": 9},
                "internet_access": {"mixed": 10, "outbound_only": 10},
                "compliance_requirements": {"soc2": 9, "hipaa": 10, "multiple": 10},
                "scale": {"200-1000": 10, ">1000": 10},
                "multi_region": {"active_passive": 10, "active_active": 10},
                "on_premises": {"direct_connect_required": 10, "vpn_sufficient": 8}
            },
            "Isolated VPCs with VPC Peering": {
                "workload_type": {"microservices": 8, "data_processing": 9, "machine_learning": 10},
                "internet_access": {"no_internet": 10, "outbound_only": 8, "mixed": 6},
                "compliance_requirements": {"hipaa": 10, "pci_dss": 10, "multiple": 9},
                "scale": {"50-200": 8, "200-1000": 9, ">1000": 7},
                "multi_region": {"single_region": 9, "active_passive": 7},
                "on_premises": {"no": 10, "vpn_sufficient": 7}
            }
        },
        "options": {
            "Single VPC with Public/Private Subnets": {
                "description": "Standard VPC with public and private subnets across 2-3 AZs",
                "monthly_cost_range": (50.00, 200.00),
                "pros": [
                    "Simple to set up and manage",
                    "Good for most web applications",
                    "Clear separation between public and private resources",
                    "Lower cost than complex architectures"
                ],
                "cons": [
                    "Limited isolation between workloads",
                    "NAT Gateway costs can add up",
                    "Not ideal for strict compliance"
                ]
            },
            "Multi-Tier VPC (Public/Private/Data)": {
                "description": "Three-tier architecture with dedicated data subnet layer",
                "monthly_cost_range": (150.00, 500.00),
                "pros": [
                    "Strong separation of concerns",
                    "Database isolation from app tier",
                    "Good for compliance requirements",
                    "Scalable architecture"
                ],
                "cons": [
                    "More complex routing",
                    "Additional NAT Gateway costs",
                    "Requires more CIDR planning"
                ]
            },
            "Hub-and-Spoke with Transit Gateway": {
                "description": "Central hub VPC with multiple spoke VPCs connected via Transit Gateway",
                "monthly_cost_range": (500.00, 3000.00),
                "pros": [
                    "Centralized egress/ingress control",
                    "Scales to hundreds of VPCs",
                    "Simplifies hybrid connectivity",
                    "Shared services model"
                ],
                "cons": [
                    "Transit Gateway costs (~$50/month base + data transfer)",
                    "Complex to set up initially",
                    "Requires dedicated networking team"
                ]
            },
            "Isolated VPCs with VPC Peering": {
                "description": "Separate VPCs for each workload with direct peering connections",
                "monthly_cost_range": (100.00, 800.00),
                "pros": [
                    "Maximum isolation between workloads",
                    "No central point of failure",
                    "Simplified security policies",
                    "Good for compliance"
                ],
                "cons": [
                    "Peering connections don't scale (max 125 per VPC)",
                    "No transitive routing",
                    "More complex to manage at scale"
                ]
            }
        }
    },

    "compute": {
        "questions": [
            {
                "id": "application_type",
                "text": "What type of application are you running?",
                "options": ["web_api", "batch_processing", "real_time_processing", "container_app", "serverless"],
                "weight": 10
            },
            {
                "id": "scaling_pattern",
                "text": "What's your scaling pattern?",
                "options": ["steady_load", "predictable_spikes", "unpredictable_bursts", "always_on"],
                "weight": 9
            },
            {
                "id": "compute_requirements",
                "text": "What are your compute requirements?",
                "options": ["cpu_intensive", "memory_intensive", "gpu_required", "balanced", "minimal"],
                "weight": 8
            },
            {
                "id": "deployment_frequency",
                "text": "How often do you deploy?",
                "options": ["multiple_per_day", "daily", "weekly", "monthly"],
                "weight": 7
            },
            {
                "id": "state_management",
                "text": "Does your app maintain state?",
                "options": ["stateless", "session_state", "persistent_state"],
                "weight": 8
            },
            {
                "id": "cold_start_tolerance",
                "text": "Can you tolerate cold starts?",
                "options": ["yes_fine", "occasional_ok", "never_acceptable"],
                "weight": 6
            }
        ],
        "recommendation_logic": {
            "Lambda": {
                "application_type": {"serverless": 10, "web_api": 9, "batch_processing": 8},
                "scaling_pattern": {"unpredictable_bursts": 10, "predictable_spikes": 9, "steady_load": 5},
                "compute_requirements": {"minimal": 10, "balanced": 8, "cpu_intensive": 4},
                "deployment_frequency": {"multiple_per_day": 10, "daily": 9, "weekly": 8},
                "state_management": {"stateless": 10, "session_state": 6, "persistent_state": 3},
                "cold_start_tolerance": {"yes_fine": 10, "occasional_ok": 8, "never_acceptable": 2}
            },
            "ECS Fargate": {
                "application_type": {"container_app": 10, "web_api": 9, "real_time_processing": 8},
                "scaling_pattern": {"predictable_spikes": 10, "unpredictable_bursts": 9, "steady_load": 8},
                "compute_requirements": {"balanced": 10, "cpu_intensive": 9, "memory_intensive": 10},
                "deployment_frequency": {"multiple_per_day": 9, "daily": 10, "weekly": 8},
                "state_management": {"stateless": 9, "session_state": 10, "persistent_state": 7},
                "cold_start_tolerance": {"occasional_ok": 10, "never_acceptable": 9, "yes_fine": 8}
            },
            "EKS": {
                "application_type": {"container_app": 10, "microservices": 10, "real_time_processing": 9},
                "scaling_pattern": {"steady_load": 10, "predictable_spikes": 10, "unpredictable_bursts": 8},
                "compute_requirements": {"cpu_intensive": 10, "memory_intensive": 10, "gpu_required": 9},
                "deployment_frequency": {"multiple_per_day": 10, "daily": 10, "weekly": 8},
                "state_management": {"session_state": 10, "persistent_state": 10, "stateless": 9},
                "cold_start_tolerance": {"never_acceptable": 10, "occasional_ok": 9}
            },
            "EC2 with Auto Scaling": {
                "application_type": {"web_api": 8, "batch_processing": 9, "real_time_processing": 8},
                "scaling_pattern": {"predictable_spikes": 10, "steady_load": 10, "always_on": 10},
                "compute_requirements": {"cpu_intensive": 10, "memory_intensive": 10, "gpu_required": 10},
                "deployment_frequency": {"weekly": 10, "monthly": 10, "daily": 7},
                "state_management": {"persistent_state": 10, "session_state": 9, "stateless": 7},
                "cold_start_tolerance": {"never_acceptable": 10, "occasional_ok": 8}
            }
        },
        "options": {
            "Lambda": {
                "description": "Serverless compute - pay only for execution time",
                "monthly_cost_range": (10.00, 500.00),
                "pros": [
                    "Zero infrastructure management",
                    "Auto-scales instantly",
                    "Pay per request (no idle costs)",
                    "Integrated with AWS services"
                ],
                "cons": [
                    "15-minute max execution time",
                    "Cold start latency",
                    "Limited to 10 GB memory",
                    "Complex debugging"
                ]
            },
            "ECS Fargate": {
                "description": "Serverless containers - no cluster management",
                "monthly_cost_range": (100.00, 2000.00),
                "pros": [
                    "No server management",
                    "Run any containerized app",
                    "Integrated load balancing",
                    "Predictable pricing"
                ],
                "cons": [
                    "Higher cost than EC2 for steady workloads",
                    "Limited instance type flexibility",
                    "Slight cold start delay"
                ]
            },
            "EKS": {
                "description": "Managed Kubernetes for container orchestration",
                "monthly_cost_range": (300.00, 5000.00),
                "pros": [
                    "Full Kubernetes capabilities",
                    "Portable across clouds",
                    "Rich ecosystem",
                    "Advanced deployment strategies"
                ],
                "cons": [
                    "$0.10/hour cluster cost ($73/month)",
                    "Steep learning curve",
                    "Requires Kubernetes expertise",
                    "More operational overhead"
                ]
            },
            "EC2 with Auto Scaling": {
                "description": "Traditional VMs with automatic scaling",
                "monthly_cost_range": (50.00, 3000.00),
                "pros": [
                    "Full control over instances",
                    "Cost-effective for steady workloads",
                    "Supports all instance types",
                    "Can use Spot instances"
                ],
                "cons": [
                    "Requires OS and patch management",
                    "Manual scaling configuration",
                    "Pay for idle capacity",
                    "More operational overhead"
                ]
            }
        }
    },

    "storage": {
        "questions": [
            {
                "id": "data_type",
                "text": "What type of data are you storing?",
                "options": ["static_assets", "user_uploads", "logs", "backups", "archives", "shared_files"],
                "weight": 10
            },
            {
                "id": "access_pattern",
                "text": "How frequently will you access this data?",
                "options": ["constantly", "frequent", "occasional", "rare", "archive"],
                "weight": 9
            },
            {
                "id": "performance_needs",
                "text": "What performance do you need?",
                "options": ["milliseconds", "seconds", "minutes", "hours"],
                "weight": 8
            },
            {
                "id": "data_size",
                "text": "How much data will you store?",
                "options": ["<100gb", "100gb-1tb", "1-10tb", ">10tb"],
                "weight": 7
            },
            {
                "id": "concurrent_access",
                "text": "How many systems need concurrent access?",
                "options": ["1", "2-10", "10-100", ">100"],
                "weight": 7
            },
            {
                "id": "durability_requirements",
                "text": "What durability do you need?",
                "options": ["11_nines", "9_nines", "best_effort"],
                "weight": 8
            }
        ],
        "recommendation_logic": {
            "S3 Standard": {
                "data_type": {"static_assets": 10, "user_uploads": 10, "logs": 8, "backups": 7},
                "access_pattern": {"constantly": 10, "frequent": 10, "occasional": 9},
                "performance_needs": {"milliseconds": 10, "seconds": 10},
                "data_size": {"<100gb": 9, "100gb-1tb": 10, "1-10tb": 10, ">10tb": 10},
                "concurrent_access": {">100": 10, "10-100": 10, "2-10": 9, "1": 8},
                "durability_requirements": {"11_nines": 10, "9_nines": 10}
            },
            "S3 Glacier": {
                "data_type": {"archives": 10, "backups": 10, "logs": 7},
                "access_pattern": {"rare": 10, "archive": 10, "occasional": 5},
                "performance_needs": {"hours": 10, "minutes": 7, "seconds": 3},
                "data_size": {"1-10tb": 10, ">10tb": 10, "100gb-1tb": 9},
                "concurrent_access": {"1": 10, "2-10": 9},
                "durability_requirements": {"11_nines": 10, "9_nines": 10}
            },
            "EFS": {
                "data_type": {"shared_files": 10, "user_uploads": 8, "logs": 7},
                "access_pattern": {"frequent": 10, "constantly": 10, "occasional": 8},
                "performance_needs": {"milliseconds": 10, "seconds": 10},
                "data_size": {"100gb-1tb": 10, "1-10tb": 10, "<100gb": 8},
                "concurrent_access": {"10-100": 10, ">100": 10, "2-10": 10},
                "durability_requirements": {"11_nines": 10, "9_nines": 10}
            },
            "FSx for Windows": {
                "data_type": {"shared_files": 10, "user_uploads": 8},
                "access_pattern": {"constantly": 10, "frequent": 10},
                "performance_needs": {"milliseconds": 10, "seconds": 9},
                "data_size": {"100gb-1tb": 10, "1-10tb": 10, ">10tb": 9},
                "concurrent_access": {"10-100": 10, ">100": 10, "2-10": 9},
                "durability_requirements": {"11_nines": 10, "9_nines": 10}
            }
        },
        "options": {
            "S3 Standard": {
                "description": "Object storage with 99.99% availability and 11 nines durability",
                "monthly_cost_range": (23.00, 2300.00),
                "pros": [
                    "Unlimited scalability",
                    "99.999999999% durability",
                    "Integrated with all AWS services",
                    "Lifecycle policies to save cost"
                ],
                "cons": [
                    "Not a file system (no mounting)",
                    "Higher cost for frequent small files",
                    "Eventual consistency for overwrites"
                ]
            },
            "S3 Glacier": {
                "description": "Low-cost archive storage with retrieval times from minutes to hours",
                "monthly_cost_range": (4.00, 400.00),
                "pros": [
                    "Extremely low cost ($0.004/GB)",
                    "11 nines durability",
                    "Compliance and vault lock",
                    "Multiple retrieval options"
                ],
                "cons": [
                    "Retrieval takes minutes to hours",
                    "Retrieval costs apply",
                    "Not suitable for frequent access",
                    "Minimum 90-day storage commitment"
                ]
            },
            "EFS": {
                "description": "Fully managed NFS file system for Linux workloads",
                "monthly_cost_range": (100.00, 3000.00),
                "pros": [
                    "True file system (mount with NFS)",
                    "Auto-scales storage",
                    "Concurrent access from thousands of instances",
                    "Bursting and provisioned throughput"
                ],
                "cons": [
                    "Higher cost than S3 ($0.30/GB vs $0.023/GB)",
                    "Linux/POSIX only",
                    "Performance depends on size",
                    "Not suitable for Windows workloads"
                ]
            },
            "FSx for Windows": {
                "description": "Fully managed Windows file system with SMB protocol",
                "monthly_cost_range": (150.00, 5000.00),
                "pros": [
                    "Native Windows file system",
                    "SMB protocol support",
                    "Active Directory integration",
                    "Sub-millisecond latency"
                ],
                "cons": [
                    "Windows only",
                    "Higher cost than EFS",
                    "Requires capacity provisioning",
                    "More complex setup"
                ]
            }
        }
    },

    "application": {
        "questions": [
            {
                "id": "app_architecture",
                "text": "What's your application architecture?",
                "options": ["monolith", "microservices", "serverless", "hybrid"],
                "weight": 10
            },
            {
                "id": "traffic_pattern",
                "text": "What's your traffic pattern?",
                "options": ["steady", "spiky", "unpredictable", "batch"],
                "weight": 9
            },
            {
                "id": "protocol",
                "text": "What protocol does your app use?",
                "options": ["http_https", "websocket", "grpc", "tcp_udp"],
                "weight": 8
            },
            {
                "id": "ssl_termination",
                "text": "Where do you want SSL termination?",
                "options": ["load_balancer", "application", "both"],
                "weight": 7
            },
            {
                "id": "global_presence",
                "text": "Do you need global presence?",
                "options": ["single_region", "multi_region", "global_cdn"],
                "weight": 8
            },
            {
                "id": "api_management",
                "text": "Do you need API management features?",
                "options": ["basic_routing", "rate_limiting", "full_api_gateway", "not_needed"],
                "weight": 7
            }
        ],
        "recommendation_logic": {
            "ALB + CloudFront": {
                "app_architecture": {"monolith": 10, "microservices": 9, "hybrid": 10},
                "traffic_pattern": {"steady": 10, "spiky": 9, "unpredictable": 8},
                "protocol": {"http_https": 10, "websocket": 9},
                "ssl_termination": {"load_balancer": 10, "both": 9},
                "global_presence": {"global_cdn": 10, "multi_region": 9, "single_region": 7},
                "api_management": {"basic_routing": 10, "not_needed": 10}
            },
            "API Gateway + Lambda": {
                "app_architecture": {"serverless": 10, "microservices": 9, "hybrid": 7},
                "traffic_pattern": {"unpredictable": 10, "spiky": 10, "steady": 6},
                "protocol": {"http_https": 10, "websocket": 9, "grpc": 5},
                "ssl_termination": {"load_balancer": 10, "both": 9},
                "global_presence": {"single_region": 10, "multi_region": 8, "global_cdn": 7},
                "api_management": {"full_api_gateway": 10, "rate_limiting": 10, "basic_routing": 8}
            },
            "NLB": {
                "app_architecture": {"monolith": 9, "microservices": 8, "hybrid": 9},
                "traffic_pattern": {"steady": 10, "spiky": 9, "batch": 10},
                "protocol": {"tcp_udp": 10, "grpc": 9, "http_https": 6},
                "ssl_termination": {"application": 10, "both": 8},
                "global_presence": {"single_region": 10, "multi_region": 8},
                "api_management": {"not_needed": 10, "basic_routing": 7}
            },
            "AppSync": {
                "app_architecture": {"serverless": 10, "microservices": 8},
                "traffic_pattern": {"unpredictable": 9, "spiky": 10, "steady": 7},
                "protocol": {"http_https": 10, "websocket": 10},
                "ssl_termination": {"load_balancer": 10},
                "global_presence": {"single_region": 10, "multi_region": 9, "global_cdn": 8},
                "api_management": {"full_api_gateway": 10, "rate_limiting": 9}
            }
        },
        "options": {
            "ALB + CloudFront": {
                "description": "Application Load Balancer with CloudFront CDN for global distribution",
                "monthly_cost_range": (50.00, 1000.00),
                "pros": [
                    "Global edge caching reduces latency",
                    "Layer 7 load balancing with path-based routing",
                    "DDoS protection with Shield",
                    "Easy SSL certificate management"
                ],
                "cons": [
                    "Two services to manage (ALB + CloudFront)",
                    "CloudFront costs based on data transfer",
                    "Cache invalidation complexity"
                ]
            },
            "API Gateway + Lambda": {
                "description": "Fully managed API with serverless compute",
                "monthly_cost_range": (10.00, 500.00),
                "pros": [
                    "Serverless (no infrastructure)",
                    "Built-in throttling and rate limiting",
                    "Request/response transformation",
                    "API versioning and stages"
                ],
                "cons": [
                    "29-second timeout limit",
                    "Higher latency than ALB",
                    "Can get expensive at scale ($3.50 per million)",
                    "Limited WebSocket support"
                ]
            },
            "NLB": {
                "description": "Network Load Balancer for ultra-low latency and high throughput",
                "monthly_cost_range": (25.00, 500.00),
                "pros": [
                    "Handles millions of requests/second",
                    "Ultra-low latency (microseconds)",
                    "Static IP addresses",
                    "Preserves source IP"
                ],
                "cons": [
                    "Layer 4 only (no HTTP features)",
                    "No built-in SSL termination",
                    "No path-based routing",
                    "Requires health check configuration"
                ]
            },
            "AppSync": {
                "description": "Managed GraphQL API service",
                "monthly_cost_range": (20.00, 1000.00),
                "pros": [
                    "Built-in GraphQL support",
                    "Real-time subscriptions",
                    "Offline sync capabilities",
                    "Direct integration with DynamoDB, Lambda, RDS"
                ],
                "cons": [
                    "GraphQL only (not REST)",
                    "Learning curve for GraphQL",
                    "Limited to AWS data sources",
                    "Can get expensive with subscriptions"
                ]
            }
        }
    }
}
