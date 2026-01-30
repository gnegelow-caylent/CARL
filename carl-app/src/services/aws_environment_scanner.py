"""
AWS Environment Scanner - Comprehensive scan for intelligent architecture decisions.

This scanner gathers deep AWS environment information to feed into AI agents
for intelligent question asking, architecture recommendations, and code generation.

Used by:
- /carl recommend - Understand current state for better recommendations
- /carl build - Know what exists to ask intelligent configuration questions
- /carl ask - Context-aware answers about your environment
"""
import boto3
from botocore.exceptions import ClientError
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any
import json

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class VPCInfo:
    """Detailed VPC information."""
    vpc_id: str
    cidr: str
    name: Optional[str]
    is_default: bool
    subnets: List[Dict[str, Any]]
    route_tables: List[Dict[str, Any]]
    nat_gateways: List[str]
    internet_gateways: List[str]
    vpc_endpoints: List[Dict[str, Any]]
    has_private_subnets: bool
    has_public_subnets: bool
    availability_zones: List[str]


@dataclass
class DatabaseInfo:
    """Database resources."""
    rds_instances: List[Dict[str, Any]]
    rds_clusters: List[Dict[str, Any]]
    dynamodb_tables: List[str]


@dataclass
class ComputeInfo:
    """Compute resources."""
    ec2_instances: List[Dict[str, Any]]
    ecs_clusters: List[str]
    eks_clusters: List[str]
    lambda_functions: List[str]


@dataclass
class SecurityInfo:
    """Security posture."""
    guardduty_enabled: bool
    security_hub_enabled: bool
    cloudtrail_trails: List[Dict[str, Any]]
    config_enabled: bool
    kms_keys: List[str]
    secrets_manager_secrets: List[str]


@dataclass
class NetworkingInfo:
    """Networking configuration."""
    vpcs: List[VPCInfo]
    transit_gateways: List[str]
    vpc_peering_connections: List[Dict[str, Any]]
    direct_connect_gateways: List[str]
    vpn_connections: List[str]
    load_balancers: List[Dict[str, Any]]


@dataclass
class AWSEnvironmentScan:
    """Complete AWS environment scan results."""
    region: str
    account_id: str
    networking: NetworkingInfo
    databases: DatabaseInfo
    compute: ComputeInfo
    security: SecurityInfo
    scan_timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def to_context_summary(self) -> str:
        """Generate human-readable summary for AI context."""
        summary = f"AWS Environment Scan (Account: {self.account_id}, Region: {self.region})\n\n"

        # Networking
        summary += "NETWORKING:\n"
        if self.networking.vpcs:
            summary += f"  VPCs: {len(self.networking.vpcs)} found\n"
            for vpc in self.networking.vpcs[:3]:  # First 3
                summary += f"    - {vpc.vpc_id} ({vpc.cidr})"
                if vpc.name:
                    summary += f" - {vpc.name}"
                summary += f" | Subnets: {len(vpc.subnets)} ({len([s for s in vpc.subnets if s.get('public')])} public, {len([s for s in vpc.subnets if not s.get('public')])} private)\n"
        else:
            summary += "  VPCs: None found\n"

        if self.networking.load_balancers:
            summary += f"  Load Balancers: {len(self.networking.load_balancers)} found\n"

        # Databases
        summary += "\nDATABASES:\n"
        if self.databases.rds_instances:
            summary += f"  RDS Instances: {len(self.databases.rds_instances)} found\n"
            for db in self.databases.rds_instances[:3]:
                summary += f"    - {db['identifier']} ({db['engine']} {db.get('version', '')})\n"
        if self.databases.dynamodb_tables:
            summary += f"  DynamoDB Tables: {len(self.databases.dynamodb_tables)} found\n"

        # Compute
        summary += "\nCOMPUTE:\n"
        if self.compute.ec2_instances:
            summary += f"  EC2 Instances: {len(self.compute.ec2_instances)} running\n"
        if self.compute.ecs_clusters:
            summary += f"  ECS Clusters: {len(self.compute.ecs_clusters)} found\n"
        if self.compute.lambda_functions:
            summary += f"  Lambda Functions: {len(self.compute.lambda_functions)} found\n"

        # Security
        summary += "\nSECURITY:\n"
        summary += f"  GuardDuty: {'✓ Enabled' if self.security.guardduty_enabled else '✗ Not enabled'}\n"
        summary += f"  Security Hub: {'✓ Enabled' if self.security.security_hub_enabled else '✗ Not enabled'}\n"
        summary += f"  CloudTrail: {len(self.security.cloudtrail_trails)} trail(s)\n"
        summary += f"  Config: {'✓ Enabled' if self.security.config_enabled else '✗ Not enabled'}\n"

        return summary


class AWSEnvironmentScanner:
    """
    Comprehensive AWS environment scanner.

    Gathers detailed information about AWS resources to enable intelligent
    architecture decisions without hardcoded rules.
    """

    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self.ec2 = boto3.client("ec2", region_name=region)
        self.rds = boto3.client("rds", region_name=region)
        self.dynamodb = boto3.client("dynamodb", region_name=region)
        self.elbv2 = boto3.client("elbv2", region_name=region)
        self.ecs = boto3.client("ecs", region_name=region)
        self.eks = boto3.client("eks", region_name=region)
        self.lambda_client = boto3.client("lambda", region_name=region)
        self.guardduty = boto3.client("guardduty", region_name=region)
        self.securityhub = boto3.client("securityhub", region_name=region)
        self.cloudtrail = boto3.client("cloudtrail", region_name=region)
        self.config = boto3.client("config", region_name=region)
        self.kms = boto3.client("kms", region_name=region)
        self.secretsmanager = boto3.client("secretsmanager", region_name=region)
        self.sts = boto3.client("sts", region_name=region)

    def scan(self) -> AWSEnvironmentScan:
        """
        Perform comprehensive AWS environment scan.

        Returns:
            AWSEnvironmentScan with detailed results
        """
        logger.info(f"Starting comprehensive AWS environment scan in {self.region}")

        # Get account ID
        account_id = self.sts.get_caller_identity()["Account"]

        # Scan each category
        networking = self._scan_networking()
        databases = self._scan_databases()
        compute = self._scan_compute()
        security = self._scan_security()

        import datetime
        scan_timestamp = datetime.datetime.utcnow().isoformat()

        scan_result = AWSEnvironmentScan(
            region=self.region,
            account_id=account_id,
            networking=networking,
            databases=databases,
            compute=compute,
            security=security,
            scan_timestamp=scan_timestamp
        )

        logger.info("AWS environment scan completed")
        return scan_result

    def _scan_networking(self) -> NetworkingInfo:
        """Scan networking resources."""
        logger.info("Scanning networking resources...")

        vpcs = []
        try:
            response = self.ec2.describe_vpcs()
            for vpc_data in response.get("Vpcs", []):
                vpc_id = vpc_data["VpcId"]
                cidr = vpc_data["CidrBlock"]
                is_default = vpc_data.get("IsDefault", False)

                # Get VPC name from tags
                name = None
                for tag in vpc_data.get("Tags", []):
                    if tag["Key"] == "Name":
                        name = tag["Value"]
                        break

                # Get subnets
                subnets = []
                subnet_response = self.ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])
                for subnet in subnet_response.get("Subnets", []):
                    subnet_name = None
                    for tag in subnet.get("Tags", []):
                        if tag["Key"] == "Name":
                            subnet_name = tag["Value"]
                            break

                    # Check if public (has route to IGW)
                    is_public = False
                    try:
                        route_table_response = self.ec2.describe_route_tables(
                            Filters=[{"Name": "association.subnet-id", "Values": [subnet["SubnetId"]]}]
                        )
                        for rt in route_table_response.get("RouteTables", []):
                            for route in rt.get("Routes", []):
                                if route.get("GatewayId", "").startswith("igw-"):
                                    is_public = True
                                    break
                    except:
                        pass

                    subnets.append({
                        "subnet_id": subnet["SubnetId"],
                        "cidr": subnet["CidrBlock"],
                        "az": subnet["AvailabilityZone"],
                        "name": subnet_name,
                        "public": is_public
                    })

                # Get NAT gateways
                nat_gateways = []
                nat_response = self.ec2.describe_nat_gateways(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])
                nat_gateways = [nat["NatGatewayId"] for nat in nat_response.get("NatGateways", [])]

                # Get Internet gateways
                internet_gateways = []
                igw_response = self.ec2.describe_internet_gateways(Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}])
                internet_gateways = [igw["InternetGatewayId"] for igw in igw_response.get("InternetGateways", [])]

                # Get VPC endpoints
                vpc_endpoints = []
                endpoint_response = self.ec2.describe_vpc_endpoints(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])
                for endpoint in endpoint_response.get("VpcEndpoints", []):
                    vpc_endpoints.append({
                        "endpoint_id": endpoint["VpcEndpointId"],
                        "service_name": endpoint["ServiceName"],
                        "type": endpoint["VpcEndpointType"]
                    })

                # Get route tables
                route_tables = []
                rt_response = self.ec2.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])
                for rt in rt_response.get("RouteTables", []):
                    route_tables.append({
                        "route_table_id": rt["RouteTableId"],
                        "routes": len(rt.get("Routes", [])),
                        "associations": len(rt.get("Associations", []))
                    })

                has_private = any(not s["public"] for s in subnets)
                has_public = any(s["public"] for s in subnets)
                azs = list(set(s["az"] for s in subnets))

                vpcs.append(VPCInfo(
                    vpc_id=vpc_id,
                    cidr=cidr,
                    name=name,
                    is_default=is_default,
                    subnets=subnets,
                    route_tables=route_tables,
                    nat_gateways=nat_gateways,
                    internet_gateways=internet_gateways,
                    vpc_endpoints=vpc_endpoints,
                    has_private_subnets=has_private,
                    has_public_subnets=has_public,
                    availability_zones=azs
                ))

        except ClientError as e:
            logger.warning(f"Error scanning VPCs: {e}")

        # Load balancers
        load_balancers = []
        try:
            response = self.elbv2.describe_load_balancers()
            for lb in response.get("LoadBalancers", []):
                load_balancers.append({
                    "name": lb["LoadBalancerName"],
                    "type": lb["Type"],
                    "scheme": lb["Scheme"],
                    "vpc_id": lb.get("VpcId")
                })
        except ClientError as e:
            logger.warning(f"Error scanning load balancers: {e}")

        return NetworkingInfo(
            vpcs=vpcs,
            transit_gateways=[],  # TODO: Add if needed
            vpc_peering_connections=[],
            direct_connect_gateways=[],
            vpn_connections=[],
            load_balancers=load_balancers
        )

    def _scan_databases(self) -> DatabaseInfo:
        """Scan database resources."""
        logger.info("Scanning database resources...")

        rds_instances = []
        try:
            response = self.rds.describe_db_instances()
            for db in response.get("DBInstances", []):
                rds_instances.append({
                    "identifier": db["DBInstanceIdentifier"],
                    "engine": db["Engine"],
                    "version": db.get("EngineVersion"),
                    "instance_class": db["DBInstanceClass"],
                    "multi_az": db.get("MultiAZ", False),
                    "storage": db.get("AllocatedStorage"),
                    "vpc_id": db.get("DBSubnetGroup", {}).get("VpcId")
                })
        except ClientError as e:
            logger.warning(f"Error scanning RDS instances: {e}")

        rds_clusters = []
        try:
            response = self.rds.describe_db_clusters()
            for cluster in response.get("DBClusters", []):
                rds_clusters.append({
                    "identifier": cluster["DBClusterIdentifier"],
                    "engine": cluster["Engine"],
                    "version": cluster.get("EngineVersion")
                })
        except ClientError as e:
            logger.warning(f"Error scanning RDS clusters: {e}")

        dynamodb_tables = []
        try:
            response = self.dynamodb.list_tables()
            dynamodb_tables = response.get("TableNames", [])
        except ClientError as e:
            logger.warning(f"Error scanning DynamoDB tables: {e}")

        return DatabaseInfo(
            rds_instances=rds_instances,
            rds_clusters=rds_clusters,
            dynamodb_tables=dynamodb_tables
        )

    def _scan_compute(self) -> ComputeInfo:
        """Scan compute resources."""
        logger.info("Scanning compute resources...")

        ec2_instances = []
        try:
            response = self.ec2.describe_instances(Filters=[{"Name": "instance-state-name", "Values": ["running"]}])
            for reservation in response.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    name = None
                    for tag in instance.get("Tags", []):
                        if tag["Key"] == "Name":
                            name = tag["Value"]
                            break

                    ec2_instances.append({
                        "instance_id": instance["InstanceId"],
                        "instance_type": instance["InstanceType"],
                        "name": name,
                        "vpc_id": instance.get("VpcId"),
                        "subnet_id": instance.get("SubnetId")
                    })
        except ClientError as e:
            logger.warning(f"Error scanning EC2 instances: {e}")

        ecs_clusters = []
        try:
            response = self.ecs.list_clusters()
            ecs_clusters = response.get("clusterArns", [])
        except ClientError as e:
            logger.warning(f"Error scanning ECS clusters: {e}")

        eks_clusters = []
        try:
            response = self.eks.list_clusters()
            eks_clusters = response.get("clusters", [])
        except ClientError as e:
            logger.warning(f"Error scanning EKS clusters: {e}")

        lambda_functions = []
        try:
            response = self.lambda_client.list_functions()
            lambda_functions = [func["FunctionName"] for func in response.get("Functions", [])]
        except ClientError as e:
            logger.warning(f"Error scanning Lambda functions: {e}")

        return ComputeInfo(
            ec2_instances=ec2_instances,
            ecs_clusters=ecs_clusters,
            eks_clusters=eks_clusters,
            lambda_functions=lambda_functions
        )

    def _scan_security(self) -> SecurityInfo:
        """Scan security resources."""
        logger.info("Scanning security resources...")

        guardduty_enabled = False
        try:
            response = self.guardduty.list_detectors()
            guardduty_enabled = len(response.get("DetectorIds", [])) > 0
        except ClientError:
            pass

        security_hub_enabled = False
        try:
            self.securityhub.describe_hub()
            security_hub_enabled = True
        except ClientError:
            pass

        cloudtrail_trails = []
        try:
            response = self.cloudtrail.describe_trails()
            for trail in response.get("trailList", []):
                cloudtrail_trails.append({
                    "name": trail["Name"],
                    "s3_bucket": trail.get("S3BucketName"),
                    "is_multi_region": trail.get("IsMultiRegionTrail", False)
                })
        except ClientError as e:
            logger.warning(f"Error scanning CloudTrail: {e}")

        config_enabled = False
        try:
            response = self.config.describe_configuration_recorders()
            config_enabled = len(response.get("ConfigurationRecorders", [])) > 0
        except ClientError:
            pass

        kms_keys = []
        secrets = []

        return SecurityInfo(
            guardduty_enabled=guardduty_enabled,
            security_hub_enabled=security_hub_enabled,
            cloudtrail_trails=cloudtrail_trails,
            config_enabled=config_enabled,
            kms_keys=kms_keys,
            secrets_manager_secrets=secrets
        )
