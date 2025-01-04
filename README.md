# DevZero Control Plane CLI

A command-line interface tool for deploying and managing the DevZero Control Plane on AWS.

## Prerequisites

- AWS CLI installed and configured with appropriate credentials
- Terraform v1.0.0 or later
- kubectl
- Helm v3.0.0 or later
- Python 3.8 or later
- A domain name (preferably in Route 53)
- Helm registry credentials from DevZero team

## Installation

### Clone the repository
`git clone https://github.com/devzero-inc/selfhost-cli.git`

### Navigate to the directory
`cd selfhost-cli`

### Install the CLI tool
`pip install -e`

## Usage

### Full Installation (Recommended)
`selfhost-cli install`

### Check AWS permissions
`selfhost-cli check-permissions`

### Set up infrastructure
`selfhost-cli setup-terraform`

### Deploy Helm charts
`selfhost-cli deploy-helm --domain your-domain.com --email your@email.com`

### Clean up resources
`selfhost-cli destroy`