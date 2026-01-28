"""
Storage Patterns for CARL
Provides decision frameworks for AWS file storage services (EFS, FSx) selection and performance optimization.
"""

from typing import List, Dict, Any
from .models import (
    DecisionPattern,
    DecisionOption,
    DecisionCriteria,
    ProConsList,
    SOC2Control
)


def get_storage_filesystem_pattern() -> DecisionPattern:
    """
    Pattern for selecting file system storage (EFS vs FSx variants).
    Covers use cases, performance requirements, and protocol support.
    """
    return DecisionPattern(
        pattern_id="storage-filesystem-selection",
        name="AWS File System Storage Selection",
        category="storage",
        subcategory="filesystem",
        description="Framework for selecting the appropriate AWS file system storage service (EFS, FSx for Windows, FSx for Lustre, FSx for NetApp ONTAP, FSx for OpenZFS) based on protocol requirements, performance needs, and application compatibility.",
        decision_criteria=[
            DecisionCriteria(
                criterion="Protocol and Compatibility",
                weight=0.30,
                considerations=[
                    "What file system protocol do you need (NFS, SMB, Lustre)?",
                    "What operating systems will access the storage (Linux, Windows)?",
                    "Do you need Active Directory integration?",
                    "Are there specific application requirements?"
                ]
            ),
            DecisionCriteria(
                criterion="Performance Requirements",
                weight=0.25,
                considerations=[
                    "What throughput do you need (MB/s)?",
                    "What IOPS requirements do you have?",
                    "Do you need low-latency access?",
                    "Do you have HPC or machine learning workloads?"
                ]
            ),
            DecisionCriteria(
                criterion="Scalability and Capacity",
                weight=0.20,
                considerations=[
                    "How much storage do you need initially?",
                    "What is your expected growth?",
                    "Do you need elastic scaling?",
                    "Can you estimate capacity or need unlimited?"
                ]
            ),
            DecisionCriteria(
                criterion="Feature Requirements",
                weight=0.15,
                considerations=[
                    "Do you need snapshots or backups?",
                    "Do you need data deduplication or compression?",
                    "Do you need data replication?",
                    "Do you need multi-AZ or single-AZ deployment?"
                ]
            ),
            DecisionCriteria(
                criterion="Cost Optimization",
                weight=0.10,
                considerations=[
                    "What is your file storage budget?",
                    "Can you use lifecycle management?",
                    "Do you need cost-effective options?",
                    "What is your expected data access pattern?"
                ]
            )
        ],
        options=[
            DecisionOption(
                option_id="storage-efs",
                name="Amazon EFS (Elastic File System)",
                description="Fully managed, elastic NFS file system that automatically scales storage capacity. Supports Linux workloads with NFSv4 protocol.",
                pros_cons=ProConsList(
                    pros=[
                        "Elastic storage - automatically grows and shrinks",
                        "Fully managed - no infrastructure to provision",
                        "Multi-AZ durability (Standard) or Single-AZ (One Zone)",
                        "Supports thousands of concurrent connections",
                        "Lifecycle management to transition to Infrequent Access",
                        "Integrates with AWS services (Lambda, ECS, EKS)",
                        "Low-cost Infrequent Access storage class",
                        "Simple to set up and use"
                    ],
                    cons=[
                        "NFSv4 only - no SMB support (Linux/Mac only, not Windows)",
                        "Lower performance than FSx for high-throughput workloads",
                        "Higher cost per GB than S3 for infrequent access",
                        "No native data deduplication or compression",
                        "Limited Windows support (requires NFS client)",
                        "Performance depends on size (larger files = higher throughput)",
                        "Cross-region access requires VPC peering/Transit Gateway"
                    ]
                ),
                estimated_cost="Standard: $0.30/GB-month; IA: $0.025/GB-month + access fees; typical: $100-2,000/month for 300GB-6TB",
                implementation_complexity="Low",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="High availability - multi-AZ elastic file system",
                        implementation_guidance="Use Standard storage class for multi-AZ; configure mount targets in each AZ; implement lifecycle policies for cost optimization; monitor file system metrics; test failover across AZs"
                    ),
                    SOC2Control(
                        control_id="CC6.7",
                        description="Encryption - at-rest and in-transit encryption",
                        implementation_guidance="Enable encryption at rest (KMS); enforce encryption in transit (TLS); configure appropriate KMS key policies; audit encryption settings; monitor unencrypted access attempts"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Data protection - automatic backups with AWS Backup",
                        implementation_guidance="Configure AWS Backup for EFS; set appropriate backup frequency and retention; test restore procedures; monitor backup success; maintain backup documentation"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Performance monitoring - CloudWatch metrics",
                        implementation_guidance="Monitor throughput and IOPS; track burst credit balance; configure alarms for performance issues; optimize performance mode (General Purpose vs Max I/O); review metrics regularly"
                    )
                ]
            ),
            DecisionOption(
                option_id="storage-fsx-windows",
                name="FSx for Windows File Server",
                description="Fully managed Windows file server built on Windows Server with SMB protocol, Active Directory integration, and Windows-native features.",
                pros_cons=ProConsList(
                    pros=[
                        "Native Windows SMB protocol support",
                        "Full Active Directory integration",
                        "Windows features (DFS, deduplication, compression, VSS)",
                        "High performance (up to 2 GB/s throughput)",
                        "Automatic backups and snapshots",
                        "Multi-AZ deployment for high availability",
                        "Supports SQL Server, SharePoint, IIS, and Windows apps",
                        "Can be accessed from on-premises via Direct Connect/VPN"
                    ],
                    cons=[
                        "Higher cost than EFS",
                        "Windows-specific - limited Linux support",
                        "Requires capacity planning (not elastic like EFS)",
                        "More complex setup than EFS (AD, DNS)",
                        "Higher minimum capacity (32 GB SSD)",
                        "Cross-region access requires replication or DFS",
                        "Storage capacity cannot shrink (only grow)"
                    ]
                ),
                estimated_cost="SSD: $0.13/GB-month + throughput; HDD: $0.013/GB-month + throughput; typical: $200-5,000/month for 1-10TB SSD",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="High availability - multi-AZ Windows file server",
                        implementation_guidance="Deploy in multi-AZ configuration; configure automatic failover; implement DFS for namespace management; test failover procedures; monitor file server health; maintain HA documentation"
                    ),
                    SOC2Control(
                        control_id="CC6.1",
                        description="Access control - Active Directory integration",
                        implementation_guidance="Integrate with Microsoft AD or AWS Managed AD; configure NTFS permissions; implement least-privilege access; use Windows ACLs; audit file access; maintain access control matrix"
                    ),
                    SOC2Control(
                        control_id="CC6.7",
                        description="Encryption - Windows encryption at rest and in transit",
                        implementation_guidance="Enable encryption at rest with KMS; enforce SMB encryption in transit; configure appropriate cipher suites; audit encryption settings; monitor unencrypted connections"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Data protection - automatic backups and VSS snapshots",
                        implementation_guidance="Configure automatic daily backups; implement VSS shadow copies; set appropriate retention periods; test restore procedures; maintain backup and recovery documentation; monitor backup success"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Performance monitoring - file server metrics",
                        implementation_guidance="Monitor IOPS, throughput, and latency; track storage capacity; configure CloudWatch alarms; optimize throughput capacity; review performance metrics regularly; right-size based on usage"
                    )
                ]
            ),
            DecisionOption(
                option_id="storage-fsx-lustre",
                name="FSx for Lustre",
                description="High-performance parallel file system for compute-intensive workloads like HPC, machine learning, and big data analytics. Sub-millisecond latencies and hundreds of GB/s throughput.",
                pros_cons=ProConsList(
                    pros=[
                        "Extreme performance (hundreds of GB/s, millions of IOPS)",
                        "Sub-millisecond latencies",
                        "Optimized for HPC, ML training, big data analytics",
                        "Native S3 integration (data repository association)",
                        "Scales to hundreds of GB/s and millions of IOPS",
                        "Cost-effective for high-performance workloads",
                        "Supports POSIX-compliant file system",
                        "Ideal for burst workloads"
                    ],
                    cons=[
                        "Not suitable for general file sharing",
                        "More expensive than EFS for low-performance needs",
                        "Requires understanding of HPC file systems",
                        "Deployment types affect features (scratch vs persistent)",
                        "Scratch deployment has no replication (data loss on failure)",
                        "Persistent deployment more expensive but durable",
                        "Not ideal for small files or random I/O patterns"
                    ]
                ),
                estimated_cost="Scratch: $0.140/GB-month; Persistent: $0.145-0.210/GB-month; typical: $1,000-20,000/month for HPC workloads",
                implementation_complexity="High",
                soc2_controls=[
                    SOC2Control(
                        control_id="A1.1",
                        description="High performance computing - extreme throughput and IOPS",
                        implementation_guidance="Select deployment type (Scratch for temporary, Persistent for durability); configure appropriate storage capacity and throughput; integrate with S3 for data loading; monitor performance metrics; optimize for workload patterns"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Data durability - persistent deployment with backups",
                        implementation_guidance="Use Persistent deployment for important data; configure automatic backups (Persistent only); implement S3 data repository for source data; test data recovery procedures; document data lifecycle"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Performance monitoring - HPC metrics",
                        implementation_guidance="Monitor aggregate throughput and IOPS; track disk usage; configure CloudWatch alarms; analyze performance for optimization; benchmark workloads; tune file system parameters"
                    ),
                    SOC2Control(
                        control_id="CC6.7",
                        description="Encryption - at-rest encryption for sensitive HPC data",
                        implementation_guidance="Enable encryption at rest; configure KMS key policies; enforce encryption in transit where possible; audit encryption settings; document compliance for HPC workloads"
                    )
                ]
            ),
            DecisionOption(
                option_id="storage-fsx-ontap",
                name="FSx for NetApp ONTAP",
                description="Fully managed NetApp ONTAP file system with multi-protocol support (NFS, SMB, iSCSI), advanced data management, and enterprise features.",
                pros_cons=ProConsList(
                    pros=[
                        "Multi-protocol support (NFS, SMB, iSCSI)",
                        "Supports Linux, Windows, and macOS clients",
                        "Advanced data management (snapshots, cloning, replication)",
                        "Data deduplication, compression, and thin provisioning",
                        "SnapMirror replication for DR",
                        "Supports hybrid cloud (on-premises to AWS)",
                        "Storage efficiency reduces costs",
                        "Familiar NetApp tools and APIs"
                    ],
                    cons=[
                        "Higher cost than EFS or basic FSx options",
                        "More complex to configure and manage",
                        "Requires NetApp ONTAP knowledge",
                        "Minimum capacity requirements",
                        "Overkill for simple file sharing needs",
                        "License costs for advanced features",
                        "Steeper learning curve"
                    ]
                ),
                estimated_cost="$0.138/GB-month (SSD) + throughput; typical: $500-10,000/month with storage efficiency",
                implementation_complexity="High",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="Enterprise availability - multi-protocol with replication",
                        implementation_guidance="Deploy in multi-AZ configuration; configure SnapMirror for replication; implement FlexClone for testing; monitor file system health; test failover procedures; maintain HA runbooks"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Advanced data protection - snapshots and replication",
                        implementation_guidance="Configure automated snapshots; implement SnapMirror to secondary region; use NetApp backups; test restore from snapshots; document RPO/RTO; maintain backup verification procedures"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Storage efficiency - deduplication and compression",
                        implementation_guidance="Enable deduplication and compression; monitor storage efficiency ratios; track actual vs provisioned capacity; optimize storage usage; review efficiency reports; right-size based on actual usage"
                    ),
                    SOC2Control(
                        control_id="CC6.1",
                        description="Multi-protocol access control - NFS, SMB, iSCSI",
                        implementation_guidance="Configure appropriate access controls per protocol; implement NTFS ACLs for SMB; configure NFS export policies; use RBAC for iSCSI; audit multi-protocol access; maintain security matrix"
                    )
                ]
            ),
            DecisionOption(
                option_id="storage-fsx-openzfs",
                name="FSx for OpenZFS",
                description="Fully managed ZFS file system with high performance, data compression, snapshots, and point-in-time cloning. Cost-effective with storage efficiency.",
                pros_cons=ProConsList(
                    pros=[
                        "High performance (up to 4 GB/s, 1M IOPS)",
                        "Built-in data compression reduces storage costs",
                        "Instant point-in-time snapshots",
                        "Instant cloning with no storage overhead",
                        "NFS protocol support (NFSv3, NFSv4)",
                        "Cost-effective with compression (up to 2x savings)",
                        "Low sub-millisecond latencies",
                        "Supports Linux and macOS"
                    ],
                    cons=[
                        "NFS only - no SMB support",
                        "Newer service with smaller ecosystem than others",
                        "Requires ZFS knowledge for advanced features",
                        "Single-AZ deployment only (no multi-AZ option)",
                        "Limited cross-region replication options",
                        "Minimum capacity requirements",
                        "Not suitable for Windows workloads"
                    ]
                ),
                estimated_cost="$0.126/GB-month + throughput; typical: $300-5,000/month (effective cost reduced by compression)",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="A1.1",
                        description="High performance - low latency NFS storage",
                        implementation_guidance="Configure appropriate provisioned IOPS and throughput; enable compression for cost savings; monitor performance metrics; optimize for workload; benchmark and tune; document performance characteristics"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Data protection - snapshots and cloning",
                        implementation_guidance="Configure automated snapshots; use point-in-time recovery; implement cloning for dev/test; test snapshot restore; maintain snapshot retention policy; document data protection strategy"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Cost optimization - compression and storage efficiency",
                        implementation_guidance="Enable data compression; monitor compression ratios; track storage savings; optimize snapshot usage; review capacity utilization; right-size based on compressed size"
                    ),
                    SOC2Control(
                        control_id="CC9.1",
                        description="Availability - single-AZ with snapshot protection",
                        implementation_guidance="Note: Single-AZ only; implement backups for DR; configure cross-region backup replication; maintain recovery procedures; test failover to backup; document RTO/RPO"
                    )
                ]
            )
        ],
        decision_framework="""
        FILE SYSTEM STORAGE SELECTION FRAMEWORK:

        1. DETERMINE PROTOCOL REQUIREMENTS:
           - NFS (Linux/Mac) → EFS, FSx for Lustre, ONTAP, or OpenZFS
           - SMB (Windows) → FSx for Windows File Server or ONTAP
           - iSCSI (block storage) → FSx for ONTAP
           - Multi-protocol → FSx for ONTAP

        2. EVALUATE PERFORMANCE NEEDS:
           - Low-moderate (< 500 MB/s) → EFS
           - Moderate-high (500 MB/s - 2 GB/s) → FSx for Windows or OpenZFS
           - Extreme (> 2 GB/s, HPC/ML) → FSx for Lustre
           - Need low latency (sub-millisecond) → FSx for Lustre or OpenZFS

        3. ASSESS APPLICATION REQUIREMENTS:
           - General Linux file sharing → EFS
           - Windows applications (SQL Server, SharePoint) → FSx for Windows
           - HPC, ML training, big data → FSx for Lustre
           - Database workloads (Oracle, etc.) → FSx for ONTAP or OpenZFS
           - Hybrid cloud, NetApp migration → FSx for ONTAP

        4. CONSIDER SCALABILITY NEEDS:
           - Unknown capacity, need elastic → EFS
           - Predictable capacity → Any FSx option
           - Burst workloads → FSx for Lustre (Scratch)
           - Continuous workloads → EFS or FSx (Persistent)

        5. EVALUATE COST SENSITIVITY:
           - Cost-sensitive, infrequent access → EFS with Lifecycle Management
           - Need storage efficiency → FSx for ONTAP or OpenZFS (compression)
           - High performance required → FSx for Lustre or OpenZFS
           - Windows required → FSx for Windows (no cheaper alternative)

        FILE SYSTEM COMPARISON:

        | Feature | EFS | FSx Windows | FSx Lustre | FSx ONTAP | FSx OpenZFS |
        |---------|-----|-------------|------------|-----------|-------------|
        | Protocol | NFS | SMB | Lustre | NFS/SMB/iSCSI | NFS |
        | OS Support | Linux/Mac | Windows | Linux | All | Linux/Mac |
        | Max Throughput | ~10 GB/s* | 2 GB/s | 1+ TB/s | 4 GB/s | 4 GB/s |
        | Max IOPS | 500k+ | 100k | Millions | 160k | 1M |
        | Latency | ms | ms | sub-ms | ms | sub-ms |
        | Elastic | Yes | No | No | No | No |
        | Multi-AZ | Yes | Yes | No | Yes | No |
        | Cost/GB | $0.30 | $0.13 | $0.14 | $0.138 | $0.126 |
        | Use Case | General Linux | Windows Apps | HPC/ML | Enterprise | High Perf NFS |

        *EFS throughput scales with size and can burst

        USE CASE RECOMMENDATIONS:

        | Use Case | Best File System | Rationale |
        |----------|-----------------|-----------|
        | General Linux file sharing | EFS | Elastic, simple, cost-effective |
        | Windows home directories | FSx for Windows | Native SMB, AD integration |
        | SQL Server on Windows | FSx for Windows | VSS snapshots, high IOPS |
        | Machine learning training | FSx for Lustre | Extreme throughput, S3 integration |
        | HPC simulations | FSx for Lustre | Sub-ms latency, parallel access |
        | Containerized apps (ECS/EKS) | EFS | Easy integration, elastic |
        | Oracle databases | FSx for ONTAP | Snapshots, cloning, high IOPS |
        | Media rendering | FSx for OpenZFS | High throughput, compression |
        | Enterprise file server | FSx for ONTAP | Multi-protocol, replication |
        | Dev/test environments | EFS or OpenZFS | Cost-effective, easy cloning |

        COST OPTIMIZATION STRATEGIES:

        EFS Cost Optimization:
        - Use Lifecycle Management to Infrequent Access (IA) storage
        - Standard: $0.30/GB-month → IA: $0.025/GB-month
        - IA access charges: $0.01 per GB transferred
        - Can save 90%+ for infrequently accessed files
        - Use One Zone for non-critical data (50% cheaper)

        FSx for Windows Cost Optimization:
        - Use HDD storage for throughput-optimized (vs SSD for latency)
        - HDD: $0.013/GB vs SSD: $0.13/GB (10x cheaper)
        - Enable deduplication and compression
        - Right-size throughput capacity
        - Use Single-AZ for dev/test

        FSx for Lustre Cost Optimization:
        - Use Scratch deployment for temporary workloads
        - Scratch: $0.140/GB vs Persistent: $0.210/GB
        - Leverage S3 integration (store in S3, process in Lustre)
        - Use Data Compression to reduce size
        - Delete file system when not in use (burst workloads)

        FSx for ONTAP Cost Optimization:
        - Enable deduplication and compression (2x+ savings)
        - Use thin provisioning
        - Tier cold data to capacity pool
        - Use snapshots efficiently (delta only)
        - Right-size based on actual usage

        FSx for OpenZFS Cost Optimization:
        - Enable compression (automatic 2x savings typical)
        - Use snapshots for dev/test (instant clones, no storage)
        - Right-size throughput and IOPS
        - Monitor compression ratios
        - Optimize based on actual storage usage

        PERFORMANCE OPTIMIZATION:

        EFS Performance:
        - Choose performance mode: General Purpose (default) or Max I/O
        - General Purpose: Lower latency, up to 7k ops/sec per file system
        - Max I/O: Higher latency, unlimited ops/sec (for big data, media)
        - Throughput mode: Bursting (default) or Provisioned
        - Bursting scales with size, use Provisioned for consistent high throughput
        - Use multiple mount targets (one per AZ)

        FSx for Windows Performance:
        - Choose storage type: SSD (latency-sensitive) or HDD (throughput)
        - Configure throughput capacity (8 - 2,048 MB/s per TB)
        - Use SSD for databases, HDD for file shares
        - Enable multi-AZ for higher availability (slight latency increase)
        - Monitor disk IOPS and throughput

        FSx for Lustre Performance:
        - Select deployment type: Scratch (higher throughput) or Persistent
        - Scratch: 200 MB/s per TB, Persistent: 50-1,000 MB/s per TB
        - Use S3 data repository for data loading/hydration
        - Size appropriately for workload (larger = more throughput)
        - Optimize file striping for large files

        FSx for ONTAP Performance:
        - Configure provisioned IOPS (automatic or manual)
        - Use SSD tier for hot data
        - Enable compression (minimal performance impact, reduces I/O)
        - Use FlexCache for read caching
        - Optimize based on workload (sequential vs random)

        FSx for OpenZFS Performance:
        - Configure throughput and IOPS (128-4,096 MB/s per TB)
        - Enable compression (reduces I/O, improves throughput)
        - Use SSD for all storage (high performance)
        - Optimize record size for workload
        - Use snapshots for instant cloning

        MONITORING AND MANAGEMENT:

        Key Metrics:
        - DataReadBytes/DataWriteBytes: I/O throughput
        - MetadataIOPS: Metadata operations
        - ClientConnections: Number of clients connected
        - StorageCapacity: Used vs provisioned capacity
        - BurstCreditBalance (EFS): Available burst capacity

        CloudWatch Alarms:
        - StorageCapacity > 80% (capacity planning)
        - PercentIOLimit > 80% (EFS performance limit)
        - BurstCreditBalance < threshold (EFS burst exhaustion)
        - ClientConnections spike (potential DDoS)
        - High latency or low throughput (performance issues)

        Best Practices:
        - Monitor daily for capacity planning
        - Set up automated alerts for critical metrics
        - Review performance trends monthly
        - Right-size based on actual usage
        - Test performance under load
        - Maintain capacity and performance runbooks

        SECURITY BEST PRACTICES:

        Encryption:
        - Enable encryption at rest (all file systems support)
        - Use customer-managed KMS keys for compliance
        - Enforce encryption in transit (NFS over TLS, SMB encryption)
        - Audit encryption settings regularly

        Access Control:
        - Use security groups to restrict network access
        - Implement least-privilege IAM policies
        - Use POSIX permissions (EFS, Lustre, OpenZFS)
        - Use NTFS ACLs (FSx for Windows)
        - Integrate with Active Directory (Windows, ONTAP)
        - Audit file access regularly

        Network Security:
        - Deploy in private VPC subnets
        - Use VPC endpoints for private connectivity
        - Configure security groups appropriately
        - Implement network ACLs for additional protection
        - Use VPN or Direct Connect for on-premises access

        DISASTER RECOVERY:

        EFS:
        - Enable automatic backups with AWS Backup
        - Configure replication to another region (manual)
        - Use EFS-to-EFS Replication for DR (when available)
        - Test restore procedures quarterly

        FSx for Windows:
        - Enable automatic daily backups
        - Configure backup retention (7-35 days)
        - Use DFS Replication for multi-region
        - Test restore from backups
        - Maintain DR documentation

        FSx for Lustre:
        - Persistent deployment: Automatic backups
        - Use S3 as source of truth for DR
        - Export data to S3 after processing
        - Scratch deployment: No backups (temporary data)

        FSx for ONTAP:
        - Use SnapMirror for cross-region replication
        - Configure automated snapshots
        - Enable backups with AWS Backup
        - Test failover to DR site
        - Document DR procedures

        FSx for OpenZFS:
        - Configure automated snapshots
        - Use AWS Backup for cross-region backup
        - Test snapshot restore procedures
        - Maintain backup verification procedures
        - Document RTO/RPO metrics
        """,
        real_world_examples=[
            "Media company used FSx for Lustre for 4K video rendering, achieving 10 GB/s throughput and completing rendering jobs 5x faster than previous NAS solution",
            "Enterprise deployed EFS for container storage across 100+ ECS tasks, automatically scaling from 100GB to 5TB with zero downtime and $150/month cost",
            "Financial services used FSx for Windows for SQL Server databases, achieving 50k IOPS with VSS snapshots for point-in-time recovery and meeting compliance requirements",
            "Research institution used FSx for OpenZFS for genomics data, achieving 2:1 compression ratio and saving 50% on storage costs while maintaining sub-millisecond latencies"
        ],
        references=[
            "https://docs.aws.amazon.com/efs/latest/ug/whatisefs.html",
            "https://docs.aws.amazon.com/fsx/latest/WindowsGuide/what-is.html",
            "https://docs.aws.amazon.com/fsx/latest/LustreGuide/what-is.html",
            "https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/what-is.html",
            "https://docs.aws.amazon.com/fsx/latest/OpenZFSGuide/what-is.html"
        ]
    )


def get_storage_performance_pattern() -> DecisionPattern:
    """
    Pattern for optimizing file system performance and capacity planning.
    Covers throughput modes, IOPS optimization, and performance monitoring.
    """
    return DecisionPattern(
        pattern_id="storage-performance-optimization",
        name="File System Performance Optimization",
        category="storage",
        subcategory="filesystem",
        description="Framework for optimizing file system performance through appropriate throughput configuration, IOPS provisioning, and performance monitoring strategies.",
        decision_criteria=[
            DecisionCriteria(
                criterion="Workload Characteristics",
                weight=0.30,
                considerations=[
                    "Is your workload read-heavy, write-heavy, or balanced?",
                    "Do you have small files or large files?",
                    "Is I/O pattern sequential or random?",
                    "Do you have burst or sustained workload?"
                ]
            ),
            DecisionCriteria(
                criterion="Performance Requirements",
                weight=0.25,
                considerations=[
                    "What throughput do you need (MB/s)?",
                    "What IOPS do you need?",
                    "What are your latency requirements?",
                    "Do you have performance SLAs?"
                ]
            ),
            DecisionCriteria(
                criterion="Scalability Needs",
                weight=0.20,
                considerations=[
                    "Is performance requirement consistent or variable?",
                    "Do you need to handle traffic spikes?",
                    "Can you predict performance needs?",
                    "What is your expected growth?"
                ]
            ),
            DecisionCriteria(
                criterion="Cost Sensitivity",
                weight=0.15,
                considerations=[
                    "What is your performance budget?",
                    "Can you tolerate burst-based pricing?",
                    "Can you over-provision for performance?",
                    "What is the cost of poor performance?"
                ]
            ),
            DecisionCriteria(
                criterion="Operational Complexity",
                weight=0.10,
                considerations=[
                    "Can you monitor and tune performance?",
                    "Do you need predictable performance?",
                    "Can you handle manual performance adjustments?",
                    "What is your team's expertise?"
                ]
            )
        ],
        options=[
            DecisionOption(
                option_id="storage-performance-basic",
                name="Basic Performance - Default Configuration",
                description="Use default performance settings with automatic scaling. Suitable for general workloads without specific performance requirements.",
                pros_cons=ProConsList(
                    pros=[
                        "Simplest configuration - no tuning needed",
                        "Lowest cost for low-moderate workloads",
                        "Automatic scaling with workload (EFS)",
                        "No risk of over-provisioning",
                        "Good for unpredictable workloads",
                        "No performance planning required"
                    ],
                    cons=[
                        "May not meet high-performance requirements",
                        "Burst credits can be exhausted (EFS)",
                        "Performance depends on file system size (EFS)",
                        "Cannot guarantee specific throughput/IOPS",
                        "May experience throttling during spikes",
                        "Limited control over performance characteristics"
                    ]
                ),
                estimated_cost="No additional performance costs (baseline pricing only)",
                implementation_complexity="Low",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="Basic availability - default performance settings",
                        implementation_guidance="Monitor baseline metrics; configure alarms for performance degradation; understand performance limitations; document acceptable performance ranges; plan capacity growth"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Performance monitoring - baseline metrics tracking",
                        implementation_guidance="Track throughput and IOPS; monitor burst credits (EFS); configure alarms for throttling; review performance trends; identify optimization opportunities"
                    )
                ]
            ),
            DecisionOption(
                option_id="storage-performance-provisioned",
                name="Provisioned Performance - Fixed Throughput/IOPS",
                description="Configure provisioned throughput (EFS) or IOPS (FSx) for consistent, predictable performance independent of size.",
                pros_cons=ProConsList(
                    pros=[
                        "Consistent, predictable performance",
                        "Independent of storage size",
                        "No burst credit exhaustion concerns",
                        "Suitable for performance-critical applications",
                        "Can provision higher than burst limits",
                        "Meets SLA requirements for performance"
                    ],
                    cons=[
                        "Higher cost than burst mode",
                        "Pay for provisioned capacity even if unused",
                        "Requires accurate performance planning",
                        "Over-provisioning wastes money",
                        "Under-provisioning causes throttling",
                        "Need to adjust as requirements change"
                    ]
                ),
                estimated_cost="Base cost + $6/MB/s/month provisioned throughput (EFS) or throughput capacity costs (FSx); typical: $200-2,000/month additional",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="A1.1",
                        description="Performance SLA - guaranteed throughput/IOPS",
                        implementation_guidance="Provision based on performance requirements; monitor actual vs provisioned usage; configure alarms for performance limits; adjust provisioning quarterly; document performance SLAs"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Performance monitoring - track provisioned vs actual",
                        implementation_guidance="Monitor throughput and IOPS utilization; track percentage of provisioned capacity used; identify over/under-provisioning; optimize monthly; maintain performance dashboards"
                    ),
                    SOC2Control(
                        control_id="CC9.1",
                        description="Predictable performance - eliminate throttling",
                        implementation_guidance="Configure appropriate provisioned capacity; test under peak load; validate SLA compliance; implement performance runbooks; train team on performance management"
                    )
                ]
            ),
            DecisionOption(
                option_id="storage-performance-optimized",
                name="Performance Optimized - Tuned Configuration",
                description="Comprehensive performance optimization with right-sized provisioning, performance mode selection, and tuning for specific workload characteristics.",
                pros_cons=ProConsList(
                    pros=[
                        "Maximum performance for workload",
                        "Optimized for specific I/O patterns",
                        "Right-sized to minimize costs",
                        "Performance mode optimized (General Purpose vs Max I/O)",
                        "Throughput and IOPS tuned appropriately",
                        "Regular monitoring and adjustment",
                        "Meets stringent performance SLAs"
                    ],
                    cons=[
                        "Requires deep performance analysis",
                        "Higher operational overhead to maintain",
                        "Need expertise in file system performance",
                        "Requires ongoing monitoring and tuning",
                        "More complex troubleshooting",
                        "Cost of performance testing and optimization"
                    ]
                ),
                estimated_cost="Optimized provisioning (varies); typical: $500-5,000/month depending on requirements",
                implementation_complexity="High",
                soc2_controls=[
                    SOC2Control(
                        control_id="A1.1",
                        description="Performance excellence - comprehensive optimization",
                        implementation_guidance="Analyze workload characteristics; select appropriate performance mode; provision optimal throughput/IOPS; implement performance testing; tune based on actual patterns; document optimization decisions"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Advanced monitoring - comprehensive performance tracking",
                        implementation_guidance="Implement detailed CloudWatch dashboards; track latency percentiles (p50, p99); monitor client-side metrics; use performance monitoring tools; analyze trends for optimization; maintain performance reports"
                    ),
                    SOC2Control(
                        control_id="CC9.1",
                        description="Performance SLA - guaranteed performance levels",
                        implementation_guidance="Define performance SLAs (throughput, IOPS, latency); configure monitoring to track SLA compliance; implement automated alerting; conduct regular performance reviews; optimize continuously"
                    ),
                    SOC2Control(
                        control_id="CC5.2",
                        description="Performance management - change control and testing",
                        implementation_guidance="Test performance changes in non-production; implement gradual rollout; maintain rollback procedures; document all tuning changes; track performance impact; maintain optimization history"
                    )
                ]
            )
        ],
        decision_framework="""
        STORAGE PERFORMANCE OPTIMIZATION FRAMEWORK:

        1. ANALYZE WORKLOAD CHARACTERISTICS:
           - Unknown/variable workload → Basic Performance
           - Predictable, moderate performance → Provisioned Performance
           - High performance, critical SLAs → Performance Optimized
           - Burst workloads → Basic Performance with burst credits

        2. EVALUATE PERFORMANCE REQUIREMENTS:
           - Low-moderate (<250 MB/s) → Basic Performance
           - Moderate-high (250-1,000 MB/s) → Provisioned Performance
           - Very high (>1,000 MB/s) → Performance Optimized
           - Variable with spikes → Provisioned with headroom

        3. ASSESS COST SENSITIVITY:
           - Cost-sensitive, tolerant of variation → Basic Performance
           - Balance cost and performance → Provisioned Performance
           - Performance-critical, justify cost → Performance Optimized
           - SLA-driven → Provisioned or Optimized

        4. DETERMINE OPERATIONAL CAPACITY:
           - Limited resources → Basic Performance
           - Can provision and monitor → Provisioned Performance
           - Advanced performance engineering → Performance Optimized
           - Need hands-off solution → Basic Performance (auto-scaling)

        5. CONSIDER APPLICATION TOLERANCE:
           - Can tolerate variable performance → Basic Performance
           - Need consistent performance → Provisioned Performance
           - Zero tolerance for degradation → Performance Optimized
           - Can buffer/queue → Basic Performance acceptable

        PERFORMANCE CONFIGURATION COMPARISON:

        | Configuration | Consistency | Cost | Complexity | SLA Support | Best For |
        |---------------|-------------|------|------------|-------------|----------|
        | Basic | Variable | Lowest | Low | Limited | General workloads |
        | Provisioned | Consistent | Medium | Medium | Yes | SLA-driven apps |
        | Optimized | Excellent | Higher | High | Yes | Critical workloads |

        EFS PERFORMANCE MODES:

        General Purpose (Default):
        - Lower latency
        - Suitable for most workloads
        - Max 7,000 file operations per second per file system
        - Lowest latency for web serving, content management
        - Use for: Web servers, CMS, home directories

        Max I/O:
        - Higher latency (trade-off for higher ops/sec)
        - Unlimited operations per second
        - Aggregate throughput scales with file system size
        - Use for: Big data, media processing, genomics
        - Note: Cannot change mode after creation

        EFS THROUGHPUT MODES:

        Bursting (Default):
        - Throughput scales with file system size
        - 50 MB/s per TB of storage (baseline)
        - Can burst to 100 MB/s per TB (up to 1 TB total)
        - Burst credits accumulate when below baseline
        - Use for: Variable workloads, unpredictable traffic

        Provisioned:
        - Fixed throughput independent of size
        - Range: 1-1,024 MB/s
        - Cost: $6 per MB/s per month
        - Use for: Consistent high throughput needs
        - Use for: Small file systems with high throughput needs

        FSx PERFORMANCE CONFIGURATION:

        FSx for Windows:
        - Storage type: SSD (latency) or HDD (throughput)
        - SSD: 3 IOPS/GB (up to 100k IOPS per file system)
        - HDD: 12 MB/s per TB throughput
        - Throughput capacity: 8-2,048 MB/s per TB
        - Scale throughput independently of storage

        FSx for Lustre:
        - Deployment type affects performance:
        - Scratch: 200 MB/s per TB (temporary, high perf)
        - Persistent: 50, 100, or 200 MB/s per TB
        - Storage capacity drives throughput
        - IOPS: 100k+ per TB (sub-millisecond latencies)

        FSx for ONTAP:
        - Throughput capacity: 128-2,048 MB/s per TB
        - Provisioned IOPS: Automatic or manual
        - SSD tier for hot data (high IOPS)
        - Capacity pool for cold data (lower cost)
        - Compression improves effective throughput

        FSx for OpenZFS:
        - Throughput capacity: 128-4,096 MB/s per TB
        - Provisioned IOPS: Up to 1 million
        - SSD-based for low latency
        - Compression improves effective performance
        - Record size tuning for workload

        PERFORMANCE MONITORING:

        Key CloudWatch Metrics:

        EFS:
        - DataReadIOBytes/DataWriteIOBytes: Throughput
        - MetadataIOBytes: Metadata operations
        - PercentIOLimit: Approaching I/O limit (Max I/O mode)
        - BurstCreditBalance: Available burst capacity
        - TotalIOBytes: Total I/O

        FSx:
        - DataReadBytes/DataWriteBytes: Throughput
        - DataReadOperations/DataWriteOperations: IOPS
        - FileSystemAvailableCapacity: Free space
        - ClientConnections: Active clients
        - DiskThroughput/DiskIOPS: Disk utilization

        Performance Alarms:

        Critical Alarms:
        - PercentIOLimit > 90% (EFS approaching limit)
        - BurstCreditBalance < 1 TiB-hours (EFS burst exhaustion)
        - Throughput > 90% provisioned (capacity planning)
        - IOPS > 90% provisioned (performance limit)
        - High latency (p99 > threshold)

        Warning Alarms:
        - PercentIOLimit > 70%
        - BurstCreditBalance declining trend
        - Throughput > 70% provisioned
        - Client connection spikes

        PERFORMANCE OPTIMIZATION TECHNIQUES:

        1. Right-Size Storage:
           - EFS bursting: More storage = more baseline throughput
           - FSx: Balance storage and throughput capacity
           - Don't under-provision storage for performance
           - Monitor and adjust based on actual usage

        2. Optimize File Operations:
           - Batch small files into larger files
           - Use parallelism for large datasets
           - Optimize file access patterns
           - Reduce metadata operations
           - Use caching where appropriate

        3. Tune Client Configuration:
           - Use multiple mount points (NFS)
           - Configure appropriate read/write buffer sizes
           - Optimize number of concurrent connections
           - Use latest NFS client versions
           - Enable compression (where supported)

        4. Network Optimization:
           - Use enhanced networking (ENA) on EC2
           - Place clients in same AZ as mount targets
           - Use VPC endpoints for lower latency
           - Optimize security group rules
           - Monitor network throughput limits

        5. Application-Level Optimization:
           - Implement client-side caching
           - Use appropriate I/O patterns for workload
           - Optimize file sizes for throughput
           - Use parallel processing where possible
           - Minimize small, random I/O operations

        CAPACITY PLANNING:

        Growth Projection:
        - Track storage growth rate
        - Monitor usage trends
        - Project future capacity needs
        - Plan for seasonal variations
        - Budget for capacity expansion

        Performance Planning:
        - Baseline current performance metrics
        - Identify performance bottlenecks
        - Project future performance needs
        - Plan provisioned capacity increases
        - Budget for performance scaling

        Cost Planning:
        - Current cost analysis
        - Project storage growth costs
        - Calculate provisioned throughput costs
        - Identify optimization opportunities
        - Budget for expected usage

        PERFORMANCE TESTING:

        Baseline Testing:
        - Test with representative workload
        - Measure throughput and IOPS
        - Track latency percentiles
        - Document performance characteristics
        - Establish performance baselines

        Load Testing:
        - Test at expected peak load
        - Test beyond expected peaks (headroom)
        - Identify performance limits
        - Validate SLA compliance
        - Document maximum capabilities

        Failure Testing:
        - Test AZ failure scenarios
        - Measure failover time and impact
        - Validate performance after failover
        - Test recovery procedures
        - Document recovery characteristics

        COST OPTIMIZATION FOR PERFORMANCE:

        1. Start with Basic/Bursting:
           - Use default configuration initially
           - Monitor actual usage patterns
           - Identify consistent performance needs
           - Switch to provisioned only if needed

        2. Right-Size Provisioned:
           - Provision for p99 requirements (not peak)
           - Leave 20% headroom for growth
           - Review and adjust quarterly
           - Use auto-scaling where available

        3. Optimize Storage Class:
           - Use appropriate storage type (SSD vs HDD)
           - Use lifecycle policies (EFS IA)
           - Implement compression (FSx ONTAP, OpenZFS)
           - Balance performance and cost

        4. Monitor and Optimize:
           - Review performance metrics monthly
           - Identify over-provisioning
           - Adjust provisioned capacity as needed
           - Track cost savings from optimization
        """,
        real_world_examples=[
            "E-commerce platform started with EFS Bursting, monitored for 3 months, then switched to Provisioned Throughput (512 MB/s) saving $300/month vs over-provisioning storage for bursting performance",
            "HPC research lab optimized FSx for Lustre by selecting Persistent deployment with 200 MB/s per TB, achieving required 20 GB/s throughput for genomics analysis at $5,000/month",
            "Media company tuned FSx for Windows to use SSD storage with 1,024 MB/s throughput, achieving <5ms latency for 4K video editing workloads supporting 50 concurrent editors",
            "Financial services implemented Performance Optimized EFS with Max I/O mode and Provisioned Throughput, supporting 100k operations/second for high-frequency trading data analysis"
        ],
        references=[
            "https://docs.aws.amazon.com/efs/latest/ug/performance.html",
            "https://docs.aws.amazon.com/fsx/latest/WindowsGuide/performance.html",
            "https://docs.aws.amazon.com/fsx/latest/LustreGuide/performance.html",
            "https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html",
            "https://docs.aws.amazon.com/fsx/latest/OpenZFSGuide/performance.html"
        ]
    )


# Export all patterns
STORAGE_PATTERNS = [
    get_storage_filesystem_pattern(),
    get_storage_performance_pattern()
]
