import subprocess
import time
import json
import click
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()
TERRAFORM_DIR = "self-hosted-tf/examples/aws/control-and-data-plane"

def get_terraform_output(output_name):
    """Retrieve a value from Terraform outputs."""
    try:
        result = subprocess.run(
            ["terraform", "output", "-json", output_name],
            cwd=TERRAFORM_DIR,
            capture_output=True,
            text=True,
            check=True
        )
        value = json.loads(result.stdout.strip())
        return value
    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ Failed to fetch Terraform output '{output_name}': {e.stderr}[/red]")
        raise click.Abort()
    except json.JSONDecodeError:
        console.print(f"[red]❌ Invalid JSON in Terraform output '{output_name}'[/red]")
        raise click.Abort()

def get_cluster_info():
    """Get cluster name and region from Terraform outputs."""
    console.print("\n[bold blue]Retrieving Cluster Information[/bold blue]")
    
    try:
        cluster_name = get_terraform_output("eks_cluster_name")
        region = get_terraform_output("aws_region")
        
        console.print(f"[green]✅ Found cluster: {cluster_name} in region: {region}[/green]")
        return cluster_name, region
    except Exception as e:
        console.print(
            "\n[yellow]Unable to automatically retrieve cluster information.[/yellow]\n"
            "This might happen if:\n"
            "1. Terraform hasn't been applied yet\n"
            "2. You're not in the correct directory\n"
            "3. The Terraform state is not accessible\n"
        )
        
        # Fall back to manual input
        cluster_name = click.prompt("Please enter your EKS cluster name")
        region = click.prompt("Please enter your AWS region", default="us-west-2")
        return cluster_name, region

def get_ingress_address():
    """Retrieve the ingress service address with improved error handling."""
    console.print("\n[bold blue]Retrieving Ingress Service Address[/bold blue]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Waiting for ingress service...", total=None)
        max_attempts = 30
        attempt = 0
        
        while attempt < max_attempts:
            try:
                result = subprocess.run(
                    [
                        "kubectl", "get", "ingress",
                        "-n", "devzero",
                        "-o", "jsonpath={.items[0].status.loadBalancer.ingress[0].hostname}"
                    ],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                if result.stdout.strip():
                    address = result.stdout.strip()
                    console.print(f"[green]✅ Ingress address found: {address}[/green]")
                    return address
                
            except subprocess.CalledProcessError as e:
                if attempt == max_attempts - 1:
                    console.print(
                        "\n[red]❌ Failed to retrieve ingress address. Please check:[/red]\n"
                        "1. Your kubectl context is correct\n"
                        "2. The ingress controller is deployed\n"
                        "3. The devzero namespace exists\n"
                        f"\nError details: {e.stderr}"
                    )
                    raise click.Abort()
            
            attempt += 1
            time.sleep(10)
            progress.update(task, description=f"Waiting for ingress service... (attempt {attempt}/{max_attempts})")
        
        console.print("[red]❌ Timeout waiting for ingress address[/red]")
        raise click.Abort()

def display_route53_instructions(domain, ingress_address):
    """Display instructions for Route 53 DNS configuration."""
    instructions = f"""
# Route 53 DNS Configuration Instructions

## Prerequisites
- You must have a registered domain in Route 53
- Access to the AWS Console

## Steps to Configure DNS

1. Open the [Route 53 Console](https://console.aws.amazon.com/route53)

2. Select your hosted zone for: [bold cyan]{domain}[/bold cyan]

3. Create two DNS records:

   a) Create a CNAME record:
      - Name: [bold]*[/bold]
      - Type: [bold]CNAME[/bold]
      - Value: [bold cyan]{ingress_address}[/bold cyan]
      - TTL: 300 seconds

   b) Create an A record:
      - Name: [bold]@ (empty/root)[/bold]
      - Type: [bold]A[/bold]
      - Toggle: [bold]Alias[/bold]
      - Value: [bold cyan]dualstack.{ingress_address}[/bold cyan]
      - Evaluate Target Health: Yes

## Verification
- The DNS changes may take up to 15 minutes to propagate
- You can verify the setup by visiting:
  [bold cyan]https://{domain}/dashboard[/bold cyan]

[yellow]Note: If you need to manage DNS records outside of Route 53, please contact your DNS provider for equivalent setup instructions.[/yellow]
    """
    
    console.print(Panel(
        Markdown(instructions),
        title="[bold]DNS Configuration Required[/bold]",
        expand=False
    ))

def verify_dns_propagation(domain):
    """Verify DNS propagation with dynamic wait times."""
    console.print("\n[bold blue]Verifying DNS Propagation[/bold blue]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Checking DNS propagation...", total=None)
        max_attempts = 30
        attempt = 0
        wait_time = 20  # Initial wait time in seconds
        
        while attempt < max_attempts:
            try:
                # Check both A and CNAME records
                a_record = subprocess.run(["dig", "+short", "A", domain], capture_output=True, text=True)
                cname_record = subprocess.run(["dig", "+short", "CNAME", f"*.{domain}"], capture_output=True, text=True)
                
                if a_record.stdout.strip() or cname_record.stdout.strip():
                    console.print("[green]✅ DNS records have propagated successfully[/green]")
                    return True
                
            except subprocess.CalledProcessError:
                pass
            
            attempt += 1
            progress.update(
                task,
                description=f"Checking DNS propagation... (attempt {attempt}/{max_attempts}, waiting {wait_time}s)"
            )
            time.sleep(wait_time)
            
            # Increase wait time gradually
            wait_time = min(wait_time * 1.5, 60)  # Cap at 60 seconds
        
        console.print(
            "\n[yellow]⚠️ DNS propagation is taking longer than expected[/yellow]\n"
            "This is normal and might take up to 48 hours, though usually completes within 15-30 minutes.\n"
            "You can continue to check manually using:\n"
            f"[bold]dig +short {domain}[/bold]"
        )
        return False

def setup_ingress(domain):
    """Main function to set up ingress and DNS."""
    try:
        # Get cluster information
        cluster_name, region = get_cluster_info()
        
        # Get ingress address
        ingress_address = get_ingress_address()
        
        # Display Route 53 configuration instructions
        display_route53_instructions(domain, ingress_address)
        
        if click.confirm("\nWould you like to wait for DNS propagation?"):
            verify_dns_propagation(domain)
            
        console.print(f"""
[bold green]✅ Setup Complete![/bold green]

You can now access your DevZero Control Plane at:
[bold cyan]https://{domain}/dashboard[/bold cyan]

[yellow]Important Notes:[/yellow]
1. If you can't access the dashboard immediately:
   - DNS propagation can take up to 15-30 minutes
   - In rare cases, it might take up to 48 hours
2. Ensure you're using https:// (not http://)
3. If issues persist, verify:
   - Route 53 DNS records are correctly configured
   - Your browser can resolve {domain}
   - The ingress controller is running: [bold]kubectl get pods -n devzero[/bold]
        """)
        
    except Exception as e:
        console.print(f"\n[red bold]Error during ingress setup:[/red bold] {str(e)}")
        raise click.Abort()
