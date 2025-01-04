import subprocess
import time
import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

def run_command_with_spinner(command, message, error_message):
    """Run a command with a spinner and handle errors."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(description=message, total=None)
        
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True
            )
            progress.update(task, completed=True)
            console.print(f"[green]✅ {message} completed successfully.[/green]")
            return result.stdout
        except subprocess.CalledProcessError as e:
            progress.update(task, completed=True)
            console.print(f"[red]❌ {error_message}[/red]")
            if e.stderr:
                console.print(f"[red]Error details: {e.stderr}[/red]")
            raise click.Abort()

def setup_kubeconfig(cluster_name=None, region=None):
    """Set up kubeconfig for the EKS cluster."""
    console.print("\n[bold blue]Setting up Kubernetes Configuration[/bold blue]")
    
    if not cluster_name:
        cluster_name = click.prompt("Enter your EKS cluster name")
    if not region:
        region = click.prompt("Enter your AWS region", default="us-west-2")
    
    run_command_with_spinner(
        ["aws", "eks", "update-kubeconfig", "--region", region, "--name", cluster_name],
        "Setting up kubeconfig",
        "Failed to set up kubeconfig. Please check your AWS credentials and cluster name."
    )

def wait_for_eks_cluster(cluster_name, region):
    """Wait for EKS cluster to be ready."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(description="Waiting for EKS cluster to be ready...", total=None)
        
        while True:
            try:
                result = subprocess.run(
                    ["kubectl", "get", "nodes"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                if "Ready" in result.stdout:
                    progress.update(task, completed=True)
                    console.print("[green]✅ EKS cluster is ready.[/green]")
                    break
            except subprocess.CalledProcessError:
                time.sleep(10)
                continue

def login_to_helm_registry():
    """Log in to the Helm registry."""
    console.print("\n[bold blue]Helm Registry Authentication[/bold blue]")
    
    console.print(
        "\n[yellow]Note: Your Helm registry credentials should have been provided by the DevZero team.[/yellow]\n"
        "If you don't have them, please contact support@devzero.io"
    )
    
    username = click.prompt(
        "Enter your Helm registry username",
        help_text="This is usually the email address you use with DevZero"
    )
    password = click.prompt(
        "Enter your Helm registry password",
        hide_input=True
    )
    
    run_command_with_spinner(
        ["helm", "registry", "login", "registry.devzero.io", "--username", username, "--password", password],
        "Logging in to Helm registry",
        "Failed to log in to Helm registry. Please check your credentials."
    )

def install_crds():
    """Install the required CRDs using Helm."""
    console.print("\n[bold blue]Installing Control Plane CRDs[/bold blue]")
    
    run_command_with_spinner(
        [
            "helm", "install", "dz-control-plane-crds",
            "oci://registry.devzero.io/devzero-control-plane/beta/dz-control-plane-crds",
            "-n", "devzero",
            "--create-namespace"
        ],
        "Installing CRDs",
        "Failed to install CRDs. Please check your Helm configuration."
    )

def install_helm_chart(domain=None, email=None):
    """Install the control plane Helm chart."""
    console.print("\n[bold blue]Installing Control Plane[/bold blue]")
    
    if not domain:
        domain = click.prompt("Enter your domain name for the control plane")
    if not email:
        email = click.prompt("Enter your email for the certificate issuer")
    
    run_command_with_spinner(
        [
            "helm", "install", "dz-control-plane",
            "oci://registry.devzero.io/devzero-control-plane/beta/dz-control-plane",
            "-n", "devzero",
            "--set", f"domain={domain}",
            "--set", f"issuer.email={email}"
        ],
        "Installing Helm chart",
        "Failed to install the Helm chart. Please check your configuration."
    )

def verify_helm_installation():
    """Verify the Helm installation status."""
    console.print("\n[bold blue]Verifying Installation[/bold blue]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(description="Verifying Helm installation...", total=None)
        
        try:
            # Check pod status
            result = subprocess.run(
                ["kubectl", "get", "pods", "-n", "devzero"],
                capture_output=True,
                text=True,
                check=True
            )
            
            if "Running" not in result.stdout:
                console.print("[yellow]⚠️ Some pods are not running. Please check their status:[/yellow]")
                console.print(result.stdout)
            else:
                console.print("[green]✅ All pods are running.[/green]")
                
            progress.update(task, completed=True)
            
        except subprocess.CalledProcessError as e:
            progress.update(task, completed=True)
            console.print("[red]❌ Failed to verify installation.[/red]")
            if e.stderr:
                console.print(f"[red]Error details: {e.stderr}[/red]")
            raise click.Abort()

def deploy_helm_charts(cluster_name=None, region=None, domain=None, email=None):
    """Main function to deploy Helm charts."""
    try:
        # Get cluster info from Terraform outputs if not provided
        if not cluster_name or not region:
            try:
                terraform_outputs = get_terraform_outputs(TERRAFORM_DIR)
                cluster_name = cluster_name or terraform_outputs.get("eks_cluster_name")
                region = region or terraform_outputs.get("region")
                console.print(f"[green]Using cluster: {cluster_name} in region: {region}[/green]")
            except Exception as e:
                console.print("[yellow]Could not automatically retrieve cluster information.[/yellow]")
        
        setup_kubeconfig(cluster_name, region)
        wait_for_eks_cluster(cluster_name, region)
        
        # Always prompt for Helm registry credentials
        console.print(
            "\n[bold blue]Helm Registry Authentication[/bold blue]\n"
            "[yellow]Note: You should have received Helm registry credentials from the DevZero team.[/yellow]\n"
            "If you don't have them, please contact support@devzero.io\n"
        )
        
        username = click.prompt("Enter your Helm registry username (your DevZero email)")
        password = click.prompt("Enter your Helm registry password", hide_input=True)
        
        run_command_with_spinner(
            ["helm", "registry", "login", "registry.devzero.io", "--username", username, "--password", password],
            "Logging in to Helm registry",
            "Failed to log in to Helm registry. Please check your credentials."
        )
        
        install_crds()
        install_helm_chart(domain, email)
        verify_helm_installation()
        console.print("\n[green bold]✅ Helm deployment completed successfully![/green bold]")
    except Exception as e:
        console.print(f"\n[red bold]Error during Helm deployment:[/red bold] {str(e)}")
        raise click.Abort()
