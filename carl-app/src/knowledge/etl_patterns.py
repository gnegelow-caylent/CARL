"""
ETL and Data Processing Patterns for AWS.

Patterns for Extract, Transform, Load operations, data pipelines, and workflow orchestration.
"""

from knowledge.architecture_patterns import ArchitectureDecision, DecisionOption

ETL_GLUE_BASIC = ArchitectureDecision(
    question="What should I use for ETL (Extract, Transform, Load) data processing?",
    options=[
        DecisionOption(
            name="AWS Glue (Recommended for Serverless)",
            description="Serverless ETL service with auto-scaling, data catalog, and built-in connectors for S3, databases, and more",
            when_to_use=[
                "Daily or weekly batch ETL jobs",
                "Data lake transformations",
                "Schema discovery needed (Glue Crawlers)",
                "Want serverless (no infrastructure to manage)",
                "Sporadic workloads (pay per use)",
                "Need integration with AWS services",
            ],
            when_not_to_use=[
                "Need 24/7 streaming processing",
                "Processing >1TB continuously",
                "Need instant job startup (2-3 min cold start)",
                "Need full Spark customization control",
                "Very cost-sensitive for 24/7 workloads",
            ],
            pros=[
                "No servers to manage (serverless)",
                "Pay only for job runtime (no idle costs)",
                "Automatic schema discovery with Crawlers",
                "Built-in connectors (JDBC, S3, DynamoDB, Redshift)",
                "Job bookmarks for incremental processing",
                "Integrated with AWS Glue Data Catalog",
            ],
            cons=[
                "2-3 minute cold start time per job",
                "Less control than EMR",
                "More expensive for 24/7 workloads than EMR",
                "Limited customization compared to self-managed Spark",
            ],
            monthly_cost_range=(50.0, 200.0),
            cost_drivers=[
                "DPU (Data Processing Unit): $0.44/hour",
                "Minimum 2 DPUs per job (4 vCPU + 16GB RAM each)",
                "Example: Daily 30-min job = $0.44/hr * 0.5hr * 30 days ≈ $50/month",
                "Glue Crawler: $0.44/hour when running",
            ],
            soc2_controls=["PI1.1", "PI1.2", "CC7.2", "CC6.7"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="AWS EMR (Elastic MapReduce)",
            description="Managed Hadoop/Spark cluster on EC2 instances with full framework control for large-scale big data processing",
            when_to_use=[
                "Large-scale data processing (>1TB regularly)",
                "Need 24/7 streaming or continuous processing",
                "Need full Spark/Hadoop control",
                "Multiple frameworks needed (Spark, Hive, Presto, Flink)",
                "Custom libraries and configurations required",
                "Team has Spark/Hadoop expertise",
            ],
            when_not_to_use=[
                "Small, sporadic ETL jobs (Glue is cheaper)",
                "Simple transformations (Lambda is simpler)",
                "No big data expertise on team",
                "Don't want to manage clusters",
                "Cost-sensitive for small workloads",
            ],
            pros=[
                "More powerful for large-scale data (>1TB)",
                "Full control over Spark/Hadoop configuration",
                "Faster execution for big data workloads",
                "Cheaper for 24/7 continuous workloads vs Glue",
                "Supports multiple frameworks",
            ],
            cons=[
                "Must manage cluster (patching, scaling, monitoring)",
                "Higher cost for small/sporadic workloads",
                "More complex to set up and maintain",
                "Requires Spark/Hadoop expertise",
                "Idle capacity costs money",
            ],
            monthly_cost_range=(100.0, 500.0),
            cost_drivers=[
                "EC2 instance costs (m5.xlarge ≈ $120/month 24/7)",
                "EMR service fees (10-25% on top of EC2)",
                "Example: 3 m5.xlarge nodes 24/7 ≈ $350/month",
                "EBS storage for HDFS",
            ],
            soc2_controls=["PI1.1", "PI1.2", "CC7.2"],
            implementation_complexity="high",
            operational_overhead="high",
        ),
        DecisionOption(
            name="Lambda + S3 (Micro-ETL)",
            description="Event-driven serverless functions triggered by S3 file uploads for simple, real-time transformations",
            when_to_use=[
                "Simple transformations (CSV to JSON, data cleaning)",
                "Small files (<1GB per file)",
                "Real-time processing needed (immediate on upload)",
                "Event-driven architecture",
                "Very low cost priority",
            ],
            when_not_to_use=[
                "Complex transformations (joins, aggregations)",
                "Large files (>1GB)",
                "Processing takes >15 minutes",
                "Need job bookmarks or state management",
                "Batch processing with scheduling",
            ],
            pros=[
                "Instant processing (no cold start for S3 triggers)",
                "Very cheap ($0.20/million invocations)",
                "Simple to implement",
                "True serverless (fully managed)",
                "Perfect for micro-ETL tasks",
            ],
            cons=[
                "15-minute timeout limit",
                "10GB RAM limit",
                "Not suitable for complex transformations",
                "No built-in job bookmarks",
                "Hard to debug complex workflows",
            ],
            monthly_cost_range=(1.0, 20.0),
            cost_drivers=[
                "Lambda: $0.20 per 1M requests",
                "$0.0000166667 per GB-second",
                "S3 PUT/GET requests",
                "Example: 100K files/month ≈ $2/month",
            ],
            soc2_controls=["PI1.1", "CC7.2"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
    ],
    recommendation_logic="""
    **Decision Tree:**

    IF file_size < 100MB AND transformation_simple:
        → Lambda (cheapest, fastest)

    ELIF workload_pattern == "daily_batch" OR workload_pattern == "weekly_batch":
        → AWS Glue (serverless, no idle costs)

    ELIF data_volume > 1TB AND processing_continuous:
        → EMR (most cost-effective for 24/7)

    ELSE:
        → AWS Glue (default for most cases)

    **Glue vs EMR Cost Comparison:**
    - Glue: Pay per job runtime only ($50-200/mo for daily jobs)
    - EMR: Pay for cluster 24/7 ($100-500/mo, cheaper if always running)

    **Breakeven:**
    - If ETL runs <4 hours/day → Glue is cheaper
    - If ETL runs >8 hours/day → EMR is cheaper
    """,
    soc2_relevance="""
    ETL processing is critical for SOC 2 PI (Processing Integrity) controls:

    **PI1.1 (Accuracy):** Transformations must be accurate and tested
    **PI1.2 (Completeness):** All data must be processed without loss
    **CC7.2 (Monitoring):** ETL job monitoring and alerting required
    **CC6.7 (Data Classification):** Sensitive data must be encrypted

    Glue and EMR both support encryption at rest/in-transit and CloudWatch monitoring.
    """,
    common_mistakes=[
        "Using EMR for small, infrequent jobs (wastes money)",
        "Not enabling job bookmarks in Glue (reprocesses all data)",
        "Running Lambda on large files (hits timeout)",
        "Not encrypting data in transit between ETL stages",
        "Forgetting to set CloudWatch alarms for job failures",
    ],
)

ETL_STEP_FUNCTIONS = ArchitectureDecision(
    question="How should I orchestrate complex data pipelines with multiple ETL steps?",
    options=[
        DecisionOption(
            name="Step Functions + Glue (Recommended)",
            description="AWS Step Functions orchestrates Glue ETL jobs, Lambda functions, and other AWS services with visual workflows",
            when_to_use=[
                "Multiple ETL steps with dependencies",
                "Need error handling and retries",
                "Parallel processing required",
                "Need workflow visualization",
                "Want serverless orchestration",
            ],
            when_not_to_use=[
                "Simple single-step ETL (just use Glue)",
                "Need real-time streaming (use Kinesis)",
                "Very high throughput (>1000 executions/sec)",
                "Open-source orchestration preference (use Airflow)",
            ],
            pros=[
                "Visual workflow designer",
                "Built-in error handling and retries",
                "Serverless (no infrastructure)",
                "Integrates with 200+ AWS services",
                "Automatic CloudWatch logging",
            ],
            cons=[
                "AWS-specific (not portable)",
                "Limited to 25,000 events per execution",
                "More expensive than self-hosted for high volume",
            ],
            monthly_cost_range=(5.0, 50.0),
            cost_drivers=[
                "Step Functions: $25 per 1M state transitions",
                "Example: 10K workflows/month with 5 steps = $1.25/month",
                "Plus underlying service costs (Glue, Lambda)",
            ],
            soc2_controls=["PI1.1", "PI1.2", "CC7.2", "CC8.1"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Apache Airflow (MWAA)",
            description="Managed Apache Airflow on AWS for complex DAG-based data pipelines with Python code",
            when_to_use=[
                "Complex dependencies and conditional logic",
                "Team familiar with Airflow",
                "Need Python-based DAG definitions",
                "Migrating from on-prem Airflow",
                "Need backfills and historical runs",
            ],
            when_not_to_use=[
                "Simple linear workflows (Step Functions simpler)",
                "Serverless preference (MWAA has always-on cost)",
                "Small-scale (<100 DAGs)",
                "Cost-sensitive (MWAA minimum $300/month)",
            ],
            pros=[
                "Powerful Python-based DAG definitions",
                "Strong community and plugins",
                "Complex dependency management",
                "Portable (can run anywhere)",
                "Rich UI for monitoring",
            ],
            cons=[
                "$300+/month minimum (always-on environment)",
                "More complex to learn",
                "Requires Python knowledge",
                "More operational overhead than Step Functions",
            ],
            monthly_cost_range=(300.0, 800.0),
            cost_drivers=[
                "MWAA Environment: $0.49/hour (mw1.small) = $355/month minimum",
                "Additional workers: $0.49-0.98/hour each",
                "Metadata database storage",
            ],
            soc2_controls=["PI1.1", "PI1.2", "CC7.2", "CC8.1"],
            implementation_complexity="high",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="EventBridge + Lambda",
            description="Event-driven orchestration using EventBridge rules to trigger Lambda functions based on events",
            when_to_use=[
                "Event-driven architecture",
                "Simple trigger-based workflows",
                "Need real-time responsiveness",
                "Very cost-sensitive",
            ],
            when_not_to_use=[
                "Complex multi-step workflows (use Step Functions)",
                "Need workflow state management",
                "Long-running processes (>15 minutes)",
                "Need visual workflow diagram",
            ],
            pros=[
                "Very cheap (near-zero cost)",
                "Real-time event processing",
                "Simple for event-driven patterns",
                "Serverless and scalable",
            ],
            cons=[
                "No built-in workflow visualization",
                "Hard to manage complex dependencies",
                "No native retry logic",
                "Lambda 15-minute limit",
            ],
            monthly_cost_range=(1.0, 10.0),
            cost_drivers=[
                "EventBridge: Free for first 14M events",
                "Lambda: $0.20/million invocations",
                "Very low cost for most workloads",
            ],
            soc2_controls=["CC7.2"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
    ],
    recommendation_logic="""
    **Decision Tree:**

    IF workflow_simple AND steps < 3:
        → EventBridge + Lambda (simplest, cheapest)

    ELIF team_knows_airflow OR need_complex_dag:
        → MWAA (most powerful, but $300+/month)

    ELSE:
        → Step Functions + Glue (best balance)

    **Cost Comparison (for 10K workflows/month):**
    - EventBridge + Lambda: ~$5/month
    - Step Functions: ~$10/month
    - MWAA: ~$355/month (always-on)

    Step Functions is the sweet spot for most AWS-native data pipelines.
    """,
    soc2_relevance="""
    Pipeline orchestration is critical for PI (Processing Integrity) and CC8.1 (Change Management):

    **PI1.1:** Workflows must execute steps in correct order
    **PI1.2:** All steps must complete successfully
    **CC8.1:** Pipeline changes must be version controlled and tested

    All three options support CloudWatch logging and monitoring for compliance.
    """,
    common_mistakes=[
        "Using MWAA for simple workflows (overkill and expensive)",
        "Not implementing retry logic in EventBridge workflows",
        "Running long processes in Lambda (use Step Functions + Glue)",
        "No CloudWatch alarms for workflow failures",
        "Not version controlling workflow definitions (CC8.1 violation)",
    ],
)

# Export patterns list
PATTERNS = [ETL_GLUE_BASIC, ETL_STEP_FUNCTIONS]
