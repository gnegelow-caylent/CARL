"""
ETL and Data Processing Patterns for AWS.

Patterns for Extract, Transform, Load operations, data pipelines, and workflow orchestration.
"""

from knowledge.architecture_patterns import ArchitectureDecision

ETL_GLUE_BASIC = ArchitectureDecision(
    name="AWS Glue ETL Pipeline",
    context="""
    Need to transform and process data:
    - Extract data from various sources (S3, databases, APIs)
    - Transform data (clean, enrich, aggregate)
    - Load to target (data warehouse, data lake, database)
    - Schedule regular runs
    - Handle schema changes
    """,
    options={
        "AWS Glue (Recommended for Serverless)": """
        **Architecture:**
        - Glue Crawlers (discover schema)
        - Glue Data Catalog (metadata store)
        - Glue ETL Jobs (PySpark or Python Shell)
        - Glue Triggers (scheduling)
        - S3 for source/target data

        **Features:**
        - Serverless (no infrastructure)
        - Auto-scaling
        - Built-in connectors (JDBC, S3, DynamoDB)
        - Data catalog integration
        - Job bookmarks (incremental processing)

        **Cost:** approx. $0.44/DPU-hour
        - DPU (Data Processing Unit) = 4 vCPU + 16GB RAM
        - Min 2 DPUs per job
        - Example: Daily 30-min job = approx. $50/month

        **Pros:**
        - No servers to manage
        - Pay per use
        - Integrated with AWS services
        - Schema discovery automatic
        - Good for sporadic workloads

        **Cons:**
        - Cold start time (2-3 minutes)
        - Less control than EMR
        - Limited customization
        - More expensive for 24/7 workloads

        **When to use:** Most ETL workloads, data lake transformations, scheduled batch jobs
        """,

        "AWS EMR (Elastic MapReduce)": """
        **Architecture:**
        - EMR cluster (EC2 instances)
        - Spark/Hive/Presto on EMR
        - S3 for data storage
        - Step execution or interactive notebooks

        **Features:**
        - Full Spark control
        - Multiple frameworks (Spark, Hive, Presto, Flink)
        - Custom libraries
        - Faster for large-scale processing

        **Cost:** approx. $100-500/month
        - EC2 instance costs + EMR fees
        - Example: 3 m5.xlarge instances 24/7 = approx. $350/month

        **Pros:**
        - More powerful for big data
        - Full framework control
        - Faster execution
        - Better for 24/7 workloads

        **Cons:**
        - Must manage cluster
        - Higher cost for small workloads
        - More complex
        - Need Spark expertise

        **When to use:** Large-scale data processing (>1TB), real-time streaming, 24/7 workloads
        """,

        "Lambda + S3 (Micro-ETL)": """
        **Architecture:**
        - Lambda triggered by S3 events
        - Process files as they arrive
        - Write to target (S3, DynamoDB, RDS)

        **Features:**
        - Event-driven (immediate processing)
        - Serverless
        - Simple transformations

        **Cost:** approx. $0.20/million invocations
        - Very cheap for small files
        - 15-min timeout limit

        **Pros:**
        - Instant processing
        - Very cheap
        - Simple to implement
        - No cold start for ETL

        **Cons:**
        - 15-min timeout
        - Limited to 10GB RAM
        - Not for complex transformations
        - No built-in job bookmarks

        **When to use:** Simple transformations, real-time processing, small files (<1GB)
        """
    },
    recommendation="AWS Glue for most ETL workloads",
    tradeoffs="""
    **Glue vs EMR:**
    - Glue: Serverless, easy, $50-200/mo for daily jobs
    - EMR: Managed cluster, powerful, $100-500/mo for 24/7

    **Glue vs Lambda:**
    - Glue: Complex transformations, large data, scheduled
    - Lambda: Simple transformations, small data, event-driven

    **Decision tree:**
    - Small files (<100MB), simple transform → Lambda
    - Daily/weekly batch jobs, any size → Glue
    - 24/7 streaming, >1TB data → EMR
    """,
    related_controls=["PI1.1", "PI1.2", "CC7.2", "CC6.7"],
    aws_services=["glue", "s3", "cloudwatch", "kms"],
    estimated_cost="$50-200/month for daily Glue jobs"
)

ETL_STEP_FUNCTIONS = ArchitectureDecision(
    name="Data Pipeline Orchestration with Step Functions",
    context="""
    Need to orchestrate complex data workflows:
    - Multiple ETL steps with dependencies
    - Error handling and retries
    - Parallel processing
    - Human approval steps
    - Monitoring and alerting
    """,
    options={
        "Step Functions + Glue (Recommended)": """
        **Architecture:**
        - Step Functions state machine (orchestration)
        - Glue jobs (data processing)
        - Lambda (validation, notifications)
        - EventBridge (scheduling)
        - SNS (alerts)

        **Workflow Example:**
        1. Extract: Glue crawler discovers new data
        2. Validate: Lambda checks data quality
        3. Transform: Glue job processes data (parallel if needed)
        4. Load: Glue job writes to Redshift/S3
        5. Notify: SNS sends completion notification

        **Features:**
        - Visual workflow editor
        - Built-in error handling
        - Parallel execution
        - Human approval steps
        - Audit trail (CloudWatch)

        **Cost:** approx. $25/million state transitions
        - Typically $1-5/month for daily pipelines
        - Glue jobs cost separately

        **Pros:**
        - Easy to visualize workflow
        - Built-in retries
        - Error handling
        - Audit trail
        - No servers

        **Cons:**
        - Limited to 25,000 events in execution history
        - Can get expensive for high-frequency workflows

        **When to use:** Multi-step pipelines, error handling needed, audit requirements
        """,

        "Glue Workflows": """
        **Architecture:**
        - Glue Workflow (orchestration)
        - Glue Triggers (dependencies)
        - Glue Jobs and Crawlers

        **Features:**
        - Native Glue orchestration
        - DAG-style dependencies
        - Simpler than Step Functions

        **Cost:** Free (included with Glue)

        **Pros:**
        - No extra service
        - Integrated with Glue console
        - Free orchestration

        **Cons:**
        - Limited to Glue jobs/crawlers
        - Less flexible than Step Functions
        - No Lambda integration
        - Basic error handling

        **When to use:** Simple Glue-only workflows, tight budget
        """,

        "Airflow on MWAA (Managed Workflows for Apache Airflow)": """
        **Architecture:**
        - MWAA managed Airflow environment
        - Python DAGs for workflow definition
        - Integration with AWS services

        **Features:**
        - Full Airflow capabilities
        - Custom operators
        - Complex scheduling
        - Rich UI

        **Cost:** approx. $300-1000/month
        - MWAA environment: $0.49/hour (approx. $350/month)
        - Plus worker costs

        **Pros:**
        - Industry-standard Airflow
        - Very flexible
        - Complex workflows
        - Existing Airflow knowledge

        **Cons:**
        - Expensive (always running)
        - Complex to manage
        - Overkill for simple workflows

        **When to use:** Migrating from Airflow, complex scheduling, team has Airflow expertise
        """
    },
    recommendation="Step Functions + Glue for most orchestration needs",
    tradeoffs="""
    **Step Functions vs Glue Workflows:**
    - Step Functions: More flexible, Lambda integration, $1-5/mo
    - Glue Workflows: Simpler, Glue-only, free

    **Step Functions vs Airflow:**
    - Step Functions: Serverless, cheap, visual, $1-5/mo
    - Airflow: More powerful, expensive, always-on, $300-1000/mo

    **When to use Airflow:** Only if you have complex scheduling needs or existing Airflow DAGs
    **Default choice:** Step Functions (serverless, cheap, flexible)
    """,
    related_controls=["PI1.4", "CC8.1", "CC7.2"],
    aws_services=["stepfunctions", "glue", "lambda", "eventbridge", "sns"],
    estimated_cost="$1-10/month for orchestration"
)

ETL_DATA_QUALITY = ArchitectureDecision(
    name="Data Quality and Validation",
    context="""
    Need to ensure data quality in ETL pipelines:
    - Validate schema
    - Check data completeness
    - Detect anomalies
    - Track data lineage
    - Alert on quality issues
    """,
    options={
        "Glue Data Quality (Recommended)": """
        **Architecture:**
        - Glue Data Quality rules
        - Integrated with Glue jobs
        - CloudWatch metrics for quality
        - SNS alerts on failures

        **Features:**
        - Declarative quality rules
        - Built into Glue jobs
        - Automatic metrics
        - No separate infrastructure

        **Quality Checks:**
        - Completeness (null checks)
        - Uniqueness (duplicate detection)
        - Validity (range checks, regex)
        - Consistency (referential integrity)
        - Timeliness (freshness checks)

        **Cost:** Free (included with Glue)

        **Example Rules:**
        ```python
        rules = [
            "ColumnValues 'email' matches '[^@]+@[^@]+\\.[^@]+'",
            "ColumnValues 'age' between 0 and 120",
            "Completeness 'customer_id' > 0.99",
            "Uniqueness 'order_id' = 1.0"
        ]
        ```

        **Pros:**
        - Integrated with Glue
        - No extra cost
        - Simple declarative rules
        - Automatic metrics

        **Cons:**
        - Limited to Glue jobs
        - Basic anomaly detection

        **When to use:** All Glue ETL jobs (should be default)
        """,

        "Great Expectations on Lambda": """
        **Architecture:**
        - Lambda function with Great Expectations
        - Validate data before/after ETL
        - Store results in S3
        - Generate data docs

        **Features:**
        - Sophisticated validations
        - Statistical tests
        - Data profiling
        - HTML reports

        **Cost:** approx. $1-5/month (Lambda costs)

        **Pros:**
        - Very powerful
        - Industry standard
        - Rich reporting
        - Statistical anomaly detection

        **Cons:**
        - Requires setup
        - Lambda timeout limits
        - More complex

        **When to use:** Advanced quality needs, statistical testing, detailed reports
        """,

        "AWS Deequ on Glue": """
        **Architecture:**
        - Deequ library in Glue jobs
        - Scala/Spark-based validation
        - Quality metrics to CloudWatch

        **Features:**
        - ML-based anomaly detection
        - Profile data automatically
        - Suggest constraints

        **Cost:** Free (runs in Glue job)

        **Pros:**
        - Advanced ML features
        - Automatic profiling
        - Spark-native

        **Cons:**
        - Scala/Spark knowledge needed
        - Less documentation

        **When to use:** Complex quality needs, ML-based detection, Spark expertise
        """
    },
    recommendation="Glue Data Quality for standard validation",
    tradeoffs="""
    **Start with Glue Data Quality** (free, integrated)
    **Upgrade to Great Expectations** if you need:
    - Statistical tests
    - Detailed HTML reports
    - Advanced anomaly detection

    **Use Deequ** if you have Spark expertise and need ML features
    """,
    related_controls=["PI1.1", "PI1.2", "PI1.5", "CC7.2"],
    aws_services=["glue", "lambda", "cloudwatch", "sns"],
    estimated_cost="$0-5/month"
)

ETL_COMPLETE = ArchitectureDecision(
    name="Complete Production ETL Pipeline",
    context="""
    Production-grade ETL pipeline with all best practices:
    - Scheduled data processing
    - Error handling and retries
    - Data quality validation
    - Monitoring and alerting
    - Audit trail
    - SOC 2 compliant
    """,
    options={
        "Full Stack ETL (Recommended)": """
        **Complete Architecture:**

        **Data Processing:**
        - S3 (landing zone, processed zone, archive zone)
        - Glue Crawlers (schema discovery)
        - Glue Data Catalog (metadata)
        - Glue ETL Jobs (PySpark transformations)
        - Glue Data Quality (validation rules)

        **Orchestration:**
        - Step Functions state machine
        - EventBridge schedule (daily trigger)
        - Lambda (pre/post processing, notifications)

        **Security:**
        - KMS encryption (S3 at rest)
        - TLS in transit
        - IAM roles (least privilege)
        - VPC endpoints (private Glue access)
        - Secrets Manager (database credentials)

        **Monitoring:**
        - CloudWatch Logs (all logs centralized)
        - CloudWatch Metrics (job duration, records processed)
        - CloudWatch Alarms:
          * Job failures
          * Data quality failures
          * Processing time > threshold
          * Record count anomalies
        - SNS notifications

        **Data Governance:**
        - Glue Data Catalog tags
        - Lake Formation permissions
        - CloudTrail audit logs
        - Data lineage tracking

        **Workflow Example:**
        ```
        1. EventBridge triggers Step Functions (daily 2am)
        2. Step Functions orchestrates:
           a. Glue Crawler discovers new data
           b. Lambda validates source files exist
           c. Glue Job processes data (with data quality checks)
           d. Lambda validates output
           e. Glue Job loads to Redshift/Athena
           f. SNS notifies on success/failure
        3. CloudWatch tracks all metrics
        ```

        **SOC 2 Controls Addressed:**
        - PI1.1: Data processing accuracy (Glue Data Quality)
        - PI1.2: Data completeness (validation checks)
        - PI1.4: Authorization (IAM roles, least privilege)
        - CC7.2: System monitoring (CloudWatch)
        - CC6.7: Encryption (KMS)
        - CC8.1: Change management (tracked in Git)

        **Cost Breakdown:** approx. $100-300/month
        - Glue jobs: $50-200/month (daily 30-min runs)
        - S3 storage: $5-20/month (depends on data volume)
        - Step Functions: $1-5/month
        - CloudWatch: $5-10/month (logs, metrics, alarms)
        - Glue Data Catalog: $1/month
        - Lambda: <$1/month
        - VPC endpoints: $7.50/month (optional)

        **Terraform Modules Needed:**
        - S3 buckets (landing, processed, archive) with encryption
        - Glue Data Catalog database
        - Glue Crawlers
        - Glue ETL Jobs with data quality rules
        - IAM roles for Glue
        - Step Functions state machine
        - EventBridge schedule rule
        - Lambda functions (validation, notifications)
        - CloudWatch alarms
        - SNS topic for alerts
        - VPC endpoints (optional, for private access)

        **Pros:**
        - Production-ready
        - SOC 2 compliant
        - Comprehensive monitoring
        - Error handling
        - Data quality built-in

        **Cons:**
        - Higher initial setup
        - $100-300/month cost

        **When to use:** All production ETL pipelines
        """
    },
    recommendation="Full stack with orchestration, quality checks, and monitoring",
    tradeoffs="No tradeoffs - this is the complete, production-ready setup",
    related_controls=["PI1.1", "PI1.2", "PI1.4", "PI1.5", "CC6.7", "CC7.2", "CC8.1"],
    aws_services=["glue", "stepfunctions", "s3", "lambda", "eventbridge", "cloudwatch", "sns", "kms", "lakeformation"],
    estimated_cost="$100-300/month"
)

# Export patterns
PATTERNS = [
    ETL_GLUE_BASIC,
    ETL_STEP_FUNCTIONS,
    ETL_DATA_QUALITY,
    ETL_COMPLETE
]
