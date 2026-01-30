"""
Streaming Data Patterns for AWS.

Patterns for Kinesis Data Streams, Kinesis Firehose, and real-time data processing.
"""

from knowledge.architecture_patterns import ArchitectureDecision

KINESIS_DATA_STREAMS = ArchitectureDecision(
    name="Real-Time Data Ingestion with Kinesis",
    context="""
    Need real-time data ingestion for:
    - Log aggregation
    - Clickstream analysis
    - IoT telemetry
    - Real-time metrics
    - Event-driven architectures
    """,
    options={
        "Kinesis Data Streams (Recommended for Real-Time)": """
        **Architecture:**
        - Kinesis Data Stream (shards)
        - Producers (applications, agents)
        - Consumers (Lambda, KCL apps, Kinesis Analytics)
        - Data retention (1-365 days)

        **Features:**
        - Real-time (< 1 second latency)
        - Ordered within partition key
        - Replay capability (retention period)
        - Multiple consumers
        - Auto-scaling (on-demand or provisioned)

        **Capacity Modes:**
        - **On-Demand:** Auto-scales, $0.015/GB ingested + $0.015/GB retrieved
        - **Provisioned:** Manual shards, $0.015/shard-hour + $0.014/million PUTs

        **Cost:** approx. $35/month (on-demand, 1GB/day)
        - On-demand: 30GB/month × $0.015 ingested + $0.015 retrieved = approx. $0.90/month
        - Provisioned: 1 shard × $0.015/hour × 730 hours = approx. $11/month
        - Example: 10GB/day on-demand = approx. $9/month

        **Pros:**
        - Real-time processing
        - Replay data (retention)
        - Multiple consumers
        - Ordered per partition
        - On-demand auto-scaling

        **Cons:**
        - Need to manage consumers
        - More complex than Firehose
        - Pay for ingestion + retrieval

        **When to use:** Real-time analytics, event-driven, need replay, multiple consumers
        """,

        "Kinesis Firehose (Simpler, Near Real-Time)": """
        **Architecture:**
        - Firehose delivery stream
        - Automatic delivery to S3, Redshift, OpenSearch, HTTP
        - Optional Lambda transformation
        - No consumers to manage

        **Features:**
        - Near real-time (60 sec buffer)
        - Automatic delivery to destinations
        - Built-in format conversion (JSON → Parquet)
        - No server management

        **Cost:** approx. $0.029/GB ingested
        - 1GB/day = 30GB/month × $0.029 = approx. $0.87/month

        **Pros:**
        - Simple (no consumers)
        - Auto-delivery to S3/Redshift/etc
        - Format conversion built-in
        - Cheaper than Data Streams

        **Cons:**
        - Near real-time (60 sec buffer)
        - Single destination per stream
        - No replay capability

        **When to use:** Simple log delivery to S3, don't need real-time, single destination
        """
    },
    recommendation="Data Streams for real-time, Firehose for simple delivery",
    tradeoffs="""
    **Kinesis Data Streams vs Firehose:**
    - Data Streams: Real-time (<1s), replay, multiple consumers, $9/mo for 10GB/day
    - Firehose: Near real-time (60s), auto-delivery, single destination, $8.70/mo for 10GB/day

    **When to use Data Streams:**
    - Need real-time (<1 second)
    - Multiple consumers
    - Need to replay data
    - Complex processing (Lambda, KCL, Analytics)

    **When to use Firehose:**
    - Simple log delivery to S3
    - Near real-time acceptable (60 seconds)
    - Single destination
    - Want simplicity

    **Cost is similar**, choice is about features
    """,
    related_controls=["CC7.2", "PI1.3", "CC6.7"],
    aws_services=["kinesis", "lambda", "s3", "cloudwatch"],
    estimated_cost="$8-20/month for 10GB/day"
)

STREAMING_ANALYTICS = ArchitectureDecision(
    name="Real-Time Stream Processing",
    context="""
    Need to process streaming data in real-time:
    - Aggregations (count, sum, average)
    - Filtering and enrichment
    - Anomaly detection
    - Real-time dashboards
    - Complex event processing
    """,
    options={
        "Lambda (Recommended for Simple Processing)": """
        **Architecture:**
        - Kinesis Data Stream
        - Lambda function (consumer)
        - DynamoDB or S3 (output)
        - CloudWatch metrics

        **Features:**
        - Serverless (no infrastructure)
        - Event-driven
        - Auto-scaling
        - Simple transformations

        **Cost:** approx. $0.20/million invocations
        - 10GB/day = 10,000 records/day = 300K/month
        - 300K invocations × $0.20/million = approx. $0.06/month
        - Very cheap

        **Pros:**
        - Simplest option
        - Serverless
        - Very cheap
        - Good for ETL

        **Cons:**
        - Limited to 15-min processing
        - No SQL queries
        - No windowing/aggregations

        **When to use:** Simple filtering, transformations, routing
        """,

        "Kinesis Data Analytics (SQL on Streams)": """
        **Architecture:**
        - Kinesis Data Stream (input)
        - Kinesis Data Analytics (SQL queries)
        - Kinesis Data Stream or Firehose (output)

        **Features:**
        - SQL queries on streaming data
        - Windowing (tumbling, sliding, session)
        - Aggregations (COUNT, SUM, AVG)
        - Joins between streams
        - Anomaly detection (RANDOM_CUT_FOREST)

        **Cost:** approx. $0.11/KPU-hour
        - KPU (Kinesis Processing Unit) = 4GB RAM + 1 vCPU
        - Min 1 KPU
        - Example: 1 KPU × 730 hours = approx. $80/month

        **Pros:**
        - SQL on streams (familiar)
        - Windowing and aggregations
        - Anomaly detection built-in
        - Managed service

        **Cons:**
        - Expensive ($80/mo minimum)
        - Limited to SQL
        - Overkill for simple tasks

        **When to use:** Need SQL queries, windowing, aggregations, anomaly detection
        """,

        "Flink on EMR or KDA (Advanced)": """
        **Architecture:**
        - Apache Flink application
        - EMR cluster or Kinesis Data Analytics for Apache Flink
        - Complex stateful processing

        **Cost:** approx. $80-500/month

        **When to use:** Complex event processing, stateful operations, advanced analytics
        """
    },
    recommendation="Lambda for simple, Kinesis Data Analytics for SQL/windowing",
    tradeoffs="""
    **Lambda vs Kinesis Data Analytics:**
    - Lambda: $0.06/mo for 10GB/day, simple transforms, no SQL
    - Data Analytics: $80/mo, SQL queries, windowing, aggregations

    **When to use Lambda:**
    - Simple filtering/routing
    - ETL operations
    - Cost-sensitive

    **When to use Data Analytics:**
    - Need SQL queries on streams
    - Windowing (5-minute tumbling windows)
    - Aggregations (COUNT, AVG)
    - Anomaly detection

    **Most use cases:** Start with Lambda, upgrade to Data Analytics if needed
    """,
    related_controls=["PI1.1", "PI1.3", "CC7.2"],
    aws_services=["kinesis", "lambda", "dynamodb", "cloudwatch"],
    estimated_cost="$0.06-80/month depending on processing"
)

STREAMING_COMPLETE = ArchitectureDecision(
    name="Complete Production Streaming Pipeline",
    context="""
    Production streaming pipeline with all best practices:
    - Real-time data ingestion
    - Processing and analytics
    - Monitoring and alerting
    - Error handling
    - Data lake integration
    - SOC 2 compliant
    """,
    options={
        "Full Stack Streaming (Recommended)": """
        **Complete Architecture:**

        **Ingestion:**
        - Kinesis Data Stream (on-demand mode)
        - Enhanced fan-out (if multiple consumers)
        - KMS encryption at rest
        - 7-day retention (for replay)

        **Processing:**
        - Lambda functions (per-record processing)
        - Error handling (DLQ to SQS)
        - Enrichment (lookup in DynamoDB)
        - Filtering and routing

        **Analytics (Optional):**
        - Kinesis Data Analytics (if need SQL)
        - Tumbling windows (5-minute aggregations)
        - Anomaly detection

        **Storage:**
        - Kinesis Firehose → S3 (data lake)
        - Partition by date (year/month/day/hour)
        - Parquet format (compressed)
        - Lifecycle to Glacier after 90 days

        **Monitoring:**
        - CloudWatch Metrics:
          * IncomingRecords
          * IncomingBytes
          * GetRecords.IteratorAgeMilliseconds (consumer lag)
          * WriteProvisionedThroughputExceeded (throttling)
        - CloudWatch Alarms:
          * Iterator age > 60,000 ms (1 min lag)
          * Throttling errors > 10/minute
          * Lambda errors > 1%
        - SNS notifications

        **Error Handling:**
        - Lambda retry policy (2 retries)
        - Dead Letter Queue (SQS)
        - CloudWatch alarms on DLQ depth
        - Manual investigation of failed records

        **Security:**
        - KMS encryption at rest
        - TLS in transit
        - IAM roles (least privilege)
        - VPC endpoints (if processing in VPC)

        **Cost Optimization:**
        - On-demand mode (auto-scales)
        - Firehose buffer (128MB or 15min)
        - S3 Intelligent-Tiering
        - Lifecycle to Glacier

        **SOC 2 Controls Addressed:**
        - PI1.3: Timeliness (real-time processing)
        - CC6.7: Encryption (KMS)
        - CC7.2: System monitoring (CloudWatch)
        - PI1.1: Data accuracy (error handling, DLQ)
        - PI1.5: Error handling (retries, DLQ, alarms)

        **Cost Breakdown:** approx. $50-150/month (100GB/day)
        - Kinesis Data Stream: $45/month (100GB/day on-demand)
        - Lambda: $10/month (1M invocations)
        - Firehose: $87/month (100GB/day × $0.029/GB)
        - S3: $7/month (3TB/month storage)
        - CloudWatch: $5/month
        - Total: approx. $154/month

        **Terraform Modules Needed:**
        - Kinesis Data Stream with encryption
        - Lambda functions with DLQ
        - Kinesis Firehose to S3
        - S3 bucket with lifecycle policies
        - CloudWatch log groups and alarms
        - SNS topics
        - IAM roles
        - KMS keys

        **Pros:**
        - Production-ready
        - Real-time processing
        - Error handling
        - Data lake integration
        - SOC 2 compliant

        **Cons:**
        - $150/month cost at scale

        **When to use:** Production streaming applications, log aggregation, real-time analytics
        """
    },
    recommendation="Full stack with Data Streams, Lambda, Firehose, and comprehensive monitoring",
    tradeoffs="No tradeoffs - this is the complete, production-ready setup",
    related_controls=["PI1.1", "PI1.3", "PI1.5", "CC6.7", "CC7.2"],
    aws_services=["kinesis", "lambda", "s3", "cloudwatch", "sns", "kms", "dynamodb"],
    estimated_cost="$50-150/month for 100GB/day"
)

# Export patterns
PATTERNS = [
    KINESIS_DATA_STREAMS,
    STREAMING_ANALYTICS,
    STREAMING_COMPLETE
]
