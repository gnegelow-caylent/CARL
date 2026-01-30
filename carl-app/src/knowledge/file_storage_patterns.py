"""
File Storage Patterns for AWS.

Patterns for EFS, FSx for Windows, FSx for Lustre, and shared file storage.
"""

from knowledge.architecture_patterns import ArchitectureDecision

EFS_SHARED_STORAGE = ArchitectureDecision(
    name="EFS for Shared File Storage",
    context="""
    Need shared file storage for:
    - Multiple EC2 instances or ECS tasks
    - NFS-compatible file system
    - Auto-scaling storage
    - POSIX-compliant
    - Shared across AZs
    """,
    options={
        "EFS Standard (Recommended)": """
        **Architecture:**
        - EFS file system
        - Mount targets in each AZ
        - EC2 or ECS tasks mount via NFS
        - Security groups restrict access
        - KMS encryption at rest
        - VPC private subnets

        **Features:**
        - Elastic (grows/shrinks automatically)
        - Multi-AZ by default
        - NFS v4.1 protocol
        - POSIX-compliant
        - Concurrent access from thousands of instances

        **Performance Modes:**
        - General Purpose: <7,000 file ops/sec (most workloads)
        - Max I/O: >7,000 file ops/sec (big data, media processing)

        **Throughput Modes:**
        - Bursting: Scales with storage size
        - Provisioned: Pay for specific throughput

        **Cost:** approx. $0.30/GB/month (Standard) or $0.043/GB/month (Infrequent Access)
        - Standard: $0.30/GB/month
        - IA: $0.043/GB/month (files not accessed for 30 days)
        - Example: 100GB with lifecycle to IA = approx. $10-15/month

        **Pros:**
        - Elastic (no capacity planning)
        - Multi-AZ (highly available)
        - Shared across many instances
        - POSIX-compliant
        - Good for containers (ECS, EKS)

        **Cons:**
        - More expensive than EBS
        - NFS protocol (not Windows SMB)
        - Latency higher than EBS

        **When to use:** Shared storage for containers, web content, home directories, CMS
        """,

        "EBS Volumes (Not Shared)": """
        **Architecture:**
        - EBS volume attached to single EC2 instance
        - Block storage (not file system)

        **Cost:** approx. $0.10/GB/month (gp3)

        **Pros:**
        - Cheaper than EFS
        - Lower latency

        **Cons:**
        - Single instance only (not shared)
        - Must manage capacity

        **When to use:** Single-instance storage, database volumes, boot volumes
        """
    },
    recommendation="EFS for shared storage, EBS for single-instance",
    tradeoffs="""
    **EFS vs EBS:**
    - EFS: Shared, elastic, $0.30/GB/mo, NFS
    - EBS: Single instance, fixed size, $0.10/GB/mo, block storage

    **When to use EFS:**
    - Need to share files across instances
    - Containers (ECS, EKS) need persistent storage
    - Don't know capacity needs upfront

    **When to use EBS:**
    - Single EC2 instance
    - Database volumes
    - Boot volumes
    """,
    related_controls=["CC6.7", "A1.3"],
    aws_services=["efs", "kms", "ec2", "ecs"],
    estimated_cost="$10-50/month for 100GB with lifecycle"
)

FSX_WINDOWS = ArchitectureDecision(
    name="FSx for Windows File Server",
    context="""
    Need Windows-compatible file storage with:
    - SMB protocol
    - Active Directory integration
    - Windows ACLs
    - DFS namespaces
    - Shadow copies (snapshots)
    """,
    options={
        "FSx for Windows File Server (Recommended for Windows)": """
        **Architecture:**
        - FSx file system (managed Windows File Server)
        - Active Directory integration (AWS Managed AD or on-prem)
        - Multi-AZ deployment
        - Automatic backups
        - VPC private subnets

        **Features:**
        - Native Windows SMB protocol
        - Windows ACLs and NTFS
        - Active Directory integration
        - DFS namespaces and replication
        - Shadow copies (user-accessible snapshots)
        - Data deduplication
        - 2GB/s throughput

        **Deployment Types:**
        - Single-AZ: Cheaper, no HA
        - Multi-AZ: Automatic failover, higher availability

        **Cost:** approx. $0.13/GB/month + $2.20/MB/s throughput
        - Storage: $0.13/GB/month (SSD)
        - Throughput: $2.20/MB/s/month
        - Example: 200GB, 32 MB/s = approx. $96/month

        **Pros:**
        - Native Windows compatibility
        - Active Directory integration
        - DFS support
        - Shadow copies
        - Managed service

        **Cons:**
        - More expensive than EFS
        - Windows-only

        **When to use:** Windows workloads, Active Directory, SMB required
        """,

        "EFS (Linux/NFS Only)": """
        **Cost:** approx. $0.30/GB/month

        **Pros:** Cheaper for Linux workloads

        **Cons:** No SMB, no Windows ACLs, no AD integration

        **When to use:** Linux-only workloads
        """
    },
    recommendation="FSx for Windows workloads, EFS for Linux",
    tradeoffs="""
    **FSx for Windows vs EFS:**
    - FSx: Windows, SMB, AD, DFS, $96/mo for 200GB
    - EFS: Linux, NFS, no AD, $60/mo for 200GB

    **Use FSx when:**
    - Windows applications
    - Need Active Directory
    - Need SMB protocol
    - Need DFS namespaces

    **Use EFS when:**
    - Linux applications
    - NFS sufficient
    """,
    related_controls=["CC6.1", "CC6.7", "A1.3"],
    aws_services=["fsx", "directoryservice", "kms"],
    estimated_cost="$96-300/month depending on capacity and throughput"
)

FSX_LUSTRE = ArchitectureDecision(
    name="FSx for Lustre (High-Performance Computing)",
    context="""
    Need high-performance file system for:
    - Big data analytics
    - Machine learning training
    - Media processing
    - Genomics
    - HPC workloads
    - Sub-millisecond latencies
    - Hundreds of GB/s throughput
    """,
    options={
        "FSx for Lustre (Recommended for HPC)": """
        **Architecture:**
        - FSx Lustre file system
        - S3 integration (data repository)
        - EC2 instances with Lustre client
        - VPC private subnets

        **Features:**
        - Sub-millisecond latencies
        - Hundreds of GB/s throughput
        - S3 integration (lazy load, auto export)
        - POSIX-compliant
        - Optimized for parallel workloads

        **Deployment Types:**
        - Scratch: Temporary, no replication, cheapest
        - Persistent: Replicated, automatic backups

        **Cost:** approx. $0.14/GB/month (Scratch) or $0.17-0.26/GB/month (Persistent)
        - Scratch: $0.14/GB/month (50 MB/s/TB baseline)
        - Persistent SSD: $0.17-0.26/GB/month (depends on throughput)
        - Example: 1.2TB Scratch = approx. $168/month

        **Pros:**
        - Extremely fast (hundreds of GB/s)
        - S3 integration (data lake)
        - Optimized for HPC
        - Scales to petabytes

        **Cons:**
        - Expensive
        - Complex
        - Overkill for most workloads

        **When to use:** HPC, machine learning, genomics, media rendering
        """,

        "EFS (For Standard Workloads)": """
        **Cost:** approx. $0.30/GB/month

        **Throughput:** Up to 10 GB/s

        **When to use:** Standard workloads (not HPC)
        """
    },
    recommendation="FSx Lustre only for HPC, use EFS for standard workloads",
    tradeoffs="""
    **FSx Lustre vs EFS:**
    - FSx Lustre: 100s GB/s, sub-ms latency, $168/mo for 1.2TB, HPC
    - EFS: 10 GB/s, ms latency, $360/mo for 1.2TB, standard workloads

    **Use FSx Lustre when:**
    - Sub-millisecond latencies required
    - Need >10 GB/s throughput
    - HPC, ML training, genomics, rendering

    **Use EFS when:**
    - Standard workloads
    - Don't need extreme performance
    """,
    related_controls=["CC6.7", "PI1.3"],
    aws_services=["fsx", "s3", "ec2"],
    estimated_cost="$168-500/month for 1.2TB"
)

# Export patterns
PATTERNS = [
    EFS_SHARED_STORAGE,
    FSX_WINDOWS,
    FSX_LUSTRE
]
