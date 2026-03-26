"""Rosetta Zero CDK Stack - AWS Infrastructure for Legacy Code Modernization."""

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_ec2 as ec2,
    aws_kms as kms,
    aws_s3 as s3,
    aws_s3_notifications as s3n,
    aws_dynamodb as dynamodb,
    aws_logs as logs,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_ecs as ecs,
    aws_ecr as ecr,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
    aws_events as events,
    aws_events_targets as targets,
    aws_cloudwatch as cloudwatch,
)
from constructs import Construct


class RosettaZeroStack(Stack):
    """CDK stack for Rosetta Zero infrastructure.
    
    Implements secure, isolated AWS infrastructure for legacy code modernization
    with behavioral equivalence proof. Includes VPC with private subnets, KMS keys
    for encryption and signing, S3 buckets for artifact storage, and DynamoDB tables
    for test results.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create VPC with private subnets and VPC endpoints
        self.vpc = self._create_vpc()

        # Create KMS keys for encryption and signing
        self.kms_keys = self._create_kms_keys()

        # Create S3 buckets for artifact storage
        self.buckets = self._create_s3_buckets()

        # Create DynamoDB tables for test results and workflow tracking
        self.tables = self._create_dynamodb_tables()

        # Create Lambda functions
        self.lambdas = self._create_lambda_functions()

        # Create ECR repository for legacy executor container
        self.ecr_repository = self._create_ecr_repository()

        # Create Fargate cluster and task definition for legacy execution
        self.fargate_cluster, self.fargate_task_definition = self._create_fargate_cluster()

        # Create verification Lambda functions
        self.verification_lambdas = self._create_verification_lambdas()

        # Create Step Functions state machine for verification orchestration
        self.verification_state_machine = self._create_verification_state_machine()
        
        # Update orchestrator Lambda with state machine ARN
        self.lambdas["orchestrator"].add_environment(
            "VERIFICATION_STATE_MACHINE_ARN",
            self.verification_state_machine.state_machine_arn
        )

        # Create Certificate Generator Lambda (Trust Phase)
        self.certificate_generator = self._create_certificate_generator_lambda()
        
        # Create Compliance Reporter Lambda (Requirements 30.1, 30.2, 30.3, 30.4, 30.5, 30.6)
        self.compliance_reporter = self._create_compliance_reporter_lambda()
        
        # Create Resource Cleanup Lambda (Requirements 26.1, 26.2, 26.3, 26.4)
        self.cleanup_lambda = self._create_resource_cleanup_lambda()

        # Create SNS topics for operator notifications
        self.sns_topics = self._create_sns_topics()

        # Create EventBridge rules for monitoring and notifications
        self.event_rules = self._create_eventbridge_rules()

        # Create CloudWatch dashboards for monitoring
        self.dashboards = self._create_cloudwatch_dashboards()

    def _create_vpc(self) -> ec2.Vpc:
        """Create VPC with private isolated subnets and VPC endpoints.
        
        Requirements: 21.1, 21.4, 21.5
        - 3 availability zones for high availability
        - Private isolated subnets only (no internet gateway, no NAT gateway)
        - VPC endpoints for AWS service access via PrivateLink
        
        Returns:
            VPC with private subnets and configured VPC endpoints
        """
        vpc = ec2.Vpc(
            self,
            "RosettaZeroVPC",
            max_azs=3,
            nat_gateways=0,  # No internet access per requirement 21.5
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="PrivateIsolated",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                )
            ],
        )

        # VPC Endpoint for Bedrock (requirement 21.4)
        vpc.add_interface_endpoint(
            "BedrockEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.BEDROCK_RUNTIME,
        )

        # VPC Gateway Endpoint for S3 (requirement 21.4)
        vpc.add_gateway_endpoint(
            "S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
        )

        # VPC Gateway Endpoint for DynamoDB (requirement 21.4)
        vpc.add_gateway_endpoint(
            "DynamoDBEndpoint",
            service=ec2.GatewayVpcEndpointAwsService.DYNAMODB,
        )

        # VPC Endpoint for KMS (requirement 21.4)
        vpc.add_interface_endpoint(
            "KMSEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.KMS,
        )

        # VPC Endpoint for CloudWatch Logs (requirement 21.4)
        vpc.add_interface_endpoint(
            "CloudWatchLogsEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
        )

        # VPC Endpoint for EventBridge (requirement 21.4)
        vpc.add_interface_endpoint(
            "EventBridgeEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.EVENTBRIDGE,
        )

        return vpc

    def _create_kms_keys(self) -> dict:
        """Create KMS keys for encryption and signing.
        
        Requirements: 21.3, 17.7
        - Symmetric key for data encryption with automatic rotation
        - Asymmetric RSA-4096 key for certificate signing
        
        Returns:
            Dictionary with 'encryption' and 'signing' KMS keys
        """
        # Symmetric key for data encryption (requirement 21.3)
        encryption_key = kms.Key(
            self,
            "DataEncryptionKey",
            description="Rosetta Zero data encryption key for S3, DynamoDB, and CloudWatch Logs",
            enable_key_rotation=True,  # Automatic annual rotation
            removal_policy=RemovalPolicy.RETAIN,  # Retain for compliance
        )

        encryption_key.add_alias("alias/rosetta-zero-encryption")

        # Asymmetric RSA-4096 key for certificate signing (requirement 17.7)
        signing_key = kms.Key(
            self,
            "CertificateSigningKey",
            description="Rosetta Zero certificate signing key for equivalence certificates",
            key_spec=kms.KeySpec.RSA_4096,
            key_usage=kms.KeyUsage.SIGN_VERIFY,
            removal_policy=RemovalPolicy.RETAIN,  # Retain for compliance
        )

        signing_key.add_alias("alias/rosetta-zero-signing")

        return {"encryption": encryption_key, "signing": signing_key}

    def _create_s3_buckets(self) -> dict:
        """Create S3 buckets with versioning, encryption, and lifecycle policies.
        
        Requirements: 1.1, 1.2, 2.7, 3.3, 6.8, 9.9, 14.8, 17.8, 20.5, 30.5, 27.2, 27.3
        - 9 buckets for different artifact types
        - Versioning enabled on all buckets
        - KMS encryption with customer-managed keys
        - Lifecycle policies for temporary objects (30-day expiration)
        - Block all public access
        - SSL enforcement
        - Cross-region replication for certificates bucket (disaster recovery)
        
        Returns:
            Dictionary mapping bucket names to S3 Bucket constructs
        """
        buckets = {}

        bucket_configs = [
            ("legacy-artifacts", "Legacy binaries and source code"),
            ("logic-maps", "Extracted Logic Maps"),
            ("ears-requirements", "EARS requirements documents"),
            ("modern-implementations", "Generated Lambda code"),
            ("cdk-infrastructure", "Generated CDK code"),
            ("test-vectors", "Adversarial test vectors"),
            ("discrepancy-reports", "Test failure reports"),
            ("certificates", "Equivalence certificates"),
            ("compliance-reports", "Regulatory compliance reports"),
        ]

        for bucket_name, description in bucket_configs:
            bucket = s3.Bucket(
                self,
                f"{bucket_name.replace('-', '_').title()}Bucket",
                bucket_name=f"rosetta-zero-{bucket_name}-{self.account}-{self.region}",
                versioned=True,  # Requirement 1.1, 1.2
                encryption=s3.BucketEncryption.KMS,  # Requirement 21.3
                encryption_key=self.kms_keys["encryption"],
                block_public_access=s3.BlockPublicAccess.BLOCK_ALL,  # Security best practice
                enforce_ssl=True,  # Requirement 21.2
                removal_policy=RemovalPolicy.RETAIN,  # Retain for compliance
                lifecycle_rules=[
                    s3.LifecycleRule(
                        id="DeleteTempAfter30Days",
                        prefix="temp/",
                        expiration=Duration.days(30),  # Requirement 26.2
                        enabled=True,
                    )
                ],
            )

            buckets[bucket_name] = bucket

        # Configure cross-region replication for certificates bucket (Requirements 27.2, 27.3)
        self._configure_certificates_replication(buckets["certificates"])

        return buckets

    def _configure_certificates_replication(self, certificates_bucket: s3.Bucket) -> None:
        """Configure cross-region replication for certificates bucket.
        
        Requirements: 27.2, 27.3
        - Replicate equivalence certificates to secondary AWS region for disaster recovery
        - Configure S3 replication rules for all objects in certificates bucket
        - Use KMS encryption for replicated objects
        
        Args:
            certificates_bucket: The source certificates S3 bucket
        """
        # Determine secondary region for disaster recovery
        # Use a different region from the primary for geographic redundancy
        primary_region = self.region
        
        # Map primary regions to secondary regions for disaster recovery
        region_pairs = {
            "us-east-1": "us-west-2",
            "us-west-2": "us-east-1",
            "eu-west-1": "eu-central-1",
            "eu-central-1": "eu-west-1",
            "ap-southeast-1": "ap-northeast-1",
            "ap-northeast-1": "ap-southeast-1",
        }
        
        secondary_region = region_pairs.get(primary_region, "us-west-2")
        
        # Create destination bucket in secondary region for replication
        # Note: In CDK, cross-region resources require special handling
        # We'll use CfnBucket for the destination to specify the region
        destination_bucket_name = f"rosetta-zero-certificates-replica-{self.account}-{secondary_region}"
        
        # Create IAM role for S3 replication
        replication_role = iam.Role(
            self,
            "CertificatesReplicationRole",
            assumed_by=iam.ServicePrincipal("s3.amazonaws.com"),
            description="IAM role for S3 cross-region replication of certificates",
        )
        
        # Grant permissions to read from source bucket
        certificates_bucket.grant_read(replication_role)
        
        # Grant permissions to replicate objects (write to destination)
        replication_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:ReplicateObject",
                    "s3:ReplicateDelete",
                    "s3:ReplicateTags",
                    "s3:GetObjectVersionTagging",
                ],
                resources=[
                    f"arn:aws:s3:::{destination_bucket_name}/*",
                ],
            )
        )
        
        # Grant KMS permissions for encryption/decryption during replication
        replication_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "kms:Decrypt",
                    "kms:DescribeKey",
                ],
                resources=[self.kms_keys["encryption"].key_arn],
                conditions={
                    "StringLike": {
                        "kms:ViaService": f"s3.{primary_region}.amazonaws.com",
                    }
                },
            )
        )
        
        replication_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "kms:Encrypt",
                    "kms:GenerateDataKey",
                ],
                resources=[f"arn:aws:kms:{secondary_region}:{self.account}:key/*"],
                conditions={
                    "StringLike": {
                        "kms:ViaService": f"s3.{secondary_region}.amazonaws.com",
                    }
                },
            )
        )
        
        # Configure replication on the source bucket using CfnBucket
        cfn_bucket = certificates_bucket.node.default_child
        cfn_bucket.replication_configuration = s3.CfnBucket.ReplicationConfigurationProperty(
            role=replication_role.role_arn,
            rules=[
                s3.CfnBucket.ReplicationRuleProperty(
                    id="ReplicateAllCertificates",
                    status="Enabled",
                    priority=1,
                    filter=s3.CfnBucket.ReplicationRuleFilterProperty(
                        prefix="",  # Replicate all objects
                    ),
                    destination=s3.CfnBucket.ReplicationDestinationProperty(
                        bucket=f"arn:aws:s3:::{destination_bucket_name}",
                        storage_class="STANDARD_IA",  # Use Infrequent Access for cost optimization
                        encryption_configuration=s3.CfnBucket.EncryptionConfigurationProperty(
                            replica_kms_key_id=f"arn:aws:kms:{secondary_region}:{self.account}:alias/aws/s3",
                        ),
                    ),
                    delete_marker_replication=s3.CfnBucket.DeleteMarkerReplicationProperty(
                        status="Enabled",
                    ),
                )
            ],
        )

    def _create_dynamodb_tables(self) -> dict:
        """Create DynamoDB tables with encryption and point-in-time recovery.
        
        Requirements: 15.1-15.6, 24.1-24.7
        - test-results table with test_id (PK) and execution_timestamp (SK)
        - workflow-phases table with workflow_id (PK) and phase_name (SK)
        - GSI on status field for test-results table
        - Point-in-time recovery enabled
        - KMS encryption with customer-managed keys
        - PAY_PER_REQUEST billing mode
        
        Returns:
            Dictionary mapping table names to DynamoDB Table constructs
        """
        # Test Results Table (requirements 15.1-15.6)
        test_results_table = dynamodb.Table(
            self,
            "TestResultsTable",
            table_name="rosetta-zero-test-results",
            partition_key=dynamodb.Attribute(
                name="test_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="execution_timestamp", type=dynamodb.AttributeType.STRING
            ),
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=self.kms_keys["encryption"],
            point_in_time_recovery=True,  # Requirement 15.6
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,  # Retain for compliance
        )

        # Global Secondary Index on status field
        test_results_table.add_global_secondary_index(
            index_name="status-index",
            partition_key=dynamodb.Attribute(
                name="status", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="execution_timestamp", type=dynamodb.AttributeType.STRING
            ),
        )

        # Workflow Phase Tracking Table (requirements 24.1-24.7)
        workflow_table = dynamodb.Table(
            self,
            "WorkflowPhasesTable",
            table_name="rosetta-zero-workflow-phases",
            partition_key=dynamodb.Attribute(
                name="workflow_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="phase_name", type=dynamodb.AttributeType.STRING
            ),
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=self.kms_keys["encryption"],
            point_in_time_recovery=True,
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,  # Retain for compliance
        )

        return {"test_results": test_results_table, "workflow": workflow_table}

    def _create_lambda_functions(self) -> dict:
        """Create Lambda functions for Rosetta Zero components.
        
        Requirements: 21.1, 21.2, 21.3
        
        Returns:
            Dictionary mapping function names to Lambda Function constructs
        """
        lambdas = {}
        
        # Ingestion Engine Lambda (Requirements 1.1-1.4, 2.1-2.7, 3.1-3.4, 4.1-4.6, 20.1-20.5)
        ingestion_engine_role = self._create_ingestion_engine_role()
        
        ingestion_engine = lambda_.Function(
            self,
            "IngestionEngineLambda",
            function_name="rosetta-zero-ingestion-engine",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="rosetta_zero.lambdas.ingestion_engine.handler.lambda_handler",
            code=lambda_.Code.from_asset(".", exclude=["cdk.out", ".git", ".pytest_cache", ".hypothesis"]),
            role=ingestion_engine_role,
            timeout=Duration.minutes(15),  # Requirement: 15 min timeout
            memory_size=3008,  # Requirement: 3008 MB memory
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            environment={
                "LOGIC_MAPS_BUCKET": self.buckets["logic-maps"].bucket_name,
                "EARS_BUCKET": self.buckets["ears-requirements"].bucket_name,
                "KMS_KEY_ID": self.kms_keys["encryption"].key_id,
                "POWERTOOLS_SERVICE_NAME": "ingestion-engine",
                "POWERTOOLS_METRICS_NAMESPACE": "RosettaZero",
                "LOG_LEVEL": "INFO",
            },
            log_retention=logs.RetentionDays.TEN_YEARS,  # 7+ years for compliance
        )
        
        lambdas["ingestion_engine"] = ingestion_engine
        
        # Bedrock Architect Lambda (Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8)
        bedrock_architect_role = self._create_bedrock_architect_role()
        
        bedrock_architect = lambda_.Function(
            self,
            "BedrockArchitectLambda",
            function_name="rosetta-zero-bedrock-architect",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="rosetta_zero.lambdas.bedrock_architect.handler.lambda_handler",
            code=lambda_.Code.from_asset(".", exclude=["cdk.out", ".git", ".pytest_cache", ".hypothesis"]),
            role=bedrock_architect_role,
            timeout=Duration.minutes(15),  # Requirement: 15 min timeout for synthesis
            memory_size=3008,  # Requirement: 3008 MB memory
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            environment={
                "MODERN_IMPLEMENTATIONS_BUCKET": self.buckets["modern-implementations"].bucket_name,
                "CDK_INFRASTRUCTURE_BUCKET": self.buckets["cdk-infrastructure"].bucket_name,
                "KMS_KEY_ID": self.kms_keys["encryption"].key_id,
                "BEDROCK_MODEL_ID": "anthropic.claude-3-5-sonnet-20241022-v2:0",
                "COBOL_KB_ID": "",  # To be configured with actual Knowledge Base IDs
                "FORTRAN_KB_ID": "",  # To be configured with actual Knowledge Base IDs
                "MAINFRAME_KB_ID": "",  # To be configured with actual Knowledge Base IDs
                "POWERTOOLS_SERVICE_NAME": "bedrock-architect",
                "POWERTOOLS_METRICS_NAMESPACE": "RosettaZero",
                "LOG_LEVEL": "INFO",
            },
            log_retention=logs.RetentionDays.TEN_YEARS,  # 7+ years for compliance
        )
        
        lambdas["bedrock_architect"] = bedrock_architect
        
        # Hostile Auditor Lambda (Requirements 9.1-9.9, 10.1-10.4, 28.1-28.4)
        hostile_auditor_role = self._create_hostile_auditor_role()
        
        hostile_auditor = lambda_.Function(
            self,
            "HostileAuditorLambda",
            function_name="rosetta-zero-hostile-auditor",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="rosetta_zero.lambdas.hostile_auditor.handler.lambda_handler",
            code=lambda_.Code.from_asset(".", exclude=["cdk.out", ".git", ".pytest_cache", ".hypothesis"]),
            role=hostile_auditor_role,
            timeout=Duration.minutes(15),  # Requirement: 15 min timeout for test generation
            memory_size=10240,  # Requirement: 10240 MB memory for large-scale test generation
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            environment={
                "TEST_VECTORS_BUCKET": self.buckets["test-vectors"].bucket_name,
                "WORKFLOW_TABLE_NAME": self.tables["workflow"].table_name,
                "KMS_KEY_ID": self.kms_keys["encryption"].key_id,
                "TARGET_TEST_COUNT": "1000000",
                "TARGET_COVERAGE": "0.95",
                "BATCH_SIZE": "10000",
                "POWERTOOLS_SERVICE_NAME": "hostile-auditor",
                "POWERTOOLS_METRICS_NAMESPACE": "RosettaZero",
                "LOG_LEVEL": "INFO",
            },
            log_retention=logs.RetentionDays.TEN_YEARS,  # 7+ years for compliance
        )
        
        lambdas["hostile_auditor"] = hostile_auditor
        
        # Workflow Orchestrator Lambda (Requirements 19.1, 24.6)
        orchestrator_role = self._create_orchestrator_role()
        
        orchestrator = lambda_.Function(
            self,
            "WorkflowOrchestratorLambda",
            function_name="rosetta-zero-workflow-orchestrator",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="rosetta_zero.lambdas.workflow_orchestrator.handler.orchestrator_handler",
            code=lambda_.Code.from_asset(".", exclude=["cdk.out", ".git", ".pytest_cache", ".hypothesis"]),
            role=orchestrator_role,
            timeout=Duration.minutes(5),  # Orchestration should be quick
            memory_size=512,  # Minimal memory for orchestration logic
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            environment={
                "WORKFLOW_PHASES_TABLE": self.tables["workflow"].table_name,
                "INGESTION_ENGINE_FUNCTION_NAME": "rosetta-zero-ingestion-engine",
                "BEDROCK_ARCHITECT_FUNCTION_NAME": "rosetta-zero-bedrock-architect",
                "HOSTILE_AUDITOR_FUNCTION_NAME": "rosetta-zero-hostile-auditor",
                "CERTIFICATE_GENERATOR_FUNCTION_NAME": "rosetta-zero-certificate-generator",
                "VERIFICATION_STATE_MACHINE_ARN": "",  # Will be set after state machine creation
                "POWERTOOLS_SERVICE_NAME": "workflow-orchestrator",
                "POWERTOOLS_METRICS_NAMESPACE": "RosettaZero",
                "LOG_LEVEL": "INFO",
            },
            log_retention=logs.RetentionDays.TEN_YEARS,  # 7+ years for compliance
        )
        
        lambdas["orchestrator"] = orchestrator
        
        return lambdas
    
    def _create_ingestion_engine_role(self) -> iam.Role:
        """Create IAM role for Ingestion Engine Lambda.
        
        Requirements: 21.1, 21.2, 21.3
        
        Grants:
        - S3 read access to legacy-artifacts bucket
        - S3 write access to logic-maps and ears-requirements buckets
        - bedrock:InvokeModel permission for Claude 3.5 Sonnet
        - macie2 permissions for PII detection
        - CloudWatch Logs permissions
        - KMS decrypt/encrypt permissions
        
        Returns:
            IAM Role for Ingestion Engine Lambda
        """
        role = iam.Role(
            self,
            "IngestionEngineRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="IAM role for Rosetta Zero Ingestion Engine Lambda",
        )
        
        # VPC execution permissions
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaVPCAccessExecutionRole"
            )
        )
        
        # S3 read access to legacy-artifacts bucket (Requirement 21.1)
        self.buckets["legacy-artifacts"].grant_read(role)
        
        # S3 write access to logic-maps bucket (Requirement 21.2)
        self.buckets["logic-maps"].grant_write(role)
        
        # S3 write access to ears-requirements bucket (Requirement 21.2)
        self.buckets["ears-requirements"].grant_write(role)
        
        # Bedrock InvokeModel permission (Requirement 21.2)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock:InvokeModel"],
                resources=[
                    f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0"
                ],
            )
        )
        
        # Macie permissions for PII detection (Requirement 21.2)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "macie2:CreateClassificationJob",
                    "macie2:DescribeClassificationJob",
                    "macie2:ListFindings",
                    "macie2:GetFindings",
                ],
                resources=["*"],  # Macie doesn't support resource-level permissions
            )
        )
        
        # CloudWatch Logs permissions (Requirement 21.2)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/rosetta-zero-ingestion-engine:*"
                ],
            )
        )
        
        # KMS decrypt/encrypt permissions (Requirement 21.3)
        self.kms_keys["encryption"].grant_encrypt_decrypt(role)
        
        # SNS publish for operator alerts
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["sns:Publish"],
                resources=[f"arn:aws:sns:{self.region}:{self.account}:rosetta-zero-operator-alerts"],
            )
        )
        
        # SSM parameter read for SNS topic ARN
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ssm:GetParameter"],
                resources=[
                    f"arn:aws:ssm:{self.region}:{self.account}:parameter/rosetta-zero/operator-alerts-topic-arn"
                ],
            )
        )
        
        # STS GetCallerIdentity for Macie
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["sts:GetCallerIdentity"],
                resources=["*"],
            )
        )
        
        return role
    
    def _create_bedrock_architect_role(self) -> iam.Role:
        """Create IAM role for Bedrock Architect Lambda.
        
        Requirements: 21.1, 21.2, 21.3
        
        Grants:
        - S3 read access to logic-maps bucket
        - S3 write access to modern-implementations and cdk-infrastructure buckets
        - bedrock:InvokeModel permission for Claude 3.5 Sonnet
        - bedrock:Retrieve permission for Knowledge Bases
        - CloudWatch Logs permissions
        - KMS decrypt/encrypt permissions
        
        Returns:
            IAM Role for Bedrock Architect Lambda
        """
        role = iam.Role(
            self,
            "BedrockArchitectRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="IAM role for Rosetta Zero Bedrock Architect Lambda",
        )
        
        # VPC execution permissions
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaVPCAccessExecutionRole"
            )
        )
        
        # S3 read access to logic-maps bucket (Requirement 21.1)
        self.buckets["logic-maps"].grant_read(role)
        
        # S3 write access to modern-implementations bucket (Requirement 21.2)
        self.buckets["modern-implementations"].grant_write(role)
        
        # S3 write access to cdk-infrastructure bucket (Requirement 21.2)
        self.buckets["cdk-infrastructure"].grant_write(role)
        
        # Bedrock InvokeModel permission (Requirement 21.2)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock:InvokeModel"],
                resources=[
                    f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0"
                ],
            )
        )
        
        # Bedrock Knowledge Base Retrieve permission (Requirement 21.2)
        # Note: Knowledge Base ARNs will be added when KBs are created
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:Retrieve",
                    "bedrock:RetrieveAndGenerate",
                ],
                resources=[
                    f"arn:aws:bedrock:{self.region}:{self.account}:knowledge-base/*"
                ],
            )
        )
        
        # CloudWatch Logs permissions (Requirement 21.2)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/rosetta-zero-bedrock-architect:*"
                ],
            )
        )
        
        # KMS decrypt/encrypt permissions (Requirement 21.3)
        self.kms_keys["encryption"].grant_encrypt_decrypt(role)
        
        # SNS publish for operator alerts (Requirement 19.3)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["sns:Publish"],
                resources=[f"arn:aws:sns:{self.region}:{self.account}:rosetta-zero-operator-alerts"],
            )
        )
        
        return role

    def _create_hostile_auditor_role(self) -> iam.Role:
        """Create IAM role for Hostile Auditor Lambda.
        
        Requirements: 21.1, 21.2, 21.3
        
        Grants:
        - S3 read access to logic-maps bucket
        - S3 write access to test-vectors bucket
        - DynamoDB read/write access to workflow table
        - CloudWatch Logs permissions
        - KMS decrypt/encrypt permissions
        - SNS publish for operator alerts
        
        Returns:
            IAM Role for Hostile Auditor Lambda
        """
        role = iam.Role(
            self,
            "HostileAuditorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="IAM role for Rosetta Zero Hostile Auditor Lambda",
        )
        
        # VPC execution permissions
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaVPCAccessExecutionRole"
            )
        )
        
        # S3 read access to logic-maps bucket (Requirement 21.1)
        self.buckets["logic-maps"].grant_read(role)
        
        # S3 write access to test-vectors bucket (Requirement 21.2)
        self.buckets["test-vectors"].grant_write(role)
        
        # DynamoDB read/write access to workflow table (Requirement 21.2)
        self.tables["workflow"].grant_read_write_data(role)
        
        # CloudWatch Logs permissions (Requirement 21.2)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/rosetta-zero-hostile-auditor:*"
                ],
            )
        )
        
        # KMS decrypt/encrypt permissions (Requirement 21.3)
        self.kms_keys["encryption"].grant_encrypt_decrypt(role)
        
        # SNS publish for operator alerts (Requirement 19.3)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["sns:Publish"],
                resources=[f"arn:aws:sns:{self.region}:{self.account}:rosetta-zero-operator-alerts"],
            )
        )
        
        return role

    def _create_orchestrator_role(self) -> iam.Role:
        """Create IAM role for Workflow Orchestrator Lambda.
        
        Requirements: 19.1, 21.1, 21.2, 21.3
        
        Grants:
        - Lambda invoke permissions for all component Lambdas
        - Step Functions start execution permission
        - DynamoDB read/write access to workflow table
        - EventBridge put events permission
        - CloudWatch Logs permissions
        - KMS decrypt/encrypt permissions
        
        Returns:
            IAM Role for Workflow Orchestrator Lambda
        """
        role = iam.Role(
            self,
            "WorkflowOrchestratorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="IAM role for Rosetta Zero Workflow Orchestrator Lambda",
        )
        
        # VPC execution permissions
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaVPCAccessExecutionRole"
            )
        )
        
        # Lambda invoke permissions for all component Lambdas (Requirement 19.1)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction"],
                resources=[
                    f"arn:aws:lambda:{self.region}:{self.account}:function:rosetta-zero-ingestion-engine",
                    f"arn:aws:lambda:{self.region}:{self.account}:function:rosetta-zero-bedrock-architect",
                    f"arn:aws:lambda:{self.region}:{self.account}:function:rosetta-zero-hostile-auditor",
                    f"arn:aws:lambda:{self.region}:{self.account}:function:rosetta-zero-certificate-generator",
                ],
            )
        )
        
        # Step Functions start execution permission (Requirement 19.1)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["states:StartExecution"],
                resources=[
                    f"arn:aws:states:{self.region}:{self.account}:stateMachine:rosetta-zero-verification"
                ],
            )
        )
        
        # DynamoDB read/write access to workflow table (Requirement 21.2)
        self.tables["workflow"].grant_read_write_data(role)
        
        # EventBridge put events permission (Requirement 24.6)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["events:PutEvents"],
                resources=[f"arn:aws:events:{self.region}:{self.account}:event-bus/default"],
            )
        )
        
        # CloudWatch Logs permissions (Requirement 21.2)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/rosetta-zero-workflow-orchestrator:*"
                ],
            )
        )
        
        # KMS decrypt/encrypt permissions (Requirement 21.3)
        self.kms_keys["encryption"].grant_encrypt_decrypt(role)
        
        return role

    def _create_ecr_repository(self) -> ecr.Repository:
        """Create ECR repository for legacy executor Docker image.
        
        Requirements: 12.1, 12.2
        
        Returns:
            ECR Repository for legacy executor container image
        """
        repository = ecr.Repository(
            self,
            "LegacyExecutorRepository",
            repository_name="rosetta-zero-legacy-executor",
            image_scan_on_push=True,  # Security best practice
            removal_policy=RemovalPolicy.RETAIN,  # Retain for compliance
            lifecycle_rules=[
                ecr.LifecycleRule(
                    description="Keep last 10 images",
                    max_image_count=10,
                )
            ],
        )
        
        return repository
    
    def _create_fargate_cluster(self) -> tuple:
        """Create Fargate cluster and task definition for legacy binary execution.
        
        Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 18.5, 18.6
        
        Creates:
        - ECS cluster for legacy execution
        - Fargate task definition with 4096 MB memory, 2048 CPU
        - Task execution role with S3 read access
        - Task role with S3 read access to legacy-artifacts bucket
        - CloudWatch Logs with 7-year retention
        - Isolated networking in VPC private subnets
        
        Returns:
            Tuple of (ECS Cluster, Fargate Task Definition)
        """
        # Create ECS cluster (Requirement 12.5)
        cluster = ecs.Cluster(
            self,
            "LegacyExecutionCluster",
            cluster_name="rosetta-zero-legacy-cluster",
            vpc=self.vpc,
            container_insights=True,  # Enable CloudWatch Container Insights
        )
        
        # Create CloudWatch Log Group with 7-year retention (Requirements 18.5, 18.6)
        log_group = logs.LogGroup(
            self,
            "LegacyExecutorLogGroup",
            log_group_name="/ecs/rosetta-zero-legacy-executor",
            retention=logs.RetentionDays.TEN_YEARS,  # 7+ years for compliance
            encryption_key=self.kms_keys["encryption"],  # Requirement 18.6
            removal_policy=RemovalPolicy.RETAIN,
        )
        
        # Create task execution role (for ECS to pull image and write logs)
        task_execution_role = iam.Role(
            self,
            "LegacyExecutorTaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="Task execution role for legacy executor Fargate tasks",
        )
        
        # Grant ECR pull permissions
        task_execution_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AmazonECSTaskExecutionRolePolicy"
            )
        )
        
        # Grant CloudWatch Logs permissions
        log_group.grant_write(task_execution_role)
        
        # Grant KMS decrypt for CloudWatch Logs
        self.kms_keys["encryption"].grant_decrypt(task_execution_role)
        
        # Create task role (for container to access AWS services)
        task_role = iam.Role(
            self,
            "LegacyExecutorTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="Task role for legacy executor container to access S3",
        )
        
        # Grant S3 read access to legacy-artifacts bucket (Requirement 21.1)
        self.buckets["legacy-artifacts"].grant_read(task_role)
        
        # Grant KMS decrypt for S3 objects
        self.kms_keys["encryption"].grant_decrypt(task_role)
        
        # Create Fargate task definition (Requirement 12.5)
        task_definition = ecs.FargateTaskDefinition(
            self,
            "LegacyExecutorTaskDefinition",
            family="rosetta-zero-legacy-executor",
            cpu=2048,  # Requirement 12.5: 2048 CPU units (2 vCPU)
            memory_limit_mib=4096,  # Requirement 12.5: 4096 MB memory
            execution_role=task_execution_role,
            task_role=task_role,
        )
        
        # Add container to task definition (Requirements 12.1, 12.2, 12.3, 12.4)
        container = task_definition.add_container(
            "LegacyExecutor",
            image=ecs.ContainerImage.from_ecr_repository(
                self.ecr_repository,
                tag="latest"
            ),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="legacy-executor",
                log_group=log_group,
            ),
            environment={
                "CAPTURE_SIDE_EFFECTS": "true",  # Requirements 12.3, 12.4
                "AWS_REGION": self.region,
            },
            # Container will receive test vector via environment variable
        )
        
        return cluster, task_definition

    def _create_verification_lambdas(self) -> dict:
        """Create Lambda functions for Verification Environment.
        
        Requirements: 11.1, 11.2, 11.3, 11.4, 13.1-13.6, 14.1-14.9, 15.1-15.6
        
        Returns:
            Dictionary mapping function names to Lambda Function constructs
        """
        lambdas = {}
        
        # Comparator Lambda (Requirements 13.1-13.6, 16.1, 16.2)
        comparator_role = self._create_comparator_role()
        
        comparator_lambda = lambda_.Function(
            self,
            "ComparatorLambda",
            function_name="rosetta-zero-comparator",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="rosetta_zero.lambdas.verification.handler.comparator_handler",
            code=lambda_.Code.from_asset(".", exclude=["cdk.out", ".git", ".pytest_cache", ".hypothesis"]),
            role=comparator_role,
            timeout=Duration.minutes(5),
            memory_size=1024,
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            environment={
                "TEST_RESULTS_TABLE": self.tables["test_results"].table_name,
                "DISCREPANCY_BUCKET": self.buckets["discrepancy-reports"].bucket_name,
                "KMS_KEY_ID": self.kms_keys["encryption"].key_id,
                "POWERTOOLS_SERVICE_NAME": "comparator",
                "POWERTOOLS_METRICS_NAMESPACE": "RosettaZero",
                "LOG_LEVEL": "INFO",
            },
            log_retention=logs.RetentionDays.TEN_YEARS,
        )
        
        lambdas["comparator"] = comparator_lambda
        
        return lambdas
    
    def _create_comparator_role(self) -> iam.Role:
        """Create IAM role for Comparator Lambda.
        
        Requirements: 21.1, 21.2, 21.3
        
        Grants:
        - DynamoDB read/write access to test-results table
        - S3 write access to discrepancy-reports bucket
        - CloudWatch Logs permissions
        - KMS decrypt/encrypt permissions
        - EventBridge PutEvents permission
        
        Returns:
            IAM Role for Comparator Lambda
        """
        role = iam.Role(
            self,
            "ComparatorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="IAM role for Rosetta Zero Comparator Lambda",
        )
        
        # VPC execution permissions
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaVPCAccessExecutionRole"
            )
        )
        
        # DynamoDB read/write access to test-results table (Requirement 21.2)
        self.tables["test_results"].grant_read_write_data(role)
        
        # S3 write access to discrepancy-reports bucket (Requirement 21.2)
        self.buckets["discrepancy-reports"].grant_write(role)
        
        # CloudWatch Logs permissions (Requirement 21.2)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/rosetta-zero-comparator:*"
                ],
            )
        )
        
        # KMS decrypt/encrypt permissions (Requirement 21.3)
        self.kms_keys["encryption"].grant_encrypt_decrypt(role)
        
        # EventBridge PutEvents permission (Requirement 14.9)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["events:PutEvents"],
                resources=[f"arn:aws:events:{self.region}:{self.account}:event-bus/default"],
            )
        )
        
        return role
    
    def _create_verification_state_machine(self) -> sfn.StateMachine:
        """Create Step Functions state machine for verification orchestration.
        
        Requirements: 11.1, 11.4, 11.7, 18.5, 18.6
        
        Workflow:
        1. Parallel execution: Legacy (Fargate) + Modern (Lambda)
        2. Compare outputs with Comparator Lambda
        3. Check match status
        4. On pass: Store result in DynamoDB (done by comparator)
        5. On fail: Generate discrepancy report and halt pipeline
        
        Returns:
            Step Functions State Machine
        """
        # Define parallel execution branches
        
        # Branch 1: Execute legacy binary in Fargate (Requirement 11.2)
        execute_legacy_task = tasks.EcsRunTask(
            self,
            "ExecuteLegacyBinary",
            cluster=self.fargate_cluster,
            task_definition=self.fargate_task_definition,
            launch_target=tasks.EcsFargateLaunchTarget(
                platform_version=ecs.FargatePlatformVersion.LATEST
            ),
            integration_pattern=sfn.IntegrationPattern.RUN_JOB,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            container_overrides=[
                tasks.ContainerOverride(
                    container_definition=self.fargate_task_definition.default_container,
                    environment=[
                        tasks.TaskEnvironmentVariable(
                            name="TEST_VECTOR",
                            value=sfn.JsonPath.string_at("$.test_vector")
                        )
                    ]
                )
            ],
            result_path="$.legacy_result",
        )
        
        # Branch 2: Execute modern Lambda (Requirement 11.3)
        # Note: This would invoke the actual modern implementation Lambda
        # For now, we use a placeholder
        execute_modern_task = tasks.LambdaInvoke(
            self,
            "ExecuteModernLambda",
            lambda_function=self.verification_lambdas["comparator"],  # Placeholder
            payload=sfn.TaskInput.from_object({
                "test_vector": sfn.JsonPath.string_at("$.test_vector"),
                "action": "execute_modern"
            }),
            result_path="$.modern_result",
        )
        
        # Parallel execution (Requirement 11.4)
        parallel_execution = sfn.Parallel(
            self,
            "ParallelExecution",
            result_path="$.execution_results"
        )
        parallel_execution.branch(execute_legacy_task)
        parallel_execution.branch(execute_modern_task)
        
        # Compare outputs (Requirement 11.7)
        compare_outputs_task = tasks.LambdaInvoke(
            self,
            "CompareOutputs",
            lambda_function=self.verification_lambdas["comparator"],
            payload=sfn.TaskInput.from_object({
                "test_vector": sfn.JsonPath.string_at("$.test_vector"),
                "legacy_result": sfn.JsonPath.string_at("$.execution_results[0]"),
                "modern_result": sfn.JsonPath.string_at("$.execution_results[1]")
            }),
            result_path="$.comparison_result",
        )
        
        # Check match status (Requirement 11.7)
        check_match = sfn.Choice(self, "CheckMatch")
        
        # On pass: Success state
        test_passed = sfn.Succeed(
            self,
            "TestPassed",
            comment="Test passed - outputs match"
        )
        
        # On fail: Halt pipeline
        test_failed = sfn.Fail(
            self,
            "TestFailed",
            cause="Behavioral discrepancy detected",
            error="BehavioralDiscrepancy"
        )
        
        # Define workflow
        definition = parallel_execution \
            .next(compare_outputs_task) \
            .next(
                check_match
                .when(
                    sfn.Condition.boolean_equals("$.comparison_result.Payload.match", True),
                    test_passed
                )
                .otherwise(test_failed)
            )
        
        # Create CloudWatch Log Group for state machine (Requirements 18.5, 18.6)
        log_group = logs.LogGroup(
            self,
            "VerificationStateMachineLogGroup",
            log_group_name="/aws/stepfunctions/rosetta-zero-verification",
            retention=logs.RetentionDays.TEN_YEARS,  # 7+ years for compliance
            encryption_key=self.kms_keys["encryption"],
            removal_policy=RemovalPolicy.RETAIN,
        )
        
        # Create state machine
        state_machine = sfn.StateMachine(
            self,
            "VerificationStateMachine",
            state_machine_name="rosetta-zero-verification",
            definition=definition,
            logs=sfn.LogOptions(
                destination=log_group,
                level=sfn.LogLevel.ALL,
                include_execution_data=True
            ),
            tracing_enabled=True,
        )
        
        # Grant state machine permissions to invoke Lambda and run ECS tasks
        self.verification_lambdas["comparator"].grant_invoke(state_machine)
        
        state_machine.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecs:RunTask",
                    "ecs:StopTask",
                    "ecs:DescribeTasks"
                ],
                resources=[
                    self.fargate_task_definition.task_definition_arn,
                    f"arn:aws:ecs:{self.region}:{self.account}:task/{self.fargate_cluster.cluster_name}/*"
                ]
            )
        )
        
        state_machine.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["iam:PassRole"],
                resources=[
                    self.fargate_task_definition.task_role.role_arn,
                    self.fargate_task_definition.execution_role.role_arn
                ]
            )
        )
        
        return state_machine

    def _create_certificate_generator_lambda(self) -> lambda_.Function:
        """Create Certificate Generator Lambda for Trust Phase.
        
        Requirements: 17.1-17.9, 21.1, 21.2, 21.3
        
        Creates Lambda function that:
        - Queries all test results from DynamoDB
        - Verifies all tests passed
        - Generates equivalence certificate
        - Signs certificate with KMS asymmetric key
        - Stores signed certificate in S3
        - Publishes completion event to EventBridge
        - Sends SNS notification to operators
        
        Returns:
            Lambda Function for Certificate Generator
        """
        # Create IAM role for Certificate Generator
        cert_gen_role = self._create_certificate_generator_role()
        
        # Create Lambda function
        certificate_generator = lambda_.Function(
            self,
            "CertificateGeneratorLambda",
            function_name="rosetta-zero-certificate-generator",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="rosetta_zero.lambdas.certificate_generator.handler.lambda_handler",
            code=lambda_.Code.from_asset(".", exclude=["cdk.out", ".git", ".pytest_cache", ".hypothesis"]),
            role=cert_gen_role,
            timeout=Duration.minutes(15),  # Requirement: 15 min timeout for certificate generation
            memory_size=3008,  # Requirement: 3008 MB memory
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            environment={
                "TEST_RESULTS_TABLE": self.tables["test_results"].table_name,
                "CERTIFICATES_BUCKET": self.buckets["certificates"].bucket_name,
                "KMS_SIGNING_KEY_ID": self.kms_keys["signing"].key_id,
                "EVENT_BUS_NAME": "default",
                "SNS_TOPIC_ARN": f"arn:aws:sns:{self.region}:{self.account}:rosetta-zero-operator-alerts",
                "POWERTOOLS_SERVICE_NAME": "certificate-generator",
                "POWERTOOLS_METRICS_NAMESPACE": "RosettaZero",
                "LOG_LEVEL": "INFO",
            },
            log_retention=logs.RetentionDays.TEN_YEARS,  # 7+ years for compliance
        )
        
        return certificate_generator
    
    def _create_certificate_generator_role(self) -> iam.Role:
        """Create IAM role for Certificate Generator Lambda.
        
        Requirements: 21.1, 21.2, 21.3
        
        Grants:
        - DynamoDB read access to test-results table
        - S3 write access to certificates bucket
        - KMS Sign and Verify permissions for signing key
        - EventBridge PutEvents permission
        - SNS Publish permission
        - CloudWatch Logs permissions
        
        Returns:
            IAM Role for Certificate Generator Lambda
        """
        role = iam.Role(
            self,
            "CertificateGeneratorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="IAM role for Rosetta Zero Certificate Generator Lambda",
        )
        
        # VPC execution permissions
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaVPCAccessExecutionRole"
            )
        )
        
        # DynamoDB read access to test-results table (Requirement 21.1)
        self.tables["test_results"].grant_read_data(role)
        
        # S3 write access to certificates bucket (Requirement 21.2)
        self.buckets["certificates"].grant_write(role)
        
        # KMS Sign and Verify permissions for signing key (Requirement 21.3, 17.7)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "kms:Sign",
                    "kms:Verify",
                    "kms:DescribeKey",
                    "kms:GetPublicKey"
                ],
                resources=[self.kms_keys["signing"].key_arn],
            )
        )
        
        # KMS decrypt/encrypt for S3 and DynamoDB (Requirement 21.3)
        self.kms_keys["encryption"].grant_encrypt_decrypt(role)
        
        # EventBridge PutEvents permission (Requirement 17.9)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["events:PutEvents"],
                resources=[f"arn:aws:events:{self.region}:{self.account}:event-bus/default"],
            )
        )
        
        # SNS Publish permission for operator notifications (Requirement 17.9, 19.3)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["sns:Publish"],
                resources=[f"arn:aws:sns:{self.region}:{self.account}:rosetta-zero-operator-alerts"],
            )
        )
        
        # CloudWatch Logs permissions (Requirement 21.2)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/rosetta-zero-certificate-generator:*"
                ],
            )
        )
        
        return role
    
    def _create_compliance_reporter_lambda(self) -> lambda_.Function:
        """Create Compliance Reporter Lambda for regulatory reporting.
        
        Requirements: 30.1, 30.2, 30.3, 30.4, 30.5, 30.6, 21.1, 21.2, 21.3
        
        Creates Lambda function that:
        - Queries all test results from DynamoDB
        - Retrieves equivalence certificate from S3
        - Retrieves all discrepancy reports from S3
        - Collects audit log references from CloudWatch
        - Generates comprehensive compliance report
        - Signs compliance report with KMS
        - Stores signed report in S3 (JSON and HTML formats)
        
        Returns:
            Lambda Function for Compliance Reporter
        """
        # Create IAM role for Compliance Reporter
        compliance_role = self._create_compliance_reporter_role()
        
        # Create Lambda function
        compliance_reporter = lambda_.Function(
            self,
            "ComplianceReporterLambda",
            function_name="rosetta-zero-compliance-reporter",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="rosetta_zero.lambdas.compliance_reporter.handler.handler",
            code=lambda_.Code.from_asset(".", exclude=["cdk.out", ".git", ".pytest_cache", ".hypothesis"]),
            role=compliance_role,
            timeout=Duration.minutes(15),  # Requirement: 15 min timeout for report generation
            memory_size=3008,  # Requirement: 3008 MB memory
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            environment={
                "TEST_RESULTS_TABLE": self.tables["test_results"].table_name,
                "CERTIFICATES_BUCKET": self.buckets["certificates"].bucket_name,
                "DISCREPANCY_REPORTS_BUCKET": self.buckets["discrepancy-reports"].bucket_name,
                "COMPLIANCE_REPORTS_BUCKET": self.buckets["compliance-reports"].bucket_name,
                "KMS_SIGNING_KEY_ID": self.kms_keys["signing"].key_id,
                "POWERTOOLS_SERVICE_NAME": "compliance-reporter",
                "POWERTOOLS_METRICS_NAMESPACE": "RosettaZero",
                "LOG_LEVEL": "INFO",
            },
            log_retention=logs.RetentionDays.TEN_YEARS,  # 7+ years for compliance
        )
        
        return compliance_reporter
    
    def _create_compliance_reporter_role(self) -> iam.Role:
        """Create IAM role for Compliance Reporter Lambda.
        
        Requirements: 21.1, 21.2, 21.3
        
        Grants:
        - DynamoDB read access to test-results table
        - S3 read access to certificates and discrepancy-reports buckets
        - S3 write access to compliance-reports bucket
        - CloudWatch Logs read access for audit log references
        - KMS Sign permission for report signing
        - CloudWatch Logs permissions
        
        Returns:
            IAM Role for Compliance Reporter Lambda
        """
        role = iam.Role(
            self,
            "ComplianceReporterRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="IAM role for Rosetta Zero Compliance Reporter Lambda",
        )
        
        # VPC execution permissions
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaVPCAccessExecutionRole"
            )
        )
        
        # DynamoDB read access to test-results table (Requirement 21.1, 30.1)
        self.tables["test_results"].grant_read_data(role)
        
        # S3 read access to certificates bucket (Requirement 21.1, 30.3)
        self.buckets["certificates"].grant_read(role)
        
        # S3 read access to discrepancy-reports bucket (Requirement 21.1, 30.4)
        self.buckets["discrepancy-reports"].grant_read(role)
        
        # S3 write access to compliance-reports bucket (Requirement 21.2, 30.5)
        self.buckets["compliance-reports"].grant_write(role)
        
        # KMS Sign permission for report signing (Requirement 21.3, 30.6)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "kms:Sign",
                    "kms:DescribeKey",
                    "kms:GetPublicKey"
                ],
                resources=[self.kms_keys["signing"].key_arn],
            )
        )
        
        # KMS decrypt/encrypt for S3 and DynamoDB (Requirement 21.3)
        self.kms_keys["encryption"].grant_encrypt_decrypt(role)
        
        # CloudWatch Logs read access for audit log references (Requirement 30.2)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams",
                    "logs:GetLogEvents",
                    "logs:FilterLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/rosetta-zero-*:*"
                ],
            )
        )
        
        # CloudWatch Logs permissions for this Lambda (Requirement 21.2)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/rosetta-zero-compliance-reporter:*"
                ],
            )
        )
        
        return role
    
    def _create_resource_cleanup_lambda(self) -> lambda_.Function:
        """Create Resource Cleanup Lambda function.
        
        Requirements: 26.1, 26.2, 26.3, 26.4
        
        Handles:
        - Terminating temporary Fargate tasks after test execution
        - Deleting temporary S3 objects older than 30 days
        - Tagging AWS resources with workflow identifiers
        - Publishing resource usage metrics to CloudWatch
        
        Returns:
            Lambda Function construct for resource cleanup
        """
        # Create IAM role for resource cleanup Lambda
        cleanup_role = self._create_resource_cleanup_role()
        
        # Create Lambda function
        cleanup_lambda = lambda_.Function(
            self,
            "ResourceCleanupLambda",
            function_name="rosetta-zero-resource-cleanup",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="rosetta_zero.lambdas.resource_cleanup.handler.cleanup_handler",
            code=lambda_.Code.from_asset("rosetta_zero"),
            role=cleanup_role,
            timeout=Duration.minutes(15),
            memory_size=1024,
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            environment={
                "ECS_CLUSTER_NAME": "rosetta-zero-legacy-cluster",
                "TEMP_BUCKETS": ",".join([
                    self.buckets["test-vectors"].bucket_name,
                    self.buckets["discrepancy-reports"].bucket_name
                ]),
                "LOG_LEVEL": "INFO",
                "POWERTOOLS_SERVICE_NAME": "resource-cleanup",
                "POWERTOOLS_METRICS_NAMESPACE": "RosettaZero"
            },
            log_retention=logs.RetentionDays.SEVEN_YEARS,
        )
        
        # Grant permissions to cleanup Lambda
        # ECS permissions for task termination
        cleanup_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecs:StopTask",
                    "ecs:DescribeTasks",
                    "ecs:ListTasks",
                    "ecs:TagResource"
                ],
                resources=["*"]  # ECS tasks don't have predictable ARNs
            )
        )
        
        # S3 permissions for cleanup
        for bucket in self.buckets.values():
            bucket.grant_read_write(cleanup_lambda)
        
        # CloudWatch permissions for metrics
        cleanup_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cloudwatch:PutMetricData"
                ],
                resources=["*"]
            )
        )
        
        # Resource tagging permissions
        cleanup_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "tag:TagResources",
                    "tag:UntagResources",
                    "tag:GetResources"
                ],
                resources=["*"]
            )
        )
        
        return cleanup_lambda
    
    def _create_resource_cleanup_role(self) -> iam.Role:
        """Create IAM role for Resource Cleanup Lambda.
        
        Requirements: 21.1, 21.2, 21.3
        
        Returns:
            IAM Role for resource cleanup Lambda
        """
        role = iam.Role(
            self,
            "ResourceCleanupLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for Rosetta Zero Resource Cleanup Lambda",
        )
        
        # Basic Lambda execution permissions
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaVPCAccessExecutionRole"
            )
        )
        
        # CloudWatch Logs permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/rosetta-zero-resource-cleanup:*"
                ],
            )
        )
        
        # KMS permissions for encryption
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "kms:Decrypt",
                    "kms:Encrypt",
                    "kms:GenerateDataKey"
                ],
                resources=[
                    self.kms_keys["encryption"].key_arn
                ],
            )
        )
        
        return role

    def _create_sns_topics(self) -> dict:
        """Create SNS topics for operator notifications.
        
        Requirements: 19.3, 19.4
        
        Creates:
        - Operator alerts topic for AWS 500-level errors and critical events
        - KMS encryption for topic
        - Email subscription placeholder (to be configured manually)
        
        Returns:
            Dictionary mapping topic names to SNS Topic constructs
        """
        # Create SNS topic for operator alerts (Requirements 19.3, 19.4)
        operator_alerts_topic = sns.Topic(
            self,
            "OperatorAlertsTopic",
            topic_name="rosetta-zero-operator-alerts",
            display_name="Rosetta Zero Operator Alerts",
            master_key=self.kms_keys["encryption"],  # KMS encryption
        )
        
        # Note: Email subscriptions should be added manually or via configuration
        # Example: operator_alerts_topic.add_subscription(
        #     subscriptions.EmailSubscription("operator@example.com")
        # )
        
        return {
            "operator_alerts": operator_alerts_topic
        }
    
    def _create_eventbridge_rules(self) -> dict:
        """Create EventBridge rules for monitoring and notifications.
        
        Requirements: 17.9, 19.3, 24.6, 25.5
        
        Creates rules for:
        - Certificate generation events
        - AWS 500-level error events
        - Behavioral discrepancy events
        - Workflow phase completion events
        
        Returns:
            Dictionary mapping rule names to EventBridge Rule constructs
        """
        rules = {}
        
        # Rule for certificate generation events (Requirement 17.9)
        certificate_rule = events.Rule(
            self,
            "CertificateGenerationRule",
            rule_name="rosetta-zero-certificate-generated",
            description="Trigger on equivalence certificate generation",
            event_pattern=events.EventPattern(
                source=["rosetta-zero.certificate-generator"],
                detail_type=["Certificate Generated"]
            )
        )
        
        # Add SNS target for operator notification
        certificate_rule.add_target(
            targets.SnsTopic(
                self.sns_topics["operator_alerts"],
                message=events.RuleTargetInput.from_text(
                    "Equivalence Certificate Generated\n\n"
                    "Certificate ID: $.detail.certificate_id\n"
                    "S3 Location: $.detail.s3_location\n"
                    "Total Tests: $.detail.total_tests\n"
                    "Coverage: $.detail.coverage_percent%"
                )
            )
        )
        
        rules["certificate_generation"] = certificate_rule
        
        # Rule for AWS 500-level error events (Requirement 19.3)
        error_500_rule = events.Rule(
            self,
            "AWS500ErrorRule",
            rule_name="rosetta-zero-aws-500-error",
            description="Trigger on AWS 500-level errors requiring operator intervention",
            event_pattern=events.EventPattern(
                source=events.Match.prefix("rosetta-zero."),
                detail_type=["AWS 500-Level Error"]
            )
        )
        
        # Add SNS target for critical operator alert
        error_500_rule.add_target(
            targets.SnsTopic(
                self.sns_topics["operator_alerts"],
                message=events.RuleTargetInput.from_text(
                    "[CRITICAL] AWS 500-Level Error - Operator Intervention Required\n\n"
                    "Service: $.detail.service\n"
                    "Error Code: $.detail.error_code\n"
                    "Error Message: $.detail.error_message\n"
                    "Timestamp: $.detail.timestamp\n\n"
                    "Action Required: System execution has been paused. "
                    "Please investigate and resolve the issue."
                )
            )
        )
        
        rules["aws_500_error"] = error_500_rule
        
        # Rule for behavioral discrepancy events (Requirement 24.6)
        discrepancy_rule = events.Rule(
            self,
            "BehavioralDiscrepancyRule",
            rule_name="rosetta-zero-behavioral-discrepancy",
            description="Trigger on behavioral discrepancy detection",
            event_pattern=events.EventPattern(
                source=["rosetta-zero.verification-environment"],
                detail_type=["Behavioral Discrepancy Detected"]
            )
        )
        
        # Add SNS target for operator notification
        discrepancy_rule.add_target(
            targets.SnsTopic(
                self.sns_topics["operator_alerts"],
                message=events.RuleTargetInput.from_text(
                    "[HIGH] Behavioral Discrepancy Detected\n\n"
                    "Test Vector ID: $.detail.test_vector_id\n"
                    "Discrepancy Report ID: $.detail.discrepancy_report_id\n"
                    "S3 Location: $.detail.s3_location\n"
                    "Timestamp: $.detail.timestamp\n\n"
                    "Action Required: Review discrepancy report and investigate "
                    "differences between legacy and modern implementations."
                )
            )
        )
        
        rules["behavioral_discrepancy"] = discrepancy_rule
        
        # Rule for workflow phase completion events (Requirement 24.6, 25.5)
        phase_completion_rule = events.Rule(
            self,
            "WorkflowPhaseCompletionRule",
            rule_name="rosetta-zero-phase-completion",
            description="Trigger on workflow phase completion",
            event_pattern=events.EventPattern(
                source=["rosetta-zero.workflow"],
                detail_type=["Workflow Phase Completed"]
            )
        )
        
        # Add orchestrator Lambda as target to trigger next phase (Requirement 19.1)
        phase_completion_rule.add_target(
            targets.LambdaFunction(self.lambdas["orchestrator"])
        )
        
        # Add resource cleanup Lambda as target (Requirements 26.1, 26.2, 26.3, 26.4)
        phase_completion_rule.add_target(
            targets.LambdaFunction(self.cleanup_lambda)
        )
        
        # Add SNS target for operator notification (optional, can be filtered)
        phase_completion_rule.add_target(
            targets.SnsTopic(
                self.sns_topics["operator_alerts"],
                message=events.RuleTargetInput.from_text(
                    "Workflow Phase Completed\n\n"
                    "Workflow ID: $.detail.workflow_id\n"
                    "Phase: $.detail.phase_name\n"
                    "Status: $.detail.status\n"
                    "Timestamp: $.detail.timestamp"
                )
            )
        )
        
        rules["phase_completion"] = phase_completion_rule
        
        # Rule for scheduled cleanup of temporary S3 objects (Requirement 26.2)
        scheduled_cleanup_rule = events.Rule(
            self,
            "ScheduledCleanupRule",
            rule_name="rosetta-zero-scheduled-cleanup",
            description="Daily cleanup of temporary S3 objects older than 30 days",
            schedule=events.Schedule.cron(
                minute="0",
                hour="2",  # Run at 2 AM UTC daily
                month="*",
                week_day="*",
                year="*"
            )
        )
        
        # Add cleanup Lambda as target
        scheduled_cleanup_rule.add_target(
            targets.LambdaFunction(self.cleanup_lambda)
        )
        
        rules["scheduled_cleanup"] = scheduled_cleanup_rule
        
        # Add S3 event notification to trigger orchestrator on artifact upload (Requirement 19.1)
        self.buckets["legacy-artifacts"].add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(self.lambdas["orchestrator"])
        )
        
        return rules
    
    def _create_cloudwatch_dashboards(self) -> dict:
        """Create CloudWatch dashboards for monitoring.
        
        Requirement: 29.5
        
        Creates dashboards for:
        - Test execution rate
        - Test pass rate
        - Lambda performance metrics
        - Fargate resource utilization
        - Error rates by component
        
        Returns:
            Dictionary mapping dashboard names to CloudWatch Dashboard constructs
        """
        dashboards = {}
        
        # Main Rosetta Zero Dashboard
        main_dashboard = cloudwatch.Dashboard(
            self,
            "RosettaZeroMainDashboard",
            dashboard_name="RosettaZero-Main",
        )
        
        # Test Execution Rate Widget
        test_execution_widget = cloudwatch.GraphWidget(
            title="Test Execution Rate",
            left=[
                cloudwatch.Metric(
                    namespace="RosettaZero",
                    metric_name="TestThroughput",
                    dimensions_map={"Component": "verification-environment"},
                    statistic="Average",
                    period=Duration.minutes(5)
                )
            ],
            width=12,
            height=6
        )
        
        # Test Pass Rate Widget
        test_pass_rate_widget = cloudwatch.GraphWidget(
            title="Test Pass Rate",
            left=[
                cloudwatch.MathExpression(
                    expression="(pass / (pass + fail)) * 100",
                    using_metrics={
                        "pass": cloudwatch.Metric(
                            namespace="RosettaZero",
                            metric_name="TestResult",
                            dimensions_map={"Status": "PASS"},
                            statistic="Sum",
                            period=Duration.minutes(5)
                        ),
                        "fail": cloudwatch.Metric(
                            namespace="RosettaZero",
                            metric_name="TestResult",
                            dimensions_map={"Status": "FAIL"},
                            statistic="Sum",
                            period=Duration.minutes(5)
                        )
                    },
                    label="Pass Rate (%)"
                )
            ],
            width=12,
            height=6
        )
        
        # Lambda Performance Metrics Widget
        lambda_performance_widget = cloudwatch.GraphWidget(
            title="Lambda Performance Metrics",
            left=[
                cloudwatch.Metric(
                    namespace="AWS/Lambda",
                    metric_name="Duration",
                    dimensions_map={"FunctionName": "rosetta-zero-ingestion-engine"},
                    statistic="Average",
                    period=Duration.minutes(5),
                    label="Ingestion Engine"
                ),
                cloudwatch.Metric(
                    namespace="AWS/Lambda",
                    metric_name="Duration",
                    dimensions_map={"FunctionName": "rosetta-zero-bedrock-architect"},
                    statistic="Average",
                    period=Duration.minutes(5),
                    label="Bedrock Architect"
                ),
                cloudwatch.Metric(
                    namespace="AWS/Lambda",
                    metric_name="Duration",
                    dimensions_map={"FunctionName": "rosetta-zero-hostile-auditor"},
                    statistic="Average",
                    period=Duration.minutes(5),
                    label="Hostile Auditor"
                ),
                cloudwatch.Metric(
                    namespace="AWS/Lambda",
                    metric_name="Duration",
                    dimensions_map={"FunctionName": "rosetta-zero-comparator"},
                    statistic="Average",
                    period=Duration.minutes(5),
                    label="Comparator"
                ),
                cloudwatch.Metric(
                    namespace="AWS/Lambda",
                    metric_name="Duration",
                    dimensions_map={"FunctionName": "rosetta-zero-certificate-generator"},
                    statistic="Average",
                    period=Duration.minutes(5),
                    label="Certificate Generator"
                )
            ],
            width=12,
            height=6
        )
        
        # Fargate Resource Utilization Widget
        fargate_utilization_widget = cloudwatch.GraphWidget(
            title="Fargate Resource Utilization",
            left=[
                cloudwatch.Metric(
                    namespace="AWS/ECS",
                    metric_name="CPUUtilization",
                    dimensions_map={
                        "ServiceName": "legacy-executor",
                        "ClusterName": "rosetta-zero-legacy-cluster"
                    },
                    statistic="Average",
                    period=Duration.minutes(5),
                    label="CPU Utilization"
                )
            ],
            right=[
                cloudwatch.Metric(
                    namespace="AWS/ECS",
                    metric_name="MemoryUtilization",
                    dimensions_map={
                        "ServiceName": "legacy-executor",
                        "ClusterName": "rosetta-zero-legacy-cluster"
                    },
                    statistic="Average",
                    period=Duration.minutes(5),
                    label="Memory Utilization"
                )
            ],
            width=12,
            height=6
        )
        
        # Error Rates by Component Widget
        error_rates_widget = cloudwatch.GraphWidget(
            title="Error Rates by Component",
            left=[
                cloudwatch.Metric(
                    namespace="AWS/Lambda",
                    metric_name="Errors",
                    dimensions_map={"FunctionName": "rosetta-zero-ingestion-engine"},
                    statistic="Sum",
                    period=Duration.minutes(5),
                    label="Ingestion Engine"
                ),
                cloudwatch.Metric(
                    namespace="AWS/Lambda",
                    metric_name="Errors",
                    dimensions_map={"FunctionName": "rosetta-zero-bedrock-architect"},
                    statistic="Sum",
                    period=Duration.minutes(5),
                    label="Bedrock Architect"
                ),
                cloudwatch.Metric(
                    namespace="AWS/Lambda",
                    metric_name="Errors",
                    dimensions_map={"FunctionName": "rosetta-zero-hostile-auditor"},
                    statistic="Sum",
                    period=Duration.minutes(5),
                    label="Hostile Auditor"
                ),
                cloudwatch.Metric(
                    namespace="AWS/Lambda",
                    metric_name="Errors",
                    dimensions_map={"FunctionName": "rosetta-zero-comparator"},
                    statistic="Sum",
                    period=Duration.minutes(5),
                    label="Comparator"
                ),
                cloudwatch.Metric(
                    namespace="AWS/Lambda",
                    metric_name="Errors",
                    dimensions_map={"FunctionName": "rosetta-zero-certificate-generator"},
                    statistic="Sum",
                    period=Duration.minutes(5),
                    label="Certificate Generator"
                )
            ],
            width=12,
            height=6
        )
        
        # API Latency Widget
        api_latency_widget = cloudwatch.GraphWidget(
            title="AWS Service API Latency",
            left=[
                cloudwatch.Metric(
                    namespace="RosettaZero",
                    metric_name="APILatency",
                    dimensions_map={"Service": "bedrock"},
                    statistic="Average",
                    period=Duration.minutes(5),
                    label="Bedrock"
                ),
                cloudwatch.Metric(
                    namespace="RosettaZero",
                    metric_name="APILatency",
                    dimensions_map={"Service": "s3"},
                    statistic="Average",
                    period=Duration.minutes(5),
                    label="S3"
                ),
                cloudwatch.Metric(
                    namespace="RosettaZero",
                    metric_name="APILatency",
                    dimensions_map={"Service": "dynamodb"},
                    statistic="Average",
                    period=Duration.minutes(5),
                    label="DynamoDB"
                )
            ],
            width=12,
            height=6
        )
        
        # Add widgets to dashboard
        main_dashboard.add_widgets(
            test_execution_widget,
            test_pass_rate_widget
        )
        main_dashboard.add_widgets(
            lambda_performance_widget,
            fargate_utilization_widget
        )
        main_dashboard.add_widgets(
            error_rates_widget,
            api_latency_widget
        )
        
        dashboards["main"] = main_dashboard
        
        return dashboards
