# Rosetta Zero - CDK Deployment Makefile
#
# Provides convenient targets for common deployment operations.
# Requirements: 23.1, 23.2

.PHONY: help install bootstrap synth-dev synth-staging synth-prod deploy-dev deploy-staging deploy-prod diff-dev diff-staging diff-prod destroy-dev destroy-staging destroy-prod clean

# Default target
help:
	@echo "Rosetta Zero - CDK Deployment Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install Python dependencies"
	@echo "  make bootstrap        Bootstrap CDK (set REGION and ACCOUNT)"
	@echo ""
	@echo "Development:"
	@echo "  make synth-dev        Synthesize dev templates"
	@echo "  make deploy-dev       Deploy to dev environment"
	@echo "  make diff-dev         Show dev infrastructure differences"
	@echo "  make destroy-dev      Destroy dev infrastructure"
	@echo ""
	@echo "Staging:"
	@echo "  make synth-staging    Synthesize staging templates"
	@echo "  make deploy-staging   Deploy to staging environment"
	@echo "  make diff-staging     Show staging infrastructure differences"
	@echo "  make destroy-staging  Destroy staging infrastructure"
	@echo ""
	@echo "Production:"
	@echo "  make synth-prod       Synthesize prod templates"
	@echo "  make deploy-prod      Deploy to production environment"
	@echo "  make diff-prod        Show prod infrastructure differences"
	@echo "  make destroy-prod     Destroy prod infrastructure (requires confirmation)"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean            Clean CDK output directory"
	@echo ""
	@echo "Environment Variables:"
	@echo "  REGION                AWS region (default: us-east-1)"
	@echo "  ACCOUNT               AWS account ID (required)"
	@echo "  STACK                 Specific stack to operate on (optional)"
	@echo ""
	@echo "Examples:"
	@echo "  make bootstrap REGION=us-east-1 ACCOUNT=123456789012"
	@echo "  make deploy-dev REGION=us-east-1 ACCOUNT=123456789012"
	@echo "  make deploy-prod REGION=us-east-1 ACCOUNT=123456789012 STACK=RosettaZeroStack"

# Configuration
REGION ?= us-east-1
ACCOUNT ?=
STACK ?=

# Validate required variables
check-account:
ifndef ACCOUNT
	$(error ACCOUNT is required. Set with: make <target> ACCOUNT=123456789012)
endif

# Installation
install:
	pip install -r requirements.txt

# Bootstrap CDK
bootstrap: check-account
	python3 scripts/deploy.py bootstrap --region $(REGION) --account $(ACCOUNT)

# Development environment
synth-dev: check-account
	python3 scripts/deploy.py synth --env dev --region $(REGION) --account $(ACCOUNT) $(if $(STACK),--stack $(STACK))

deploy-dev: check-account
	python3 scripts/deploy.py deploy --env dev --region $(REGION) --account $(ACCOUNT) $(if $(STACK),--stack $(STACK))

diff-dev: check-account
	python3 scripts/deploy.py diff --env dev --region $(REGION) --account $(ACCOUNT) $(if $(STACK),--stack $(STACK))

destroy-dev: check-account
	python3 scripts/deploy.py destroy --env dev --region $(REGION) --account $(ACCOUNT) $(if $(STACK),--stack $(STACK))

# Staging environment
synth-staging: check-account
	python3 scripts/deploy.py synth --env staging --region $(REGION) --account $(ACCOUNT) $(if $(STACK),--stack $(STACK))

deploy-staging: check-account
	python3 scripts/deploy.py deploy --env staging --region $(REGION) --account $(ACCOUNT) $(if $(STACK),--stack $(STACK))

diff-staging: check-account
	python3 scripts/deploy.py diff --env staging --region $(REGION) --account $(ACCOUNT) $(if $(STACK),--stack $(STACK))

destroy-staging: check-account
	python3 scripts/deploy.py destroy --env staging --region $(REGION) --account $(ACCOUNT) $(if $(STACK),--stack $(STACK))

# Production environment
synth-prod: check-account
	python3 scripts/deploy.py synth --env prod --region $(REGION) --account $(ACCOUNT) $(if $(STACK),--stack $(STACK))

deploy-prod: check-account
	python3 scripts/deploy.py deploy --env prod --region $(REGION) --account $(ACCOUNT) $(if $(STACK),--stack $(STACK))

diff-prod: check-account
	python3 scripts/deploy.py diff --env prod --region $(REGION) --account $(ACCOUNT) $(if $(STACK),--stack $(STACK))

destroy-prod: check-account
	python3 scripts/deploy.py destroy --env prod --region $(REGION) --account $(ACCOUNT) $(if $(STACK),--stack $(STACK))

# Utilities
clean:
	rm -rf cdk.out
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
