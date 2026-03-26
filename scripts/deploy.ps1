# CDK Deployment Script for Rosetta Zero (PowerShell/Windows)
#
# This script provides convenient wrappers for deploying Rosetta Zero infrastructure.
# Requirements: 23.1, 23.2

$ErrorActionPreference = "Stop"

# Script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# Change to project root
Set-Location $ProjectRoot

# Check if Python is available
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Python is not installed" -ForegroundColor Red
    exit 1
}

# Check if CDK is installed
if (-not (Get-Command cdk -ErrorAction SilentlyContinue)) {
    Write-Host "Error: AWS CDK is not installed" -ForegroundColor Red
    Write-Host "Install with: npm install -g aws-cdk"
    exit 1
}

# Run the Python deployment script
python scripts/deploy.py $args
