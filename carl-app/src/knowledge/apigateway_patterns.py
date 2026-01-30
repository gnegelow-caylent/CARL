"""
API Gateway Patterns for CARL
Provides decision frameworks for Amazon API Gateway type selection, authorization, and optimization patterns.
"""

from typing import List, Dict, Any
from .models import (
    DecisionPattern,
    DecisionOption,
    DecisionCriteria,
    ProConsList,
    SOC2Control
)


def get_apigateway_type_pattern() -> DecisionPattern:
    """
    Pattern for selecting API Gateway type (REST, HTTP, WebSocket).
    Covers feature requirements, performance needs, and cost optimization.
    """
    return DecisionPattern(
        pattern_id="apigateway-type-selection",
        name="API Gateway Type Selection",
        category="networking",
        subcategory="apigateway",
        description="Framework for selecting the appropriate API Gateway type based on protocol requirements, feature needs, performance characteristics, and cost optimization goals.",
        decision_criteria=[
            DecisionCriteria(
                criterion="Protocol Requirements",
                weight=0.30,
                considerations=[
                    "Do you need RESTful API support?",
                    "Do you need WebSocket for real-time bidirectional communication?",
                    "Do you need HTTP/2 support?",
                    "What API protocols must you support?"
                ]
            ),
            DecisionCriteria(
                criterion="Feature Requirements",
                weight=0.25,
                considerations=[
                    "Do you need API keys and usage plans?",
                    "Do you need request/response transformations?",
                    "Do you need caching capabilities?",
                    "Do you need request validation?"
                ]
            ),
            DecisionCriteria(
                criterion="Performance and Scale",
                weight=0.20,
                considerations=[
                    "What is your expected request volume?",
                    "What are your latency requirements?",
                    "Do you need caching to reduce backend load?",
                    "Do you have high-throughput requirements?"
                ]
            ),
            DecisionCriteria(
                criterion="Cost Optimization",
                weight=0.15,
                considerations=[
                    "What is your API infrastructure budget?",
                    "What is your expected monthly request volume?",
                    "Do you need cost-effective solution for high volume?",
                    "Can you trade features for lower cost?"
                ]
            ),
            DecisionCriteria(
                criterion="Integration Needs",
                weight=0.10,
                considerations=[
                    "What backend services will you integrate (Lambda, HTTP, AWS services)?",
                    "Do you need VPC Link for private integrations?",
                    "Do you need native AWS service integrations?",
                    "Do you need proxy vs custom integrations?"
                ]
            )
        ],
        options=[
            DecisionOption(
                option_id="apigateway-http-api",
                name="HTTP API",
                description="Low-latency, cost-effective API Gateway designed for serverless workloads and HTTP backends. Supports HTTP/2 and automatic deployments.",
                pros_cons=ProConsList(
                    pros=[
                        "Lowest cost - up to 71% cheaper than REST API",
                        "Lowest latency - optimized for performance",
                        "HTTP/2 support for improved performance",
                        "Simplified configuration and automatic deployments",
                        "Native JWT authorizer (no Lambda needed)",
                        "Better default CORS handling",
                        "Automatic CloudWatch metrics and logging"
                    ],
                    cons=[
                        "Limited features vs REST API (no caching, usage plans, API keys)",
                        "No request/response transformation",
                        "No request validation",
                        "Limited throttling controls (per-route only)",
                        "No mock integrations or SDK generation",
                        "Cannot use WAF directly (need CloudFront)",
                        "No resource policies or private APIs"
                    ]
                ),
                estimated_cost="$1.00 per million requests (first 300M); typical: $50-500/month for 50-500M requests",
                implementation_complexity="Low",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC6.1",
                        description="Access control - JWT authorizers and IAM",
                        implementation_guidance="Implement JWT authorizers for user authentication; use IAM authorization for service-to-service; configure CORS appropriately; monitor authorization failures"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Monitoring and logging - automatic CloudWatch integration",
                        implementation_guidance="Enable access logging to CloudWatch; configure CloudWatch alarms for errors and latency; export logs to S3 for retention; monitor request metrics"
                    ),
                    SOC2Control(
                        control_id="CC9.1",
                        description="Performance - low-latency API delivery",
                        implementation_guidance="Monitor p50/p99 latency metrics; implement per-route throttling; use Lambda proxy integration; optimize backend performance"
                    )
                ]
            ),
            DecisionOption(
                option_id="apigateway-rest-api",
                name="REST API",
                description="Feature-rich API Gateway with caching, request transformation, API keys, usage plans, and comprehensive throttling controls. Edge-optimized or regional deployment.",
                pros_cons=ProConsList(
                    pros=[
                        "Full-featured API management platform",
                        "Built-in caching (0.5GB to 237GB)",
                        "API keys and usage plans for rate limiting",
                        "Request/response transformation and validation",
                        "Resource policies and private API support",
                        "SDK generation for multiple languages",
                        "WAF integration for security",
                        "Canary deployments and staged releases"
                    ],
                    cons=[
                        "Higher cost than HTTP API ($3.50 per million requests)",
                        "Higher latency than HTTP API",
                        "More complex configuration",
                        "Manual stage deployment required",
                        "No native JWT authorizer (requires custom Lambda)",
                        "More operational overhead"
                    ]
                ),
                estimated_cost="$3.50 per million requests + caching ($0.02/hour per GB); typical: $200-2,000/month for 50-500M requests + caching",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC6.1",
                        description="Access control - multiple authorization methods",
                        implementation_guidance="Implement Lambda authorizers or Cognito; use API keys for client identification; configure resource policies; enable WAF rules for protection"
                    ),
                    SOC2Control(
                        control_id="CC6.6",
                        description="Audit logging - comprehensive request/response logging",
                        implementation_guidance="Enable CloudWatch access logs; log full request/response for audit; export logs to S3; configure CloudTrail for API management actions"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Security monitoring - WAF and CloudWatch",
                        implementation_guidance="Configure WAF with rate limiting and SQL injection rules; set CloudWatch alarms for 4xx/5xx errors; monitor usage plan quotas; track API key usage"
                    ),
                    SOC2Control(
                        control_id="CC9.1",
                        description="Performance and availability - caching and throttling",
                        implementation_guidance="Configure API caching to reduce backend load; implement throttling and burst limits; use usage plans for rate limiting; monitor cache hit rates"
                    ),
                    SOC2Control(
                        control_id="CC6.2",
                        description="Network security - private APIs and resource policies",
                        implementation_guidance="Use private APIs for VPC-only access; configure resource policies for IP restrictions; implement VPC endpoints; restrict public access as needed"
                    )
                ]
            ),
            DecisionOption(
                option_id="apigateway-websocket",
                name="WebSocket API",
                description="Persistent, bidirectional communication API for real-time applications like chat, gaming, and live dashboards. Message-based pricing.",
                pros_cons=ProConsList(
                    pros=[
                        "Persistent connections for real-time communication",
                        "Bidirectional messaging (server can push to clients)",
                        "Connection management with connection IDs",
                        "Route selection based on message content",
                        "Integrates with Lambda, HTTP, and AWS services",
                        "Automatic reconnection handling",
                        "Usage-based pricing (connections + messages)"
                    ],
                    cons=[
                        "More complex than HTTP APIs to implement",
                        "Requires connection state management",
                        "Higher cost for long-lived connections",
                        "No caching or usage plans",
                        "Limited to WebSocket protocol",
                        "Requires custom authorizer for authentication",
                        "Connection limits (per-account quotas)"
                    ]
                ),
                estimated_cost="$1.00 per million messages + $0.25 per million connection minutes; typical: $100-1,000/month depending on connections and messages",
                implementation_complexity="High",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC6.1",
                        description="Access control - custom authorizers for connections",
                        implementation_guidance="Implement Lambda authorizer for $connect route; validate tokens or credentials; maintain connection authorization state; monitor unauthorized connection attempts"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Connection monitoring - track active connections and messages",
                        implementation_guidance="Monitor connection count and duration; track message rates per connection; configure alarms for unusual patterns; log connection lifecycle events"
                    ),
                    SOC2Control(
                        control_id="CC9.1",
                        description="Scalability - manage connection lifecycle",
                        implementation_guidance="Implement connection management in DynamoDB; handle reconnections gracefully; implement idle connection timeout; monitor connection limits"
                    ),
                    SOC2Control(
                        control_id="CC6.6",
                        description="Audit logging - message and connection logging",
                        implementation_guidance="Enable CloudWatch access logs; log connection events; track message routes; export logs for compliance; implement message-level audit trails"
                    )
                ]
            ),
            DecisionOption(
                option_id="apigateway-rest-api-private",
                name="REST API Private",
                description="Private REST API accessible only from within your VPC via VPC endpoints, providing network-level isolation for internal APIs.",
                pros_cons=ProConsList(
                    pros=[
                        "Complete network isolation (no public internet exposure)",
                        "VPC endpoint for private connectivity",
                        "All REST API features (caching, transformations, etc.)",
                        "Resource policies for fine-grained access control",
                        "Suitable for internal microservices communication",
                        "Meets strict compliance requirements for network isolation",
                        "Can restrict access to specific VPCs or VPC endpoints"
                    ],
                    cons=[
                        "Only accessible from within VPC (requires VPN/Direct Connect for external access)",
                        "Higher cost than HTTP API",
                        "More complex setup with VPC endpoints",
                        "VPC endpoint costs ($0.01/hour per AZ)",
                        "Requires resource policy configuration",
                        "Not suitable for public-facing APIs",
                        "Additional latency vs public endpoints"
                    ]
                ),
                estimated_cost="$3.50 per million requests + VPC endpoint (approx. $7/month per AZ) + caching; typical: $250-2,500/month",
                implementation_complexity="High",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC6.2",
                        description="Network isolation - private VPC-only access",
                        implementation_guidance="Create VPC endpoint for API Gateway; configure resource policy to allow only VPC endpoint; deploy in private subnets; document network architecture"
                    ),
                    SOC2Control(
                        control_id="CC6.1",
                        description="Access control - resource policies and authorization",
                        implementation_guidance="Configure resource policy for VPC/VPC endpoint restrictions; implement Lambda authorizers; use IAM for service authentication; audit access regularly"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Security monitoring - private API access tracking",
                        implementation_guidance="Enable VPC flow logs; configure CloudWatch access logs; monitor connection sources; alert on unexpected access patterns; integrate with SIEM"
                    ),
                    SOC2Control(
                        control_id="CC6.6",
                        description="Audit logging - comprehensive access audit trails",
                        implementation_guidance="Log all API requests with source VPC endpoint; export logs to S3; maintain logs per compliance requirements; implement log analysis for security events"
                    ),
                    SOC2Control(
                        control_id="PI1.5",
                        description="Data privacy - network-level data protection",
                        implementation_guidance="Ensure all traffic stays within AWS network; document data flows; implement encryption in transit; verify no internet egress for sensitive data"
                    )
                ]
            )
        ],
        decision_framework="""
        API GATEWAY TYPE SELECTION FRAMEWORK:

        1. DETERMINE PROTOCOL REQUIREMENTS:
           - RESTful HTTP API only → HTTP API or REST API
           - Need WebSocket/real-time → WebSocket API
           - Need HTTP/2 → HTTP API or REST API
           - Need bidirectional push → WebSocket API

        2. EVALUATE FEATURE NEEDS:
           - Basic proxy to Lambda/HTTP → HTTP API (lowest cost)
           - Need caching, transformations, API keys → REST API
           - Need usage plans and quotas → REST API
           - Need request validation → REST API
           - Need private VPC-only access → REST API Private

        3. ASSESS COST SENSITIVITY:
           - Cost-sensitive, high volume (>100M/month) → HTTP API
           - Need features worth premium cost → REST API
           - Real-time connections required → WebSocket API
           - Internal APIs, network isolation → REST API Private

        4. CONSIDER AUTHORIZATION NEEDS:
           - JWT tokens → HTTP API (native support)
           - Complex custom logic → REST API (Lambda authorizer)
           - API keys and usage plans → REST API
           - WebSocket authentication → WebSocket API with custom authorizer

        5. EVALUATE PERFORMANCE REQUIREMENTS:
           - Lowest latency critical → HTTP API
           - Need caching to reduce backend load → REST API
           - Real-time, persistent connections → WebSocket API
           - Internal low-latency → REST API Private (with optimization)

        API GATEWAY COMPARISON:

        | Feature | HTTP API | REST API | WebSocket API | REST API Private |
        |---------|----------|----------|---------------|------------------|
        | Cost per M requests | $1.00 | $3.50 | $1.00 messages* | $3.50 |
        | Latency | Lowest | Higher | Persistent | Medium |
        | Caching | No | Yes | No | Yes |
        | API Keys | No | Yes | No | Yes |
        | Usage Plans | No | Yes | No | Yes |
        | Transformations | No | Yes | No | Yes |
        | Request Validation | No | Yes | No | Yes |
        | JWT Authorizer | Native | No** | Custom | No** |
        | WAF Integration | Via CloudFront | Direct | Via CloudFront | Direct |
        | Private API | No | No | No | Yes |
        | SDK Generation | No | Yes | No | Yes |
        | Protocols | HTTP/1.1, HTTP/2 | HTTP/1.1 | WebSocket | HTTP/1.1 |

        *WebSocket also charges $0.25 per million connection minutes
        **Requires Lambda authorizer

        USE CASE RECOMMENDATIONS:

        | Use Case | Best Fit | Rationale |
        |----------|----------|-----------|
        | Serverless API (Lambda) | HTTP API | Lowest cost, native JWT, low latency |
        | Microservices gateway | REST API | Caching, transformations, usage plans |
        | Public REST API with rate limiting | REST API | API keys, usage plans, throttling |
        | Chat application | WebSocket API | Bidirectional real-time messaging |
        | Live dashboard | WebSocket API | Server push for real-time updates |
        | Gaming backend | WebSocket API | Low-latency bidirectional communication |
        | Internal service mesh | REST API Private | VPC isolation, network security |
        | Mobile app backend (JWT auth) | HTTP API | Cost-effective, native JWT support |
        | Third-party API monetization | REST API | Usage plans, API keys, detailed metrics |
        | Simple HTTP proxy | HTTP API | Lowest cost and latency |

        COST OPTIMIZATION STRATEGIES:

        1. Choose HTTP API When Possible:
           - 71% cheaper than REST API
           - Sufficient for 80% of use cases
           - Native JWT eliminates Lambda authorizer costs
           - Only trade-off is reduced features

        2. Optimize REST API Costs:
           - Use caching to reduce backend invocations (cache hits are free)
           - Implement usage plans to prevent abuse
           - Right-size cache capacity (start small, scale up)
           - Monitor cache hit rate (aim for >60%)

        3. Optimize WebSocket Costs:
           - Implement idle connection timeout
           - Close connections when not actively used
           - Batch messages where possible
           - Monitor connection duration and message rates

        4. Consider Regional vs Edge-Optimized:
           - Regional: Lower latency if users in same region, no CloudFront cost
           - Edge-Optimized: Global users, higher cost but better performance
           - Use regional for internal APIs or single-region users

        PERFORMANCE OPTIMIZATION:

        HTTP API:
        - Naturally low latency (optimized code path)
        - Use Lambda proxy integration for best performance
        - Minimize Lambda cold starts with provisioned concurrency
        - Consider HTTP/2 for client-side performance

        REST API:
        - Enable caching for frequently accessed endpoints
        - Use mock integrations for static responses
        - Optimize Lambda functions to reduce execution time
        - Configure appropriate timeout values

        WebSocket API:
        - Implement efficient connection management
        - Use DynamoDB for connection ID storage
        - Optimize message routing logic
        - Implement client-side reconnection with backoff

        SECURITY CONSIDERATIONS:

        1. Always use HTTPS/TLS for data in transit
        2. Implement appropriate authorization (JWT, Lambda authorizer, IAM)
        3. Use WAF for REST APIs to prevent common attacks
        4. Configure CORS appropriately (restrictive as possible)
        5. Enable CloudWatch logging for audit trails
        6. Use API keys with usage plans to prevent abuse (REST API)
        7. Implement request throttling to prevent DoS
        8. Use resource policies for additional access control

        MIGRATION PATHS:

        HTTP API → REST API:
        - Create REST API with same routes
        - Migrate complex routes first
        - Use weighted routing in Route 53 for gradual migration
        - Update clients to new endpoint

        REST API → HTTP API:
        - Remove dependencies on REST-only features
        - Migrate authorizer to JWT if applicable
        - Test thoroughly (some behaviors differ)
        - Consider keeping REST API for specific features

        REST API → Private REST API:
        - Create VPC endpoint for API Gateway
        - Create new private API
        - Configure resource policy for VPC endpoint
        - Update service clients to use private DNS
        """,
        real_world_examples=[
            "Startup built serverless API with HTTP API and Lambda, reducing costs by 65% vs REST API while serving 200M requests/month at <100ms p99 latency",
            "E-commerce platform used REST API with caching (20GB) for product catalog, achieving 80% cache hit rate and reducing backend database load by 75%",
            "Gaming company implemented WebSocket API for real-time multiplayer, handling 50k concurrent connections with <50ms message latency at $800/month",
            "Financial services firm deployed REST API Private for internal microservices, meeting compliance requirements with complete VPC isolation and no internet exposure"
        ],
        references=[
            "https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api.html",
            "https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-rest-api.html",
            "https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-websocket-api.html",
            "https://aws.amazon.com/api-gateway/pricing/"
        ]
    )


def get_apigateway_authorization_pattern() -> DecisionPattern:
    """
    Pattern for API Gateway authorization and authentication strategies.
    Covers IAM, Lambda authorizers, Cognito, JWT, and API keys.
    """
    return DecisionPattern(
        pattern_id="apigateway-authorization-strategy",
        name="API Gateway Authorization Strategy",
        category="security",
        subcategory="apigateway",
        description="Framework for selecting the appropriate API Gateway authorization method based on client types, authentication requirements, and integration complexity.",
        decision_criteria=[
            DecisionCriteria(
                criterion="Client Type",
                weight=0.30,
                considerations=[
                    "Who are your API clients (web apps, mobile apps, services)?",
                    "Do you need user-based authentication?",
                    "Do you need service-to-service authentication?",
                    "Are clients AWS-aware or generic HTTP clients?"
                ]
            ),
            DecisionCriteria(
                criterion="Authentication Needs",
                weight=0.25,
                considerations=[
                    "Do you need OAuth 2.0 / OpenID Connect?",
                    "Do you need custom authentication logic?",
                    "Do you have existing identity provider?",
                    "Do you need fine-grained authorization?"
                ]
            ),
            DecisionCriteria(
                criterion="Complexity and Flexibility",
                weight=0.20,
                considerations=[
                    "How complex is your authorization logic?",
                    "Do you need caching of authorization decisions?",
                    "Can you use standard protocols or need custom logic?",
                    "Do you need per-request authorization context?"
                ]
            ),
            DecisionCriteria(
                criterion="Cost and Performance",
                weight=0.15,
                considerations=[
                    "What is your authorization budget?",
                    "How many authorization requests per second?",
                    "Can you tolerate authorizer latency?",
                    "Do you need authorization result caching?"
                ]
            ),
            DecisionCriteria(
                criterion="Security Requirements",
                weight=0.10,
                considerations=[
                    "What are your compliance requirements?",
                    "Do you need MFA support?",
                    "Do you need user session management?",
                    "Are there data access control requirements?"
                ]
            )
        ],
        options=[
            DecisionOption(
                option_id="apigateway-iam-authorization",
                name="IAM Authorization",
                description="AWS Signature Version 4 signing for service-to-service authentication. No additional cost, native AWS integration.",
                pros_cons=ProConsList(
                    pros=[
                        "No additional cost - included with API Gateway",
                        "No latency overhead - built-in validation",
                        "Tight AWS integration with IAM policies",
                        "Fine-grained permissions with IAM policy conditions",
                        "No authorization infrastructure to manage",
                        "Automatic credential rotation via IAM roles",
                        "CloudTrail integration for audit"
                    ],
                    cons=[
                        "Only suitable for AWS-aware clients (SDKs or SigV4 libraries)",
                        "Not suitable for browser-based applications",
                        "Requires AWS credentials or IAM roles",
                        "Complex for non-AWS clients to implement",
                        "No user-based authentication (service-based only)",
                        "Limited to AWS identity model"
                    ]
                ),
                estimated_cost="No additional cost (included in API Gateway pricing)",
                implementation_complexity="Low",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC6.1",
                        description="Access control - IAM policies for authorization",
                        implementation_guidance="Create least-privilege IAM policies for API access; use IAM roles for service accounts; implement policy conditions for fine-grained control; audit IAM policies quarterly"
                    ),
                    SOC2Control(
                        control_id="CC6.6",
                        description="Audit logging - CloudTrail for authorization events",
                        implementation_guidance="Enable CloudTrail for API Gateway; log all API requests with IAM principal; export logs to S3; integrate with SIEM for analysis"
                    ),
                    SOC2Control(
                        control_id="CC6.2",
                        description="Service authentication - SigV4 signing",
                        implementation_guidance="Use IAM roles for EC2, ECS, Lambda; implement credential rotation; use temporary credentials; monitor credential usage"
                    )
                ]
            ),
            DecisionOption(
                option_id="apigateway-cognito-authorization",
                name="Amazon Cognito User Pools",
                description="Managed user authentication with OAuth 2.0 and OpenID Connect support. Integrates natively with API Gateway for user-based authorization.",
                pros_cons=ProConsList(
                    pros=[
                        "Fully managed user directory and authentication",
                        "OAuth 2.0 and OpenID Connect support",
                        "Built-in user registration, login, and password reset",
                        "MFA and adaptive authentication",
                        "Social identity providers (Google, Facebook, etc.)",
                        "No Lambda function needed for authorization",
                        "User session management included",
                        "Scales automatically"
                    ],
                    cons=[
                        "Additional cost for Cognito User Pools ($0.0055 per MAU after free tier)",
                        "Locked into Cognito ecosystem",
                        "Less flexible than custom Lambda authorizers",
                        "Limited customization of authentication flows",
                        "Cannot implement complex authorization logic",
                        "Requires Cognito integration in client applications"
                    ]
                ),
                estimated_cost="Free for <50k MAU, then $0.0055 per MAU; typical: $50-500/month for 10k-100k MAU",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC6.1",
                        description="User authentication - managed user directory",
                        implementation_guidance="Configure Cognito User Pool with appropriate password policies; enable MFA for privileged users; implement account recovery; monitor authentication metrics"
                    ),
                    SOC2Control(
                        control_id="CC6.2",
                        description="Access control - OAuth 2.0 tokens",
                        implementation_guidance="Configure appropriate token expiration; implement token refresh; validate tokens at API Gateway; monitor token usage and revocation"
                    ),
                    SOC2Control(
                        control_id="CC6.6",
                        description="User activity logging - Cognito and API Gateway logs",
                        implementation_guidance="Enable CloudWatch logs for Cognito; log authentication attempts; track user activity via API Gateway logs; export for compliance"
                    ),
                    SOC2Control(
                        control_id="CC7.3",
                        description="Threat protection - adaptive authentication",
                        implementation_guidance="Enable adaptive authentication for risk-based access; configure account takeover protection; implement CAPTCHA for suspicious activity; monitor brute force attempts"
                    )
                ]
            ),
            DecisionOption(
                option_id="apigateway-jwt-authorization",
                name="JWT Authorizer (HTTP API)",
                description="Native JWT validation for HTTP APIs, supporting tokens from any OpenID Connect (OIDC) identity provider. No Lambda function required.",
                pros_cons=ProConsList(
                    pros=[
                        "No Lambda cost - native API Gateway validation",
                        "Low latency - no Lambda cold start",
                        "Standards-based (JWT / OIDC)",
                        "Works with any OIDC provider (Auth0, Okta, etc.)",
                        "Simple configuration with issuer URL and audience",
                        "Automatic token validation and caching",
                        "Supports multiple issuers per API"
                    ],
                    cons=[
                        "Only available for HTTP APIs (not REST APIs)",
                        "Limited to JWT validation - no custom logic",
                        "Cannot implement complex authorization rules",
                        "No fine-grained permission checks",
                        "Requires OIDC-compliant identity provider",
                        "Cannot enrich request context beyond JWT claims"
                    ]
                ),
                estimated_cost="No additional cost (included in HTTP API pricing)",
                implementation_complexity="Low",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC6.1",
                        description="Token-based authentication - JWT validation",
                        implementation_guidance="Configure JWT authorizer with OIDC issuer; validate audience and scopes; implement token expiration; monitor authentication failures"
                    ),
                    SOC2Control(
                        control_id="CC6.2",
                        description="Standards-based security - OAuth 2.0 / OIDC",
                        implementation_guidance="Use reputable identity provider; enforce HTTPS for token exchange; implement token refresh strategy; audit token configuration"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Monitoring - authentication metrics",
                        implementation_guidance="Configure CloudWatch alarms for 401 errors; monitor token validation failures; track unusual authentication patterns; integrate with security monitoring"
                    )
                ]
            ),
            DecisionOption(
                option_id="apigateway-lambda-authorizer",
                name="Lambda Authorizer (Custom)",
                description="Custom Lambda function for authorization logic, supporting any authentication protocol and complex authorization rules. Highly flexible but adds latency and cost.",
                pros_cons=ProConsList(
                    pros=[
                        "Maximum flexibility - implement any authorization logic",
                        "Supports any authentication protocol or token format",
                        "Can integrate with any identity provider or database",
                        "Fine-grained authorization with custom business rules",
                        "Can enrich request context for downstream services",
                        "Caching support to reduce invocations (up to 1 hour)",
                        "Available for REST and HTTP APIs"
                    ],
                    cons=[
                        "Additional Lambda costs ($0.20 per million requests)",
                        "Adds latency (cold start: 100-500ms, warm: 10-50ms)",
                        "Requires Lambda function management and monitoring",
                        "More complex to implement and test",
                        "Must handle caching and error scenarios",
                        "Potential single point of failure if not designed properly"
                    ]
                ),
                estimated_cost="$0.20 per million Lambda invocations (128MB, 50ms avg); typical: $20-200/month depending on volume and caching",
                implementation_complexity="High",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC6.1",
                        description="Custom authorization - flexible access control",
                        implementation_guidance="Implement authorization logic with least privilege; cache authorization decisions appropriately; handle errors gracefully; log authorization decisions; test thoroughly"
                    ),
                    SOC2Control(
                        control_id="CC6.6",
                        description="Authorization audit - comprehensive logging",
                        implementation_guidance="Log all authorization attempts in Lambda; capture authorization context; export logs to S3; implement log analysis for suspicious patterns; maintain audit trails"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Authorizer monitoring - performance and errors",
                        implementation_guidance="Monitor Lambda execution time and errors; configure alarms for authorization failures; track cache hit rates; monitor cold start frequency; implement fallback logic"
                    ),
                    SOC2Control(
                        control_id="CC9.1",
                        description="Availability - resilient authorization",
                        implementation_guidance="Implement retry logic; use provisioned concurrency for consistent performance; handle failures gracefully; configure appropriate timeouts; test failure scenarios"
                    )
                ]
            )
        ],
        decision_framework="""
        API GATEWAY AUTHORIZATION SELECTION FRAMEWORK:

        1. IDENTIFY CLIENT TYPE:
           - AWS services (Lambda, EC2, ECS) → IAM Authorization
           - Web/mobile apps with user login → Cognito or JWT Authorizer
           - Third-party integrations → Lambda Authorizer or API Keys
           - Microservices → IAM or Lambda Authorizer

        2. EVALUATE AUTHENTICATION REQUIREMENTS:
           - Service-to-service only → IAM Authorization
           - User authentication needed → Cognito or JWT Authorizer
           - Custom authentication protocol → Lambda Authorizer
           - Social login required → Cognito User Pools

        3. ASSESS COMPLEXITY NEEDS:
           - Simple token validation → JWT Authorizer (HTTP API)
           - User management needed → Cognito
           - Complex authorization rules → Lambda Authorizer
           - Fine-grained permissions → IAM or Lambda Authorizer

        4. CONSIDER COST AND PERFORMANCE:
           - Zero authorization cost → IAM or JWT Authorizer
           - Low latency critical → IAM or JWT Authorizer
           - Budget for user management → Cognito
           - Can tolerate Lambda latency → Lambda Authorizer

        5. FACTOR IN EXISTING SYSTEMS:
           - Already using Cognito → Cognito User Pools
           - Existing OIDC provider → JWT Authorizer
           - Custom identity system → Lambda Authorizer
           - AWS-native architecture → IAM Authorization

        AUTHORIZATION METHOD COMPARISON:

        | Method | Use Case | Latency | Cost | Flexibility | Complexity |
        |--------|----------|---------|------|-------------|------------|
        | IAM | Service-to-service | None | None | Medium | Low |
        | Cognito | User apps (managed) | Low | $-$$ | Low | Medium |
        | JWT | User apps (OIDC) | None | None | Low | Low |
        | Lambda | Custom logic | Medium | $ | High | High |

        AUTHORIZATION FLOW EXAMPLES:

        IAM Authorization:
        1. Client signs request with AWS credentials (SigV4)
        2. API Gateway validates signature against IAM
        3. IAM policy evaluation determines access
        4. Request forwarded to backend or denied

        Cognito User Pools:
        1. User authenticates with Cognito (login)
        2. Cognito returns JWT access token
        3. Client sends token in Authorization header
        4. API Gateway validates token with Cognito
        5. Request forwarded with user context

        JWT Authorizer:
        1. User authenticates with identity provider
        2. Provider returns JWT token
        3. Client sends token in Authorization header
        4. API Gateway validates JWT signature and claims
        5. Request forwarded with user context

        Lambda Authorizer:
        1. Client sends authentication token (any format)
        2. API Gateway invokes Lambda authorizer
        3. Lambda validates token and returns IAM policy
        4. API Gateway caches policy (optional)
        5. Request allowed/denied based on policy

        USE CASE RECOMMENDATIONS:

        | Scenario | Best Authorization | Rationale |
        |----------|-------------------|-----------|
        | Microservices (AWS) | IAM | Zero cost, native AWS, no latency |
        | Mobile app (new users) | Cognito | Managed auth, MFA, social login |
        | SPA with Auth0 | JWT Authorizer | Native support, no Lambda needed |
        | API with custom auth | Lambda Authorizer | Maximum flexibility |
        | B2B partner integration | Lambda Authorizer + API Keys | Custom logic + rate limiting |
        | Internal admin API | IAM + Resource Policy | Strong security, AWS-native |
        | Multi-tenant SaaS | Lambda Authorizer | Tenant isolation logic |

        COST OPTIMIZATION:

        1. Use Native Authorizers When Possible:
           - JWT Authorizer (HTTP API) - no cost
           - IAM Authorization - no cost
           - Avoid Lambda for simple validation

        2. Optimize Lambda Authorizer Costs:
           - Enable caching (TTL up to 1 hour)
           - Use lowest memory needed (128MB often sufficient)
           - Optimize function code for speed
           - Monitor cold starts and consider provisioned concurrency for high-volume

        3. Cognito Cost Management:
           - Use free tier effectively (<50k MAU)
           - Implement token refresh to reduce active users
           - Archive inactive users
           - Consider pricing tiers for large deployments

        SECURITY BEST PRACTICES:

        1. Always Use HTTPS:
           - Enforce TLS for all API requests
           - Use minimum TLS 1.2
           - Custom domains with ACM certificates

        2. Implement Defense in Depth:
           - Combine authorization with WAF rules
           - Use resource policies for additional restrictions
           - Implement rate limiting with usage plans
           - Monitor for suspicious patterns

        3. Token Management:
           - Use short-lived access tokens (15-60 minutes)
           - Implement refresh token rotation
           - Validate token expiration and audience
           - Monitor for token replay attacks

        4. Caching Considerations:
           - Cache authorization decisions with appropriate TTL
           - Include user/request context in cache key
           - Consider security vs performance trade-off
           - Implement cache invalidation if needed

        5. Logging and Monitoring:
           - Log all authorization attempts
           - Monitor authorization failure rates
           - Alert on unusual patterns
           - Maintain audit trails for compliance

        PERFORMANCE OPTIMIZATION:

        Lambda Authorizer:
        - Enable response caching (reduces invocations by 80%+)
        - Use provisioned concurrency for consistent latency
        - Optimize code for sub-50ms execution
        - Use environment variables for configuration
        - Implement connection pooling for database calls

        Cognito:
        - Implement token refresh to reduce Cognito calls
        - Cache user attributes in application
        - Use appropriate token expiration
        - Monitor Cognito API latency

        JWT Authorizer:
        - Ensure JWKS endpoint is fast and cached
        - Use CDN for JWKS if custom provider
        - Monitor token validation latency

        COMMON PATTERNS:

        1. Multi-Tenant SaaS:
           - Lambda Authorizer to validate tenant
           - Enrich request with tenant context
           - Backend uses tenant ID for data isolation

        2. Partner API with Rate Limiting:
           - API Keys for partner identification
           - Lambda Authorizer for custom validation
           - Usage Plans for rate limiting per partner

        3. Public + Private Endpoints:
           - Public endpoints: JWT Authorizer or Cognito
           - Private endpoints: IAM Authorization
           - Resource policy to restrict sources

        4. Step-up Authentication:
           - JWT Authorizer for standard access
           - Lambda Authorizer checks claims for sensitive operations
           - Require MFA token for high-risk actions
        """,
        real_world_examples=[
            "Microservices platform used IAM Authorization for 500+ internal API calls per second, achieving zero authorization cost and <1ms latency overhead",
            "B2C SaaS implemented Cognito User Pools with social login for 100k users, managing authentication at $550/month with built-in MFA and account recovery",
            "Enterprise integrated with Okta using JWT Authorizer on HTTP API, eliminating Lambda authorizer costs ($200/month savings) while maintaining SSO",
            "Multi-tenant platform built Lambda Authorizer with 5-minute caching, processing 50M requests/month with 95% cache hit rate at $250/month Lambda cost"
        ],
        references=[
            "https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-control-access-to-api.html",
            "https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-integrate-with-cognito.html",
            "https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html",
            "https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-use-lambda-authorizer.html"
        ]
    )


def get_apigateway_optimization_pattern() -> DecisionPattern:
    """
    Pattern for API Gateway performance optimization and cost management.
    Covers caching, throttling, monitoring, and best practices.
    """
    return DecisionPattern(
        pattern_id="apigateway-optimization-strategy",
        name="API Gateway Performance and Cost Optimization",
        category="optimization",
        subcategory="apigateway",
        description="Framework for optimizing API Gateway performance, cost, and reliability through caching, throttling, monitoring, and operational best practices.",
        decision_criteria=[
            DecisionCriteria(
                criterion="Performance Requirements",
                weight=0.30,
                considerations=[
                    "What are your latency requirements (p50, p99)?",
                    "What is your expected throughput (requests per second)?",
                    "Can you benefit from caching?",
                    "Do you have backend capacity constraints?"
                ]
            ),
            DecisionCriteria(
                criterion="Cost Optimization",
                weight=0.25,
                considerations=[
                    "What is your API Gateway monthly cost?",
                    "Can you reduce backend invocations with caching?",
                    "What percentage of responses are cacheable?",
                    "Can you optimize request routing?"
                ]
            ),
            DecisionCriteria(
                criterion="Reliability and Protection",
                weight=0.20,
                considerations=[
                    "Do you need protection against traffic spikes?",
                    "Do you need rate limiting per client?",
                    "Do you need burst handling?",
                    "Are there DoS/DDoS concerns?"
                ]
            ),
            DecisionCriteria(
                criterion="Observability",
                weight=0.15,
                considerations=[
                    "What monitoring and metrics do you need?",
                    "Do you need request/response logging?",
                    "Do you need distributed tracing?",
                    "Are there compliance logging requirements?"
                ]
            ),
            DecisionCriteria(
                criterion="Operational Complexity",
                weight=0.10,
                considerations=[
                    "Can you manage cache invalidation?",
                    "Do you need automated scaling controls?",
                    "What is your team's operational maturity?",
                    "Do you need hands-off management?"
                ]
            )
        ],
        options=[
            DecisionOption(
                option_id="apigateway-basic-optimization",
                name="Basic Optimization - Monitoring and Throttling",
                description="Essential optimizations with CloudWatch metrics, basic throttling, and logging for API observability without caching.",
                pros_cons=ProConsList(
                    pros=[
                        "Low cost - minimal additional charges",
                        "Simple to implement and manage",
                        "CloudWatch metrics included by default",
                        "Basic throttling protects backend",
                        "Suitable for most APIs without caching needs",
                        "Access logging for debugging and audit"
                    ],
                    cons=[
                        "No caching - all requests hit backend",
                        "Higher backend costs and load",
                        "Higher latency than with caching",
                        "Limited request rate management",
                        "No detailed request tracing",
                        "Basic protection only"
                    ]
                ),
                estimated_cost="Base API Gateway cost + CloudWatch Logs (approx. $0.50/GB ingested); typical: $50-500/month",
                implementation_complexity="Low",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC7.2",
                        description="Basic monitoring - CloudWatch metrics and logs",
                        implementation_guidance="Enable CloudWatch metrics; configure access logging; set alarms for 4xx/5xx errors; monitor request count and latency; review logs weekly"
                    ),
                    SOC2Control(
                        control_id="CC9.1",
                        description="Backend protection - account-level throttling",
                        implementation_guidance="Configure steady-state rate limit; set burst limit; monitor throttling events; implement exponential backoff in clients; document throttle settings"
                    ),
                    SOC2Control(
                        control_id="CC6.6",
                        description="Access logging - audit trail for requests",
                        implementation_guidance="Enable access logs to CloudWatch; configure log format; export logs to S3 for retention; implement log analysis for security events"
                    )
                ]
            ),
            DecisionOption(
                option_id="apigateway-caching-optimization",
                name="Caching Optimization - REST API Cache",
                description="REST API with response caching (0.5GB to 237GB) to reduce backend load, improve latency, and lower costs for cacheable responses.",
                pros_cons=ProConsList(
                    pros=[
                        "Significant latency reduction for cached responses (<10ms)",
                        "Reduces backend load and costs (cache hits are free)",
                        "Configurable TTL (0-3600 seconds)",
                        "Per-method cache key customization",
                        "Can achieve 60-90% cache hit rate for cacheable content",
                        "Reduces database and Lambda costs significantly",
                        "Supports cache encryption and per-key TTL"
                    ],
                    cons=[
                        "Additional caching cost ($0.02/hour per GB)",
                        "Only available for REST API (not HTTP API)",
                        "Requires careful cache key design",
                        "Cache invalidation complexity",
                        "Not suitable for personalized or dynamic content",
                        "Memory sizing can be tricky (over/under-provisioning)",
                        "Cold cache period on deployment"
                    ]
                ),
                estimated_cost="Base cost + caching ($0.02/hour per GB = $15/month per GB); typical: $200-1,000/month (0.5-20GB cache)",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="Performance optimization - caching for latency and cost",
                        implementation_guidance="Configure cache size based on working set; set appropriate TTL per method; implement cache key design; monitor cache hit rate (target >70%); optimize cacheable endpoints"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Cache monitoring - track effectiveness",
                        implementation_guidance="Monitor CacheHitCount and CacheMissCount metrics; track cache utilization; set alarms for low hit rate; review cache performance weekly; adjust TTL based on data"
                    ),
                    SOC2Control(
                        control_id="CC6.7",
                        description="Cache security - encrypted cache storage",
                        implementation_guidance="Enable cache encryption; implement cache key authorization; validate cache invalidation logic; audit cached data sensitivity; document cache strategy"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Backend protection - reduce load with caching",
                        implementation_guidance="Monitor backend request reduction; track cost savings from cache; implement cache warming for critical endpoints; handle cache invalidation for data updates"
                    )
                ]
            ),
            DecisionOption(
                option_id="apigateway-advanced-optimization",
                name="Advanced Optimization - Usage Plans and Rate Limiting",
                description="REST API with usage plans, API keys, per-client rate limiting, and tiered access for fine-grained control and monetization.",
                pros_cons=ProConsList(
                    pros=[
                        "Per-client rate limiting and quotas",
                        "API key management for client identification",
                        "Tiered access plans (e.g., free, premium, enterprise)",
                        "Prevents individual client abuse",
                        "Enables API monetization",
                        "Detailed per-client metrics",
                        "Throttling independent of backend capacity"
                    ],
                    cons=[
                        "Requires REST API (not available for HTTP API)",
                        "Additional operational overhead managing keys and plans",
                        "Clients must include API key header",
                        "Key distribution and rotation complexity",
                        "Not suitable for public unauthenticated APIs",
                        "Requires careful plan design and monitoring"
                    ]
                ),
                estimated_cost="Base REST API cost + potential caching; typical: $200-2,000/month depending on volume",
                implementation_complexity="Medium-High",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="Client-level protection - usage plans and quotas",
                        implementation_guidance="Define usage plans with appropriate rate limits; configure burst limits per plan; assign API keys to plans; monitor quota usage; implement alerting for quota approaching limits"
                    ),
                    SOC2Control(
                        control_id="CC6.1",
                        description="Client identification - API key management",
                        implementation_guidance="Generate API keys per client; implement key rotation strategy; audit key usage regularly; revoke compromised keys; maintain key inventory; document key assignment"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Usage monitoring - per-client metrics",
                        implementation_guidance="Track usage per API key; monitor rate limit hits; analyze usage patterns; identify abusive clients; generate usage reports; optimize plans based on actual usage"
                    ),
                    SOC2Control(
                        control_id="CC6.6",
                        description="Client activity audit - detailed logging",
                        implementation_guidance="Log API key with each request; track client activity patterns; export logs for billing/audit; implement anomaly detection; maintain compliance audit trails"
                    )
                ]
            ),
            DecisionOption(
                option_id="apigateway-enterprise-optimization",
                name="Enterprise Optimization - Full Observability and Protection",
                description="Comprehensive optimization with caching, usage plans, X-Ray tracing, WAF protection, detailed logging, and automated monitoring.",
                pros_cons=ProConsList(
                    pros=[
                        "Complete observability with X-Ray distributed tracing",
                        "WAF protection against common attacks",
                        "Caching for performance and cost reduction",
                        "Usage plans for client-level control",
                        "Detailed request/response logging",
                        "Automated monitoring and alerting",
                        "Meets enterprise and compliance requirements",
                        "Full security and performance optimization"
                    ],
                    cons=[
                        "Highest cost across all optimization features",
                        "Most complex to configure and manage",
                        "Requires expertise across multiple services",
                        "Higher operational overhead",
                        "Significant log volumes and costs",
                        "Requires REST API (full feature set)",
                        "May be over-engineered for simple APIs"
                    ]
                ),
                estimated_cost="Base + caching (approx. $15/GB) + X-Ray (approx. $5/million traces) + WAF (approx. $5/month + $1/million requests) + logs; typical: $500-5,000/month",
                implementation_complexity="High",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="Enterprise performance - comprehensive optimization",
                        implementation_guidance="Implement caching with monitoring; configure usage plans; enable X-Ray tracing; optimize cache and throttle settings; maintain performance SLAs; document optimization strategy"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Complete observability - X-Ray and CloudWatch",
                        implementation_guidance="Enable X-Ray tracing for request flows; configure CloudWatch dashboards; implement automated alerting; track all performance metrics; maintain operational dashboards; integrate with SIEM"
                    ),
                    SOC2Control(
                        control_id="CC7.3",
                        description="Security protection - WAF and threat prevention",
                        implementation_guidance="Configure WAF with rate limiting; implement SQL injection and XSS rules; enable IP blocklist/allowlist; monitor WAF metrics; respond to threats automatically; maintain security runbooks"
                    ),
                    SOC2Control(
                        control_id="CC6.6",
                        description="Comprehensive audit - detailed request logging",
                        implementation_guidance="Enable full request/response logging; include X-Ray trace IDs; export logs to S3; implement log analysis and retention; maintain compliance audit trails; integrate with log analytics platforms"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Reliability - multi-layer protection and monitoring",
                        implementation_guidance="Implement defense-in-depth; monitor all layers (API, cache, backend); configure automated response; maintain incident response procedures; test failure scenarios; document recovery procedures"
                    ),
                    SOC2Control(
                        control_id="CC6.7",
                        description="Data protection - encryption and caching security",
                        implementation_guidance="Encrypt cache data; enforce TLS 1.2+; validate request headers; sanitize logged data; implement WAF data protection rules; audit security configurations quarterly"
                    )
                ]
            )
        ],
        decision_framework="""
        API GATEWAY OPTIMIZATION SELECTION FRAMEWORK:

        1. ASSESS PERFORMANCE NEEDS:
           - Latency not critical, low volume → Basic Optimization
           - High latency cost, cacheable content → Caching Optimization
           - Per-client controls needed → Advanced Optimization
           - Enterprise SLAs and compliance → Enterprise Optimization

        2. EVALUATE COST OPTIMIZATION POTENTIAL:
           - Backend costs low, simple API → Basic Optimization
           - High backend costs, cacheable responses → Caching Optimization
           - Need client-level billing/limits → Advanced Optimization
           - Complex cost optimization needs → Enterprise Optimization

        3. DETERMINE SECURITY REQUIREMENTS:
           - Basic internal API → Basic Optimization
           - Public API, moderate risk → Advanced Optimization
           - High-value API, attack target → Enterprise Optimization (WAF)
           - Compliance requirements → Enterprise Optimization

        4. CONSIDER OBSERVABILITY NEEDS:
           - Basic metrics sufficient → Basic Optimization
           - Need performance insights → Caching Optimization
           - Need per-client visibility → Advanced Optimization
           - Need distributed tracing → Enterprise Optimization

        5. FACTOR IN OPERATIONAL CAPACITY:
           - Limited ops team → Basic Optimization
           - Can manage caching → Caching Optimization
           - Can manage API keys and plans → Advanced Optimization
           - Advanced ops team → Enterprise Optimization

        OPTIMIZATION COMPARISON:

        | Optimization Level | Caching | Usage Plans | WAF | X-Ray | Cost Factor | Complexity |
        |--------------------|---------|-------------|-----|-------|-------------|------------|
        | Basic | No | No | No | No | 1x | Low |
        | Caching | Yes | No | No | No | 1.5-3x | Medium |
        | Advanced | Optional | Yes | Optional | No | 1.5-4x | Medium-High |
        | Enterprise | Yes | Yes | Yes | Yes | 3-10x | High |

        CACHING STRATEGY:

        Cache Size Selection:
        - Start small (0.5-1GB) and monitor utilization
        - Monitor CloudWatch CacheHitCount/CacheMissCount
        - Scale up if cache evictions are frequent
        - Aim for <80% cache utilization

        Cache Key Design:
        - Include only necessary request parameters
        - Exclude user-specific parameters for shared cache
        - Use query strings, headers, or path for keys
        - Test cache key effectiveness

        TTL Configuration:
        - Static content: 3600 seconds (1 hour)
        - Semi-static content: 300-900 seconds (5-15 minutes)
        - Dynamic with acceptable staleness: 60-300 seconds
        - Real-time data: Do not cache or very low TTL

        Cache Invalidation:
        - Implement cache flush API for manual invalidation
        - Use cache control headers for per-request bypass
        - Consider cache key versioning for deployments
        - Monitor cache staleness issues

        THROTTLING STRATEGY:

        Account-Level Throttling (All APIs):
        - Steady-state rate: Requests per second across all APIs
        - Burst: Additional capacity for short spikes
        - Default: 10,000 rps steady, 5,000 burst
        - Adjust based on backend capacity

        Method-Level Throttling (REST API):
        - Configure per-method rate limits
        - Prioritize critical endpoints
        - Protect expensive operations
        - Example: Limit POST to 100 rps, GET to 1000 rps

        Usage Plans (REST API):
        - Define tiers (e.g., Free, Pro, Enterprise)
        - Set rate and burst limits per tier
        - Configure daily/monthly quotas
        - Monitor and adjust based on actual usage

        MONITORING BEST PRACTICES:

        Essential Metrics:
        - Count: Total requests
        - IntegrationLatency: Backend execution time
        - Latency: Total end-to-end latency
        - 4XXError: Client errors
        - 5XXError: Server errors
        - CacheHitCount/CacheMissCount (if caching enabled)

        CloudWatch Alarms:
        - 5XXError rate >1% (backend issues)
        - 4XXError rate >5% (client issues or abuse)
        - IntegrationLatency p99 > threshold (backend performance)
        - Latency p99 > threshold (overall performance)
        - Throttle events (capacity issues)

        X-Ray Tracing (Enterprise):
        - Enable for all routes or sample (e.g., 10%)
        - Trace Lambda, DynamoDB, and other integrations
        - Identify bottlenecks in request flow
        - Monitor trace error rates

        COST OPTIMIZATION TACTICS:

        1. Choose Right API Type:
           - Use HTTP API over REST API when possible (71% savings)
           - Only use REST API when features required

        2. Optimize Caching:
           - Right-size cache capacity (start small)
           - Monitor hit rate and adjust TTL
           - Cache hit = free request to backend
           - Example: 80% hit rate = 80% backend cost savings

        3. Reduce Logging Costs:
           - Log only necessary fields
           - Use sampling for high-volume endpoints
           - Export to S3 for long-term retention (cheaper)
           - Implement log filtering

        4. Optimize Integrations:
           - Use Lambda proxy integration for efficiency
           - Minimize integration timeout values
           - Optimize backend performance (faster = cheaper)
           - Batch requests where possible

        5. Monitor and Adjust:
           - Review AWS Cost Explorer monthly
           - Identify high-cost endpoints
           - Implement caching or optimization as needed
           - Eliminate unused APIs promptly

        PERFORMANCE OPTIMIZATION:

        Reduce Latency:
        - Use regional endpoints for single-region users
        - Use edge-optimized for global users
        - Enable caching for cacheable responses
        - Optimize Lambda cold starts (provisioned concurrency)
        - Minimize integration payload size

        Increase Throughput:
        - Request account limit increase if needed (default 10k rps)
        - Use usage plans to distribute capacity fairly
        - Implement client-side throttling and backoff
        - Scale backend services appropriately

        Improve Reliability:
        - Implement retry logic with exponential backoff
        - Use Circuit Breaker pattern for failing backends
        - Configure appropriate timeouts
        - Monitor and alert on error rates
        - Test failure scenarios

        SECURITY OPTIMIZATION:

        WAF Configuration (Enterprise):
        - Rate-based rule: Block IPs exceeding threshold
        - SQL injection and XSS rules
        - Geo-blocking for specific regions
        - IP allowlist/blocklist
        - Custom rules for application logic

        Request Validation:
        - Use request validators (REST API)
        - Validate request bodies against models
        - Validate query parameters and headers
        - Reject malformed requests at edge

        CORS Configuration:
        - Configure restrictive CORS policies
        - Specify allowed origins explicitly
        - Limit allowed methods and headers
        - Set appropriate credentials and max-age
        """,
        real_world_examples=[
            "Media company implemented Caching Optimization with 20GB cache for CDN origin, achieving 85% cache hit rate and reducing Lambda costs from $3,000 to $450/month",
            "SaaS platform used Advanced Optimization with usage plans for API monetization, managing 100+ clients with tiered rate limits and generating $50k/month API revenue",
            "Financial services deployed Enterprise Optimization with WAF, X-Ray, and caching, achieving <100ms p99 latency while blocking 500k malicious requests/month",
            "Startup used Basic Optimization for MVP API, spending $150/month with CloudWatch monitoring, then migrated to caching as traffic grew, saving 60% on backend costs"
        ],
        references=[
            "https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-caching.html",
            "https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-request-throttling.html",
            "https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-xray.html",
            "https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-control-access-aws-waf.html"
        ]
    )


# Export all patterns
APIGATEWAY_PATTERNS = [
    get_apigateway_type_pattern(),
    get_apigateway_authorization_pattern(),
    get_apigateway_optimization_pattern()
]
