import os
import subprocess
import click
from rich.console import Console
from rich.prompt import Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()
TERRAFORM_DIR = "self-hosted-tf/examples/aws/control-and-data-plane"

def check_prerequisites():
    """Check if we have access to required tools and directories."""
    console.print("\n[bold blue]Checking Prerequisites[/bold blue]")
    
    # Check if terraform directory exists
    if not os.path.exists(TERRAFORM_DIR):
        console.print(
            "[red]❌ Terraform directory not found![/red]\n"
            "Please ensure you're in the correct directory and have run the installation first."
        )
        raise click.Abort()
    
    # Check AWS credentials
    try:
        subprocess.run(
            ["aws", "sts", "get-caller-identity"],
            check=True,
            capture_output=True,
            text=True
        )
    except subprocess.CalledProcessError:
        console.print(
            "[red]❌ AWS credentials not configured or invalid.[/red]\n"
            "Please ensure your AWS credentials are properly configured."
        )
        raise click.Abort()

def cleanup_helm_resources():
    """Remove Helm releases and related Kubernetes resources."""
    console.print("\n[bold blue]Cleaning up Helm Resources[/bold blue]")
    
    try:
        # Uninstall Helm releases
        releases = ["dz-control-plane", "dz-control-plane-crds"]
        for release in releases:
            console.print(f"Uninstalling Helm release: {release}")
            subprocess.run(
                ["helm", "uninstall", release, "-n", "devzero"],
                check=False,  # Don't fail if release doesn't exist
                capture_output=True
            )
        
        # Delete the namespace
        console.print("Deleting devzero namespace")
        subprocess.run(
            ["kubectl", "delete", "namespace", "devzero", "--timeout=5m"],
            check=False,
            capture_output=True
        )
        
        console.print("[green]✅ Helm resources cleaned up successfully[/green]")
    except Exception as e:
        console.print(f"[yellow]⚠️ Warning during Helm cleanup: {str(e)}[/yellow]")
        # Continue with destruction even if Helm cleanup fails

def run_terraform_destroy():
    """Run terraform destroy to remove AWS resources."""
    console.print("\n[bold blue]Destroying AWS Infrastructure[/bold blue]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Running terraform destroy...", total=None)
        
        try:
            process = subprocess.Popen(
                ["terraform", "destroy", "-auto-approve"],
                cwd=TERRAFORM_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Stream output in real-time
            for line in iter(process.stdout.readline, ""):
                if line.strip():
                    console.print(line.strip())
            
            process.wait()
            
            if process.returncode != 0:
                error_output = process.stderr.read()
                console.print(f"[red]❌ Terraform destroy failed:[/red]\n{error_output}")
                raise click.Abort()
            
            console.print("[green]✅ AWS resources destroyed successfully[/green]")
            
        except Exception as e:
            console.print(f"[red]❌ Error during terraform destroy: {str(e)}[/red]")
            raise click.Abort()

def confirm_destruction():
    """Get confirmation from user before destroying resources."""
    console.print(
        "\n[bold red]⚠️  WARNING: Resource Destruction[/bold red]\n"
        "This will destroy:\n"
        "1. All AWS resources created during installation\n"
        "2. The EKS cluster and all its workloads\n"
        "3. All related networking resources\n"
        "\n[yellow]This action is irreversible![/yellow]"
    )
    
    confirmation_text = click.prompt(
        "\nType 'destroy' to confirm",
        default="",
    )
    
    if confirmation_text.lower() != "destroy":
        console.print("[yellow]Destruction cancelled.[/yellow]")
        raise click.Abort()

def destroy_resources(force=False):
    """Main function to destroy all resources."""
    try:
        if not force:
            confirm_destruction()
        
        check_prerequisites()
        cleanup_helm_resources()
        run_terraform_destroy()
        
        console.print("""
[bold green]✅ Cleanup Complete![/bold green]

All resources have been destroyed. To verify:
1. Check your AWS Console for any remaining resources
2. Run [bold]kubectl get all -n devzero[/bold] to confirm namespace cleanup
3. Check Route 53 for any remaining DNS records

[yellow]Note: DNS records might need to be cleaned up manually if you created them outside of Terraform.[/yellow]
        """)
        
    except click.Abort:
        raise
    except Exception as e:
        console.print(f"\n[red bold]Error during resource destruction:[/red bold] {str(e)}")
        raise click.Abort()
