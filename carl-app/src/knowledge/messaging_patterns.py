"""
Messaging Patterns for CARL
Provides decision frameworks for AWS messaging services including SQS, SNS, and EventBridge patterns.
"""

from typing import List, Dict, Any
from .models import (
    DecisionPattern,
    DecisionOption,
    DecisionCriteria,
    ProConsList,
    SOC2Control
)


def get_messaging_queue_pattern() -> DecisionPattern:
    """
    Pattern for selecting messaging/queue service (SQS Standard, FIFO, SNS, EventBridge).
    Covers use cases, ordering requirements, and integration patterns.
    """
    return DecisionPattern(
        pattern_id="messaging-queue-selection",
        name="Messaging and Queue Service Selection",
        category="integration",
        subcategory="messaging",
        description="Framework for selecting the appropriate AWS messaging service (SQS Standard/FIFO, SNS, EventBridge) based on delivery guarantees, ordering requirements, and integration patterns.",
        decision_criteria=[
            DecisionCriteria(
                criterion="Message Delivery Pattern",
                weight=0.30,
                considerations=[
                    "Do you need point-to-point or publish-subscribe?",
                    "How many consumers need to receive each message?",
                    "Do you need message routing and filtering?",
                    "Do you need fan-out to multiple services?"
                ]
            ),
            DecisionCriteria(
                criterion="Ordering and Delivery Guarantees",
                weight=0.25,
                considerations=[
                    "Do you need strict message ordering?",
                    "Can you tolerate duplicate messages?",
                    "Do you need exactly-once processing?",
                    "What is your deduplication window requirement?"
                ]
            ),
            DecisionCriteria(
                criterion="Performance and Scale",
                weight=0.20,
                considerations=[
                    "What is your message volume (per second)?",
                    "Do you need unlimited throughput?",
                    "Do you need low latency?",
                    "Do you need batching capabilities?"
                ]
            ),
            DecisionCriteria(
                criterion="Integration Requirements",
                weight=0.15,
                considerations=[
                    "What services need to integrate (Lambda, ECS, on-prem)?",
                    "Do you need event-driven architecture patterns?",
                    "Do you need content-based routing?",
                    "Do you need cross-account/cross-region delivery?"
                ]
            ),
            DecisionCriteria(
                criterion="Cost Optimization",
                weight=0.10,
                considerations=[
                    "What is your messaging budget?",
                    "What is your expected message volume?",
                    "Do you need cost-effective fan-out?",
                    "Can you tolerate at-least-once delivery for lower cost?"
                ]
            )
        ],
        options=[
            DecisionOption(
                option_id="messaging-sqs-standard",
                name="SQS Standard Queue",
                description="High-throughput, at-least-once delivery queue with nearly unlimited throughput. No ordering guarantees but allows duplicates.",
                pros_cons=ProConsList(
                    pros=[
                        "Nearly unlimited throughput (no TPS limit)",
                        "Low cost ($0.40 per million requests after free tier)",
                        "Best-effort ordering (messages generally arrive in order)",
                        "Long polling reduces empty receives and costs",
                        "Scales automatically to handle any load",
                        "Dead Letter Queue (DLQ) for failed messages",
                        "Supports message visibility timeout and delays",
                        "Simple to use and integrate"
                    ],
                    cons=[
                        "No strict message ordering guarantees",
                        "At-least-once delivery (duplicates possible)",
                        "Application must be idempotent",
                        "No message deduplication",
                        "Cannot guarantee FIFO processing",
                        "Not suitable for strictly ordered workflows"
                    ]
                ),
                estimated_cost="$0.40 per million requests after 1M free; typical: $5-100/month for 10-250M requests",
                implementation_complexity="Low",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="High availability - distributed queue with auto-scaling",
                        implementation_guidance="Configure appropriate retention period (1-14 days); implement DLQ for failed messages; monitor queue depth; configure alarms for age of oldest message; handle duplicates in application logic"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Message durability - replicated storage",
                        implementation_guidance="Configure message retention period; implement DLQ with longer retention; monitor DLQ depth; implement message replay capability; test message recovery procedures"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Monitoring - queue metrics and alarms",
                        implementation_guidance="Monitor ApproximateNumberOfMessagesVisible; track ApproximateAgeOfOldestMessage; configure alarms for queue depth; monitor DLQ; review CloudWatch metrics regularly"
                    )
                ]
            ),
            DecisionOption(
                option_id="messaging-sqs-fifo",
                name="SQS FIFO Queue",
                description="First-in-first-out delivery queue with exactly-once processing and strict ordering within message groups. Limited to 3,000 TPS.",
                pros_cons=ProConsList(
                    pros=[
                        "Strict message ordering within message groups",
                        "Exactly-once processing (no duplicates)",
                        "Message deduplication (5-minute window)",
                        "Supports up to 10 message groups per queue",
                        "High throughput mode: 3,000 TPS (30,000 with batching)",
                        "Dead Letter Queue support",
                        "Visibility timeout and message delays"
                    ],
                    cons=[
                        "Limited throughput (3,000 messages/sec, 30,000 with batching)",
                        "Higher cost than Standard queue ($0.50 per million requests)",
                        "More complex message group design required",
                        "Name must end with .fifo suffix",
                        "Cannot convert Standard queue to FIFO",
                        "Ordering only within message groups (not global)"
                    ]
                ),
                estimated_cost="$0.50 per million requests; typical: $10-200/month for 20-400M requests",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="Ordered processing - FIFO guarantees with high availability",
                        implementation_guidance="Design message group strategy; configure deduplication; implement DLQ; monitor throughput vs limits; handle throughput throttling; test ordering guarantees"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Exactly-once processing - message deduplication",
                        implementation_guidance="Configure content-based or message deduplication ID; set appropriate deduplication interval; monitor duplicates; test deduplication logic; document message group design"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Performance monitoring - throughput and ordering",
                        implementation_guidance="Monitor messages sent per second; track message groups; configure alarms for throughput limits; review performance patterns; optimize message group distribution"
                    )
                ]
            ),
            DecisionOption(
                option_id="messaging-sns",
                name="Amazon SNS (Simple Notification Service)",
                description="Fully managed pub/sub messaging service supporting fan-out to multiple subscribers (SQS, Lambda, HTTP, email, SMS).",
                pros_cons=ProConsList(
                    pros=[
                        "Publish-subscribe pattern with multiple subscribers",
                        "Fan-out to SQS, Lambda, HTTP/S, email, SMS, mobile push",
                        "Message filtering based on attributes",
                        "High throughput with no limits",
                        "Cross-region and cross-account delivery",
                        "FIFO topics for ordered fan-out",
                        "Message archival to S3 or Kinesis",
                        "Low latency delivery"
                    ],
                    cons=[
                        "No message persistence (fire-and-forget)",
                        "No message replay capability",
                        "No built-in retry for HTTP subscribers (unless using SQS)",
                        "At-most-once delivery to HTTP endpoints",
                        "Limited message size (256KB)",
                        "No message batching for efficiency",
                        "More expensive for high-volume point-to-point"
                    ]
                ),
                estimated_cost="$0.50 per million requests + delivery costs (HTTP: $0.60/million, SMS: varies); typical: $10-150/month",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="Fan-out delivery - multiple subscriber support",
                        implementation_guidance="Configure topic with appropriate subscribers; implement message filtering; use SQS for durable delivery; monitor delivery success; configure DLQ for failed deliveries; test subscriber failures"
                    ),
                    SOC2Control(
                        control_id="CC6.1",
                        description="Access control - topic policies for subscribers",
                        implementation_guidance="Configure topic policy for authorized subscribers; use IAM for access control; enable encryption at rest; implement least-privilege subscriptions; audit topic access"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Delivery monitoring - track success and failures",
                        implementation_guidance="Monitor NumberOfNotificationsDelivered; track NumberOfNotificationsFailed; configure CloudWatch alarms; implement retry logic for HTTP endpoints; review delivery logs"
                    )
                ]
            ),
            DecisionOption(
                option_id="messaging-eventbridge",
                name="Amazon EventBridge",
                description="Serverless event bus for building event-driven architectures with content-based routing, transformation, and integration with 90+ AWS services.",
                pros_cons=ProConsList(
                    pros=[
                        "Content-based routing with powerful pattern matching",
                        "Native integration with 90+ AWS services",
                        "Schema registry for event definition and discovery",
                        "Event replay and archive capabilities",
                        "Cross-account and cross-region routing",
                        "Event transformation with input transformers",
                        "SaaS partner integrations (Zendesk, Shopify, etc.)",
                        "API destinations for custom HTTP endpoints",
                        "Dead-letter queues for failed targets"
                    ],
                    cons=[
                        "Higher cost than SQS/SNS ($1 per million events)",
                        "5 targets per rule limit (though can use SNS fan-out)",
                        "More complex than simple queuing",
                        "Learning curve for event patterns and routing",
                        "Not ideal for simple point-to-point messaging",
                        "Event size limit (256KB)",
                        "Eventual consistency for rule updates"
                    ]
                ),
                estimated_cost="$1.00 per million events + ingestion ($1/million for partner/custom); typical: $50-500/month for 50-500M events",
                implementation_complexity="High",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="Event-driven architecture - reliable event routing",
                        implementation_guidance="Design event schemas; configure event rules with appropriate patterns; implement DLQ for failed targets; enable event archiving; test routing patterns; monitor event delivery"
                    ),
                    SOC2Control(
                        control_id="CC6.1",
                        description="Access control - event bus policies and schemas",
                        implementation_guidance="Configure event bus policies; use IAM for event publishing; implement least-privilege target access; encrypt events at rest; audit event bus access; document event flows"
                    ),
                    SOC2Control(
                        control_id="CC6.6",
                        description="Event audit trails - event archiving and replay",
                        implementation_guidance="Enable event archiving to S3; configure retention periods; implement event replay capability; export events for analysis; maintain event audit logs; integrate with SIEM"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Event monitoring - comprehensive visibility",
                        implementation_guidance="Monitor Invocations metric; track FailedInvocations; configure alarms for delivery failures; use schema registry for event discovery; review event patterns; implement observability"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Event durability - archiving and replay",
                        implementation_guidance="Configure event archive with appropriate retention; test event replay; document replay procedures; verify archived events; implement disaster recovery for events"
                    )
                ]
            )
        ],
        decision_framework="""
        MESSAGING SERVICE SELECTION FRAMEWORK:

        1. DETERMINE DELIVERY PATTERN:
           - Point-to-point (single consumer) → SQS (Standard or FIFO)
           - Publish-subscribe (multiple consumers) → SNS or EventBridge
           - Event-driven routing → EventBridge
           - Simple fan-out → SNS

        2. EVALUATE ORDERING REQUIREMENTS:
           - No ordering needed → SQS Standard or SNS
           - Strict ordering required → SQS FIFO or SNS FIFO
           - Order within groups → SQS FIFO with message groups
           - Event ordering with routing → EventBridge (with SQS FIFO targets)

        3. ASSESS DELIVERY GUARANTEES:
           - At-least-once acceptable (idempotent) → SQS Standard or SNS
           - Exactly-once required → SQS FIFO
           - Fire-and-forget acceptable → SNS
           - Need message replay → EventBridge (with archive)

        4. CONSIDER THROUGHPUT NEEDS:
           - Unlimited throughput → SQS Standard, SNS, or EventBridge
           - <3,000 TPS with ordering → SQS FIFO
           - Variable throughput → SQS Standard (auto-scales)
           - High-volume event routing → EventBridge

        5. EVALUATE INTEGRATION COMPLEXITY:
           - Simple queue for Lambda → SQS Standard
           - Multiple consumers (same message) → SNS
           - Complex routing rules → EventBridge
           - Cross-service integration → EventBridge

        MESSAGING SERVICE COMPARISON:

        | Feature | SQS Standard | SQS FIFO | SNS | EventBridge |
        |---------|-------------|----------|-----|-------------|
        | Delivery | At-least-once | Exactly-once | At-most-once* | At-least-once |
        | Ordering | Best-effort | Strict FIFO | No** | No** |
        | Throughput | Unlimited | 3k TPS | Unlimited | Unlimited |
        | Persistence | Yes | Yes | No*** | Archive |
        | Fan-out | No | No | Yes | Yes |
        | Routing | No | No | Filter | Patterns |
        | Replay | No | No | No | Yes |
        | Cost/M | $0.40 | $0.50 | $0.50+ | $1.00 |

        *At-least-once with SQS subscribers
        **SNS FIFO and EventBridge with ordered targets can maintain order
        ***SNS messages can be archived via Kinesis Firehose

        USE CASE RECOMMENDATIONS:

        | Use Case | Best Service | Rationale |
        |----------|-------------|-----------|
        | Task queue for workers | SQS Standard | Decoupling, at-least-once, high throughput |
        | Order processing | SQS FIFO | Strict ordering, exactly-once |
        | Fan-out notifications | SNS | Multiple subscribers, simple pub/sub |
        | Microservices decoupling | SQS Standard | Point-to-point, buffering |
        | Event-driven architecture | EventBridge | Content routing, integrations |
        | Log processing pipeline | SQS Standard → Lambda | Buffering, retry, DLQ |
        | Real-time alerts | SNS | Immediate delivery, multiple channels |
        | Workflow orchestration | EventBridge + SQS FIFO | Event routing + ordering |
        | Cross-account events | EventBridge | Built-in cross-account support |
        | Payment processing | SQS FIFO | Exactly-once, ordered |

        COMMON PATTERNS:

        1. SNS + SQS Fan-Out Pattern:
           - SNS topic → multiple SQS queues
           - Benefits: Durable fan-out, independent processing, DLQ per queue
           - Use case: Single event needs processing by multiple services

        2. EventBridge + SQS Pattern:
           - EventBridge routes events → SQS queues based on rules
           - Benefits: Content-based routing + durable queuing
           - Use case: Different event types to different processors

        3. SQS FIFO + DLQ Pattern:
           - FIFO queue → Lambda processor → DLQ for failures
           - Benefits: Ordered processing with failure handling
           - Use case: Sequential workflows with error handling

        4. EventBridge Archive + Replay:
           - EventBridge archives all events → replay on demand
           - Benefits: Event sourcing, debugging, recovery
           - Use case: Audit trails, event replay for testing

        COST OPTIMIZATION:

        SQS Optimization:
        - Use long polling (ReceiveMessageWaitTimeSeconds=20) to reduce empty receives
        - Batch messages (up to 10 per request) to reduce API calls
        - Set appropriate message retention (1-14 days, default 4)
        - Use visibility timeout wisely to avoid duplicate processing
        - Monitor and delete unused queues

        SNS Optimization:
        - Use SQS subscribers for durable delivery (cheaper than HTTP retries)
        - Implement message filtering to reduce unnecessary deliveries
        - Batch where possible (not native, but can aggregate at publisher)
        - Use appropriate delivery protocols (SQS cheaper than HTTP)
        - Monitor and remove unused subscriptions

        EventBridge Optimization:
        - Use specific event patterns to reduce rule evaluations
        - Consolidate rules where possible (5 targets per rule)
        - Use SNS for additional fan-out beyond 5 targets
        - Archive only necessary events (storage costs)
        - Monitor and remove unused rules

        SECURITY BEST PRACTICES:

        SQS Security:
        - Enable encryption at rest (SQS-managed or KMS)
        - Enable encryption in transit (HTTPS)
        - Use IAM policies for access control
        - Implement queue policies for cross-account access
        - Enable VPC endpoints for private access
        - Monitor queue access with CloudTrail

        SNS Security:
        - Enable encryption at rest with KMS
        - Use topic policies to control publishers/subscribers
        - Implement subscription confirmation for HTTP/S
        - Enable delivery status logging
        - Use VPC endpoints for private publishing
        - Monitor topic access with CloudTrail

        EventBridge Security:
        - Enable encryption for event bus
        - Use event bus policies for cross-account access
        - Implement least-privilege IAM for publishers
        - Enable CloudTrail for event bus API calls
        - Use resource-based policies for targets
        - Encrypt archived events in S3

        MONITORING AND ALARMS:

        SQS Key Metrics:
        - ApproximateNumberOfMessagesVisible: Queue depth
        - ApproximateAgeOfOldestMessage: Processing lag
        - NumberOfMessagesSent/Deleted: Throughput
        - ApproximateNumberOfMessagesNotVisible: In-flight messages
        - NumberOfMessagesDeleted: Processing rate

        SNS Key Metrics:
        - NumberOfMessagesPublished: Publish rate
        - NumberOfNotificationsDelivered: Successful deliveries
        - NumberOfNotificationsFailed: Failed deliveries
        - NumberOfNotificationsFilteredOut: Filtered messages
        - DeliveryLatency: Time to deliver (HTTP/S)

        EventBridge Key Metrics:
        - Invocations: Total events matched by rules
        - FailedInvocations: Failed target deliveries
        - TriggeredRules: Rules that matched events
        - ThrottledRules: Rules that hit limits
        - Events: Total events published

        Recommended Alarms:
        - SQS: ApproximateAgeOfOldestMessage > 5 minutes
        - SQS: ApproximateNumberOfMessagesVisible > threshold
        - SNS: NumberOfNotificationsFailed > 0
        - EventBridge: FailedInvocations > threshold
        - All: DLQ message count > 0

        RELIABILITY PATTERNS:

        Dead Letter Queues:
        - Configure DLQ for all queues and topics
        - Set maxReceiveCount appropriately (3-5 for SQS)
        - Monitor DLQ depth and investigate failures
        - Implement DLQ processing and recovery
        - Alert on DLQ messages

        Retry and Backoff:
        - Implement exponential backoff in consumers
        - Use visibility timeout for automatic retry (SQS)
        - Configure retry policies for SNS subscriptions
        - Handle transient failures gracefully
        - Monitor retry metrics

        Idempotency:
        - Design consumers to be idempotent
        - Use deduplication IDs (SQS FIFO)
        - Implement idempotency keys in processing
        - Track processed message IDs
        - Handle duplicate deliveries gracefully
        """,
        real_world_examples=[
            "E-commerce platform used SQS Standard for order processing queue, handling 500k orders/day with Lambda workers, implementing DLQ for failed orders",
            "Financial services used SQS FIFO for payment processing, ensuring exactly-once processing and strict ordering of transactions, preventing duplicate charges",
            "SaaS company used SNS fan-out to 5 SQS queues for different microservices, enabling independent scaling and processing of customer events",
            "Enterprise implemented EventBridge for event-driven architecture, routing 10M events/day to 50+ targets with content-based rules and event replay capability"
        ],
        references=[
            "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/welcome.html",
            "https://docs.aws.amazon.com/sns/latest/dg/welcome.html",
            "https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-what-is.html",
            "https://aws.amazon.com/messaging/pricing/"
        ]
    )


def get_messaging_reliability_pattern() -> DecisionPattern:
    """
    Pattern for implementing reliable messaging with error handling and retries.
    Covers DLQ, retry strategies, and failure handling patterns.
    """
    return DecisionPattern(
        pattern_id="messaging-reliability-strategy",
        name="Messaging Reliability and Error Handling",
        category="integration",
        subcategory="messaging",
        description="Framework for implementing reliable messaging patterns with dead letter queues, retry strategies, idempotency, and failure recovery procedures.",
        decision_criteria=[
            DecisionCriteria(
                criterion="Failure Impact",
                weight=0.30,
                considerations=[
                    "What is the impact of message loss?",
                    "Can you tolerate message processing failures?",
                    "Do you need guaranteed delivery?",
                    "What is the cost of duplicate processing?"
                ]
            ),
            DecisionCriteria(
                criterion="Recovery Requirements",
                weight=0.25,
                considerations=[
                    "How quickly must you recover from failures?",
                    "Do you need automatic retry?",
                    "Do you need manual intervention for failures?",
                    "Can you replay messages?"
                ]
            ),
            DecisionCriteria(
                criterion="Consistency Requirements",
                weight=0.20,
                considerations=[
                    "Do you need exactly-once processing?",
                    "Can you handle duplicate messages?",
                    "Do you need idempotent operations?",
                    "What are your ordering guarantees?"
                ]
            ),
            DecisionCriteria(
                criterion="Operational Complexity",
                weight=0.15,
                considerations=[
                    "Can you manage DLQ processing?",
                    "Can you implement retry logic?",
                    "Do you need automated recovery?",
                    "What is your monitoring capability?"
                ]
            ),
            DecisionCriteria(
                criterion="Cost Tolerance",
                weight=0.10,
                considerations=[
                    "Can you tolerate retry costs?",
                    "What is your failure rate?",
                    "Can you implement efficient retry strategies?",
                    "What is your DLQ storage cost tolerance?"
                ]
            )
        ],
        options=[
            DecisionOption(
                option_id="messaging-basic-reliability",
                name="Basic Reliability - DLQ Only",
                description="Simple reliability with Dead Letter Queues to capture permanently failed messages for manual investigation.",
                pros_cons=ProConsList(
                    pros=[
                        "Simple to implement and understand",
                        "Prevents message loss from repeated failures",
                        "Low operational overhead",
                        "DLQ provides failure visibility",
                        "Manual control over failure handling",
                        "No additional cost beyond DLQ storage"
                    ],
                    cons=[
                        "No automatic retry mechanism",
                        "Requires manual DLQ processing",
                        "Messages can be lost if consumer crashes before acknowledgment",
                        "No exponential backoff for transient failures",
                        "Limited failure recovery automation",
                        "Can accumulate large DLQ backlogs"
                    ]
                ),
                estimated_cost="Base messaging cost + DLQ storage (minimal); typical: $5-50/month",
                implementation_complexity="Low",
                soc2_controls=[
                    SOC2Control(
                        control_id="A1.2",
                        description="Message durability - DLQ for failed messages",
                        implementation_guidance="Configure DLQ for all queues; set maxReceiveCount appropriately; monitor DLQ depth; implement manual DLQ review process; document failure investigation procedures"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Failure monitoring - DLQ visibility",
                        implementation_guidance="Configure CloudWatch alarm for DLQ message count; review DLQ messages regularly; categorize failure types; track resolution time; maintain failure metrics"
                    )
                ]
            ),
            DecisionOption(
                option_id="messaging-retry-with-backoff",
                name="Automatic Retry with Exponential Backoff",
                description="Implements automatic retry with exponential backoff using visibility timeout (SQS) or Lambda retry configuration for transient failures.",
                pros_cons=ProConsList(
                    pros=[
                        "Automatic handling of transient failures",
                        "Exponential backoff prevents thundering herd",
                        "Reduces manual intervention",
                        "Configurable retry limits",
                        "Works well for network/timeout errors",
                        "Balances quick retry with system protection"
                    ],
                    cons=[
                        "Can increase message processing latency",
                        "Retry costs accumulate",
                        "Ineffective for permanent failures (still need DLQ)",
                        "Requires careful tuning of backoff parameters",
                        "Can delay failure detection",
                        "More complex than DLQ-only approach"
                    ]
                ),
                estimated_cost="Base cost + retry invocations (~20-50% increase typical); typical: $10-150/month",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="A1.1",
                        description="Automatic recovery - retry for transient failures",
                        implementation_guidance="Configure visibility timeout for retries; implement exponential backoff (e.g., 1s, 2s, 4s, 8s); set maxReceiveCount before DLQ; monitor retry success rate; tune backoff parameters based on failure patterns"
                    ),
                    SOC2Control(
                        control_id="CC9.1",
                        description="Resilience - graceful failure handling",
                        implementation_guidance="Implement circuit breaker pattern; handle both transient and permanent failures; log retry attempts; configure appropriate timeout values; test retry behavior under load"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Retry monitoring - track retry patterns",
                        implementation_guidance="Monitor ApproximateReceiveCount; track retry success vs failure; configure alarms for high retry rates; analyze failure patterns; optimize retry configuration"
                    )
                ]
            ),
            DecisionOption(
                option_id="messaging-idempotent-processing",
                name="Idempotent Processing with Deduplication",
                description="Ensures exactly-once processing semantics using idempotency keys, deduplication IDs, and DynamoDB/ElastiCache for tracking.",
                pros_cons=ProConsList(
                    pros=[
                        "Prevents duplicate processing",
                        "Safe to retry without side effects",
                        "Works with SQS Standard (at-least-once)",
                        "Enables safe automatic retries",
                        "Critical for financial transactions and payments",
                        "Provides strong consistency guarantees",
                        "Simplifies application logic"
                    ],
                    cons=[
                        "Additional storage cost for idempotency tracking",
                        "Increased processing latency (idempotency check)",
                        "Requires careful design of idempotency keys",
                        "Need to manage idempotency store lifecycle",
                        "Adds complexity to consumer implementation",
                        "Performance impact of idempotency lookups"
                    ]
                ),
                estimated_cost="Base + DynamoDB/ElastiCache for tracking (~$20-100/month); typical: $50-300/month",
                implementation_complexity="High",
                soc2_controls=[
                    SOC2Control(
                        control_id="A1.1",
                        description="Exactly-once semantics - idempotency implementation",
                        implementation_guidance="Design idempotency key strategy; implement idempotency store (DynamoDB or ElastiCache); set appropriate TTL for idempotency records; handle idempotency check failures; test duplicate scenarios"
                    ),
                    SOC2Control(
                        control_id="CC6.6",
                        description="Processing audit - idempotency tracking",
                        implementation_guidance="Log all idempotency checks; track duplicate detection; monitor idempotency store performance; maintain audit trail of processed messages; implement idempotency key analysis"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Deduplication monitoring - track effectiveness",
                        implementation_guidance="Monitor duplicate detection rate; track idempotency store hits; configure alarms for idempotency failures; analyze processing patterns; optimize idempotency key design"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Data consistency - idempotency store durability",
                        implementation_guidance="Configure appropriate backup for idempotency store; test recovery scenarios; implement TTL for old records; monitor store capacity; document idempotency strategy"
                    )
                ]
            ),
            DecisionOption(
                option_id="messaging-comprehensive-reliability",
                name="Comprehensive Reliability - Full Automation",
                description="Enterprise-grade reliability with automatic retry, circuit breakers, idempotency, DLQ processing, alerting, and automated recovery.",
                pros_cons=ProConsList(
                    pros=[
                        "Maximum reliability with minimal message loss",
                        "Automatic handling of transient and permanent failures",
                        "Idempotency prevents duplicate processing",
                        "Circuit breakers protect downstream systems",
                        "Automated DLQ processing and recovery",
                        "Comprehensive monitoring and alerting",
                        "Detailed failure analytics and reporting",
                        "Meets enterprise and compliance requirements"
                    ],
                    cons=[
                        "Highest cost across infrastructure components",
                        "Most complex to implement and maintain",
                        "Requires expertise in distributed systems",
                        "Higher operational overhead",
                        "Significant monitoring and logging costs",
                        "May be over-engineered for simple use cases",
                        "Requires ongoing tuning and optimization"
                    ]
                ),
                estimated_cost="Base + idempotency store + monitoring + automation (~$100-500/month); typical: $200-1,000/month",
                implementation_complexity="Very High",
                soc2_controls=[
                    SOC2Control(
                        control_id="A1.1",
                        description="Enterprise reliability - comprehensive failure handling",
                        implementation_guidance="Implement retry with exponential backoff; configure circuit breakers; implement idempotency; deploy DLQ processing automation; configure appropriate timeouts; test all failure scenarios comprehensively"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Message durability - multi-layer protection",
                        implementation_guidance="Configure DLQ with long retention; implement automated DLQ processing; enable message archiving; test recovery procedures; maintain disaster recovery plan; document message lifecycle"
                    ),
                    SOC2Control(
                        control_id="CC9.1",
                        description="System resilience - protect downstream systems",
                        implementation_guidance="Implement circuit breaker pattern; configure bulkhead pattern for isolation; implement rate limiting; monitor system health; automate failover; maintain service dependencies documentation"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Comprehensive monitoring - full observability",
                        implementation_guidance="Monitor all retry attempts; track idempotency hits; configure detailed CloudWatch dashboards; implement distributed tracing; alert on anomalies; integrate with SIEM; maintain operational runbooks"
                    ),
                    SOC2Control(
                        control_id="CC7.3",
                        description="Automated response - self-healing capabilities",
                        implementation_guidance="Implement Lambda for automated DLQ processing; configure EventBridge for workflow orchestration; automate recovery procedures; implement self-healing mechanisms; test automation regularly"
                    ),
                    SOC2Control(
                        control_id="CC6.6",
                        description="Complete audit trail - comprehensive logging",
                        implementation_guidance="Log all message lifecycle events; track processing attempts; maintain failure audit trail; export logs for compliance; implement log analysis; retain logs per requirements (7+ years)"
                    )
                ]
            )
        ],
        decision_framework="""
        MESSAGING RELIABILITY SELECTION FRAMEWORK:

        1. ASSESS FAILURE IMPACT:
           - Low impact, acceptable loss → Basic Reliability
           - Moderate impact, transient failures → Retry with Backoff
           - High impact, financial/critical → Idempotent Processing
           - Mission-critical, zero tolerance → Comprehensive Reliability

        2. EVALUATE FAILURE TYPES:
           - Mostly permanent failures → Basic Reliability (DLQ)
           - Mix of transient and permanent → Retry with Backoff
           - At-least-once delivery issues → Idempotent Processing
           - Complex distributed system → Comprehensive Reliability

        3. DETERMINE PROCESSING GUARANTEES:
           - At-least-once acceptable → Basic or Retry
           - Need exactly-once → Idempotent Processing or Comprehensive
           - Strict ordering required → SQS FIFO + appropriate strategy
           - Multiple consumers → Comprehensive with fan-out protection

        4. CONSIDER OPERATIONAL CAPACITY:
           - Limited ops team → Basic Reliability
           - Can implement retry logic → Retry with Backoff
           - Can manage idempotency → Idempotent Processing
           - Advanced ops team → Comprehensive Reliability

        5. FACTOR IN COST SENSITIVITY:
           - Cost-sensitive, simple use case → Basic Reliability
           - Moderate budget, need automation → Retry with Backoff
           - Justify additional infrastructure → Idempotent Processing
           - Maximum reliability required → Comprehensive Reliability

        RELIABILITY COMPARISON:

        | Strategy | Message Loss | Duplicates | Complexity | Cost Factor | Auto Recovery |
        |----------|-------------|-----------|------------|-------------|---------------|
        | Basic | Low | Possible | Low | 1x | Manual |
        | Retry | Very Low | Possible | Medium | 1.2-1.5x | Partial |
        | Idempotent | Very Low | Prevented | High | 1.5-2x | Partial |
        | Comprehensive | Near Zero | Prevented | Very High | 2-3x | Full |

        RETRY STRATEGIES:

        Exponential Backoff Configuration:
        - Initial delay: 1 second
        - Backoff multiplier: 2x
        - Maximum delay: 60-300 seconds
        - Max retries: 3-5 (before DLQ)
        - Jitter: Add randomness to prevent thundering herd

        SQS Visibility Timeout:
        - Set based on expected processing time
        - Example: Processing takes 30s, set visibility timeout to 40s
        - For retries: Increase timeout on each retry (approximates backoff)
        - Monitor: ApproximateReceiveCount to track retry attempts

        Lambda Retry Configuration:
        - SQS: Configure MaxReceiveCount on queue
        - SNS: Configure retry policy on subscription
        - EventBridge: Configure retry policy and DLQ on target
        - Asynchronous invocations: 0-2 retries (default 2)

        IDEMPOTENCY IMPLEMENTATION:

        Idempotency Key Design:
        - Use message ID + operation ID
        - Include timestamp for uniqueness
        - Consider business-level keys (order ID, transaction ID)
        - Example: {messageId}-{operationType}-{businessId}

        Idempotency Store Options:
        - DynamoDB: Conditional writes for atomic checks
        - ElastiCache (Redis): SET with NX flag
        - Aurora: Unique constraints on idempotency key
        - Choose based on performance and cost requirements

        Idempotency TTL:
        - Set based on deduplication window
        - SQS FIFO: 5 minutes (matches deduplication)
        - Standard processing: 1-24 hours
        - Long-lived workflows: Days to weeks
        - Balance storage cost vs duplicate risk

        CIRCUIT BREAKER PATTERN:

        Implementation:
        - Track failure rate over sliding window
        - Open circuit if failure rate exceeds threshold (e.g., 50%)
        - Half-open state: Allow limited requests to test recovery
        - Close circuit when success rate improves

        Configuration:
        - Failure threshold: 50-80%
        - Circuit open duration: 30-60 seconds
        - Half-open requests: 3-5 test requests
        - Monitor: Circuit state changes and trip events

        DLQ PROCESSING STRATEGIES:

        Manual DLQ Review:
        - Periodic review (daily/weekly)
        - Categorize failure types
        - Fix application issues
        - Replay messages manually

        Automated DLQ Processing:
        - Lambda triggered by DLQ messages
        - Analyze failure reason
        - Categorize and route appropriately
        - Automatic replay for transient issues
        - Alert for manual intervention needed

        DLQ Metrics:
        - Monitor DLQ message count
        - Track message age in DLQ
        - Categorize failure types
        - Measure resolution time
        - Alert on DLQ growth

        MONITORING AND ALERTING:

        Key Metrics:
        - Processing success rate (>99.9% target)
        - Retry rate (low is good)
        - DLQ message count (should be low)
        - Idempotency hit rate (duplicates prevented)
        - Processing latency (p50, p99)
        - Circuit breaker trips

        Critical Alarms:
        - DLQ message count > threshold (immediate)
        - Processing success rate < 95% (critical)
        - Retry rate > 20% (warning)
        - Idempotency failures (critical)
        - Circuit open > 5 minutes (warning)

        FAILURE RECOVERY PROCEDURES:

        Transient Failures:
        1. Automatic retry with backoff
        2. Monitor retry success
        3. Circuit breaker protection
        4. Alert if retries exhausted

        Permanent Failures:
        1. Message sent to DLQ
        2. Alert team for investigation
        3. Categorize failure type
        4. Fix application issue
        5. Replay from DLQ

        Systematic Failures:
        1. Circuit breaker opens
        2. Prevent further failures
        3. Alert team urgently
        4. Fix underlying issue
        5. Circuit auto-closes after recovery

        COST OPTIMIZATION:

        Reduce Retry Costs:
        - Implement circuit breakers (avoid repeated failures)
        - Use appropriate backoff (avoid aggressive retries)
        - Fix root causes quickly
        - Monitor and optimize retry success rate

        Optimize Idempotency Store:
        - Use appropriate TTL (balance cost vs risk)
        - Choose cost-effective storage (DynamoDB on-demand for variable)
        - Archive old idempotency records
        - Monitor and right-size capacity

        DLQ Management:
        - Process DLQ promptly (avoid accumulation)
        - Set reasonable retention periods
        - Archive processed DLQ messages
        - Delete after successful replay
        """,
        real_world_examples=[
            "E-commerce platform implemented Idempotent Processing for order creation, preventing $500k in duplicate orders over 6 months using DynamoDB for deduplication",
            "Payment processor used Comprehensive Reliability with circuit breakers and automated DLQ processing, achieving 99.99% message delivery with zero duplicate charges",
            "IoT platform implemented Retry with Backoff for sensor data ingestion, reducing manual intervention by 90% while maintaining 99.9% processing success rate",
            "SaaS company used Basic Reliability with DLQ for non-critical notifications, accepting occasional loss while keeping costs under $20/month for 50M messages"
        ],
        references=[
            "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html",
            "https://docs.aws.amazon.com/lambda/latest/dg/invocation-retries.html",
            "https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/"
        ]
    )


def get_messaging_security_pattern() -> DecisionPattern:
    """
    Pattern for messaging security including encryption, access control, and compliance.
    Covers SQS, SNS, and EventBridge security configurations.
    """
    return DecisionPattern(
        pattern_id="messaging-security-strategy",
        name="Messaging Security and Compliance Strategy",
        category="security",
        subcategory="messaging",
        description="Comprehensive framework for implementing messaging security including encryption at rest and in transit, access control, audit logging, and compliance requirements for SQS, SNS, and EventBridge.",
        decision_criteria=[
            DecisionCriteria(
                criterion="Data Sensitivity",
                weight=0.30,
                considerations=[
                    "What type of data flows through messages?",
                    "Do you have PII, PHI, or financial data in messages?",
                    "What are your encryption requirements?",
                    "Are there regulatory compliance requirements?"
                ]
            ),
            DecisionCriteria(
                criterion="Access Control Requirements",
                weight=0.25,
                considerations=[
                    "Who should publish/consume messages?",
                    "Do you need cross-account access?",
                    "Do you need fine-grained permissions?",
                    "Are there segregation of duties requirements?"
                ]
            ),
            DecisionCriteria(
                criterion="Audit and Compliance",
                weight=0.20,
                considerations=[
                    "Do you need audit trails for message access?",
                    "Are there message retention requirements?",
                    "Do you need to prove message delivery?",
                    "What compliance frameworks apply (HIPAA, PCI-DSS)?"
                ]
            ),
            DecisionCriteria(
                criterion="Network Security",
                weight=0.15,
                considerations=[
                    "Should messaging be accessible from internet?",
                    "Do you need VPC endpoint access only?",
                    "Do you need private connectivity?",
                    "Are there data residency requirements?"
                ]
            ),
            DecisionCriteria(
                criterion="Operational Complexity",
                weight=0.10,
                considerations=[
                    "Can you manage KMS keys?",
                    "Can you manage complex IAM policies?",
                    "Do you need simple security setup?",
                    "What is your security team's expertise?"
                ]
            )
        ],
        options=[
            DecisionOption(
                option_id="messaging-basic-security",
                name="Basic Security - IAM and HTTPS",
                description="Essential security with IAM-based access control and encryption in transit using HTTPS. Server-side encryption with AWS-managed keys.",
                pros_cons=ProConsList(
                    pros=[
                        "Simple configuration with AWS defaults",
                        "IAM-based access control included",
                        "Encryption in transit with HTTPS (free)",
                        "Server-side encryption with AWS keys (free)",
                        "Suitable for internal, non-sensitive data",
                        "Low operational overhead",
                        "No additional costs"
                    ],
                    cons=[
                        "AWS-managed keys don't meet some compliance requirements",
                        "No encryption at rest with customer-managed keys",
                        "Limited auditability of message access",
                        "No VPC endpoint isolation",
                        "Basic access control (no fine-grained)",
                        "Not suitable for highly sensitive data"
                    ]
                ),
                estimated_cost="Included in base messaging cost (no additional charges)",
                implementation_complexity="Low",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC6.1",
                        description="Access control - IAM policies for messaging",
                        implementation_guidance="Create least-privilege IAM policies for publishers and consumers; use IAM roles for applications; implement MFA for human access; audit IAM policies quarterly; document access procedures"
                    ),
                    SOC2Control(
                        control_id="CC6.7",
                        description="Encryption in transit - HTTPS endpoints",
                        implementation_guidance="Ensure all clients use HTTPS endpoints; enforce TLS 1.2+; monitor for non-TLS connections; document encryption standards; audit endpoint configurations"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Basic monitoring - CloudWatch metrics",
                        implementation_guidance="Configure CloudWatch alarms for queue depth and errors; monitor message age; track throughput; review metrics weekly; maintain incident response procedures"
                    )
                ]
            ),
            DecisionOption(
                option_id="messaging-kms-encryption",
                name="Enhanced Security - Customer-Managed KMS Keys",
                description="Improved security with customer-managed KMS keys for encryption at rest, VPC endpoints for private access, and enhanced CloudTrail logging.",
                pros_cons=ProConsList(
                    pros=[
                        "Customer-managed KMS keys for compliance",
                        "Full control over encryption key lifecycle",
                        "VPC endpoints for private connectivity",
                        "Enhanced CloudTrail logging of key usage",
                        "Meets SOC 2 and many HIPAA requirements",
                        "Automatic key rotation available",
                        "Fine-grained IAM policies for keys"
                    ],
                    cons=[
                        "Additional KMS costs ($1/key/month + API calls)",
                        "Higher operational complexity managing keys",
                        "VPC endpoint costs ($7-10/month per AZ)",
                        "Key management overhead",
                        "Potential performance impact (minimal)",
                        "Requires key access for all message operations"
                    ]
                ),
                estimated_cost="Base + KMS (~$1-10/month) + VPC endpoints (~$7/AZ/month); typical: $30-150/month additional",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC6.7",
                        description="Encryption at rest - customer-managed KMS keys",
                        implementation_guidance="Create customer-managed CMK for each service; enable automatic key rotation; configure key policies with least privilege; monitor key usage; audit key access via CloudTrail; document key management procedures"
                    ),
                    SOC2Control(
                        control_id="CC6.1",
                        description="Access control - IAM and key policies",
                        implementation_guidance="Implement least-privilege IAM policies; configure KMS key policies to restrict access; use separate keys for different sensitivity levels; audit policy changes; document access matrix"
                    ),
                    SOC2Control(
                        control_id="CC6.2",
                        description="Network security - VPC endpoints for private access",
                        implementation_guidance="Create VPC endpoints for SQS/SNS/EventBridge; configure endpoint policies; restrict access to specific VPCs; monitor VPC endpoint usage; document network architecture"
                    ),
                    SOC2Control(
                        control_id="CC6.6",
                        description="Audit logging - CloudTrail for API and key access",
                        implementation_guidance="Enable CloudTrail for all messaging services; log KMS key usage; export logs to S3; configure log file integrity validation; retain logs per compliance requirements (7+ years)"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Data protection - encrypted messages at rest",
                        implementation_guidance="Verify encryption enabled on all queues/topics; test decryption procedures; monitor for unencrypted messages; implement data classification; document encryption standards"
                    )
                ]
            ),
            DecisionOption(
                option_id="messaging-compliance-security",
                name="Compliance-Grade Security (HIPAA/PCI-DSS)",
                description="Maximum security for regulated data with comprehensive encryption, resource policies, detailed audit logging, and access controls for HIPAA/PCI-DSS compliance.",
                pros_cons=ProConsList(
                    pros=[
                        "Meets HIPAA, PCI-DSS, and SOC 2 Type II requirements",
                        "Customer-managed KMS keys with restricted access",
                        "Resource policies for fine-grained access control",
                        "Comprehensive CloudTrail and CloudWatch logging",
                        "VPC endpoints for private, isolated access",
                        "Message content logging (where appropriate)",
                        "Supports data residency requirements",
                        "Defense-in-depth security model"
                    ],
                    cons=[
                        "Highest cost with multiple security services",
                        "Complex configuration and management",
                        "Requires security and compliance expertise",
                        "Extensive logging can be expensive",
                        "More complex troubleshooting",
                        "Higher operational overhead",
                        "May be over-engineered for some use cases"
                    ]
                ),
                estimated_cost="Base + KMS + VPC endpoints + enhanced logging (~$50-300/month); typical: $100-500/month additional",
                implementation_complexity="High",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC6.7",
                        description="Multi-layer encryption - comprehensive data protection",
                        implementation_guidance="Use customer-managed CMK with restricted access; enable automatic key rotation; encrypt in transit and at rest; configure separate keys per sensitivity level; implement key usage monitoring; audit encryption quarterly"
                    ),
                    SOC2Control(
                        control_id="CC6.1",
                        description="Fine-grained access control - resource and IAM policies",
                        implementation_guidance="Implement resource-based policies for cross-account; configure IAM condition keys; use separate policies per role; implement least privilege; enable MFA delete; audit access quarterly; maintain access control matrix"
                    ),
                    SOC2Control(
                        control_id="CC6.6",
                        description="Comprehensive audit logging - complete message lifecycle",
                        implementation_guidance="Enable CloudTrail for all API calls; log KMS key usage; enable CloudWatch Logs; export to S3 for long-term retention; implement log analysis; integrate with SIEM; maintain 7+ year retention"
                    ),
                    SOC2Control(
                        control_id="CC6.2",
                        description="Network isolation - VPC endpoints and private access",
                        implementation_guidance="Deploy VPC endpoints in all VPCs; configure endpoint policies with restrictions; disable public internet access; use PrivateLink for cross-account; monitor network access; document network flows"
                    ),
                    SOC2Control(
                        control_id="PI1.5",
                        description="Data privacy - encryption and access controls for PII/PHI",
                        implementation_guidance="Classify message data sensitivity; implement appropriate encryption; configure data retention policies; audit data access; document data flows; implement privacy controls per regulations"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Security monitoring - comprehensive visibility",
                        implementation_guidance="Monitor CloudTrail for suspicious activity; configure GuardDuty for threat detection; implement Security Hub; automate security response; maintain security dashboards; integrate with incident response"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Message durability - encrypted backups and retention",
                        implementation_guidance="Configure appropriate message retention; implement DLQ with long retention; encrypt all stored messages; test recovery procedures; document backup strategy; maintain disaster recovery plan"
                    )
                ]
            )
        ],
        decision_framework="""
        MESSAGING SECURITY SELECTION FRAMEWORK:

        1. ASSESS DATA SENSITIVITY:
           - Internal, non-sensitive → Basic Security
           - Moderate sensitivity, customer data → KMS Encryption
           - PII, PHI, payment card data → Compliance-Grade Security

        2. EVALUATE COMPLIANCE REQUIREMENTS:
           - No specific compliance → Basic Security
           - SOC 2 Type II → KMS Encryption minimum
           - HIPAA or PCI-DSS → Compliance-Grade Security required

        3. DETERMINE ACCESS CONTROL NEEDS:
           - Simple IAM policies sufficient → Basic Security
           - Need customer-managed keys → KMS Encryption
           - Fine-grained control, resource policies → Compliance-Grade

        4. ASSESS NETWORK SECURITY NEEDS:
           - Public access acceptable → Basic Security
           - Need private VPC access → KMS Encryption with VPC endpoints
           - Complete isolation required → Compliance-Grade Security

        5. CONSIDER OPERATIONAL MATURITY:
           - Limited security expertise → Basic Security
           - Can manage KMS keys → KMS Encryption
           - Advanced security operations → Compliance-Grade Security

        SECURITY COMPARISON:

        | Security Level | Encryption | KMS Keys | VPC Endpoints | Logging | Cost/Month | Complexity |
        |----------------|------------|----------|---------------|---------|------------|------------|
        | Basic | AWS-managed | No | No | Basic | $0 | Low |
        | KMS | Customer CMK | Yes | Optional | Enhanced | $30-150 | Medium |
        | Compliance | Customer CMK | Yes | Yes | Comprehensive | $100-500 | High |

        ENCRYPTION CONFIGURATION:

        SQS Encryption:
        - Server-side encryption: Enable on queue
        - AWS-managed (default): SSE-SQS (free)
        - Customer-managed: SSE-KMS with CMK ($1/key + API calls)
        - Data key reuse: 1-1440 minutes (default 5 min, reduces KMS calls)

        SNS Encryption:
        - Server-side encryption: Enable on topic
        - AWS-managed: Default encryption (free)
        - Customer-managed: KMS CMK ($1/key + API calls)
        - Encrypted topics can only have encrypted SQS subscribers

        EventBridge Encryption:
        - Events encrypted at rest automatically
        - Custom event bus: Configure KMS CMK
        - Archive encryption: Separate KMS key for archives
        - Cross-account: Configure key policy for access

        KMS KEY MANAGEMENT:

        Key Creation:
        - Create separate keys per service/sensitivity level
        - Configure key policy with least privilege
        - Enable automatic rotation (yearly)
        - Set key alias for easy identification

        Key Policies:
        - Grant IAM users/roles decrypt permissions
        - Allow AWS services (SQS, SNS, EventBridge) encrypt/decrypt
        - Restrict key management to admins
        - Use IAM condition keys for fine-grained control

        Cost Optimization:
        - Use data key reuse period to reduce API calls
        - Single key for multiple queues/topics of same sensitivity
        - Monitor KMS usage with CloudWatch
        - Consider AWS-managed keys for non-regulated data

        ACCESS CONTROL:

        IAM Policy Best Practices:
        - Use least-privilege principle
        - Separate read and write permissions
        - Use IAM condition keys for restrictions
        - Grant access via roles, not users
        - Implement MFA for sensitive operations

        SQS Queue Policies:
        - Use for cross-account access
        - Restrict by source account/principal
        - Limit actions to minimum required
        - Use conditions for source IP/VPC restrictions

        SNS Topic Policies:
        - Grant publish permissions to specific principals
        - Restrict subscriptions to authorized accounts
        - Use conditions for additional security
        - Review subscriptions regularly

        EventBridge Resource Policies:
        - Grant PutEvents permission to specific principals
        - Restrict rule creation to admins
        - Use conditions for cross-account access
        - Audit policy changes

        VPC ENDPOINT CONFIGURATION:

        Setup:
        - Create VPC endpoint for SQS/SNS/EventBridge
        - Deploy in private subnets
        - Configure security group to restrict access
        - Use endpoint policies for additional control

        Endpoint Policies:
        - Restrict to specific queues/topics
        - Limit actions permitted
        - Restrict to specific IAM principals
        - Monitor endpoint usage

        Benefits:
        - Traffic stays within AWS network
        - No internet gateway required
        - Reduced data transfer costs
        - Enhanced security posture

        LOGGING AND MONITORING:

        CloudTrail Logging:
        - Enable for SQS, SNS, EventBridge API calls
        - Log to S3 with encryption
        - Configure log file integrity validation
        - Export to CloudWatch for analysis
        - Integrate with SIEM

        CloudWatch Metrics:
        - SQS: Queue depth, message age, errors
        - SNS: Published/delivered messages, failures
        - EventBridge: Invocations, failed invocations

        CloudWatch Logs:
        - EventBridge: Log matched events
        - Lambda: Log message processing
        - SNS: Log delivery status (HTTP/S)

        Compliance Logging:
        - Log all message operations
        - Capture source IP and principal
        - Retain logs per requirements (7+ years)
        - Implement log analysis and alerting
        - Maintain audit trails

        SECURITY BEST PRACTICES:

        Message Content:
        - Don't include sensitive data in messages if possible
        - Encrypt sensitive fields at application level
        - Use references/tokens instead of actual data
        - Implement data classification
        - Document data handling procedures

        Least Privilege:
        - Grant minimum required permissions
        - Use separate queues for different sensitivity levels
        - Implement role-based access control
        - Regular access reviews
        - Remove unnecessary permissions

        Defense in Depth:
        - Encryption at rest and in transit
        - Network isolation with VPC endpoints
        - IAM and resource policies
        - CloudTrail logging
        - Security monitoring and alerting

        COMPLIANCE CONSIDERATIONS:

        HIPAA Compliance:
        - BAA required with AWS
        - Customer-managed KMS keys required
        - Comprehensive audit logging
        - Access controls and authentication
        - Encryption at rest and in transit
        - Regular security assessments

        PCI-DSS Compliance:
        - Encryption of cardholder data
        - Access control and authentication
        - Network segmentation (VPC endpoints)
        - Logging and monitoring
        - Regular security testing
        - Maintain audit trails

        SOC 2 Type II:
        - Access controls and policies
        - Encryption implementation
        - Monitoring and alerting
        - Incident response procedures
        - Regular audits and reviews
        - Documentation of controls
        """,
        real_world_examples=[
            "Healthcare company implemented Compliance-Grade Security for patient data messaging, using customer-managed KMS keys and VPC endpoints, passing HIPAA audit without findings",
            "Financial services used KMS Encryption for payment processing queues, meeting PCI-DSS requirements while keeping additional costs under $100/month",
            "Startup used Basic Security for internal notification queues, meeting SOC 2 requirements with simple IAM policies and no additional costs",
            "Enterprise deployed Compliance-Grade Security across 50+ queues with separate KMS keys per data classification, achieving comprehensive audit trails and regulatory compliance"
        ],
        references=[
            "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-server-side-encryption.html",
            "https://docs.aws.amazon.com/sns/latest/dg/sns-server-side-encryption.html",
            "https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-encryption.html",
            "https://aws.amazon.com/compliance/services-in-scope/"
        ]
    )


# Export all patterns
MESSAGING_PATTERNS = [
    get_messaging_queue_pattern(),
    get_messaging_reliability_pattern(),
    get_messaging_security_pattern()
]
