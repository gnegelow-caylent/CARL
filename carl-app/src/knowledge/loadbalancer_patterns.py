"""
Load Balancer Patterns for CARL
Provides decision frameworks for AWS Load Balancer type selection, target groups, and security patterns.
"""

from typing import List, Dict, Any
from .models import (
    DecisionPattern,
    DecisionOption,
    DecisionCriteria,
    ProConsList,
    SOC2Control
)


def get_loadbalancer_type_pattern() -> DecisionPattern:
    """
    Pattern for selecting load balancer type (ALB, NLB, GWLB, CLB).
    Covers protocol requirements, performance needs, and feature comparisons.
    """
    return DecisionPattern(
        pattern_id="loadbalancer-type-selection",
        name="AWS Load Balancer Type Selection",
        category="networking",
        subcategory="loadbalancer",
        description="Framework for selecting the appropriate AWS load balancer type (Application, Network, Gateway, or Classic) based on protocol requirements, performance needs, and feature requirements.",
        decision_criteria=[
            DecisionCriteria(
                criterion="Protocol Requirements",
                weight=0.30,
                considerations=[
                    "What protocols do you need to support (HTTP/HTTPS, TCP, UDP)?",
                    "Do you need WebSocket support?",
                    "Do you need gRPC or HTTP/2 support?",
                    "Do you need Layer 4 or Layer 7 load balancing?"
                ]
            ),
            DecisionCriteria(
                criterion="Performance and Scale",
                weight=0.25,
                considerations=[
                    "What throughput do you need (requests/connections per second)?",
                    "Do you need ultra-low latency?",
                    "Do you need to preserve source IP addresses?",
                    "Do you need to handle millions of requests per second?"
                ]
            ),
            DecisionCriteria(
                criterion="Feature Requirements",
                weight=0.20,
                considerations=[
                    "Do you need content-based routing?",
                    "Do you need host-based or path-based routing?",
                    "Do you need Lambda or IP address targets?",
                    "Do you need SSL/TLS termination?"
                ]
            ),
            DecisionCriteria(
                criterion="Cost Optimization",
                weight=0.15,
                considerations=[
                    "What is your load balancer budget?",
                    "What is your expected traffic volume?",
                    "Do you need cost-effective solution for high throughput?",
                    "Can you use fixed cost model vs per-request?"
                ]
            ),
            DecisionCriteria(
                criterion="Security Requirements",
                weight=0.10,
                considerations=[
                    "Do you need WAF integration?",
                    "Do you need SSL/TLS termination?",
                    "Do you need advanced security features?",
                    "Do you need to inspect network traffic?"
                ]
            )
        ],
        options=[
            DecisionOption(
                option_id="loadbalancer-application-alb",
                name="Application Load Balancer (ALB)",
                description="Layer 7 load balancer for HTTP/HTTPS traffic with content-based routing, host/path routing, and native AWS service integrations.",
                pros_cons=ProConsList(
                    pros=[
                        "Content-based routing (host, path, headers, query strings)",
                        "WebSocket and HTTP/2 support",
                        "Native integration with ECS, EKS, Lambda",
                        "SSL/TLS termination with SNI support",
                        "WAF integration for security",
                        "Authentication with Cognito or OIDC",
                        "Fixed IP addresses via Global Accelerator",
                        "Request tracing and detailed metrics"
                    ],
                    cons=[
                        "Higher cost than NLB for simple TCP workloads",
                        "Higher latency than NLB (Layer 7 processing)",
                        "Cannot preserve client IP without proxy protocol",
                        "HTTP/HTTPS only (no arbitrary TCP/UDP)",
                        "Not suitable for ultra-low latency requirements",
                        "More complex configuration for advanced routing"
                    ]
                ),
                estimated_cost="$22/month per LB + $0.008/LCU-hour (LCU = processed bytes, connections, rules); typical: $50-500/month",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC6.1",
                        description="Access control - host and path-based routing with authentication",
                        implementation_guidance="Configure listener rules for routing; implement Cognito or OIDC authentication; use security groups to restrict access; enable access logs for audit"
                    ),
                    SOC2Control(
                        control_id="CC6.7",
                        description="Encryption in transit - SSL/TLS termination",
                        implementation_guidance="Configure HTTPS listeners; use ACM for certificate management; enforce TLS 1.2+; implement SSL policies; enable HTTP to HTTPS redirect"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Security monitoring - WAF and access logging",
                        implementation_guidance="Integrate with AWS WAF; enable access logging to S3; monitor 4xx/5xx errors; configure CloudWatch alarms; export logs for analysis"
                    ),
                    SOC2Control(
                        control_id="CC9.1",
                        description="High availability - multi-AZ load distribution",
                        implementation_guidance="Deploy targets across multiple AZs; enable cross-zone load balancing; monitor target health; configure health checks; implement auto-scaling"
                    )
                ]
            ),
            DecisionOption(
                option_id="loadbalancer-network-nlb",
                name="Network Load Balancer (NLB)",
                description="Layer 4 load balancer for TCP/UDP/TLS traffic with ultra-low latency, high throughput, and source IP preservation.",
                pros_cons=ProConsList(
                    pros=[
                        "Ultra-low latency (<100 microseconds)",
                        "Extremely high throughput (millions of requests/second)",
                        "Preserves source IP addresses",
                        "Static IP addresses (one per AZ)",
                        "Supports TCP, UDP, and TLS protocols",
                        "Fixed cost model regardless of connections",
                        "TLS termination with SNI support",
                        "PrivateLink endpoint service support"
                    ],
                    cons=[
                        "No content-based routing (Layer 4 only)",
                        "No WAF integration (use ALB in front if needed)",
                        "No native authentication support",
                        "Limited routing capabilities vs ALB",
                        "More expensive than ALB for low-traffic applications",
                        "No Lambda targets",
                        "Less detailed CloudWatch metrics than ALB"
                    ]
                ),
                estimated_cost="$22/month per LB + $0.006/NLCU-hour (NLCU = processed bytes, connections); typical: $50-300/month",
                implementation_complexity="Low-Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="High performance - ultra-low latency load balancing",
                        implementation_guidance="Configure static IPs per AZ; enable cross-zone load balancing; monitor connection count; configure appropriate health checks; track target health status"
                    ),
                    SOC2Control(
                        control_id="CC6.7",
                        description="Encryption - TLS termination at Layer 4",
                        implementation_guidance="Configure TLS listeners; use ACM certificates; implement TLS policies; enable connection logging; monitor TLS handshake errors"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Monitoring - connection and flow logs",
                        implementation_guidance="Enable VPC Flow Logs for traffic analysis; configure CloudWatch alarms for unhealthy targets; monitor connection counts; track processed bytes"
                    ),
                    SOC2Control(
                        control_id="CC6.2",
                        description="Network security - source IP preservation with security groups",
                        implementation_guidance="Configure target security groups for client IP access; use network ACLs; implement least-privilege network rules; document network architecture"
                    )
                ]
            ),
            DecisionOption(
                option_id="loadbalancer-gateway-gwlb",
                name="Gateway Load Balancer (GWLB)",
                description="Layer 3 gateway and load balancer for deploying, scaling, and managing third-party virtual appliances like firewalls and IDS/IPS.",
                pros_cons=ProConsList(
                    pros=[
                        "Transparent network gateway for appliances",
                        "Scales third-party appliances horizontally",
                        "Preserves original packet headers",
                        "Supports GENEVE protocol",
                        "Integrates with VPC routing",
                        "Enables centralized traffic inspection",
                        "Auto-scales appliance fleet"
                    ],
                    cons=[
                        "Specialized use case (not for typical application load balancing)",
                        "Requires compatible third-party appliances",
                        "More complex architecture and configuration",
                        "Higher cost for basic load balancing needs",
                        "Requires understanding of network routing",
                        "Limited to specific inspection/security use cases"
                    ]
                ),
                estimated_cost="$12.50/month per GWLB endpoint + $0.004/GB processed; typical: $200-2,000/month including appliances",
                implementation_complexity="Very High",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC7.3",
                        description="Traffic inspection - centralized security appliance deployment",
                        implementation_guidance="Deploy third-party security appliances; configure GWLB endpoints; implement VPC routing to GWLB; monitor appliance health; maintain appliance configurations"
                    ),
                    SOC2Control(
                        control_id="CC6.2",
                        description="Network security - inline traffic inspection",
                        implementation_guidance="Route traffic through security appliances; configure firewall rules; implement IDS/IPS policies; monitor security events; maintain appliance updates"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Security monitoring - appliance integration with logging",
                        implementation_guidance="Collect logs from security appliances; integrate with SIEM; configure alerting; monitor appliance performance; track security events"
                    )
                ]
            ),
            DecisionOption(
                option_id="loadbalancer-classic-clb",
                name="Classic Load Balancer (CLB) - Legacy",
                description="Previous generation load balancer supporting basic Layer 4 and Layer 7 load balancing. Not recommended for new applications.",
                pros_cons=ProConsList(
                    pros=[
                        "Simple configuration for basic load balancing",
                        "Supports EC2-Classic (legacy)",
                        "SSL termination available",
                        "Existing deployments may use it"
                    ],
                    cons=[
                        "Legacy service - not recommended for new deployments",
                        "Lacks advanced features of ALB/NLB",
                        "No content-based routing",
                        "No Lambda or IP targets",
                        "Less efficient than ALB/NLB",
                        "Higher cost for equivalent features",
                        "Limited monitoring and metrics",
                        "Will eventually be deprecated"
                    ]
                ),
                estimated_cost="$25/month per LB + $0.008/GB processed; typical: $50-400/month",
                implementation_complexity="Low",
                soc2_controls=[
                    SOC2Control(
                        control_id="MIGRATION",
                        description="Migration recommendation - migrate to ALB or NLB",
                        implementation_guidance="Plan migration to ALB (HTTP/HTTPS) or NLB (TCP/UDP); test new load balancer configuration; implement gradual cutover; decommission CLB after validation"
                    )
                ]
            )
        ],
        decision_framework="""
        LOAD BALANCER TYPE SELECTION FRAMEWORK:

        1. DETERMINE PROTOCOL REQUIREMENTS:
           - HTTP/HTTPS only → Application Load Balancer (ALB)
           - TCP/UDP/TLS → Network Load Balancer (NLB)
           - Traffic inspection/firewalls → Gateway Load Balancer (GWLB)
           - Legacy EC2-Classic → Migrate from CLB to ALB/NLB

        2. EVALUATE FEATURE NEEDS:
           - Content-based routing (path, host, headers) → ALB
           - WebSocket or HTTP/2 → ALB
           - Lambda targets → ALB
           - Simple Layer 4 routing → NLB
           - Third-party appliances → GWLB

        3. ASSESS PERFORMANCE REQUIREMENTS:
           - Ultra-low latency critical (<1ms) → NLB
           - High throughput (millions rps) → NLB
           - Need source IP preservation → NLB
           - Standard web application → ALB

        4. CONSIDER SECURITY REQUIREMENTS:
           - Need WAF integration → ALB
           - Need authentication (Cognito/OIDC) → ALB
           - SSL/TLS termination → ALB or NLB
           - Deep packet inspection → GWLB

        5. EVALUATE COST:
           - Variable low-volume HTTP traffic → ALB
           - High-volume TCP traffic → NLB
           - Simple TCP, cost-sensitive → NLB
           - Security appliance infrastructure → GWLB

        LOAD BALANCER COMPARISON:

        | Feature | ALB | NLB | GWLB | CLB |
        |---------|-----|-----|------|-----|
        | Layer | 7 (HTTP/HTTPS) | 4 (TCP/UDP/TLS) | 3 (Gateway) | 4/7 (Basic) |
        | Latency | ~2-5ms | <100μs | Low | ~2-5ms |
        | Protocols | HTTP, HTTPS, WS | TCP, UDP, TLS | GENEVE | HTTP, HTTPS, TCP |
        | Source IP Preservation | No* | Yes | Yes | No* |
        | Static IP | No** | Yes | N/A | No |
        | Content Routing | Yes | No | No | Limited |
        | WAF | Yes | No | N/A | No |
        | Lambda Targets | Yes | No | No | No |
        | Authentication | Yes | No | No | No |
        | Use Case | Web apps | High perf, IoT | Security appliances | Legacy |

        *Can use proxy protocol or X-Forwarded-For header
        **Can use Global Accelerator for static IPs

        USE CASE RECOMMENDATIONS:

        | Use Case | Best Load Balancer | Rationale |
        |----------|-------------------|-----------|
        | Web application | ALB | Content routing, WAF, authentication |
        | Microservices (HTTP) | ALB | Path-based routing, container integration |
        | REST API | ALB | HTTP/2, WebSocket, flexible routing |
        | Gaming backend | NLB | Ultra-low latency, TCP/UDP support |
        | IoT ingestion | NLB | High throughput, millions of connections |
        | VoIP/streaming | NLB | UDP support, low latency |
        | Database proxy | NLB | TCP, source IP preservation |
        | PrivateLink service | NLB | Static IP, service endpoint support |
        | Security appliances | GWLB | Traffic inspection, firewall scaling |
        | Centralized IDS/IPS | GWLB | Inline inspection, appliance scaling |

        COST OPTIMIZATION:

        ALB Cost Factors:
        - Fixed: $22/month per ALB
        - Variable: $0.008/LCU-hour
        - LCU = max(new connections/25, active connections/3000, bytes/1GB, rules)
        - Use fewer ALBs with listener rules vs multiple ALBs
        - Monitor LCU consumption to understand cost drivers

        NLB Cost Factors:
        - Fixed: $22/month per NLB
        - Variable: $0.006/NLCU-hour
        - NLCU = max(connections/800, bytes/1GB)
        - More cost-effective for high connection volume
        - Fixed IP pricing predictable

        GWLB Cost Factors:
        - Fixed: $12.50/month per endpoint
        - Variable: $0.004/GB processed
        - Plus cost of security appliances (EC2 instances)
        - Expensive but necessary for centralized security

        MIGRATION FROM CLB:

        To ALB:
        - Create ALB with same AZs
        - Configure target group with existing instances
        - Set up listener rules
        - Update DNS to point to ALB
        - Monitor and validate
        - Delete CLB

        To NLB:
        - Create NLB with same AZs
        - Configure target group with existing instances
        - Configure TCP/TLS listeners
        - Update security groups for source IP
        - Update DNS to point to NLB
        - Delete CLB

        SECURITY BEST PRACTICES:

        ALB Security:
        - Use HTTPS listeners with ACM certificates
        - Enforce TLS 1.2+ with security policies
        - Integrate with AWS WAF for application protection
        - Enable access logging for audit trails
        - Use Cognito or OIDC for authentication
        - Configure security groups to restrict access

        NLB Security:
        - Use TLS listeners for encrypted traffic
        - Configure target security groups for client IPs
        - Enable connection logging (VPC Flow Logs)
        - Use Network ACLs for additional protection
        - Monitor connection patterns for anomalies

        PERFORMANCE OPTIMIZATION:

        ALB:
        - Enable HTTP/2 for multiplexing
        - Use connection reuse (keep-alive)
        - Configure appropriate idle timeout
        - Enable cross-zone load balancing
        - Optimize health check intervals
        - Use target deregistration delay

        NLB:
        - Enable cross-zone load balancing for even distribution
        - Configure appropriate target health checks
        - Use proxy protocol v2 if source IP needed at target
        - Monitor connection resets
        - Optimize security group rules

        MONITORING:

        Key Metrics:
        - TargetResponseTime (ALB): Backend latency
        - ActiveConnectionCount (NLB): Current connections
        - ProcessedBytes: Data processed
        - HealthyHostCount: Available targets
        - UnHealthyHostCount: Failed targets
        - HTTPCode_Target_4XX/5XX: Backend errors
        - HTTPCode_ELB_4XX/5XX: Load balancer errors

        Alarms to Configure:
        - UnHealthyHostCount > 0
        - HTTPCode_ELB_5XX_Count > threshold
        - TargetResponseTime > p99 threshold
        - RejectedConnectionCount > 0 (NLB)
        """,
        real_world_examples=[
            "E-commerce platform used ALB with path-based routing to route /api/* to ECS and /admin/* to EC2, consolidating 3 load balancers into 1, saving $60/month",
            "Gaming company deployed NLB for game servers requiring <1ms latency, handling 2M concurrent TCP connections with source IP preservation for geo-based matching",
            "Enterprise implemented GWLB with Palo Alto firewalls for centralized traffic inspection, scaling firewall capacity from 2 to 10 instances based on traffic",
            "SaaS platform migrated from CLB to ALB, gaining WAF integration and cutting response time by 40% through HTTP/2 and connection reuse"
        ],
        references=[
            "https://docs.aws.amazon.com/elasticloadbalancing/latest/application/introduction.html",
            "https://docs.aws.amazon.com/elasticloadbalancing/latest/network/introduction.html",
            "https://docs.aws.amazon.com/elasticloadbalancing/latest/gateway/introduction.html",
            "https://aws.amazon.com/elasticloadbalancing/pricing/"
        ]
    )


def get_loadbalancer_targetgroup_pattern() -> DecisionPattern:
    """
    Pattern for configuring load balancer target groups and health checks.
    Covers target types, health check strategies, and best practices.
    """
    return DecisionPattern(
        pattern_id="loadbalancer-targetgroup-configuration",
        name="Load Balancer Target Group Configuration",
        category="networking",
        subcategory="loadbalancer",
        description="Framework for configuring load balancer target groups, selecting target types, and implementing effective health check strategies.",
        decision_criteria=[
            DecisionCriteria(
                criterion="Target Type",
                weight=0.30,
                considerations=[
                    "What are your backend targets (instances, IPs, Lambda, ALB)?",
                    "Do you need to target containers or EC2 instances?",
                    "Do you need cross-VPC targeting?",
                    "Do you need serverless targets?"
                ]
            ),
            DecisionCriteria(
                criterion="Health Check Strategy",
                weight=0.25,
                considerations=[
                    "How do you determine target health?",
                    "What is acceptable health check interval?",
                    "How quickly must you detect failures?",
                    "What health check protocol makes sense?"
                ]
            ),
            DecisionCriteria(
                criterion="Traffic Distribution",
                weight=0.20,
                considerations=[
                    "Do you need sticky sessions?",
                    "How should traffic be distributed?",
                    "Do you need weighted target groups?",
                    "Do you need connection draining?"
                ]
            ),
            DecisionCriteria(
                criterion="Performance Requirements",
                weight=0.15,
                considerations=[
                    "What are your latency requirements?",
                    "Do you need slow start mode?",
                    "What is your expected traffic pattern?",
                    "Do you need connection multiplexing?"
                ]
            ),
            DecisionCriteria(
                criterion="Operational Complexity",
                weight=0.10,
                considerations=[
                    "How often do targets change (auto-scaling)?",
                    "Do you need blue/green deployments?",
                    "Can you manage complex routing?",
                    "What is your deployment strategy?"
                ]
            )
        ],
        options=[
            DecisionOption(
                option_id="targetgroup-instance",
                name="Instance Target Type",
                description="Target EC2 instances directly by instance ID. Best for traditional EC2-based applications.",
                pros_cons=ProConsList(
                    pros=[
                        "Simple configuration for EC2-based apps",
                        "Automatic registration with Auto Scaling Groups",
                        "Works with both ALB and NLB",
                        "No need to manage IP addresses",
                        "Supports multiple ports per instance (ALB)",
                        "Instance metadata available for routing decisions"
                    ],
                    cons=[
                        "Limited to EC2 instances in same VPC",
                        "Cannot target on-premises resources",
                        "Cannot target resources by IP address",
                        "Less flexible than IP target type",
                        "Cannot target Lambda functions",
                        "Instance replacement requires target update"
                    ]
                ),
                estimated_cost="No additional cost (included in load balancer pricing)",
                implementation_complexity="Low",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="Target availability - EC2 Auto Scaling integration",
                        implementation_guidance="Configure Auto Scaling Group to register instances automatically; set appropriate health check grace period; monitor target registration/deregistration events; implement proper scaling policies"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Health monitoring - instance-level health checks",
                        implementation_guidance="Configure health check endpoint; set appropriate interval and threshold; monitor UnHealthyHostCount; implement health check logging; test failure scenarios"
                    )
                ]
            ),
            DecisionOption(
                option_id="targetgroup-ip",
                name="IP Address Target Type",
                description="Target resources by IP address, supporting containers, on-premises servers, and cross-VPC resources.",
                pros_cons=ProConsList(
                    pros=[
                        "Maximum flexibility - target any IP address",
                        "Supports ECS/EKS containers with awsvpc mode",
                        "Can target on-premises via Direct Connect/VPN",
                        "Supports cross-VPC and cross-account targets",
                        "Dynamic registration for microservices",
                        "Enables advanced deployment strategies"
                    ],
                    cons=[
                        "More complex to manage IP addresses manually",
                        "Requires careful IP address lifecycle management",
                        "Cannot automatically integrate with ASG",
                        "Need to handle IP changes for ephemeral containers",
                        "Security group configuration more complex",
                        "Risk of targeting incorrect IPs"
                    ]
                ),
                estimated_cost="No additional cost (included in load balancer pricing)",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="Dynamic target management - IP-based registration",
                        implementation_guidance="Implement automated target registration; use service discovery or ECS integration; monitor target IP changes; handle deregistration gracefully; document IP management strategy"
                    ),
                    SOC2Control(
                        control_id="CC6.2",
                        description="Network security - IP-based access control",
                        implementation_guidance="Configure security groups for IP ranges; use network ACLs; implement least-privilege network rules; audit IP target configurations; monitor unauthorized access"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Health monitoring - IP-based health checks",
                        implementation_guidance="Configure appropriate health check for IP targets; monitor connectivity; handle IP failures; implement automated target replacement; test cross-VPC health checks"
                    )
                ]
            ),
            DecisionOption(
                option_id="targetgroup-lambda",
                name="Lambda Function Target Type",
                description="Invoke Lambda functions directly from ALB for serverless HTTP applications (ALB only).",
                pros_cons=ProConsList(
                    pros=[
                        "Serverless architecture - no infrastructure to manage",
                        "Pay per invocation - cost-effective for variable traffic",
                        "Automatic scaling to handle any request volume",
                        "Simplified deployment and operations",
                        "Native integration with ALB",
                        "Multi-value headers and query string support",
                        "Request/response transformation built-in"
                    ],
                    cons=[
                        "ALB only - not supported by NLB",
                        "15-minute maximum Lambda execution timeout",
                        "Cold start latency for infrequent requests",
                        "Payload size limits (6MB request, 1MB response)",
                        "More complex debugging vs traditional targets",
                        "Cannot use some ALB features (sticky sessions)",
                        "Requires Lambda function to handle ALB event format"
                    ]
                ),
                estimated_cost="No target group cost + Lambda invocation ($0.20/million) and duration costs",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="Serverless availability - Lambda automatic scaling",
                        implementation_guidance="Configure appropriate Lambda concurrency; monitor throttling; implement error handling; use provisioned concurrency for consistent latency; handle cold starts"
                    ),
                    SOC2Control(
                        control_id="CC6.1",
                        description="Access control - IAM for Lambda invocation",
                        implementation_guidance="Configure IAM resource policy for ALB to invoke Lambda; implement least privilege; monitor Lambda invocation metrics; audit function access"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Health monitoring - Lambda execution monitoring",
                        implementation_guidance="Monitor Lambda errors and duration; configure CloudWatch alarms; implement Lambda error handling; track invocation metrics; test failure scenarios"
                    )
                ]
            ),
            DecisionOption(
                option_id="targetgroup-alb",
                name="ALB Target Type (NLB Only)",
                description="Target an Application Load Balancer from a Network Load Balancer for combined Layer 4 and Layer 7 benefits.",
                pros_cons=ProConsList(
                    pros=[
                        "Combines NLB static IPs with ALB content routing",
                        "Enables PrivateLink with ALB features",
                        "Preserves client IP with NLB benefits",
                        "Supports complex routing with fixed endpoints",
                        "Enables WAF with static IP requirements",
                        "Good for hybrid architectures"
                    ],
                    cons=[
                        "Additional latency from two load balancer hops",
                        "Higher cost (both NLB and ALB charges)",
                        "More complex architecture and troubleshooting",
                        "Additional failure points",
                        "Limited use cases where this is needed",
                        "Increased operational complexity"
                    ]
                ),
                estimated_cost="NLB cost + ALB cost; typical: $100-800/month for both",
                implementation_complexity="High",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="Multi-layer availability - NLB and ALB resilience",
                        implementation_guidance="Monitor both NLB and ALB health; configure health checks appropriately; implement failover procedures; test both load balancer layers; document architecture"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Multi-layer monitoring - track both load balancers",
                        implementation_guidance="Monitor NLB and ALB metrics separately; track end-to-end latency; configure alarms for both layers; implement distributed tracing; analyze traffic flow"
                    )
                ]
            )
        ],
        decision_framework="""
        TARGET GROUP CONFIGURATION SELECTION FRAMEWORK:

        1. DETERMINE TARGET TYPE:
           - Traditional EC2 application → Instance Target
           - ECS containers (awsvpc mode) → IP Target
           - EKS pods → IP Target
           - On-premises servers → IP Target
           - Serverless HTTP application → Lambda Target (ALB only)
           - Need static IPs + ALB features → ALB Target (NLB → ALB)

        2. EVALUATE DEPLOYMENT PATTERN:
           - Auto Scaling Groups → Instance Target
           - Container orchestration → IP Target
           - Blue/green deployments → IP Target (flexibility)
           - Serverless architecture → Lambda Target
           - Hybrid cloud → IP Target

        3. ASSESS OPERATIONAL REQUIREMENTS:
           - Simple EC2 management → Instance Target
           - Dynamic container workloads → IP Target
           - Minimize infrastructure → Lambda Target
           - Complex multi-layer → ALB Target

        HEALTH CHECK CONFIGURATION:

        Health Check Parameters:
        - Protocol: HTTP, HTTPS, TCP (choose based on target capability)
        - Path: /health or /healthz or appropriate endpoint
        - Port: Override or use traffic port
        - Interval: 5-300 seconds (default 30s)
        - Timeout: 2-120 seconds (default 5s)
        - Healthy threshold: 2-10 consecutive successes (default 5)
        - Unhealthy threshold: 2-10 consecutive failures (default 2)

        Health Check Best Practices:
        1. Use dedicated health check endpoint
        2. Check critical dependencies (database, cache, etc.)
        3. Respond quickly (<2 seconds)
        4. Return 200 OK for healthy, 5xx for unhealthy
        5. Balance sensitivity (detect failures) vs stability (avoid flapping)
        6. Monitor HealthyHostCount and UnHealthyHostCount

        Health Check Strategies:

        Aggressive (Fast Failure Detection):
        - Interval: 5 seconds
        - Timeout: 2 seconds
        - Unhealthy threshold: 2
        - Detects failures in 10 seconds
        - Use for: Critical, stateless services

        Balanced (Standard):
        - Interval: 30 seconds
        - Timeout: 5 seconds
        - Unhealthy threshold: 2
        - Detects failures in 60 seconds
        - Use for: Most applications

        Conservative (Avoid False Positives):
        - Interval: 30 seconds
        - Timeout: 10 seconds
        - Unhealthy threshold: 3-5
        - Detects failures in 90-150 seconds
        - Use for: Slow-starting services, databases

        STICKY SESSIONS (ALB):

        When to Use:
        - Session state stored locally on targets
        - Cannot use external session store (Redis, DynamoDB)
        - Stateful applications (legacy)

        Types:
        - Duration-based: ALB-generated cookie (1 second to 7 days)
        - Application-based: Custom application cookie

        Considerations:
        - Reduces load distribution efficiency
        - Can cause uneven load during scaling
        - Targets cannot be removed until sessions drain
        - Use external session store when possible (stateless)

        DEREGISTRATION DELAY (CONNECTION DRAINING):

        Purpose: Allow in-flight requests to complete before removing target

        Configuration:
        - Default: 300 seconds (5 minutes)
        - Range: 0-3600 seconds
        - Consider request duration patterns

        Recommendations:
        - Long-running requests (file uploads): 600-900 seconds
        - Standard web requests: 30-60 seconds
        - Quick API requests: 15-30 seconds
        - Frequent deployments: Lower delay (faster deployments)

        SLOW START MODE:

        Purpose: Gradually increase traffic to newly registered targets

        Configuration:
        - Duration: 30-900 seconds
        - Targets receive linearly increasing traffic
        - Prevents overwhelming new targets

        When to Use:
        - Targets need warm-up time (caches, connections)
        - High traffic volume
        - JVM applications with warm-up
        - Database connection pool initialization

        CROSS-ZONE LOAD BALANCING:

        Enabled: Traffic distributed evenly across all targets in all AZs
        Disabled: Traffic distributed only to targets in same AZ as LB node

        Recommendations:
        - ALB: Always enabled (no extra charge)
        - NLB: Enable for even distribution (small cross-AZ data transfer cost)
        - Disable only if targets are evenly distributed across AZs

        TARGET GROUP ATTRIBUTES:

        Key Attributes:
        - deregistration_delay.timeout_seconds: Connection draining (default 300)
        - stickiness.enabled: Enable sticky sessions (default false)
        - stickiness.type: Duration-based or application-based
        - slow_start.duration_seconds: Slow start period (default 0)
        - load_balancing.algorithm.type: round_robin or least_outstanding_requests
        - target_group_health.dns_failover.minimum_healthy_targets: DNS failover threshold

        MONITORING AND METRICS:

        Key Metrics:
        - HealthyHostCount: Number of healthy targets
        - UnHealthyHostCount: Number of unhealthy targets
        - TargetResponseTime: Backend response latency
        - RequestCount: Total requests to target group
        - TargetConnectionErrorCount: Failed connections to targets

        Alarms to Configure:
        - HealthyHostCount < minimum required targets
        - UnHealthyHostCount > 0 (critical services)
        - TargetResponseTime p99 > threshold
        - TargetConnectionErrorCount > threshold

        BLUE/GREEN DEPLOYMENTS:

        Strategy 1: Weighted Target Groups (ALB)
        - Create green target group
        - Add green targets
        - Shift traffic gradually (0% → 10% → 50% → 100%)
        - Monitor metrics during shift
        - Delete blue target group when stable

        Strategy 2: DNS-Based (Route 53 + Target Groups)
        - Create separate target groups
        - Use Route 53 weighted routing
        - Shift traffic at DNS level
        - Requires DNS TTL consideration

        CANARY DEPLOYMENTS:

        ALB Weighted Target Groups:
        - Blue target group: 95% weight
        - Canary target group: 5% weight
        - Monitor canary metrics
        - Gradually increase canary weight
        - Roll back if issues detected

        SECURITY CONSIDERATIONS:

        Security Group Configuration:
        - Load balancer security group: Allow inbound from clients
        - Target security group: Allow inbound from load balancer SG only
        - Follow least-privilege principle
        - Use security group referencing (not CIDR blocks)

        Health Check Endpoint Security:
        - Implement authentication if sensitive
        - Rate limit health check endpoint
        - Log health check access
        - Monitor for abuse

        Target Registration Security:
        - Validate target IPs before registration (IP targets)
        - Use IAM policies to control target registration
        - Audit target changes
        - Implement automated validation
        """,
        real_world_examples=[
            "E-commerce platform used Instance target type with Auto Scaling, automatically registering new instances during Black Friday, scaling from 10 to 50 instances seamlessly",
            "Microservices architecture on EKS used IP target type with ALB, dynamically registering pod IPs as services scaled, handling 1000+ pod registrations/day",
            "Startup built serverless API with Lambda targets on ALB, eliminating EC2 costs and achieving automatic scaling from 0 to 10k requests/minute",
            "Enterprise used NLB → ALB architecture to provide static IPs for client whitelisting while maintaining path-based routing and WAF protection"
        ],
        references=[
            "https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-target-groups.html",
            "https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-target-groups.html#target-group-attributes",
            "https://docs.aws.amazon.com/elasticloadbalancing/latest/application/lambda-functions.html"
        ]
    )


def get_loadbalancer_security_pattern() -> DecisionPattern:
    """
    Pattern for load balancer security configurations.
    Covers SSL/TLS, security groups, WAF integration, and access control.
    """
    return DecisionPattern(
        pattern_id="loadbalancer-security-strategy",
        name="Load Balancer Security Strategy",
        category="security",
        subcategory="loadbalancer",
        description="Comprehensive framework for implementing load balancer security including SSL/TLS termination, WAF integration, access logging, and network security controls.",
        decision_criteria=[
            DecisionCriteria(
                criterion="Data Sensitivity",
                weight=0.30,
                considerations=[
                    "What type of data flows through the load balancer?",
                    "Do you need encryption in transit?",
                    "Are there compliance requirements (PCI-DSS, HIPAA)?",
                    "Do you need end-to-end encryption?"
                ]
            ),
            DecisionCriteria(
                criterion="Threat Protection",
                weight=0.25,
                considerations=[
                    "Do you need protection against DDoS attacks?",
                    "Do you need application-layer attack protection?",
                    "Do you need IP-based access control?",
                    "Are you a target for common web attacks?"
                ]
            ),
            DecisionCriteria(
                criterion="Access Control",
                weight=0.20,
                considerations=[
                    "Who should access the load balancer (public, internal, specific IPs)?",
                    "Do you need geo-blocking?",
                    "Do you need authentication at load balancer?",
                    "Are there source IP restrictions?"
                ]
            ),
            DecisionCriteria(
                criterion="Compliance and Audit",
                weight=0.15,
                considerations=[
                    "Do you need access logs for compliance?",
                    "Are there audit trail requirements?",
                    "Do you need request/response logging?",
                    "What is the log retention requirement?"
                ]
            ),
            DecisionCriteria(
                criterion="Operational Complexity",
                weight=0.10,
                considerations=[
                    "Can you manage SSL certificates?",
                    "Can you manage WAF rules?",
                    "Do you need automated security updates?",
                    "What is your security team's expertise?"
                ]
            )
        ],
        options=[
            DecisionOption(
                option_id="loadbalancer-basic-security",
                name="Basic Security - SG and HTTPS",
                description="Essential security with security groups for network access control and HTTPS/TLS termination with ACM certificates.",
                pros_cons=ProConsList(
                    pros=[
                        "Simple configuration with AWS defaults",
                        "HTTPS/TLS encryption included at no extra cost",
                        "ACM provides free SSL certificates with auto-renewal",
                        "Security groups provide network-level protection",
                        "Suitable for internal applications and trusted traffic",
                        "Low operational overhead"
                    ],
                    cons=[
                        "No application-layer attack protection",
                        "No DDoS mitigation beyond basic AWS Shield Standard",
                        "Limited access control (network-level only)",
                        "No rate limiting or IP blocking",
                        "No request inspection or filtering",
                        "Vulnerable to application-layer attacks"
                    ]
                ),
                estimated_cost="Included in load balancer cost (ACM certificates free)",
                implementation_complexity="Low",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC6.7",
                        description="Encryption in transit - HTTPS/TLS termination",
                        implementation_guidance="Configure HTTPS listener; use ACM for certificate management; enforce TLS 1.2+; implement HTTP to HTTPS redirect; monitor certificate expiration; enable access logging"
                    ),
                    SOC2Control(
                        control_id="CC6.2",
                        description="Network access control - security groups",
                        implementation_guidance="Configure load balancer security group; allow HTTPS (443) from intended sources; implement least-privilege rules; use security group referencing for backend; audit SG changes"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Basic monitoring - CloudWatch metrics and access logs",
                        implementation_guidance="Enable access logging to S3; monitor target health and response times; configure alarms for errors; review logs periodically; export for compliance"
                    )
                ]
            ),
            DecisionOption(
                option_id="loadbalancer-waf-protection",
                name="WAF Protection - Application Layer Security",
                description="Advanced security with AWS WAF for application-layer attack protection, rate limiting, and IP filtering (ALB only).",
                pros_cons=ProConsList(
                    pros=[
                        "Protection against OWASP Top 10 attacks",
                        "SQL injection and XSS attack prevention",
                        "Rate-based rules for DDoS mitigation",
                        "IP allowlist/blocklist with geo-blocking",
                        "Bot detection and mitigation",
                        "Custom rules for application-specific threats",
                        "AWS Managed Rules for common protections",
                        "Real-time metrics and logging"
                    ],
                    cons=[
                        "Additional cost ($5/month + $1/million requests + rules)",
                        "Only available for ALB (not NLB)",
                        "Requires WAF rule configuration and tuning",
                        "False positives require rule adjustment",
                        "Operational overhead managing rules",
                        "Complex for advanced use cases"
                    ]
                ),
                estimated_cost="Base LB cost + WAF ($5/month + $1/rule + $1/million requests); typical: $50-500/month additional",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC7.3",
                        description="Threat protection - WAF rules for attack mitigation",
                        implementation_guidance="Configure AWS Managed Rules (Core, Known Bad Inputs); implement rate-based rules; configure IP blocklist/allowlist; enable geo-blocking; monitor WAF metrics; tune rules to reduce false positives"
                    ),
                    SOC2Control(
                        control_id="CC6.2",
                        description="Access control - IP and geo-based restrictions",
                        implementation_guidance="Implement IP-based rules; configure geo-blocking for restricted regions; maintain IP allowlist; audit rule changes; test rule effectiveness; document security policies"
                    ),
                    SOC2Control(
                        control_id="CC6.6",
                        description="Security logging - WAF logs for audit and analysis",
                        implementation_guidance="Enable WAF logging to S3 or CloudWatch; export logs to data lake; integrate with SIEM; analyze blocked requests; maintain logs per compliance requirements; implement log analysis automation"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Security monitoring - real-time threat detection",
                        implementation_guidance="Monitor WAF metrics (blocked/allowed requests); configure alarms for attack patterns; implement automated response; review security dashboards; maintain incident response procedures"
                    )
                ]
            ),
            DecisionOption(
                option_id="loadbalancer-shield-advanced",
                name="Shield Advanced - DDoS Protection",
                description="Enterprise DDoS protection with AWS Shield Advanced, providing 24/7 DDoS Response Team (DRT) and cost protection.",
                pros_cons=ProConsList(
                    pros=[
                        "Advanced DDoS protection for Layer 3/4/7 attacks",
                        "24/7 access to DDoS Response Team (DRT)",
                        "DDoS cost protection (credits for scaling costs)",
                        "Real-time attack notifications and forensics",
                        "Includes WAF at no additional charge",
                        "Attack visibility and detailed reporting",
                        "Protection for Route 53, CloudFront, Global Accelerator"
                    ],
                    cons=[
                        "Expensive ($3,000/month subscription)",
                        "Only justified for high-value applications",
                        "Requires commitment and engagement with DRT",
                        "Complex configuration for custom protections",
                        "May be overkill for small applications",
                        "Additional operational overhead"
                    ]
                ),
                estimated_cost="$3,000/month + data transfer out fees (with cost protection); typical: $3,000-5,000/month",
                implementation_complexity="High",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC7.3",
                        description="Advanced DDoS protection - enterprise threat mitigation",
                        implementation_guidance="Enable Shield Advanced; configure DDoS Response Team access; implement rate-based rules; configure health-based detection; test DRT engagement; maintain incident response procedures"
                    ),
                    SOC2Control(
                        control_id="CC9.1",
                        description="High availability - DDoS resilience",
                        implementation_guidance="Configure automatic mitigation; implement health checks; enable Route 53 health checks; test failover during attacks; document DDoS response procedures; maintain SLA documentation"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Attack visibility - comprehensive DDoS monitoring",
                        implementation_guidance="Monitor Shield Advanced metrics; configure attack notifications; review attack forensics; integrate with security monitoring; analyze attack patterns; maintain attack response history"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Business continuity - cost protection and availability",
                        implementation_guidance="Configure cost protection; document DDoS response procedures; test incident response; maintain DRT contact procedures; track protected resources; review coverage quarterly"
                    )
                ]
            ),
            DecisionOption(
                option_id="loadbalancer-enterprise-security",
                name="Enterprise Security - Defense in Depth",
                description="Comprehensive security with WAF, Shield Advanced, end-to-end encryption, comprehensive logging, and automated response.",
                pros_cons=ProConsList(
                    pros=[
                        "Maximum security with multiple layers of protection",
                        "End-to-end encryption (TLS to targets)",
                        "Advanced DDoS protection with cost guarantees",
                        "Application-layer attack protection with WAF",
                        "Comprehensive logging and audit trails",
                        "Automated threat response with EventBridge and Lambda",
                        "Integration with Security Hub and GuardDuty",
                        "Meets strictest compliance requirements"
                    ],
                    cons=[
                        "Highest cost across all security options",
                        "Most complex to configure and manage",
                        "Requires security expertise and dedicated resources",
                        "High operational overhead",
                        "Significant log volumes and costs",
                        "May be over-engineered for low-risk applications",
                        "Complex troubleshooting with multiple security layers"
                    ]
                ),
                estimated_cost="LB + WAF (approx. $200/month) + Shield Advanced ($3,000/month) + monitoring/automation (approx. $200/month); typical: $3,500-5,000+/month",
                implementation_complexity="Very High",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC6.7",
                        description="End-to-end encryption - TLS throughout request path",
                        implementation_guidance="Configure HTTPS listeners; enforce TLS 1.3; enable TLS to targets; use ACM for certificate management; implement certificate rotation; audit encryption settings; monitor TLS handshake errors"
                    ),
                    SOC2Control(
                        control_id="CC7.3",
                        description="Multi-layer threat protection - comprehensive defense",
                        implementation_guidance="Deploy Shield Advanced and WAF; implement AWS Managed Rules; configure custom rules; enable rate limiting; implement geo-blocking; configure automated response; integrate with Security Hub"
                    ),
                    SOC2Control(
                        control_id="CC6.6",
                        description="Comprehensive audit logging - full request/response trails",
                        implementation_guidance="Enable WAF logging; enable ALB access logs with all fields; export logs to S3 and CloudWatch; configure log encryption; integrate with SIEM; maintain 7+ year retention; implement log analysis automation"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Security monitoring - real-time detection and response",
                        implementation_guidance="Configure CloudWatch alarms; integrate with GuardDuty; deploy Security Hub; implement EventBridge rules for automated response; create Lambda functions for remediation; maintain security dashboards"
                    ),
                    SOC2Control(
                        control_id="CC6.2",
                        description="Network security - defense-in-depth access control",
                        implementation_guidance="Implement security groups with least privilege; configure NACLs; use VPC endpoints for AWS services; implement private load balancers for internal services; audit network access quarterly"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Availability and resilience - multi-AZ with DDoS protection",
                        implementation_guidance="Deploy across multiple AZs; enable cross-zone load balancing; implement health checks; configure Shield Advanced; test failover scenarios; document DR procedures; maintain SLA documentation"
                    ),
                    SOC2Control(
                        control_id="CC5.2",
                        description="Change management - secure deployment procedures",
                        implementation_guidance="Implement blue/green deployments; test security configurations; document changes; maintain rollback procedures; audit security changes; implement automated validation"
                    )
                ]
            )
        ],
        decision_framework="""
        LOAD BALANCER SECURITY SELECTION FRAMEWORK:

        1. ASSESS THREAT LANDSCAPE:
           - Internal application, trusted users → Basic Security
           - Public-facing, moderate risk → WAF Protection
           - High-value target, frequent attacks → Shield Advanced
           - Mission-critical, regulated data → Enterprise Security

        2. EVALUATE COMPLIANCE REQUIREMENTS:
           - No specific compliance → Basic Security
           - SOC 2, moderate PCI-DSS → WAF Protection
           - PCI-DSS Level 1, HIPAA → Shield Advanced or Enterprise
           - Multiple frameworks, high scrutiny → Enterprise Security

        3. DETERMINE ATTACK SURFACE:
           - Low traffic, internal only → Basic Security
           - Public API, moderate traffic → WAF Protection
           - High-profile, DDoS target → Shield Advanced
           - Critical infrastructure → Enterprise Security

        4. CONSIDER BUDGET AND RISK:
           - Limited budget, low risk → Basic Security
           - Moderate budget, moderate risk → WAF Protection
           - Justify $3k/month for DDoS protection → Shield Advanced
           - Maximum protection required → Enterprise Security

        5. ASSESS OPERATIONAL CAPABILITY:
           - Limited security team → Basic Security or Managed WAF rules
           - Can manage WAF rules → WAF Protection
           - Can engage with AWS DRT → Shield Advanced
           - Advanced security operations → Enterprise Security

        SECURITY COMPARISON:

        | Security Level | Encryption | WAF | Shield Adv | E2E TLS | Cost/Month | Complexity |
        |----------------|------------|-----|------------|---------|------------|------------|
        | Basic | TLS term | No | No | No | $0 | Low |
        | WAF | TLS term | Yes | No | Optional | $50-500 | Medium |
        | Shield Adv | TLS term | Included | Yes | Optional | $3,000+ | High |
        | Enterprise | End-to-end | Yes | Yes | Yes | $3,500+ | Very High |

        SSL/TLS CONFIGURATION:

        Security Policy Selection:
        - ELBSecurityPolicy-TLS13-1-2-2021-06: TLS 1.3 and 1.2 (recommended)
        - ELBSecurityPolicy-TLS-1-2-2017-01: TLS 1.2 only (legacy clients)
        - ELBSecurityPolicy-TLS-1-2-Ext-2018-06: TLS 1.2 with more ciphers
        - Choose based on client compatibility vs security requirements

        Certificate Management:
        - Use AWS Certificate Manager (ACM) for free certificates
        - Enable automatic renewal (ACM handles this)
        - Use single certificate with multiple SANs for multiple domains
        - Monitor certificate expiration with CloudWatch
        - Implement certificate rotation procedures

        HTTPS Best Practices:
        - Enforce HTTPS with HTTP to HTTPS redirect (ALB listener rule)
        - Implement HSTS header for browser security
        - Use TLS 1.3 for best security and performance
        - Disable older protocols (TLS 1.0, 1.1)
        - Monitor TLS handshake errors and protocol versions

        WAF CONFIGURATION:

        AWS Managed Rule Groups (Recommended):
        - Core Rule Set: Protection against OWASP Top 10
        - Known Bad Inputs: Block common malicious patterns
        - SQL Database: Prevent SQL injection
        - Linux OS: Protect against Linux-specific exploits
        - POSIX OS: Additional OS protection
        - Amazon IP Reputation: Block known malicious IPs

        Custom Rules:
        - Rate-based rule: Block IPs exceeding threshold (e.g., 2000 req/5min)
        - Geo-blocking: Block requests from specific countries
        - IP allowlist: Allow only specific IP ranges
        - String matching: Block requests with malicious patterns
        - Size constraints: Block unusually large requests

        WAF Best Practices:
        - Start with managed rules in count mode
        - Monitor false positives and tune rules
        - Implement rate limiting for all public endpoints
        - Use geo-blocking for geo-specific services
        - Log all WAF decisions for analysis
        - Review WAF dashboard regularly
        - Automate rule updates based on threats

        SHIELD ADVANCED CONFIGURATION:

        Protected Resources:
        - Load balancers (ALB, NLB, CLB)
        - CloudFront distributions
        - Route 53 hosted zones
        - Elastic IPs (EC2 instances)
        - Global Accelerator

        DDoS Response Team (DRT):
        - Grant proactive engagement authorization
        - Provide 24/7 contact information
        - Document critical applications and acceptable traffic patterns
        - Conduct tabletop exercises with DRT
        - Maintain incident response procedures

        Cost Protection:
        - Enable for all protected resources
        - Understand covered scaling costs
        - Document baseline and peak traffic
        - Request credits after DDoS attacks
        - Monitor Shield Advanced costs

        SECURITY MONITORING:

        Key Metrics to Monitor:
        - TargetResponseTime: Detect backend impacts
        - HTTPCode_Target_5XX: Backend errors
        - HTTPCode_ELB_5XX: Load balancer errors
        - RejectedConnectionCount: Connection limits hit
        - WAF BlockedRequests: Attacks blocked
        - WAF AllowedRequests: Legitimate traffic
        - Shield DDoSDetected: Active DDoS attacks

        Alarms to Configure:
        - HTTPCode_ELB_5XX > threshold (load balancer issues)
        - HTTPCode_Target_5XX > threshold (backend issues)
        - WAF BlockedRequests spike (potential attack)
        - TargetResponseTime p99 > threshold (performance degradation)
        - UnHealthyHostCount > 0 (target failures)

        LOGGING BEST PRACTICES:

        Access Logging:
        - Enable for all load balancers
        - Store in S3 with encryption
        - Set lifecycle policy for retention and archival
        - Include all fields for forensics
        - Export to data lake for analysis

        WAF Logging:
        - Enable for all Web ACLs
        - Log to S3, CloudWatch, or Kinesis Firehose
        - Include sampled requests
        - Retain per compliance requirements
        - Integrate with SIEM

        Log Analysis:
        - Use AWS Athena for S3 log queries
        - Implement automated anomaly detection
        - Create dashboards for security visibility
        - Alert on suspicious patterns
        - Maintain log analysis runbooks

        INCIDENT RESPONSE:

        Automated Response:
        - Use EventBridge for security event triggers
        - Implement Lambda functions for remediation
        - Auto-block malicious IPs with WAF
        - Scale resources during attacks
        - Notify security team via SNS

        Manual Response Procedures:
        - Document escalation procedures
        - Maintain contact list (including DRT if Shield Advanced)
        - Create response playbooks for common scenarios
        - Conduct regular drills
        - Review and update procedures quarterly
        """,
        real_world_examples=[
            "SaaS platform used WAF Protection with Managed Rules, blocking 2M malicious requests/month and preventing SQL injection attacks, adding $150/month cost",
            "Financial services deployed Enterprise Security with end-to-end TLS, WAF, and Shield Advanced, successfully mitigating 50 Gbps DDoS attack with DRT assistance",
            "E-commerce site implemented Basic Security for internal admin panel, using security group restrictions and HTTPS, meeting SOC 2 requirements at no extra cost",
            "Gaming company used Shield Advanced during DDoS attacks costing $10k in scaling, receiving $10k cost protection credits while maintaining 99.99% availability"
        ],
        references=[
            "https://docs.aws.amazon.com/elasticloadbalancing/latest/application/application-load-balancers.html#load-balancer-security",
            "https://docs.aws.amazon.com/waf/latest/developerguide/waf-chapter.html",
            "https://docs.aws.amazon.com/waf/latest/developerguide/ddos-overview.html",
            "https://aws.amazon.com/shield/features/"
        ]
    )


# Export all patterns
LOADBALANCER_PATTERNS = [
    get_loadbalancer_type_pattern(),
    get_loadbalancer_targetgroup_pattern(),
    get_loadbalancer_security_pattern()
]
