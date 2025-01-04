import click
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.theme import Theme
from selfhost_cli.commands.permissions import check_aws_permissions
from selfhost_cli.commands.terraform import run_terraform_setup
from selfhost_cli.commands.helm import deploy_helm_charts
from selfhost_cli.commands.ingress import setup_ingress
from selfhost_cli.commands.destroy import destroy_resources

# Create a console with custom theme
console = Console(theme=Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red",
    "success": "green"
}))

def display_welcome_message():
    """Display welcome message and installation overview."""
    welcome_text = """
# DevZero Control Plane Installation

## Overview
This installer will guide you through setting up the DevZero Control Plane:

1. **AWS Permissions Check**
   - Verify required AWS permissions
   - Clone necessary repositories

2. **Infrastructure Setup**
   - Initialize Terraform
   - Review and customize configuration
   - Create AWS resources

3. **Control Plane Deployment**
   - Configure Kubernetes access
   - Deploy Helm charts
   - Set up ingress

4. **DNS Configuration**
   - Configure Route 53
   - Verify DNS propagation

## Prerequisites
- AWS CLI configured with appropriate credentials
- Terraform installed
- kubectl installed
- Helm installed
- A domain name (preferably in Route 53)

> Note: The installation process typically takes 20-30 minutes.
    """
    
    console.print(Panel.fit(
        Markdown(welcome_text),
        title="Welcome to DevZero Control Plane Setup",
        border_style="blue"
    ))

def confirm_prerequisites():
    """Confirm that prerequisites are met."""
    prerequisites = """
Please confirm you have the following prerequisites:

1. AWS CLI installed and configured
2. Terraform installed (v1.0.0 or later)
3. kubectl installed
4. Helm installed (v3.0.0 or later)
5. A domain name for the control plane
6. Helm registry credentials from DevZero team
"""
    
    console.print(Panel.fit(
        Markdown(prerequisites),
        title="Prerequisites Check",
        border_style="blue"
    ))
    
    if not click.confirm("\nDo you have all prerequisites ready?"):
        console.print(
            "\n[warning]Please ensure all prerequisites are met before continuing.[/warning]"
            "\nFor help, contact support@devzero.io or refer to the documentation."
        )
        raise click.Abort()

@click.group()
def cli():
    """Selfhost CLI: A tool for deploying the DevZero Control Plane."""
    pass

@cli.command("check-permissions")
@click.option(
    "--type",
    type=click.Choice(["control-plane", "data-plane"], case_sensitive=False),
    default="control-plane",
    help="Specify the deployment type: control-plane or data-plane (default: control-plane).",
)
def check_permissions(type):
    """Check AWS permissions for the installation."""
    deployment_type = "1" if type == "control-plane" else "2"
    check_aws_permissions(deployment_type)

@cli.command()
@click.option('--non-interactive', is_flag=True, help='Run in non-interactive mode')
def install(non_interactive):
    """Run the interactive installer for DevZero Control Plane."""
    try:
        # Display welcome message and check prerequisites
        display_welcome_message()
        if not non_interactive:
            confirm_prerequisites()
        
        # Step 1: Check AWS Permissions
        console.rule("[bold blue]Step 1: Checking AWS Permissions")
        check_aws_permissions("1")  # "1" for control-plane
        
        # Step 2: Set up Infrastructure
        console.rule("[bold blue]Step 2: Setting up Infrastructure")
        if not non_interactive:
            click.pause("\nPress any key to begin infrastructure setup...")
        run_terraform_setup(non_interactive)
        
        # Step 3: Deploy Helm Charts
        console.rule("[bold blue]Step 3: Deploying Control Plane")
        if not non_interactive:
            click.pause("\nPress any key to begin control plane deployment...")
        
        # Collect required information
        domain = click.prompt("Enter your domain name for the control plane") if not non_interactive else None
        email = click.prompt("Enter your email for SSL certificates") if not non_interactive else None
        
        # Deploy Helm charts and set up ingress
        deploy_helm_charts(domain=domain, email=email)
        if domain:
            setup_ingress(domain)
        
        # Final success message
        console.print(Panel.fit(
            f"""
[success]🎉 Installation Complete![/success]

Your DevZero Control Plane has been successfully installed!

[bold]Next Steps:[/bold]
1. Access your dashboard at: https://{domain}/dashboard
2. Bookmark this URL for future access
3. Share the URL with your team members

[warning]Important Notes:[/warning]
- DNS propagation may take 15-30 minutes
- For any issues, please:
  a) Check the AWS Console for resource status
  b) Verify DNS configuration in Route 53
  c) Contact support@devzero.io for assistance

[bold]Useful Commands:[/bold]
• Check pod status: [code]kubectl get pods -n devzero[/code]
• View logs: [code]kubectl logs -n devzero <pod-name>[/code]
• Check ingress: [code]kubectl get ingress -n devzero[/code]

Thank you for choosing DevZero! 🚀
            """,
            title="Installation Complete",
            border_style="green"
        ))
        
    except click.Abort:
        console.print("\n[warning]Installation cancelled.[/warning]")
        raise
    except Exception as e:
        console.print(f"\n[error]Error during installation: {str(e)}[/error]")
        console.print(Panel.fit(
            """
[bold]Need help? Try these steps:[/bold]
1. Check the error message above
2. Verify your AWS credentials and permissions
3. Contact support@devzero.io for assistance
4. To clean up resources, run: [code]selfhost-cli destroy[/code]
            """,
            title="Troubleshooting",
            border_style="red"
        ))
        raise click.Abort()

@cli.command()
def configure_aws():
    """Configure AWS CLI for the installation."""
    click.echo("AWS configuration coming soon.")

@cli.command()
@click.option(
    '--auto-approve',
    is_flag=True,
    help='Skip interactive approval of Terraform apply'
)
def setup_terraform(auto_approve):
    """Set up infrastructure using Terraform."""
    run_terraform_setup(auto_approve)

@cli.command()
@click.option('--domain', help='Domain name for the control plane')
@click.option('--email', help='Email for the certificate issuer')
@click.option('--region', help='AWS region for the EKS cluster')
@click.option('--cluster-name', help='Name of the EKS cluster')
def deploy_helm(domain, email, region, cluster_name):
    """Deploy Helm charts for the control plane."""
    try:
        deploy_helm_charts(cluster_name, region, domain, email)
        if domain:
            setup_ingress(domain)
    except Exception as e:
        click.echo(f"Error during deployment: {str(e)}", err=True)
        raise click.Abort()

@cli.command()
@click.option(
    '--force',
    is_flag=True,
    help='Skip confirmation prompt (use with caution)'
)
def destroy(force):
    """Destroy all AWS resources created during installation."""
    try:
        destroy_resources(force)
    except Exception as e:
        click.echo(f"Error during destruction: {str(e)}", err=True)
        raise click.Abort()

if __name__ == "__main__":
    cli()