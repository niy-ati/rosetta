#!/bin/bash
# Rosetta Zero Infrastructure Setup Script

set -e

echo "Setting up Rosetta Zero AWS Infrastructure..."

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv .venv

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Verify CDK installation
echo "Verifying AWS CDK installation..."
cdk --version

echo ""
echo "Setup complete! To use the infrastructure:"
echo "1. Activate the virtual environment: source .venv/bin/activate"
echo "2. Configure AWS credentials: aws configure"
echo "3. Update cdk.context.json with your AWS account and region"
echo "4. Bootstrap CDK (first time): cdk bootstrap"
echo "5. Deploy infrastructure: cdk deploy"
