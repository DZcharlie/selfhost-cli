import click
from selfhost_cli.commands.permissions import check_aws_permissions

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
def install():
    """Run the interactive installer."""
    click.echo("Interactive installer coming soon...")


@cli.command()
def configure_aws():
    """Configure AWS CLI for the installation."""
    click.echo("AWS configuration coming soon.")

@cli.command()
def setup_terraform():
    """Set up infrastructure using Terraform."""
    click.echo("Terraform setup coming soon.")

@cli.command()
def deploy_helm():
    """Deploy Helm charts for the control plane."""
    click.echo("Helm deployment coming soon.")

if __name__ == "__main__":
    cli()