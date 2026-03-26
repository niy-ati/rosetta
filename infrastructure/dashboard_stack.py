"""
CDK Stack for Rosetta Zero Web Dashboard.

Deploys:
- AWS Cognito User Pool for authentication
- API Gateway REST API
- Lambda functions for API endpoints
- S3 bucket for frontend hosting
- CloudFront distribution
"""

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_cognito as cognito,
    aws_apigateway as apigw,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    CfnOutput,
)
from constructs import Construct


class DashboardStack(Stack):
    """Stack for Rosetta Zero Web Dashboard."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Cognito User Pool for authentication
        user_pool = cognito.UserPool(
            self, "UserPool",
            user_pool_name=f"{construct_id}-users",
            self_sign_up_enabled=False,  # Admin creates users
            sign_in_aliases=cognito.SignInAliases(email=True, username=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.DESTROY,  # For dev only
        )

        # User Pool Client
        user_pool_client = user_pool.add_client(
            "UserPoolClient",
            user_pool_client_name=f"{construct_id}-client",
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
            ),
            generate_secret=False,
            access_token_validity=Duration.hours(8),
            id_token_validity=Duration.hours(8),
            refresh_token_validity=Duration.days(30),
        )

        # Dashboard API Lambda
        dashboard_api_lambda = lambda_.Function(
            self, "DashboardAPI",
            function_name=f"{construct_id}-dashboard-api",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("rosetta_zero/lambdas/dashboard_api"),
            timeout=Duration.seconds(30),
            memory_size=512,
            environment={
                "STACK_NAME": construct_id,
                "POWERTOOLS_SERVICE_NAME": "dashboard-api",
                "LOG_LEVEL": "INFO",
            },
        )

        # Grant permissions to Dashboard API Lambda
        dashboard_api_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:ListBucket",
                    "s3:PutObject",
                ],
                resources=[
                    f"arn:aws:s3:::{construct_id}-*",
                    f"arn:aws:s3:::{construct_id}-*/*",
                ],
            )
        )

        dashboard_api_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                    "dynamodb:PutItem",
                ],
                resources=[
                    f"arn:aws:dynamodb:{self.region}:{self.account}:table/{construct_id}-*",
                ],
            )
        )

        dashboard_api_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "cloudwatch:GetMetricStatistics",
                    "cloudwatch:ListMetrics",
                ],
                resources=["*"],
            )
        )

        # API Gateway
        api = apigw.RestApi(
            self, "DashboardAPI",
            rest_api_name=f"{construct_id}-api",
            description="REST API for Rosetta Zero Dashboard",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"],
            ),
        )

        # Cognito Authorizer
        authorizer = apigw.CognitoUserPoolsAuthorizer(
            self, "CognitoAuthorizer",
            cognito_user_pools=[user_pool],
        )

        # Lambda Integration
        lambda_integration = apigw.LambdaIntegration(dashboard_api_lambda)

        # API Routes
        # Dashboard
        dashboard = api.root.add_resource("dashboard")
        dashboard_stats = dashboard.add_resource("stats")
        dashboard_stats.add_method("GET", lambda_integration, authorizer=authorizer)

        # Artifacts
        artifacts = api.root.add_resource("artifacts")
        artifacts.add_method("GET", lambda_integration, authorizer=authorizer)
        artifacts.add_method("POST", lambda_integration, authorizer=authorizer)
        
        artifact_upload = artifacts.add_resource("upload")
        artifact_upload.add_method("POST", lambda_integration, authorizer=authorizer)
        
        artifact_id = artifacts.add_resource("{id}")
        artifact_id.add_method("GET", lambda_integration, authorizer=authorizer)
        
        artifact_download = artifact_id.add_resource("download")
        artifact_download.add_method("GET", lambda_integration, authorizer=authorizer)

        # Workflows
        workflows = api.root.add_resource("workflows")
        workflows.add_method("GET", lambda_integration, authorizer=authorizer)
        
        workflow_id = workflows.add_resource("{id}")
        workflow_id.add_method("GET", lambda_integration, authorizer=authorizer)

        # System
        system = api.root.add_resource("system")
        system_health = system.add_resource("health")
        system_health.add_method("GET", lambda_integration, authorizer=authorizer)

        # S3 Bucket for Frontend
        frontend_bucket = s3.Bucket(
            self, "FrontendBucket",
            bucket_name=f"{construct_id}-frontend",
            website_index_document="index.html",
            website_error_document="index.html",
            public_read_access=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # CloudFront Origin Access Identity
        oai = cloudfront.OriginAccessIdentity(
            self, "OAI",
            comment=f"OAI for {construct_id} frontend",
        )

        frontend_bucket.grant_read(oai)

        # CloudFront Distribution
        distribution = cloudfront.Distribution(
            self, "Distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(
                    frontend_bucket,
                    origin_access_identity=oai,
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
                cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
            ],
        )

        # Outputs
        CfnOutput(
            self, "UserPoolId",
            value=user_pool.user_pool_id,
            description="Cognito User Pool ID",
        )

        CfnOutput(
            self, "UserPoolClientId",
            value=user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client ID",
        )

        CfnOutput(
            self, "ApiUrl",
            value=api.url,
            description="API Gateway URL",
        )

        CfnOutput(
            self, "DistributionUrl",
            value=f"https://{distribution.distribution_domain_name}",
            description="CloudFront Distribution URL",
        )

        CfnOutput(
            self, "FrontendBucket",
            value=frontend_bucket.bucket_name,
            description="Frontend S3 Bucket Name",
        )
