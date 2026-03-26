# Rosetta Zero Infrastructure Setup Script (PowerShell)

Write-Host "Setting up Rosetta Zero AWS Infrastructure..." -ForegroundColor Green

# Check Python version
$pythonVersion = python --version 2>&1
Write-Host "Python version: $pythonVersion"

# Create virtual environment
Write-Host "Creating virtual environment..." -ForegroundColor Yellow
python -m venv .venv

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
.\.venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
python -m pip install --upgrade pip
pip install -r requirements.txt

# Verify CDK installation
Write-Host "Verifying AWS CDK installation..." -ForegroundColor Yellow
cdk --version

Write-Host ""
Write-Host "Setup complete! To use the infrastructure:" -ForegroundColor Green
Write-Host "1. Activate the virtual environment: .\.venv\Scripts\Activate.ps1"
Write-Host "2. Configure AWS credentials: aws configure"
Write-Host "3. Update cdk.context.json with your AWS account and region"
Write-Host "4. Bootstrap CDK (first time): cdk bootstrap"
Write-Host "5. Deploy infrastructure: cdk deploy"
