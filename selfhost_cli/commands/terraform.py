import os
import subprocess
import click
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
import time
from selfhost_cli.utils.terraform import strip_ansi_escape_sequences, get_terraform_outputs, is_retryable_error

console = Console()
REPO_DIR = "self-hosted-tf"
TERRAFORM_DIR = os.path.join(REPO_DIR, "examples/aws/control-and-data-plane")

def print_section(title, content=None):
    """Print a section with a title and optional content."""
    console.print(f"\n[bold blue]{title}[/bold blue]")
    if content:
        console.print(Panel(content))

def check_repo_exists():
    """Check if the self-hosted-tf repository exists."""
    if not os.path.exists(REPO_DIR):
        console.print("\n[red]❌ Repository directory not found![/red]")
        console.print(
            "\n[yellow]Please run the following command first:[/yellow]\n"
            "[bold cyan]selfhost-cli check-permissions[/bold cyan]"
        )
        raise click.Abort()

def get_editor_choice():
    """Prompt user to choose their preferred editor."""
    editors = {
        '1': ('VS Code', 'code'),
        '2': ('Vim', 'vim'),
        '3': ('Nano', 'nano'),
        '4': ('Custom', None)
    }
    
    console.print("\n[bold cyan]Available editors:[/bold cyan]")
    for key, (name, _) in editors.items():
        console.print(f"{key}. {name}")
    
    choice = click.prompt(
        "Choose your preferred editor",
        type=click.Choice(['1', '2', '3', '4']),
        show_choices=False
    )
    
    if choice == '4':
        custom_editor = click.prompt("Enter the command for your preferred editor")
        return custom_editor
    
    return editors[choice][1]

def edit_terraform_files():
    """Edit Terraform files using the user's preferred editor."""
    # First, check if EDITOR is set in environment
    default_editor = os.environ.get('EDITOR')
    
    if default_editor:
        if click.confirm(f"\nFound editor: {default_editor}. Would you like to use it?"):
            editor = default_editor
        else:
            editor = get_editor_choice()
    else:
        editor = get_editor_choice()
    
    files = ["main.tf", "variables.tf"]
    
    while True:
        console.print("\n[bold cyan]Available actions:[/bold cyan]")
        console.print("1. Edit main.tf")
        console.print("2. Edit variables.tf")
        console.print("3. Continue with Terraform plan")
        
        choice = click.prompt(
            "Choose an action",
            type=click.Choice(['1', '2', '3']),
            show_choices=False
        )
        
        if choice == '3':
            break
            
        file_to_edit = files[int(choice) - 1]
        file_path = os.path.join(TERRAFORM_DIR, file_to_edit)
        
        if not os.path.exists(file_path):
            console.print(f"[red]File {file_to_edit} not found![/red]")
            continue
            
        try:
            if editor == 'code':
                # VS Code specific handling to wait for the editor
                subprocess.run([editor, '--wait', file_path], check=True)
            else:
                subprocess.run([editor, file_path], check=True)
            console.print(f"[green]✅ Finished editing {file_to_edit}[/green]")
        except subprocess.CalledProcessError:
            console.print(f"[red]Error while editing {file_to_edit}[/red]")
        except FileNotFoundError:
            console.print(f"[red]Editor '{editor}' not found. Please make sure it's installed.[/red]")
            if click.confirm("Would you like to choose a different editor?"):
                editor = get_editor_choice()
            else:
                break

def preview_terraform_files():
    """Offer to preview and edit the Terraform files."""
    if click.confirm("\nDo you want to preview the Terraform files?"):
        for file in ["main.tf", "variables.tf"]:
            file_path = os.path.join(TERRAFORM_DIR, file)
            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    content = f.read()
                    print_section(f"📄 {file}", content)
        
        if click.confirm("\nWould you like to edit any of the Terraform files?"):
            edit_terraform_files()
        else:
            console.print("[cyan]Continuing with Terraform plan...[/cyan]")

def stream_subprocess_output(process, command_name):
    """Stream output from a subprocess in real-time."""
    try:
        # Stream stdout in real-time
        for line in iter(process.stdout.readline, ""):
            if line.strip():  # Only print non-empty lines
                console.print(line.strip())
        
        # Get the final return code
        process.wait()
        
        # If process failed, print stderr and raise error
        if process.returncode != 0:
            error_output = process.stderr.read()
            console.print(f"[red]❌ {command_name} failed:[/red]\n{error_output}")
            raise click.Abort()
            
    except Exception as e:
        console.print(f"[red]❌ Error during {command_name}: {str(e)}[/red]")
        raise click.Abort()

def run_terraform_init():
    """Run terraform init in the appropriate directory."""
    print_section("Initializing Terraform")
    
    process = subprocess.Popen(
        ["terraform", "init"],
        cwd=TERRAFORM_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,  # Line buffered
        universal_newlines=True
    )
    
    stream_subprocess_output(process, "Terraform init")
    console.print("[green]✅ Terraform initialization completed successfully.[/green]")

def run_terraform_plan():
    """Run terraform plan to show changes."""
    print_section("Planning Terraform Changes")
    
    process = subprocess.Popen(
        ["terraform", "plan"],
        cwd=TERRAFORM_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
        universal_newlines=True
    )
    
    # Stream and clean output in real-time
    for line in iter(process.stdout.readline, ""):
        if line.strip():
            clean_line = strip_ansi_escape_sequences(line.strip())
            console.print(clean_line)
    
    process.wait()
    
    if process.returncode != 0:
        error_output = process.stderr.read()
        console.print(f"[red]❌ Terraform plan failed:[/red]\n{error_output}")
        raise click.Abort()
    
    console.print("[green]✅ Terraform plan completed successfully.[/green]")

def run_terraform_apply(auto_approve=False, max_retries=3):
    """Run terraform apply with retries for specific errors."""
    print_section("Applying Terraform Configuration")
    
    if not auto_approve and not click.confirm("\nDo you want to continue with Terraform apply?"):
        console.print("[yellow]Terraform apply cancelled.[/yellow]")
        return
    
    retries = 0
    while retries < max_retries:
        try:
            command = ["terraform", "apply"]
            if auto_approve:
                command.append("-auto-approve")
            
            process = subprocess.Popen(
                command,
                cwd=TERRAFORM_DIR,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                universal_newlines=True
            )
            
            # Stream output in real-time
            error_output = []
            for line in iter(process.stdout.readline, ""):
                if line.strip():
                    clean_line = strip_ansi_escape_sequences(line.strip())
                    console.print(clean_line)
                    error_output.append(clean_line)
            
            process.wait()
            
            if process.returncode != 0:
                stderr = process.stderr.read()
                error_text = "\n".join(error_output) + stderr
                
                if is_retryable_error(error_text) and retries < max_retries - 1:
                    retries += 1
                    console.print(f"[yellow]Retryable error detected. Attempting retry {retries}/{max_retries}...[/yellow]")
                    time.sleep(30)  # Wait before retry
                    continue
                
                console.print(f"[red]❌ Terraform apply failed:[/red]\n{stderr}")
                raise click.Abort()
            
            # Get and store Terraform outputs
            outputs = get_terraform_outputs(TERRAFORM_DIR)
            if outputs:
                console.print("\n[green]Terraform outputs:[/green]")
                for key, value in outputs.items():
                    console.print(f"  {key}: {value}")
            
            console.print("[green]✅ Terraform apply completed successfully.[/green]")
            return outputs
            
        except Exception as e:
            if retries < max_retries - 1:
                retries += 1
                console.print(f"[yellow]Error occurred. Attempting retry {retries}/{max_retries}...[/yellow]")
                time.sleep(30)
                continue
            console.print(f"[red]❌ Error during terraform apply: {str(e)}[/red]")
            raise click.Abort()

def check_prerequisites():
    """Check all prerequisites before running Terraform."""
    print_section("Checking Prerequisites")
    
    # Check if repository exists
    check_repo_exists()
    
    # Check required files
    required_files = ["main.tf", "variables.tf"]
    missing_files = [f for f in required_files if not os.path.exists(os.path.join(TERRAFORM_DIR, f))]
    if missing_files:
        console.print(f"[red]❌ Missing required files: {', '.join(missing_files)}[/red]")
        console.print(
            "\n[yellow]The repository might be corrupted. Try:[/yellow]\n"
            "1. Remove the self-hosted-tf directory\n"
            "2. Run [bold cyan]selfhost-cli check-permissions[/bold cyan] again"
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
    except (subprocess.CalledProcessError, FileNotFoundError):
        console.print("[red]❌ AWS credentials not configured or invalid. Please run configure-aws first.[/red]")
        raise click.Abort()

def check_terraform_installed():
    """Check if Terraform is installed."""
    try:
        process = subprocess.Popen(
            ["terraform", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        output, _ = process.communicate()
        version = output.splitlines()[0]
        print_section("Terraform Installation", f"✅ {version}")
        
    except FileNotFoundError:
        console.print("[red]❌ Terraform is not installed. Please install Terraform and try again.[/red]")
        raise click.Abort()

def run_terraform_setup(auto_approve=False):
    """Main function to set up infrastructure using Terraform."""
    try:
        console.print("\n[bold]Starting Terraform Setup[/bold]")
        check_prerequisites()
        check_terraform_installed()
        run_terraform_init()
        preview_terraform_files()
        run_terraform_plan()
        run_terraform_apply(auto_approve)
        console.print("\n[green bold]✅ Terraform setup completed successfully![/green bold]")
    except click.Abort:
        raise
    except Exception as e:
        console.print(f"\n[red bold]Error during Terraform setup:[/red bold] {str(e)}")
        raise click.Abort()