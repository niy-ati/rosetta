# Rosetta Zero - Deployment Quick Reference

Quick reference for common deployment commands.

**Requirements:** 23.1, 23.2

## Environment Variables

```bash
export REGION=us-east-1
export ACCOUNT=123456789012
```

## Bootstrap (First Time Only)

```bash
# Using Python script
python3 scripts/deploy.py bootstrap --region $REGION --account $ACCOUNT

# Using Makefile
make bootstrap REGION=$REGION ACCOUNT=$ACCOUNT
```

## Development Environment

```bash
# Synthesize
python3 scripts/deploy.py synth --env dev --region $REGION --account $ACCOUNT
make synth-dev REGION=$REGION ACCOUNT=$ACCOUNT

# Deploy
python3 scripts/deploy.py deploy --env dev --region $REGION --account $ACCOUNT
make deploy-dev REGION=$REGION ACCOUNT=$ACCOUNT

# Diff
python3 scripts/deploy.py diff --env dev --region $REGION --account $ACCOUNT
make diff-dev REGION=$REGION ACCOUNT=$ACCOUNT

# Destroy
python3 scripts/deploy.py destroy --env dev --region $REGION --account $ACCOUNT
make destroy-dev REGION=$REGION ACCOUNT=$ACCOUNT
```

## Staging Environment

```bash
# Synthesize
python3 scripts/deploy.py synth --env staging --region $REGION --account $ACCOUNT
make synth-staging REGION=$REGION ACCOUNT=$ACCOUNT

# Deploy
python3 scripts/deploy.py deploy --env staging --region $REGION --account $ACCOUNT
make deploy-staging REGION=$REGION ACCOUNT=$ACCOUNT

# Diff
python3 scripts/deploy.py diff --env staging --region $REGION --account $ACCOUNT
make diff-staging REGION=$REGION ACCOUNT=$ACCOUNT

# Destroy
python3 scripts/deploy.py destroy --env staging --region $REGION --account $ACCOUNT
make destroy-staging REGION=$REGION ACCOUNT=$ACCOUNT
```

## Production Environment

```bash
# Synthesize
python3 scripts/deploy.py synth --env prod --region $REGION --account $ACCOUNT
make synth-prod REGION=$REGION ACCOUNT=$ACCOUNT

# Deploy
python3 scripts/deploy.py deploy --env prod --region $REGION --account $ACCOUNT
make deploy-prod REGION=$REGION ACCOUNT=$ACCOUNT

# Diff
python3 scripts/deploy.py diff --env prod --region $REGION --account $ACCOUNT
make diff-prod REGION=$REGION ACCOUNT=$ACCOUNT

# Destroy (requires confirmation)
python3 scripts/deploy.py destroy --env prod --region $REGION --account $ACCOUNT
make destroy-prod REGION=$REGION ACCOUNT=$ACCOUNT
```

## Specific Stack Operations

```bash
# Deploy only main stack
python3 scripts/deploy.py deploy --env dev --region $REGION --account $ACCOUNT --stack RosettaZeroStack-dev
make deploy-dev REGION=$REGION ACCOUNT=$ACCOUNT STACK=RosettaZeroStack-dev

# Deploy only replica bucket
python3 scripts/deploy.py deploy --env dev --region $REGION --account $ACCOUNT --stack CertificatesReplicaBucketStack-dev
make deploy-dev REGION=$REGION ACCOUNT=$ACCOUNT STACK=CertificatesReplicaBucketStack-dev
```

## Advanced Options

```bash
# Hotswap deployment (dev only, faster iteration)
python3 scripts/deploy.py deploy --env dev --region $REGION --account $ACCOUNT --hotswap

# Skip approval prompts (for CI/CD)
python3 scripts/deploy.py deploy --env dev --region $REGION --account $ACCOUNT --no-approval

# Force destroy (skip confirmation)
python3 scripts/deploy.py destroy --env dev --region $REGION --account $ACCOUNT --force
```

## Utilities

```bash
# List all stacks
cdk list

# Clean CDK output
make clean
rm -rf cdk.out

# View stack outputs
aws cloudformation describe-stacks --stack-name RosettaZeroStack-dev --query 'Stacks[0].Outputs'
```

## Environment Configurations

| Environment | Log Retention | Deletion Protection | Termination Protection |
|-------------|---------------|---------------------|------------------------|
| dev         | 7 days        | Disabled            | Disabled               |
| staging     | 30 days       | Enabled             | Disabled               |
| prod        | 2555 days     | Enabled             | Enabled                |

## Region Pairs (Multi-Region)

| Primary        | Secondary      |
|----------------|----------------|
| us-east-1      | us-west-2      |
| us-west-2      | us-east-1      |
| eu-west-1      | eu-central-1   |
| eu-central-1   | eu-west-1      |
| ap-southeast-1 | ap-northeast-1 |
| ap-northeast-1 | ap-southeast-1 |

## Troubleshooting

```bash
# Check CDK version
cdk --version

# Check Python version
python3 --version

# Verify AWS credentials
aws sts get-caller-identity

# View CDK context
cat cdk.context.json

# View CloudFormation events
aws cloudformation describe-stack-events --stack-name RosettaZeroStack-dev --max-items 10
```
